# run.py
import sys
import logging
import asyncio
import time
import sqlite3
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

# Import đầy đủ các module cần thiết
import config
from database_handler import init_sqlite_db
from market_data_handler import get_market_data, fetch_and_filter_binance_symbols
from analysis_engine import perform_analysis
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from updater import check_signal_outcomes  # Import hàm updater

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None

# --- CÁC VÒNG LẶP (LOOPS) ---

# LOOP 1: Phân tích (Không đổi)
async def analysis_loop(monitored_symbols_ref: dict):
    # ... (Code của hàm này giữ nguyên) ...

# LOOP 2: Gửi tín hiệu (Không đổi)
async def signal_check_loop(notifier: NotificationHandler):
    # ... (Code của hàm này giữ nguyên) ...

# LOOP 3: Tự động cập nhật kết quả trade (TP/SL)
async def updater_loop(client: Client):
    """Vòng lặp này sẽ tự động chạy để kiểm tra kết quả của các trade cũ."""
    logger.info(f"--- ✅ Updater Loop starting (interval: 5 minutes) ---")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        # Chờ 5 phút cho lần kiểm tra tiếp theo
        await asyncio.sleep(300)

# --- HÀM MAIN ĐỂ KHỞI ĐỘNG MỌI THỨ ---
async def main():
    logger.info("--- Initializing Bot ---")
    if not binance_client:
        logger.critical("Binance client not initialized. Check API keys in .env file. Exiting.")
        sys.exit(1)

    init_sqlite_db(config.SQLITE_DB_PATH)
    tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
    notifier = NotificationHandler(telegram_handler=tg_handler)

    logger.info("Fetching initial symbol list...")
    all_symbols = set(config.STATIC_SYMBOLS)
    if config.DYN_SYMBOLS_ENABLED:
        dynamic_symbols = fetch_and_filter_binance_symbols(binance_client)
        if dynamic_symbols:
            all_symbols.update(dynamic_symbols)
    monitored_symbols_ref = {'symbols': all_symbols}
    logger.info(f"Bot will monitor {len(all_symbols)} symbols.")

    # Gửi tin nhắn khởi động mới và hấp dẫn
    await notifier.send_startup_notification(symbols_count=len(all_symbols))

    logger.info("--- Bot is now running. Analysis, Signal, and Updater loops are active. ---")
    
    # Chạy cả 3 vòng lặp cùng lúc
    await asyncio.gather(
        analysis_loop(monitored_symbols_ref),
        signal_check_loop(notifier=notifier),
        updater_loop(client=binance_client)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        logger.info("Bot application shutting down.")
