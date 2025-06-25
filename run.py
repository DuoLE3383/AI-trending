# run.py (Phiên bản cuối cùng, tích hợp AI và logic khởi động hoàn chỉnh)
import sys
import logging
import asyncio
import sqlite3
import joblib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Project Module Imports ---
from binance import AsyncClient
import config
from database_handler import init_sqlite_db
from analysis_engine import process_symbol
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats # Chuẩn hóa, dùng file này
from updater import get_usdt_futures_symbols, check_signal_outcomes
from trainer import train_model # Import hàm training
from training_loop import training_loop # Import vòng lặp training định kỳ

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- BOT LOOPS ---

async def analysis_loop(
    client: AsyncClient, 
    symbols_to_monitor: set, 
    model, 
    label_encoder, 
    model_features
):
    """LOOP 1: Phân tích thị trường để tìm tín hiệu mới, sử dụng model AI."""
    logger.info(f"✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes)")
    semaphore = asyncio.Semaphore(config.CONCURRENT_REQUESTS)
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            # CẬP NHẬT: Truyền model, encoder, và features vào hàm xử lý
            await process_symbol(client, symbol, model, label_encoder, model_features)

    while True:
        logger.info(f"--- Starting analysis cycle for {len(symbols_to_monitor)} symbols ---")
        tasks = [process_with_semaphore(symbol) for symbol in list(symbols_to_monitor)]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
        await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)

async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: Thông báo về các tín hiệu GIAO DỊCH MỚI được tạo ra."""
    logger.info(f"✅ New Signal Alert Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds)")
    notified_signal_ids = set()

    # Khởi động: lấy các tín hiệu đã thông báo để không gửi lại
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            # Giả định tất cả các tín hiệu trong DB lúc khởi động đều đã cũ
            existing_ids = conn.execute("SELECT rowid FROM trend_analysis").fetchall()
            notified_signal_ids.update([r[0] for r in existing_ids])
        logger.info(f"Initialized with {len(notified_signal_ids)} existing signals. Won't send old alerts.")
    except Exception as e:
        logger.error(f"❌ Error initializing signal_check_loop: {e}")

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                new_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()

            for signal in new_signals:
                if signal['rowid'] not in notified_signal_ids:
                    logger.info(f"✔️ Found new signal for {signal['symbol']} (rowid: {signal['rowid']}). Queuing notification.")
                    await notifier.send_batch_trend_alert_notification([dict(signal)])
                    notified_signal_ids.add(signal['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)


async def updater_loop(client: AsyncClient):
    """LOOP 3: Cập nhật trạng thái của các giao dịch đang hoạt động (check TP/SL)."""
    logger.info(f"✅ Trade Updater Loop starting (interval: {config.UPDATER_INTERVAL_SECONDS / 60:.0f} minutes)")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)


async def outcome_check_loop(notifier: NotificationHandler):
    """LOOP 4: Kiểm tra các giao dịch vừa đóng và gửi thông báo kết quả."""
    logger.info(f"✅ Trade Outcome Notification Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds)")
    notified_trade_ids = set()

    # Khởi động: lấy các giao dịch đã đóng để không thông báo lại
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            closed_trades = conn.execute("SELECT rowid FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
            notified_trade_ids.update([r[0] for r in closed_trades])
        logger.info(f"Initialized with {len(notified_trade_ids)} existing closed trades. Won't send old outcome alerts.")
    except Exception as e:
        logger.error(f"❌ Error initializing outcome_check_loop: {e}")

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                newly_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()

            for trade in newly_closed_trades:
                if trade['rowid'] not in notified_trade_ids:
                    logger.info(f"✔️ Found new trade outcome for {trade['symbol']} (rowid: {trade['rowid']}). Queuing notification.")
                    await notifier.send_trade_outcome_notification(dict(trade))
                    notified_trade_ids.add(trade['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in outcome_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)


# --- MAIN FUNCTION: BOT STARTUP AND MANAGEMENT ---
async def main():
    """Khởi tạo và chạy tất cả các thành phần của bot."""
    logger.info("--- 🚀 Initializing Bot ---")
    
    client = None
    if not (config.API_KEY and config.API_SECRET):
        logger.critical("API_KEY and API_SECRET not found. Exiting.")
        sys.exit(1)
        
    try:
        # --- 1. Khởi tạo các thành phần cốt lõi ---
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        
        # --- 2. Tải Model AI ---
        logger.info("🧠 Loading AI Model...")
        try:
            model = joblib.load("model_trend.pkl")
            label_encoder = joblib.load("trend_label_encoder.pkl")
            model_features = joblib.load("model_features.pkl")
            logger.info("✅ AI Model loaded successfully.")
        except FileNotFoundError:
            logger.warning("⚠️ Model files not found. Attempting to train a new one...")
            model, label_encoder, model_features = None, None, None
            
        # --- 3. Huấn luyện lần đầu khi khởi động ---
        loop = asyncio.get_running_loop()
        logger.info("💪 Performing initial model training...")
        initial_accuracy = await loop.run_in_executor(None, train_model)
        
        # Tải lại model nếu vừa được huấn luyện
        if initial_accuracy is not None:
            logger.info("Reloading model after initial training...")
            model = joblib.load("model_trend.pkl")
            label_encoder = joblib.load("trend_label_encoder.pkl")
            model_features = joblib.load("model_features.pkl")

        # --- 4. Lấy danh sách Symbols và Gửi thông báo khởi động ---
        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("Could not fetch symbols to trade. Exiting.")
            sys.exit(1)
            
        await notifier.send_startup_notification(
            symbols_count=len(all_symbols),
            accuracy=initial_accuracy
        )

        # --- 5. Khởi chạy tất cả các vòng lặp nền ---
        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        
        # Kiểm tra nếu model chưa được tải/huấn luyện thành công
        if not all([model, label_encoder, model_features]):
            logger.critical("Model could not be loaded or trained. Analysis loop will not run. Exiting.")
            sys.exit(1)

        await asyncio.gather(
            analysis_loop(client, all_symbols, model, label_encoder, model_features),
            signal_check_loop(notifier),
            updater_loop(client),
            outcome_check_loop(notifier),
            training_loop(notifier) # 🧠 Vòng lặp training định kỳ 8h
        )
    except Exception as main_exc:
        logger.critical(f"A fatal error occurred in the main execution block: {main_exc}", exc_info=True)
    finally:
        if client:
            await client.close()
            logger.info("Binance client connection closed.")
        logger.info("--- ⭕ Bot application shutting down. ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
