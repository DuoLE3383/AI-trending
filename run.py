# run.py
import sys
import logging
import asyncio
import time
from binance.client import Client
from dotenv import load_dotenv
import sqlite3
load_dotenv()

import config
from database_handler import init_sqlite_db
from market_data_handler import get_market_data, fetch_and_filter_binance_symbols
from analysis_engine import perform_analysis
from telegram_handler import TelegramHandler
from notifications import NotificationHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None

async def analysis_loop(monitored_symbols_ref: dict):
    logger.info(f"--- ✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    last_symbol_update_time = 0
    while True:
        try:
            current_time = time.time()
            if config.DYN_SYMBOLS_ENABLED and (current_time - last_symbol_update_time > config.DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS):
                logger.info("--- Updating symbol list from Binance ---")
                dynamic_symbols = fetch_and_filter_binance_symbols(binance_client)
                if dynamic_symbols:
                    monitored_symbols_ref['symbols'].update(dynamic_symbols)
                    logger.info(f"--- Symbol list updated. Now monitoring {len(monitored_symbols_ref['symbols'])} symbols. ---")
                last_symbol_update_time = current_time
            
            logger.info(f"--- Starting analysis cycle for {len(monitored_symbols_ref['symbols'])} symbols ---")
            for symbol in list(monitored_symbols_ref['symbols']):
                try:
                    market_data = get_market_data(binance_client, symbol)
                    if not market_data.empty:
                        await perform_analysis(market_data, symbol)
                except Exception as symbol_error:
                    logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {symbol_error}", exc_info=True)
            logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
            await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception(f"❌ A critical error occurred in analysis_loop. Restarting in 60 seconds... Details: {e}")
            await asyncio.sleep(60)

async def signal_check_loop(notifier: NotificationHandler):
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal = {}
    await asyncio.sleep(10)
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
            if new_signals_to_notify:
                await notifier.send_batch_trend_alert_notification(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                    analysis_results=new_signals_to_notify
                )
        except Exception:
            logger.exception("❌ Error in signal_check_loop.")
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

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

    logger.info("--- Bot is now running. Analysis and Signal loops are active. ---")
    await asyncio.gather(
        analysis_loop(monitored_symbols_ref),
        signal_check_loop(notifier=notifier)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        logger.info("Bot application shutting down.")
