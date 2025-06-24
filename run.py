# run.py
import sys
import logging
import asyncio
import sqlite3
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
from result import get_win_loss_stats
from updater import get_usdt_futures_symbols, check_signal_outcomes


# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# --- BOT LOOPS ---

async def analysis_loop(client: AsyncClient, symbols_to_monitor: set):
    """LOOP 1: Analyzes the market for new trade signals."""
    logger.info(f"✅ Analysis Loop starting (interval: {config.LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes)")
    CONCURRENT_REQUESTS = 10 
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            await process_symbol(client, symbol)

    while True:
        logger.info(f"--- Starting analysis cycle for {len(symbols_to_monitor)} symbols (max {CONCURRENT_REQUESTS} at a time) ---")
        tasks = [process_with_semaphore(symbol) for symbol in list(symbols_to_monitor)]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"--- Analysis cycle complete. symbols_count={len(symbols_to_monitor)} PAIRS. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
        await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)

async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: Notifies about newly opened trade signals."""
    logger.info(f"✅ New Signal Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds)")
    last_notified_signal_time = {}
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                
                # --- CORRECTED SQL QUERY for compatibility with older SQLite versions ---
                query = """
                SELECT t1.* FROM trend_analysis t1
                WHERE t1.analysis_timestamp_utc = (
                    SELECT MAX(t2.analysis_timestamp_utc)
                    FROM trend_analysis t2
                    WHERE t2.symbol = t1.symbol
                )
                AND t1.trend IN (?, ?) AND t1.status = 'ACTIVE';
                """
                
                latest_strong_signals = conn.execute(query, (config.TREND_STRONG_BULLISH, config.TREND_STRONG_BEARISH)).fetchall()

            for record in latest_strong_signals:
                if record['analysis_timestamp_utc'] > last_notified_signal_time.get(record['symbol'], ''):
                    await notifier.send_batch_trend_alert_notification([dict(record)])
                    last_notified_signal_time[record['symbol']] = record['analysis_timestamp_utc']
        except Exception as e:
            logger.error(f"❌ Error in signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def updater_loop(client: AsyncClient):
    """LOOP 3: Updates the status of active trades (checks for TP/SL)."""
    logger.info(f"✅ Trade Updater Loop starting (interval: {config.UPDATER_INTERVAL_SECONDS / 60:.0f} minutes)")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def summary_loop(notifier: NotificationHandler):
    """LOOP 4: Sends a periodic performance summary."""
    logger.info(f"✅ Performance Summary Loop starting (interval: {config.SUMMARY_INTERVAL_SECONDS / 3600:.0f} hours)")
    while True:
        await asyncio.sleep(config.SUMMARY_INTERVAL_SECONDS)
        try:
            stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
            await notifier.send_summary_report(stats)
        except Exception as e:
            logger.error(f"❌ A critical error occurred in the summary_loop: {e}", exc_info=True)

async def heartbeat_loop(notifier: NotificationHandler, symbols_to_monitor: set):
    """LOOP 5: Sends a periodic 'I'm alive' message."""
    logger.info(f"✅ Heartbeat Loop starting (interval: {config.HEARTBEAT_INTERVAL_SECONDS / 3600:.0f} hours)")
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL_SECONDS)
        try:
            await notifier.send_heartbeat_notification(symbols_count=len(symbols_to_monitor))
        except Exception as e:
            logger.error(f"❌ A critical error occurred in the heartbeat_loop: {e}", exc_info=True)

async def outcome_check_loop(notifier: NotificationHandler):
    """LOOP 6: Checks for recently closed trades and sends notifications."""
    logger.info(f"✅ Trade Outcome Notification Loop starting (interval: {config.SIGNAL_CHECK_INTERVAL_SECONDS} seconds)")
    notified_trade_ids = set()

    # On startup, populate the set with all already-closed trades to avoid old notifications
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            closed_trades = conn.execute("SELECT rowid FROM trend_analysis WHERE status LIKE '%_HIT'").fetchall()
            notified_trade_ids.update([r[0] for r in closed_trades])
        logger.info(f"Initialized with {len(notified_trade_ids)} existing closed trades. Won't send old alerts.")
    except Exception as e:
        logger.error(f"❌ Error initializing outcome_check_loop: {e}", exc_info=True)

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                newly_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status LIKE '%_HIT'").fetchall()

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
    """Initializes and runs all bot components."""
    logger.info("--- Initializing Bot ---")
    
    client = None
    if not (config.API_KEY and config.API_SECRET):
        logger.critical("API_KEY and API_SECRET not found. Cannot start. Exiting.")
        sys.exit(1)
        
    try:
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        logger.info("Binance client initialized successfully.")
        
        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        
        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("Could not fetch a list of symbols to trade. Exiting.")
            sys.exit(1)
        
        logger.info(f"Bot will monitor {len(all_symbols)} symbols.")
        await notifier.send_startup_notification(symbols_count=len(all_symbols))

        logger.info("--- Bot is now running. All loops are active. ---")
        await asyncio.gather(
            analysis_loop(client, all_symbols),
            signal_check_loop(notifier),
            updater_loop(client),
            summary_loop(notifier),
            heartbeat_loop(notifier, all_symbols),
            outcome_check_loop(notifier),
            training_loop()  # 🧠 Model training every 8h
        )
    except Exception as main_exc:
        logger.critical(f"A fatal error occurred in the main execution block: {main_exc}", exc_info=True)
    finally:
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")
        logger.info("--- Bot application shutting down. ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")

