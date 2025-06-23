import sys
import logging
import asyncio
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from binance import AsyncClient as Client
import config
from database_handler import init_sqlite_db
from analysis_engine import process_symbol
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from updater import check_signal_outcomes
from result import get_win_loss_stats

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# --- BOT LOOPS ---

# CHANGE: The loop now accepts the client as an argument
async def analysis_loop(client: Client, symbols_to_monitor: set):
    """LOOP 1: Continuously analyzes the market for specified symbols."""
    logger.info(f"✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes)")
    while True:
        logger.info(f"--- Starting analysis cycle for {len(symbols_to_monitor)} symbols ---")
        tasks = [process_symbol(client, symbol) for symbol in list(symbols_to_monitor)]
        await asyncio.gather(*tasks, return_exceptions=True) # Run symbols in parallel for speed
        
        logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
        await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)

async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: Checks for the latest strong signals from the DB and sends notifications."""
    logger.info(f"✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds)")
    last_notified_signal_time = {} # Dictionary to track notified signals for each symbol
    while True:
        try:
            # CHANGE: Using a safer read-only connection string
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                query = """
                WITH RankedSignals AS (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY analysis_timestamp_utc DESC) as rn
                    FROM trend_analysis
                )
                SELECT * FROM RankedSignals WHERE rn = 1 AND trend IN (?, ?) AND status = 'ACTIVE'
                """
                latest_strong_signals = conn.execute(query, (config.TREND_STRONG_BULLISH, config.TREND_STRONG_BEARISH)).fetchall()

            new_signals_to_notify = []
            for record in latest_strong_signals:
                symbol, timestamp = record['symbol'], record['analysis_timestamp_utc']
                if timestamp > last_notified_signal_time.get(symbol, ''):
                    new_signals_to_notify.append(dict(record))
                    last_notified_signal_time[symbol] = timestamp
                    logger.info(f"🔥 Queued new signal for {symbol} ({record['trend']}).")
            
            if new_signals_to_notify:
                await notifier.send_batch_trend_alert_notification(new_signals_to_notify)
        except Exception as e:
            logger.error(f"❌ Error in signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def updater_loop(client: Client):
    """LOOP 3: Automatically checks and updates the outcome of open signals (TP/SL)."""
    logger.info(f"✅ Updater Loop starting (interval: {config.UPDATER_INTERVAL_SECONDS / 60:.0f} minutes)")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def summary_loop(notifier: NotificationHandler):
    """LOOP 4: Periodically sends a performance summary report."""
    logger.info(f"✅ Performance Summary Loop starting (interval: {config.SUMMARY_INTERVAL_SECONDS / 3600:.0f} hours)")
    while True:
        # Wait for the interval period before sending the first report
        await asyncio.sleep(config.SUMMARY_INTERVAL_SECONDS)
        try:
            logger.info("--- Generating and sending performance report... ---")
            stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
            await notifier.send_summary_report(stats)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in the summary_loop: {e}", exc_info=True)

async def heartbeat_loop(notifier: NotificationHandler, symbols_to_monitor: set):
    """LOOP 5: Periodically sends a 'heartbeat' notification to confirm the bot is alive."""
    logger.info(f"✅ Heartbeat Loop starting (interval: {config.HEARTBEAT_INTERVAL_SECONDS / 3600:.0f} hours)")
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL_SECONDS)
        try:
            await notifier.send_heartbeat_notification(symbols_count=len(symbols_to_monitor))
        except Exception as e:
            logger.error(f"❌ A critical error occurred in the heartbeat_loop: {e}", exc_info=True)

# --- MAIN FUNCTION: BOT STARTUP AND MANAGEMENT ---
async def main():
    logger.info("--- Initializing Bot ---")
    
    # CHANGE: Initialize client within the async main function
    client = None
    if not (config.API_KEY and config.API_SECRET):
        logger.critical("API_KEY and API_SECRET not found. Cannot initialize Binance client. Exiting.")
        sys.exit(1)
        
    try:
        client = await Client.create(config.API_KEY, config.API_SECRET)
        logger.info("Binance client initialized successfully.")

        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        all_symbols = set(config.STATIC_SYMBOLS)
        logger.info(f"Bot will monitor {len(all_symbols)} symbols.")

        # Send a critical startup notification
        await notifier.send_startup_notification(symbols_count=len(all_symbols))

        logger.info("--- Bot is now running. All loops are active. ---")
        
        # Run all loops concurrently
        await asyncio.gather(
            analysis_loop(client, all_symbols),
            signal_check_loop(notifier),
            updater_loop(client),
            summary_loop(notifier),
            heartbeat_loop(notifier, all_symbols)
        )
    finally:
        # CHANGE: Ensure the client connection is always closed gracefully
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as main_exc:
        logger.critical(f"A fatal error occurred in the main execution block: {main_exc}", exc_info=True)
    finally:
        logger.info("--- Bot application shutting down. ---")

