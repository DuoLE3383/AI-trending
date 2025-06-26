# run.py (Phiên bản đã được bổ sung tính năng tự động cập nhật)
import sys
import logging
import asyncio
import sqlite3
import joblib
import os # Import os để thực hiện restart
from dotenv import load_dotenv

load_dotenv()

# --- Project Module Imports ---
from binance import AsyncClient
import config
from database_handler import init_sqlite_db
from analysis_engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats
from updater import get_usdt_futures_symbols, check_signal_outcomes
from trainer import train_model
from training_loop import training_loop

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- BOT LOOPS ---

async def analysis_loop(client, symbols, model, label_encoder, model_features):
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
            logger.info(f"--- Starting analysis cycle for {len(symbols)} symbols ---")
            tasks = [process_with_semaphore(s) for s in list(symbols)]
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
            notified_signal_ids.update(r[0] for r in existing_ids)
    except Exception as e:
        logger.error(f"❌ Error initializing signal_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                if not notified_signal_ids:
                    new_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
                else:
                    query = "SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE' AND rowid NOT IN ({})".format(','.join('?' for _ in notified_signal_ids))
                    new_signals = conn.execute(query, tuple(notified_signal_ids)).fetchall()
            for signal in new_signals:
                await notifier.send_batch_trend_alert_notification([dict(signal)])
                notified_signal_ids.add(signal['rowid'])
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
            notified_trade_ids.update(r[0] for r in closed_trades)
    except Exception as e:
        logger.error(f"❌ Error initializing outcome_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                if not notified_trade_ids:
                    newly_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
                else:
                    query = "SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE' AND rowid NOT IN ({})".format(','.join('?' for _ in notified_trade_ids))
                    newly_closed_trades = conn.execute(query, tuple(notified_trade_ids)).fetchall()
            for trade in newly_closed_trades:
                await notifier.send_trade_outcome_notification(dict(trade))
                notified_trade_ids.add(trade['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in outcome_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)


# --- HÀM MỚI: VÒNG LẶP TỰ ĐỘNG CẬP NHẬT ---
async def update_loop(notifier: NotificationHandler):
    """
    Vòng lặp định kỳ kiểm tra cập nhật từ Git và khởi động lại bot nếu có.
    """
    logger.info("✅ Auto-update Loop starting...")
    while True:
        await asyncio.sleep(30 * 60) # Kiểm tra mỗi 30 phút
        
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
            pull_process = await asyncio.create_subprocess_shell('git pull origin ai', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
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


# --- MAIN FUNCTION ---
async def main():
    logger.info("--- 🚀 Initializing Bot ---")
    client = None
    # CẢI TIẾN: Tạo một danh sách để quản lý các tác vụ
    running_tasks = [] 
    
    try:
        # --- 1. Khởi tạo các thành phần ---
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        
        # --- 2. Tải và Huấn luyện Model ---
        logger.info("🧠 Loading/Training AI Model...")
        model, label_encoder, model_features = None, None, None
        try:
            model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
            logger.info("✅ AI Model loaded from files.")
        except FileNotFoundError:
            logger.warning("⚠️ Model files not found. Performing initial training...")
            loop = asyncio.get_running_loop()
            initial_accuracy = await loop.run_in_executor(None, train_model)
            if initial_accuracy is not None:
                logger.info("Reloading model after initial training...")
                model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
        
        # --- 3. Gửi thông báo khởi động ---
        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("Could not fetch symbols. Exiting.")
            return

        if all([model, label_encoder, model_features]):
            # Accuracy chỉ có từ lần training đầu tiên, nếu tải từ file thì là None
            await notifier.send_startup_notification(len(all_symbols), locals().get('initial_accuracy', None))
        else:
            await notifier.send_fallback_mode_startup_notification(len(all_symbols))

        # --- 4. Khởi chạy tất cả các vòng lặp nền ---
        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        
        # CẢI TIẾN: Tạo và thêm các tác vụ vào danh sách quản lý
        running_tasks = [
            asyncio.create_task(analysis_loop(client, all_symbols, model, label_encoder, model_features)),
            asyncio.create_task(signal_check_loop(notifier)),
            asyncio.create_task(updater_loop(client)),
            asyncio.create_task(outcome_check_loop(notifier)),
            asyncio.create_task(training_loop(notifier, len(all_symbols)))
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