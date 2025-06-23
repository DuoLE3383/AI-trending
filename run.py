# run.py (Phiên bản cuối cùng với 4 vòng lặp tự động)

import sys
import logging
import asyncio
import time
import sqlite3
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

import config
from database_handler import init_sqlite_db
from market_data_handler import get_market_data, fetch_and_filter_binance_symbols
from analysis_engine import perform_analysis
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from updater import check_signal_outcomes
from results import get_win_loss_stats # Import hàm thống kê

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None

# --- CÁC VÒNG LẶP (LOOPS) CỦA BOT ---

# LOOP 1 & 2: analysis_loop và signal_check_loop (Giữ nguyên như cũ)
# ... (Bạn không cần thay đổi code của 2 hàm này)

# LOOP 3: Tự động cập nhật kết quả trade (TP/SL)
async def updater_loop(client: Client):
    logger.info(f"--- ✅ Updater Loop starting (interval: 5 minutes) ---")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(300) # Chờ 5 phút

# LOOP 4: Tự động gửi báo cáo hiệu suất
async def summary_loop(notifier: NotificationHandler):
    """Vòng lặp này sẽ gửi báo cáo hiệu suất định kỳ."""
    logger.info(f"--- ✅ Performance Summary Loop starting (interval: 12 hours) ---")
    while True:
        # Chờ 12 giờ trước khi gửi báo cáo tiếp theo
        # Bot sẽ gửi báo cáo đầu tiên sau 1 tiếng khởi động
        await asyncio.sleep(3600) # Chờ 1 tiếng cho lần đầu tiên
        
        logger.info("--- Generating performance report... ---")
        stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
        
        stats_msg = "🏆 **Strategy Performance Report (All-Time)** 🏆\n\n"
        if 'error' in stats:
            stats_msg += "Could not generate statistics due to an error."
            logger.error(f"Could not generate stats: {stats['error']}")
        elif stats.get('total_completed_trades', 0) > 0:
            stats_msg += (
                f"✅ **Win Rate:** `{stats['win_rate']}`\n"
                f"❌ **Loss Rate:** `{stats['loss_rate']}`\n"
                f"📊 **Completed Trades:** `{stats['total_completed_trades']}`\n\n"
                f"**Breakdown:**\n"
            )
            for status, count in stats['breakdown'].items():
                stats_msg += f"- `{status}`: {count}\n"
        else:
            stats_msg += "No completed trades to analyze yet."

        # Gửi báo cáo vào Telegram
        try:
            await notifier.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=stats_msg,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="Markdown"
            )
            logger.info("Successfully sent performance report to Telegram.")
        except Exception as e:
            logger.error(f"Failed to send performance report: {e}")
            
        await asyncio.sleep(12 * 60 * 60) # Chờ 12 tiếng

# --- HÀM MAIN ĐỂ KHỞI ĐỘNG MỌI THỨ ---
async def main():
    # ... (Phần khởi tạo main giữ nguyên như cũ) ...
    # ... (Phần lấy danh sách symbol giữ nguyên) ...

    await notifier.send_startup_notification(symbols_count=len(all_symbols))

    logger.info("--- Bot is now running. All 4 loops are active! ---")
    
    # Chạy cả 4 vòng lặp cùng lúc
    await asyncio.gather(
        analysis_loop(monitored_symbols_ref),
        signal_check_loop(notifier=notifier),
        updater_loop(client=binance_client),
        summary_loop(notifier=notifier) # <--- Thêm vòng lặp báo cáo
    )

# ... (Phần if __name__ == "__main__": giữ nguyên) ...

            
            if new_signals_to_notify:
                await notifier.send_batch_trend_alert_notification(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                    analysis_results=new_signals_to_notify
                )
        except Exception as e:
            logger.exception(f"❌ Error in signal_check_loop: {e}")
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

# LOOP 3: Tự động cập nhật kết quả trade (TP/SL)
async def updater_loop(client: Client):
    logger.info(f"--- ✅ Updater Loop starting (interval: 5 minutes) ---")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        # Chờ 5 phút cho lần kiểm tra tiếp theo
        await asyncio.sleep(300)

# --- HÀM MAIN: KHỞI ĐỘNG VÀ QUẢN LÝ BOT ---
async def main():
    logger.info("--- Initializing Bot ---")
    
    if not binance_client:
        logger.critical("Binance client not initialized. Check API keys in .env file. Exiting.")
        sys.exit(1)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.critical("Telegram BOT_TOKEN or CHAT_ID is missing in your .env file. Exiting.")
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

    # Gửi tin nhắn khởi động
    await notifier.send_startup_notification(symbols_count=len(all_symbols))

    logger.info("--- Bot is now running. Analysis, Signal, and Updater loops are active. ---")
    
    # Chạy cả 3 vòng lặp cùng lúc
    await asyncio.gather(
        analysis_loop(monitored_symbols_ref),
        signal_check_loop(notifier=notifier),
        updater_loop(client=binance_client)
    )

# --- Điểm bắt đầu chạy chương trình ---
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        logger.info("Bot application shutting down.")
