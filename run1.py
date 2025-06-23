import sys
import logging
import asyncio
from binance.client import Client
from dotenv import load_dotenv

# --- Load environment variables from .env file FIRST ---
load_dotenv()

# --- Import All Project Modules ---
import config
from database_handler import init_sqlite_db
from market_data_handler import get_market_data, fetch_and_filter_binance_symbols
from analysis_engine import perform_analysis
from notifications import NotificationHandler
from telegram_handler import TelegramHandler
from updater import check_signal_outcomes
from results import get_analysis_summary, get_win_loss_stats

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Initialize Binance Client ---
# Note: config.API_KEY now correctly reads from your .env file thanks to load_dotenv()
if config.API_KEY and config.API_SECRET:
    binance_client = Client(config.API_KEY, config.API_SECRET)
    logger.info("Binance client initialized successfully.")
else:
    binance_client = None
    logger.critical("Binance API Key or Secret is missing in your .env file. Cannot start.")
    sys.exit(1)

# --- MAIN ASYNC LOOPS ---

async def analysis_loop(monitored_symbols_ref: dict):
    """LOOP 1: The Data Collector & Analyst."""
    logger.info(f"--- ✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    # ... (The rest of your analysis_loop code remains the same as you had it) ...
    # This loop calls perform_analysis from analysis_engine.py
    # ...

async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: The Signal Notifier (with message batching)."""
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    # ... (This is the improved signal_check_loop that batches notifications) ...
    # ... (It calls notifier.send_batch_trend_alert_notification) ...

async def updater_loop(client: Client):
    """LOOP 3: The Trade Outcome Updater."""
    logger.info(f"--- ✅ Updater Loop starting (interval: 5 minutes) ---")
    while True:
        try:
            # This function checks for TP/SL hits on active trades
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        # We can check for outcomes more frequently than we summarize
        await asyncio.sleep(300) # Sleep for 5 minutes

async def summary_loop(notifier: NotificationHandler):
    """LOOP 4: The Periodic Summarizer & Performance Reporter."""
    logger.info(f"--- ✅ Summary Loop starting (interval: 12 hours) ---")
    while True:
        # Initial wait before first summary
        await asyncio.sleep(60)
        
        # -- Generate Trend Summary --
        logger.info("--- Generating periodic trend summary... ---")
        trend_summary = get_analysis_summary(db_path=config.SQLITE_DB_PATH, time_period_hours=12)
        summary_msg = "📊 *Hourly Trend Summary*\n"
        if 'error' not in trend_summary and trend_summary.get('total_entries', 0) > 0:
            for trend, count in trend_summary['trend_counts'].items():
                summary_msg += f"- {trend.replace('_', ' ').title()}: {count}\n"
        else:
            summary_msg += "_No new trends recorded in the last 12 hours._"
        
        # -- Generate Performance Statistics --
        logger.info("--- Generating Win/Loss performance stats... ---")
        stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
        stats_msg = "\n🏆 *Strategy Performance (All-Time)*\n"
        if 'error' not in stats and stats.get('total_completed_trades', 0) > 0:
            stats_msg += (
                f"- *Win Rate:* {stats['win_rate']}\n"
                f"- *Loss Rate:* {stats['loss_rate']}\n"
                f"- *Completed Trades:* {stats['total_completed_trades']}"
            )
        else:
            stats_msg += "_No completed trades to analyze yet._"

        # -- Send Combined Report to Telegram --
        try:
            await notifier.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=summary_msg + stats_msg,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="Markdown"
            )
            logger.info("Successfully sent periodic summary and stats report.")
        except Exception as e:
            logger.error(f"Failed to send summary report: {e}", exc_info=True)

        # Sleep for 12 hours before the next report
        await asyncio.sleep(12 * 60 * 60)

async def main():
    """Initializes and runs all the bot's concurrent loops."""
    logger.info("--- Initializing Bot ---")

    # Exit if Binance client failed to initialize
    if not binance_client:
        # The specific error is already logged above
        return

    # Check for Telegram credentials
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.critical("Telegram BOT_TOKEN or CHAT_ID is missing in your .env file. Exiting.")
        sys.exit(1)

    # Initialize the database and handlers
    init_sqlite_db(config.SQLITE_DB_PATH)
    tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
    notifier = NotificationHandler(telegram_handler=tg_handler)

    # Send startup message
    # ... (Your startup message code here, it can remain the same) ...

    logger.info("--- Bot is now running. All loops are active. ---")
    
    # Create and run all tasks concurrently
    await asyncio.gather(
        analysis_loop({'symbols': set(config.STATIC_SYMBOLS)}),
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
