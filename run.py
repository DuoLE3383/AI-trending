# run.py (Phiên bản cuối cùng đã sửa lỗi)

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
from market_data_handler import get_market_data

from analysis_engine import process_symbol
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from updater import check_signal_outcomes
from result import get_win_loss_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None

# --- CÁC VÒNG LẶP (LOOPS) CỦA BOT ---
# In run.py

# ... (imports and other code) ...

# LOOP 1: Phân tích thị trường (đã được đơn giản hóa)
async def analysis_loop(symbols_to_monitor: set):
    logger.info(f"--- ✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    while True:
        logger.info(f"--- Starting analysis cycle for {len(symbols_to_monitor)} symbols ---")
        for symbol in list(symbols_to_monitor):

            try:
                await perform_analysis(binance_client, symbol)
            except Exception as symbol_error:
                logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {symbol_error}", exc_info=True)
        logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
        await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)

# LOOP 2: Kiểm tra và gửi tín hiệu
async def signal_check_loop(notifier: NotificationHandler):
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal = {}
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM trend_analysis WHERE rowid IN (SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol)"
                latest_records = conn.execute(query).fetchall()
            
            new_signals_to_notify = []
            for record in latest_records:
                symbol, trend, timestamp = record['symbol'], record['trend'], record['analysis_timestamp_utc']
                if trend in [config.TREND_STRONG_BULLISH, config.TREND_STRONG_BEARISH]:
                    if timestamp > last_notified_signal.get(symbol, ''):
                        new_signals_to_notify.append(dict(record))
                        logger.info(f"🔥 Queued new signal for {symbol}! Trend: {trend}.")
                        last_notified_signal[symbol] = timestamp
            
            # Dòng 'if' này được thụt lề đúng, thẳng hàng với 'for' ở trên
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
        await asyncio.sleep(60) # Chờ 1 phút sau khi khởi động để gửi báo cáo đầu tiên
        
        logger.info("--- Generating performance report... ---")
        stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
        stats_msg = "🏆 **Strategy Performance Report (All-Time)** 🏆\n\n"
        if 'error' in stats:
            stats_msg += "Could not generate statistics."
        elif stats['total_completed_trades'] > 0:
            stats_msg += (
                f"✅ **Win Rate:** `{stats['win_rate']}`\n"
                f"❌ **Loss Rate:** `{stats['loss_rate']}`\n"
                f"📊 **Completed Trades:** `{stats['total_completed_trades']}`"
            )
        else:
            stats_msg += "No completed trades to analyze yet."

        try:
            await notifier.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID, message=stats_msg,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID, parse_mode="Markdown"
            )
            logger.info("Successfully sent performance report to Telegram.")
        except Exception as e:
            logger.error(f"Failed to send performance report: {e}")
            
        await asyncio.sleep(config.SUMMARY_INTERVAL_SECONDS)

# --- HÀM MAIN: KHỞI ĐỘNG VÀ QUẢN LÝ BOT ---
async def main():
    logger.info("--- Initializing Bot ---")
    if not binance_client:
        logger.critical("Binance client not initialized. Check API keys in .env file. Exiting.")
        sys.exit(1)

    init_sqlite_db(config.SQLITE_DB_PATH)
    tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
    notifier = NotificationHandler(telegram_handler=tg_handler)

    all_symbols = set(config.STATIC_SYMBOLS)
    if config.DYN_SYMBOLS_ENABLED:
        logger.info("Dynamic symbols enabled, but will not be fetched in this version for simplicity.")
        # dynamic_symbols = fetch_and_filter_binance_symbols(binance_client)
        # if dynamic_symbols: all_symbols.update(dynamic_symbols)
    logger.info(f"Bot will monitor {len(all_symbols)} symbols.")

    await notifier.send_startup_notification(symbols_count=len(all_symbols))

    logger.info("--- Bot is now running. All loops are active. ---")
    
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
