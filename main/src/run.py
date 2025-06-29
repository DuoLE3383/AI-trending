# run.py (Phiên bản đã được bổ sung tính năng tự động cập nhật)
import sys
import logging
import asyncio
import sqlite3
import joblib
import os # Import os để thực hiện restart
from binance import AsyncClient
from dotenv import load_dotenv
from . import config

load_dotenv()

# --- Project Module Imports ---
# Giả sử các file này nằm trong thư mục src/
try:
    from core.database_handler import init_sqlite_db
    from core.updater import get_usdt_futures_symbols, check_signal_outcomes
    from analysis.engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
    from services.telegram_handler import TelegramHandler
    from services.notifications import NotificationHandler
    from analysis.performance import get_performance_stats
    from models.trainer import train_model
    from models.training_loop import training_loop
except ImportError:
    # Fallback cho cấu trúc cũ nếu cần
    from database_handler import init_sqlite_db
    from updater import get_usdt_futures_symbols, check_signal_outcomes
    from analysis_engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
    from telegram_handler import TelegramHandler
    from notifications import NotificationHandler
    from performance_analyzer import get_performance_stats
    from trainer import train_model
    from training_loop import training_loop
    import config


# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- BOT LOOPS ---

async def analysis_loop(client: AsyncClient, symbols: set, model, label_encoder, model_features):
    """LOOP 1: Phân tích thị trường, chọn chiến lược từ config."""
    logger.info(f"✅ Analysis Loop starting (Strategy: {config.STRATEGY_MODE})")
    semaphore = asyncio.Semaphore(config.CONCURRENT_REQUESTS)
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            # Client được truyền vào từ hàm main, giúp cải thiện hiệu suất.
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
    """LOOP 2: Kiểm tra tín hiệu mới trong DB và gửi thông báo."""
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
    """LOOP 3: Cập nhật trạng thái của các lệnh đang mở (TP/SL)."""
    logger.info(f"✅ Trade Updater Loop starting...")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def outcome_check_loop(notifier: NotificationHandler):
    """LOOP 4: Kiểm tra các lệnh đã đóng và gửi thông báo kết quả."""
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
    # Define the branch and remote to check against
    remote_name = "origin"
    branch_name = "ai"
    remote_branch = f"{remote_name}/{branch_name}"

    while True:
        await asyncio.sleep(10 * 60) # Check every 10 minutes
        
        try:
            logger.info("📡 Checking for code updates from git...")
            
            # 1. Fetch the latest changes from the remote without merging
            fetch_process = await asyncio.create_subprocess_shell(
                f'git fetch {remote_name}', 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            await fetch_process.wait()

            # 2. Get the commit hash of the local HEAD
            local_hash_proc = await asyncio.create_subprocess_shell('git rev-parse HEAD', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            local_hash_out, local_hash_err = await local_hash_proc.communicate()
            if local_hash_proc.returncode != 0:
                logger.error(f"Could not get local commit hash: {local_hash_err.decode().strip()}")
                continue
            local_hash = local_hash_out.decode().strip()

            # 3. Get the commit hash of the remote branch
            remote_hash_proc = await asyncio.create_subprocess_shell(f'git rev-parse {remote_branch}', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            remote_hash_out, remote_hash_err = await remote_hash_proc.communicate()
            if remote_hash_proc.returncode != 0:
                logger.error(f"Could not get remote commit hash for '{remote_branch}': {remote_hash_err.decode().strip()}")
                continue
            remote_hash = remote_hash_out.decode().strip()

            # 4. Compare hashes
            if local_hash == remote_hash:
                logger.info(f"✅ Code is up-to-date with {remote_branch}.")
                continue

            logger.info(f"💡 New code found on {remote_branch}! Local: {local_hash[:7]}, Remote: {remote_hash[:7]}. Attempting to pull updates...")
            
            # CẢI TIẾN: Sử dụng git stash để tạm cất các thay đổi cục bộ (ví dụ: config.json)
            # trước khi pull, nhằm tránh xung đột. Đây là một cách an toàn để đảm bảo pull thành công.
            logger.info("Stashing local changes to prevent pull conflicts...")
            stash_proc = await asyncio.create_subprocess_shell(
                'git stash', 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            await stash_proc.wait()

            pull_process = await asyncio.create_subprocess_shell(
                f'git pull {remote_name} {branch_name}', 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            pull_stdout, pull_stderr = await pull_process.communicate()

            if pull_process.returncode == 0:
                logger.info(f"Git pull successful:\n{pull_stdout.decode()}")
                logger.critical("🚨 New code applied. Triggering bot restart...")
                await notifier._send_to_both("🚨 Bot is restarting to apply new updates\\.\\.\\.")
                await asyncio.sleep(5)
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                logger.error(f"❌ Failed to pull updates: {pull_stderr.decode()}")
                escaped_error = notifier.esc(pull_stderr.decode().strip())
                await notifier._send_to_both(f"❌ Failed to pull updates from `{notifier.esc(remote_branch)}`:\n```\n{escaped_error}\n```")

        except Exception as e:
            logger.error(f"❌ Error during update check: {e}", exc_info=True)


# --- MAIN FUNCTION ---
async def main():
    logger.info("--- 🚀 Initializing Bot ---")
    running_tasks = []
    client = None # Khởi tạo client là None
    
    try:
        # --- 1. Khởi tạo các thành phần cốt lõi ---
        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        
        # --- 2. Tạo một client Binance duy nhất, có thể tái sử dụng ---
        client = await AsyncClient.create()

        # --- 3. Tải/Huấn luyện Model AI (chỉ khi cần) ---
        model, label_encoder, model_features, initial_accuracy = None, None, None, None
        if config.STRATEGY_MODE == 'AI':
            logger.info("🧠 Chiến lược AI được chọn. Đang tải/huấn luyện Model...")
            try:
                model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
                logger.info("✅ Model AI đã được tải thành công từ tệp.")
            except FileNotFoundError:
                logger.warning("⚠️ Không tìm thấy tệp model. Đang thực hiện huấn luyện ban đầu...")
                loop = asyncio.get_running_loop()
                initial_accuracy = await loop.run_in_executor(None, train_model)
                if initial_accuracy is not None:
                    logger.info(f"✅ Huấn luyện ban đầu hoàn tất. Độ chính xác: {initial_accuracy:.2f}. Đang tải lại model...")
                    model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
                else:
                    logger.critical("❌ Huấn luyện model ban đầu thất bại. Bot không thể chạy ở chế độ 'AI' nếu không có model. Đang thoát.")
                    return # Thoát một cách an toàn

        # --- 4. Lấy danh sách cặp giao dịch và gửi thông báo khởi động ---
        all_symbols = await get_usdt_futures_symbols(client)
        
        if not all_symbols:
            logger.critical("❌ Không thể lấy danh sách cặp giao dịch từ Binance. Đang thoát.")
            return

        await notifier.send_startup_notification(len(all_symbols), initial_accuracy)
        
        # --- 5. Khởi chạy tất cả các vòng lặp nền ---
        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        
        running_tasks = [
            asyncio.create_task(analysis_loop(client, all_symbols, model, label_encoder, model_features)),
            asyncio.create_task(signal_check_loop(notifier)),
            asyncio.create_task(updater_loop(client)),
            asyncio.create_task(outcome_check_loop(notifier)),
            # Giả định training_loop cũng cần client để lấy dữ liệu lịch sử
            asyncio.create_task(training_loop(client, notifier, len(all_symbols))),
            asyncio.create_task(update_loop(notifier))
        ]
        await asyncio.gather(*running_tasks)

    except (Exception, KeyboardInterrupt) as main_exc:
        if isinstance(main_exc, KeyboardInterrupt):
            logger.info("Bot stopped by user (Ctrl+C).")
        else:
            logger.critical(f"A fatal error occurred in the main execution block: {main_exc}", exc_info=True)
    finally:
        # --- CƠ CHẾ TẮT AN TOÀN ---
        logger.info("--- ⭕ Bot application shutting down... ---")
        
        # 1. Hủy tất cả các tác vụ đang chạy
        for task in running_tasks:
            task.cancel()
        
        # 2. Chờ cho tất cả các tác vụ hoàn tất việc hủy
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
            logger.info("All loops have been cancelled.")
        
        # 3. Đóng kết nối client với Binance
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")
        logger.info("--- Shutdown complete. ---")

if __name__ == "__main__":
    # Bỏ khối try-except ở đây để khối finally trong main xử lý
    asyncio.run(main())
