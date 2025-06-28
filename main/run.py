# run.py (Phiên bản đã được bổ sung tính năng tự động cập nhật)
import sys
import logging
import asyncio
import sqlite3
import joblib
import json
import os # Import os để thực hiện restart
from dotenv import load_dotenv

load_dotenv()

# --- Project Module Imports ---
from binance import AsyncClient
import main.src.core.config as config
from main.src.handlers.database_handler import init_sqlite_db
from src.core.analysis_engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
from src.handlers.telegram_handler import TelegramHandler
from src.handlers.notifications import NotificationHandler
from src.core.performance_analyzer import get_performance_stats
from src.utils.updater import get_usdt_futures_symbols, check_signal_outcomes
from src.training.trainer import train_model
from src.training.training_loop import training_loop
from src.utils.data_simulator import simulate_trade_data # NEW: Import data simulator
from src.utils.pairlistupdater import perform_single_pairlist_update, CONFIG_FILE_PATH as PAIRLIST_CONFIG_PATH
from src.api_server import app as flask_app # Import the Flask app instance

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- BOT LOOPS ---

async def analysis_loop(client, model, label_encoder, model_features): # Removed 'symbols' parameter
    """LOOP 1: Phân tích thị trường, chọn chiến lược từ config."""
    logger.info(f"✅ Analysis Loop starting (Strategy: {config.STRATEGY_MODE})")
    semaphore = asyncio.Semaphore(config.CONCURRENT_REQUESTS)
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            if config.STRATEGY_MODE == 'Elliotv8':
                await perform_elliotv8_analysis(client, symbol)
            else: # Mặc định là 'AI'
                await perform_ai_fallback_analysis(client, symbol, model, label_encoder, model_features)

    while True:
        try:
            # Periodically refresh the symbol list
            current_symbols = await get_usdt_futures_symbols(client)
            if not current_symbols:
                logger.warning("No symbols fetched for analysis. Skipping cycle.")
                await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
                continue
            logger.info(f"--- Starting analysis cycle for {len(current_symbols)} symbols ---")
            tasks = [process_with_semaphore(s) for s in list(current_symbols)] # Use current_symbols
            await asyncio.gather(*tasks)
            logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
            await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"An error in analysis_loop: {e}", exc_info=True)
            await asyncio.sleep(60)

async def signal_check_loop(notifier: NotificationHandler):
    logger.info(f"✅ New Signal Alert Loop starting...")
    notified_signal_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            existing_ids = conn.execute("SELECT rowid FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
            notified_signal_ids.update(row['rowid'] for row in existing_ids) # Use row['rowid'] for clarity
    except Exception as e:
        logger.error(f"❌ Error initializing signal_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                all_active_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
            
            new_signals_to_notify = [s for s in all_active_signals if s['rowid'] not in notified_signal_ids]
            logger.info(f"Found {len(new_signals_to_notify)} new active signals to notify.")
            if new_signals_to_notify:
                for signal in new_signals_to_notify:
                    notifier.queue_signal(dict(signal))
                notified_signal_ids.update(s['rowid'] for s in new_signals_to_notify)
        except Exception as e:
            logger.error(f"❌ Error in signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def updater_loop(client: AsyncClient):
    logger.info(f"✅ Trade Updater Loop starting...")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def outcome_check_loop(notifier: NotificationHandler):
    logger.info(f"✅ Trade Outcome Notification Loop starting...")
    notified_trade_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            closed_trades = conn.execute("SELECT rowid FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
            notified_trade_ids.update(row['rowid'] for row in closed_trades) # Use row['rowid'] for clarity
    except Exception as e:
        logger.error(f"❌ Error initializing outcome_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                all_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
                newly_closed_trades = [t for t in all_closed_trades if t['rowid'] not in notified_trade_ids]
            if newly_closed_trades:
                for trade in newly_closed_trades:
                    notifier.queue_trade_outcome(dict(trade))
                    notified_trade_ids.add(trade['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in outcome_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def notification_flush_loop(notifier: NotificationHandler):
    """Periodically flushes the notification queue every 10 minutes."""
    interval_seconds = config.NOTIFICATION_FLUSH_INTERVAL_MINUTES * 60
    logger.info(f"✅ Notification Queue Flush Loop starting ({config.NOTIFICATION_FLUSH_INTERVAL_MINUTES} min interval)...")
    while True:
        await asyncio.sleep(interval_seconds)
        logger.info("⏰ Time-based flush for notification queue...")
        # Flush both new signals and closed trade outcomes
        await asyncio.gather(
            notifier.flush_signal_queue(),
            notifier.flush_outcome_queue()
        )

async def summary_loop(notifier: NotificationHandler):
    """Periodically sends a performance summary every 60 minutes."""
    interval_seconds = config.SUMMARY_INTERVAL_MINUTES * 60
    logger.info(f"✅ Periodic Summary Loop starting ({config.SUMMARY_INTERVAL_MINUTES} min interval)...")
    while True:
        # Wait for an hour before sending the first summary
        await asyncio.sleep(interval_seconds)
        logger.info("📰 Generating and sending periodic performance summary...")
        await notifier.send_periodic_summary_notification()



# --- HÀM MỚI: VÒNG LẶP TỰ ĐỘNG CẬP NHẬT ---
async def update_loop(notifier: NotificationHandler):
    """
    Vòng lặp định kỳ kiểm tra cập nhật từ Git và khởi động lại bot nếu có.
    """ 
    interval_seconds = config.AUTO_UPDATE_CHECK_INTERVAL_MINUTES * 60
    logger.info(f"✅ Auto-update Loop starting ({config.AUTO_UPDATE_CHECK_INTERVAL_MINUTES} min interval)...")
    while True:
        await asyncio.sleep(interval_seconds)
        
        try:
            logger.info("📡 Checking for code updates from git...")
            fetch_process = await asyncio.create_subprocess_shell('git fetch', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await fetch_process.wait()
            status_process = await asyncio.create_subprocess_shell('git status -uno', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await status_process.communicate()
            
            if b'Your branch is up to date' in stdout:
                logger.info("✅ Code is up-to-date.")
                continue
            
            logger.info("💡 New code found! Attempting to pull updates...")
            # OPTIONAL: Force update by discarding local changes. Use with caution!
            # If you want to ensure the bot always gets the latest code and
            # don't care about uncommitted local changes, uncomment the line below.
            # await asyncio.create_subprocess_shell('git reset --hard origin/ai')

            pull_process = await asyncio.create_subprocess_shell(f'git pull {config.GIT_REMOTE_NAME} {config.GIT_BRANCH_NAME}', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            pull_stdout, pull_stderr = await pull_process.communicate()

            if pull_process.returncode == 0:
                logger.info(pull_stdout.decode())
                logger.critical("🚨 New code applied. Triggering bot restart...")
                await notifier._send_to_both("🚨 Bot is restarting to apply new updates\\.\\.\\.")
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                logger.error(f"❌ Failed to pull updates: {pull_stderr.decode()}")
                await notifier._send_to_both(f"❌ Failed to pull updates: {pull_stderr.decode()}")

        except Exception as e:
            logger.error(f"❌ Error during update check: {e}", exc_info=True)

def run_api_server():
    """
    Hàm đồng bộ để chạy Flask server. Sẽ được chạy trong một thread riêng.
    """
    logger.info("✅ Starting API server in a background thread...")
    # Sử dụng debug=False trong môi trường tích hợp/production
    flask_app.run(host=config.API_HOST, port=config.API_PORT, debug=False)

# --- MAIN FUNCTION ---
async def main():
    logger.info("--- 🚀 Initializing Bot ---")
    client = None
    # CẢI TIẾN: Tạo một danh sách để quản lý các tác vụ
    initial_accuracy = None # Initialize to None
    running_tasks = [] 
    
    try:
        # --- 1. Khởi tạo các thành phần ---
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        init_sqlite_db(config.SQLITE_DB_PATH)
        
        # --- NEW: Chạy giả lập dữ liệu khi khởi động ---
        logger.info("📊 Running data simulation to prepare training data...")
        
        # Step 1: Update pairlist to get the latest symbols for simulation.
        logger.info("Updating pairlist before data simulation...")
        await perform_single_pairlist_update()

        # Step 2: Load the updated symbols from config.json.
        # This is necessary because the initial `import config` does not see file changes.
        try:
            with open(PAIRLIST_CONFIG_PATH, 'r') as f:
                current_config_data = json.load(f)
            latest_all_symbols = current_config_data.get('trading', {}).get('symbols', [])
            if not latest_all_symbols:
                logger.warning("No symbols found in config.json for simulation. Using fallback from initial config.")
                latest_all_symbols = config.trading.symbols if hasattr(config, 'trading') and hasattr(config.trading, 'symbols') else []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config.json for simulation: {e}. Using fallback from initial config.")
            latest_all_symbols = config.trading.symbols if hasattr(config, 'trading') and hasattr(config.trading, 'symbols') else []

        await simulate_trade_data(client, config.SQLITE_DB_PATH, latest_all_symbols)
        logger.info("📊 Data simulation completed.")
        # --- END NEW ---
        # Cập nhật để truyền proxy_url vào TelegramHandler
        tg_handler = TelegramHandler(
            api_token=config.TELEGRAM_BOT_TOKEN,
            proxy_url=config.TELEGRAM_PROXY_URL if hasattr(config, 'TELEGRAM_PROXY_URL') else None
        )
        notifier = NotificationHandler(telegram_handler=tg_handler)

        # --- GỬI THÔNG BÁO TỔNG KẾT GIẢ LẬP ---
        logger.info("Calculating per-symbol simulation results and sending summary...")
        loop = asyncio.get_running_loop()
        # Chạy hàm đồng bộ trong một executor để không chặn event loop
        # Lấy thống kê theo từng symbol
        simulation_stats_by_symbol = await loop.run_in_executor(
            None, 
            lambda: get_performance_stats(by_symbol=True)
        )
        await notifier.send_simulation_summary_notification(simulation_stats_by_symbol)
        logger.info("Simulation summary notification sent.")
        # --- KẾT THÚC THÔNG BÁO TỔNG KẾT ---
        
        # --- 2. Tải và Huấn luyện Model ---
        logger.info("🧠 Loading/Training AI Model...")
        model, label_encoder, model_features = None, None, None
        try:
            model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
            logger.info("✅ AI Model loaded from files.")
        except FileNotFoundError:
            logger.warning("⚠️ Model files not found. Performing initial training...")
            loop = asyncio.get_running_loop()
            initial_accuracy = await loop.run_in_executor(None, train_model) # This will set initial_accuracy
            if initial_accuracy is not None:
                logger.info("Reloading model after initial training...")
                model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
        
        # --- 3. Gửi thông báo khởi động ---
        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("Could not fetch symbols. Exiting.")
            return

        if all([model, label_encoder, model_features]):
            # Pass initial_accuracy directly
            await notifier.send_startup_notification(len(all_symbols), initial_accuracy)
        else:
            await notifier.send_fallback_mode_startup_notification(len(all_symbols))

        # --- 4. Khởi chạy tất cả các vòng lặp nền ---
        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        # Set logging level for the existing logger
        logger.setLevel(logging.DEBUG)
        
        
        # CẢI TIẾN: Tạo và thêm các tác vụ vào danh sách quản lý
        running_tasks = [ # Removed all_symbols from analysis_loop as it will fetch its own
            asyncio.create_task(analysis_loop(client, model, label_encoder, model_features)),
            asyncio.create_task(signal_check_loop(notifier)),
            asyncio.create_task(updater_loop(client)),
            asyncio.create_task(outcome_check_loop(notifier)),
            asyncio.create_task(training_loop(notifier, len(all_symbols))),
            loop.run_in_executor(None, run_api_server), # Chạy API server trong một thread
            asyncio.create_task(notification_flush_loop(notifier)), # Add notification flush loop
            asyncio.create_task(summary_loop(notifier)) # Add summary loop
        ]
        await asyncio.gather(*running_tasks)

    except (Exception, KeyboardInterrupt) as main_exc:
        if isinstance(main_exc, KeyboardInterrupt):
            logger.info("Bot stopped by user (Ctrl+C).")
        else:
            logger.critical(f"A fatal error occurred in the main execution block: {main_exc}", exc_info=True)
    finally:
        # --- CƠ CHẾ TẮT MÁY AN TOÀN ---
        logger.info("--- ⭕ Bot application shutting down... ---")
        
        # 1. Hủy tất cả các tác vụ đang chạy
        for task in running_tasks:
            task.cancel()
        
        # 2. Chờ cho tất cả các tác vụ được hủy xong
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
            logger.info("All loops have been cancelled.")

        # 3. Bây giờ mới đóng kết nối client
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")
            
        logger.info("--- Shutdown complete. ---")

if __name__ == "__main__":
    # Bỏ khối try-except ở đây để khối finally trong main xử lý
    asyncio.run(main())