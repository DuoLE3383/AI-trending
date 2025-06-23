import sys
import logging
import asyncio
import time
import sqlite3
from binance.client import Client
from dotenv import load_dotenv
from updater import check_signal_outcomes

# Load environment variables first
load_dotenv()

# Import our new modules
import config
from database_handler import init_sqlite_db
from market_data_handler import get_market_data, fetch_and_filter_binance_symbols
from analysis_engine import perform_analysis

# Import handlers
from telegram_handler import TelegramHandler
from notifications import NotificationHandler

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Initialize Binance Client ---
if config.API_KEY and config.API_KEY != config.API_KEY_PLACEHOLDER and config.API_SECRET and config.API_SECRET != config.API_SECRET_PLACEHOLDER:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized with API keys.")
else:
    binance_client = None
    logger.warning("Binance API Key or Secret is missing/placeholder. Market data fetching will not work.")

# --- MAIN LOOPS & EXECUTION ---

async def analysis_loop(monitored_symbols_ref: dict):
    """LOOP 1: The Data Collector."""
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
                    else:
                        logger.warning(f"No valid market data to analyze for {symbol}. Skipping.")
                except Exception as symbol_error:
                    logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {symbol_error}", exc_info=True)

            logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
            await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception:
            logger.exception("❌ A critical error occurred in analysis_loop. Restarting in 60 seconds...")
            await asyncio.sleep(60)

# THIS IS THE CORRECT, UPDATED FUNCTION THAT BATCHES NOTIFICATIONS
async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: The Signal Notifier (with message batching)."""
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal = {}
    await asyncio.sleep(10) # Initial delay

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM trend_analysis WHERE rowid IN (SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol)"
                latest_records = conn.execute(query).fetchall()

            # 1. Create a list to hold new signals for this cycle
            new_signals_to_notify = []

            for record in latest_records:
                symbol, trend, timestamp = record['symbol'], record['trend'], record['analysis_timestamp_utc']
                
                if trend in [config.TREND_STRONG_BULLISH, config.TREND_STRONG_BEARISH]:
                    if timestamp > last_notified_signal.get(symbol, ''):
                        # 2. Instead of sending immediately, add the signal to our batch list
                        new_signals_to_notify.append(dict(record))
                        logger.info(f"🔥 Queued new signal for {symbol}! Trend: {trend}.")
                        # Update the timestamp so we don't notify for this one again
                        last_notified_signal[symbol] = timestamp
            
            # 3. After checking all symbols, send ONE combined message if we have new signals
            if new_signals_to_notify:
                logger.info(f"--- Found {len(new_signals_to_notify)} new signals. Sending combined notification. ---")
                
                # This calls the new function that you must add to notifications.py
                await notifier.send_batch_trend_alert_notification(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                    analysis_results=new_signals_to_notify
                )

        except Exception:
            logger.exception("❌ Error in signal_check_loop. Will retry in next interval.")
            
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def main():
    """Initializes and runs the bot's concurrent loops."""
    logger.info("--- Initializing Bot ---")

    if not binance_client:
        logger.critical("Binance client not initialized. Cannot fetch market data. Exiting.")
        sys.exit(1)
    
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == config.TELEGRAM_BOT_TOKEN_PLACEHOLDER or \
       not config.TELEGRAM_CHAT_ID or config.TELEGRAM_CHAT_ID == config.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.critical("Telegram BOT_TOKEN or CHAT_ID is missing. Please check your config. Exiting.")
        sys.exit(1)

    init_sqlite_db(config.SQLITE_DB_PATH)
    
    try:
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
    except Exception as e:
        logger.critical(f"Failed to initialize handlers: {e}. Exiting.")
        sys.exit(1)

    # --- Prepare for startup message and main loops ---
    logger.info("Fetching initial symbol list for startup message...")
    all_symbols = set(config.STATIC_SYMBOLS)
    if config.DYN_SYMBOLS_ENABLED:
        dynamic_symbols = fetch_and_filter_binance_symbols(binance_client)
        if dynamic_symbols:
            all_symbols.update(dynamic_symbols)

    monitored_symbols_ref = {'symbols': all_symbols}

    priority_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    display_list = []
    remaining_symbols = all_symbols.copy()

    for symbol in priority_symbols:
        if symbol in remaining_symbols:
            display_list.append(f"#{symbol}" if not display_list else symbol)
            remaining_symbols.discard(symbol)

    if len(remaining_symbols) > 0:
        display_list.append(f"(+{len(remaining_symbols)} more)")

    formatted_symbols_str = ", ".join(display_list)

    try:
        await notifier.send_startup_notification(
            chat_id=config.TELEGRAM_CHAT_ID,
            message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
            symbols_str=formatted_symbols_str,
            symbols_full_list=list(all_symbols)
        )
    except Exception as e:
        logger.critical(f"Failed to send Telegram startup message: {e}. Exiting.")
        sys.exit(1)

    logger.info("--- Bot is now running. Analysis and Signal loops are active. ---")
    
    analysis_task = asyncio.create_task(analysis_loop(monitored_symbols_ref))
    signal_task = asyncio.create_task(signal_check_loop(notifier=notifier))
    
    await asyncio.gather(analysis_task, signal_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user via KeyboardInterrupt.")
    finally:
        logger.info("Bot application shutting down.")
        
# In run.py, replace your existing main function with this one

async def main():
    """Initializes and runs all the bot's concurrent loops."""
    logger.info("--- Initializing Bot ---")

    # Exit if Binance client failed to initialize
    if not binance_client:
        return

    # Check for Telegram credentials
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.critical("Telegram BOT_TOKEN or CHAT_ID is missing in your .env file. Exiting.")
        sys.exit(1)

    # Initialize the database and handlers
    init_sqlite_db(config.SQLITE_DB_PATH)
    tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
    notifier = NotificationHandler(telegram_handler=tg_handler)

    # --- THIS IS THE CORRECTED SECTION FOR SYMBOL SETUP ---
    logger.info("Fetching initial symbol list for analysis...")
    # Start with the static list from your config file
    all_symbols = set(config.STATIC_SYMBOLS)
    
    # If dynamic symbols are enabled, fetch them from Binance and add them
    if config.DYN_SYMBOLS_ENABLED:
        logger.info("Dynamic symbols enabled. Fetching from Binance...")
        dynamic_symbols = fetch_and_filter_binance_symbols(binance_client)
        if dynamic_symbols:
            all_symbols.update(dynamic_symbols)
            logger.info(f"Added {len(dynamic_symbols)} dynamic symbols.")

    # This dictionary is passed to the analysis loop so it knows what to monitor
    monitored_symbols_ref = {'symbols': all_symbols}
    logger.info(f"Bot will monitor a total of {len(all_symbols)} symbols.")
    
    # --- Send Startup Notification ---
    # (This section can be customized as you had it before to format the symbol list)
    try:
        startup_message = f"📈 *Bot Started*\nMonitoring {len(all_symbols)} symbols."
        await notifier.telegram_handler.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            message=startup_message,
            message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    logger.info("--- Bot is now running. All loops are active. ---")
    
    # Create and run all tasks concurrently using the correctly prepared symbol list
    await asyncio.gather(
        analysis_loop(monitored_symbols_ref), # <-- This now uses the correct variable
        signal_check_loop(notifier=notifier),
        updater_loop(client=binance_client),
        summary_loop(notifier=notifier)
    )



