# run.py (Phiên bản đã tái cấu trúc sạch sẽ)
import sys
import logging
import asyncio
import sqlite3
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

# --- Import các module của bot ---
import config
from database_handler import init_sqlite_db
from analysis_engine import process_symbol
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from updater import check_signal_outcomes
from result import get_win_loss_stats

# --- Cấu hình logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Khởi tạo Binance Client ---
if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None

# --- CÁC VÒNG LẶP (LOOPS) CỦA BOT ---

# LOOP 1: Phân tích thị trường
async def analysis_loop(symbols_to_monitor: set):
    logger.info(f"--- ✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    while True:
        logger.info(f"--- Starting analysis cycle for {len(symbols_to_monitor)} symbols ---")
        for symbol in list(symbols_to_monitor):
            try:
                # Gọi hàm xử lý chuyên biệt, không cần biết logic bên trong
                await process_symbol(binance_client, symbol)
            except Exception as symbol_error:
                logger.error(f"❌ A top-level error occurred for {symbol}: {symbol_error}", exc_info=True)
        logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
        await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)

# LOOP 2: Kiểm tra và gửi tín hiệu
async def signal_check_loop(notifier: NotificationHandler):
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal_time = {}
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                # Lấy các bản ghi mới nhất và có tín hiệu mạnh
                query = """
                SELECT * FROM trend_analysis
                WHERE trend IN (?, ?) AND rowid IN (
                    SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol
                )
                """
                latest_strong_signals = conn.execute(query, (config.TREND_STRONG_BULLISH, config.TREND_STRONG_BEARISH)).fetchall()

            new_signals_to_notify = []
            for record in latest_strong_signals:
                symbol, timestamp = record['symbol'], record['analysis_timestamp_utc']
                # Chỉ thông báo nếu tín hiệu này mới hơn tín hiệu đã thông báo trước đó
                if timestamp > last_notified_signal_time.get(symbol, ''):
                    new_signals_to_notify.append(dict(record))
                    logger.info(f"🔥 Queued new signal for {symbol}! Trend: {record['trend']}.")
                    last_notified_signal_time[symbol] = timestamp
            
            if new_signals_to_notify:
                # Gọi hàm thông báo, không cần truyền chat_id hay định dạng gì cả
                await notifier.send_batch_trend_alert_notification(new_signals_to_notify)

        except Exception as e:
            logger.exception(f"❌ Error in signal_check_loop: {e}")
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

# LOOP 3: Tự động cập nhật kết quả trade (TP/SL)
async def updater_loop(client: Client):
    logger.info(f"--- ✅ Updater Loop starting (interval: {config.UPDATER_INTERVAL_SECONDS/60:.0f} minutes) ---")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

# LOOP 4: Tự động gửi báo cáo hiệu suất
async def summary_loop(notifier: NotificationHandler):
    logger.info(f"--- ✅ Performance Summary Loop starting (interval: {config.SUMMARY_INTERVAL_SECONDS/3600:.0f} hours) ---")
    while True:
        await asyncio.sleep(config.SUMMARY_INTERVAL_SECONDS)
        try:
            logger.info("--- Generating and sending performance report... ---")
            # Bước 1: Lấy data
            stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
            # Bước 2: Yêu cầu notifier gửi đi. XONG!
            await notifier.send_summary_report(stats)
        except Exception as e:
            logger.error(f"A critical error occurred in the summary_loop: {e}", exc_info=True)

# --- HÀM MAIN: KHỞI ĐỘNG VÀ QUẢN LÝ BOT ---
async def main():
    logger.info("--- Initializing Bot ---")
    if not binance_client:
        logger.critical("Binance client not initialized. Check API keys. Exiting.")
        sys.exit(1)

    init_sqlite_db(config.SQLITE_DB_PATH)
    tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
    notifier = NotificationHandler(telegram_handler=tg_handler)

    all_symbols = set(config.STATIC_SYMBOLS)
    logger.info(f"Bot will monitor {len(all_symbols)} symbols.")

    # Gửi thông báo khởi động
    await notifier.send_startup_notification(symbols_count=len(all_symbols))

    logger.info("--- Bot is now running. All loops are active. ---")
    
    # Chạy tất cả các vòng lặp song song
    await asyncio.gather(
        analysis_loop(all_symbols),
        signal_check_loop(notifier=notifier),
        updater_loop(client=binance_client),
        summary_loop(notifier=notifier)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        logger.info("Bot application shutting down.")
