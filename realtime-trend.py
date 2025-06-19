from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import pandas_ta as ta
from binance.client import Client
import os, sqlite3, time
from binance.exceptions import BinanceAPIException, BinanceRequestException
import sys, logging, asyncio, json
from typing import Optional, Any, Dict, List, Set

# Local Modules
import telegram_handler
import notifications

# --- Constants ---
# (Constants remain the same, ensure they are here)
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TREND_STRONG_BULLISH = "✅ #StrongBullish"
TREND_STRONG_BEARISH = "❌ #StrongBearish"
# ... and so on for all your constants

# --- Logging & Config ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = { "binance": {"api_key_placeholder": API_KEY_PLACEHOLDER}, "trading": {"symbols": ["BTCUSDT"], "timeframe": "15m", "loop_sleep_interval_seconds": 3600, "periodic_notification_interval_seconds": 600}, "sqlite": {"db_path": "trend_analysis.db"}, "telegram": {"bot_token_placeholder": TELEGRAM_BOT_TOKEN_PLACEHOLDER} }
def load_config(config_path="config.json"):
    # (Your existing load_config function)
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            for section, settings in file_config.items():
                if section in config: config[section].update(settings)
    except Exception: pass
    return config

config_data = load_config()

# --- Load All Configuration Variables ---
# (Your existing config loading variables)
API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"].get("api_key_placeholder"))
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"].get("api_secret_placeholder"))
SYMBOLS = [s.strip().upper() for s in config_data["trading"]["symbols"]]
TIMEFRAME = config_data["trading"]["timeframe"]
EMA_FAST, EMA_MEDIUM, EMA_SLOW = int(config_data["trading"]["ema_fast"]), int(config_data["trading"]["ema_medium"]), int(config_data["trading"]["ema_slow"])
SQLITE_DB_PATH = config_data["sqlite"]["db_path"]
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"].get("bot_token_placeholder"))
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"].get("chat_id_placeholder"))
TELEGRAM_MESSAGE_THREAD_ID = config_data["telegram"].get("message_thread_id_placeholder") # Simplified
LOOP_SLEEP_INTERVAL_SECONDS = int(config_data["trading"]["loop_sleep_interval_seconds"])
SIGNAL_CHECK_INTERVAL_SECONDS = int(config_data["trading"]["periodic_notification_interval_seconds"])

# Initialize Binance Client
binance_client = Client(API_KEY, API_SECRET) if API_KEY != API_KEY_PLACEHOLDER else None

# --- Core Functions (init_db, get_data, perform_analysis) ---
# (Keep your existing, corrected versions of these functions. The key change is that perform_analysis NO LONGER sends notifications.)
def init_sqlite_db(db_path: str): # Your existing function
    pass
def get_market_data(symbol: str, required_candles: int) -> pd.DataFrame: # Your existing function
    return pd.DataFrame()
async def perform_analysis(df: pd.DataFrame, symbol: str) -> None: # MODIFIED: Doesn't need to return anything
    # This function's only job is to calculate and SAVE to the database.
    # (Your existing perform_analysis logic for calculating indicators and saving to DB goes here)
    # Ensure it calculates and saves all 27 columns correctly.
    # REMOVE any calls to notifications from this function.
    pass

# --- NEW ARCHITECTURE: TWO SEPARATE LOOPS ---

async def analysis_loop():
    """
    LOOP 1 (HOURLY): The Data Collector.
    Fetches from Binance, analyzes, and saves to the database. Does NOT send alerts.
    """
    logger.info(f"--- ✅ Analysis Loop starting (interval: {LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    while True:
        try:
            logger.info("--- Starting new analysis cycle ---")
            for symbol in SYMBOLS:
                market_data = get_market_data(symbol, EMA_SLOW + 200) # Buffer
                if not market_data.empty:
                    # The analysis function now just saves the data to the DB.
                    await perform_analysis(market_data, symbol)
            
            logger.info(f"--- Analysis cycle complete. Waiting for next run. ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
            
        except Exception as e:
            logger.exception("❌ Error in analysis_loop")
            await asyncio.sleep(60) # Wait a minute before retrying on error

async def signal_check_loop():
    """
    LOOP 2 (10 MINUTES): The Signal Notifier.
    Queries the database for new signals and sends alerts. Does NOT connect to Binance.
    """
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    
    # State management: Stores the timestamp of the last signal we notified for each symbol.
    last_notified_signal = {}

    await asyncio.sleep(10) # Initial delay
    while True:
        try:
            with sqlite3.connect(f'file:{SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                # This query efficiently gets the single latest record for EVERY symbol.
                query = "SELECT * FROM trend_analysis WHERE rowid IN (SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol)"
                latest_records = conn.execute(query).fetchall()

            for record in latest_records:
                symbol = record['symbol']
                trend = record['trend']
                timestamp = record['analysis_timestamp_utc']

                # Check for a strong signal
                if trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                    # Check if this signal is NEWER than the last one we notified about
                    if timestamp > last_notified_signal.get(symbol, ''):
                        logger.info(f"🔥 New signal detected for {symbol}! Trend: {trend}. Notifying...")
                        
                        await notifications.send_individual_trend_alert_notification(
                            bot_token=TELEGRAM_BOT_TOKEN,
                            chat_id=TELEGRAM_CHAT_ID,
                            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                            analysis_result=dict(record), # Pass the full record
                            # Pass constants for formatting the message
                            bbands_period_const=20, # Assuming BBANDS_PERIOD
                            bbands_std_dev_const=2.0, # Assuming BBANDS_STD_DEV
                            atr_period_const=14, # Assuming ATR_PERIOD
                            rsi_period_const=14, # Assuming RSI_PERIOD
                            ema_fast_const=EMA_FAST,
                            ema_medium_const=EMA_MEDIUM,
                            ema_slow_const=EMA_SLOW
                        )
                        
                        # IMPORTANT: Update the state to avoid re-notifying
                        last_notified_signal[symbol] = timestamp
        
        except Exception as e:
            logger.exception("❌ Error in signal_check_loop")
        
        await asyncio.sleep(SIGNAL_CHECK_INTERVAL_SECONDS)

async def main():
    """Initializes and runs the bot's concurrent loops."""
    logger.info("--- Initializing Bot with new architecture ---")
    if not binance_client:
        logger.critical("Binance client not initialized. Exiting.")
        sys.exit(1)
    
    init_sqlite_db(SQLITE_DB_PATH) # Make sure DB and table exist
    
    if not await telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID, # Pass required args
        message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID,
        symbols_display=", ".join(SYMBOLS),
        timeframe_display=TIMEFRAME,
        loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS//60}m, Signal Check: {SIGNAL_CHECK_INTERVAL_SECONDS//60}m"
    ):
        logger.critical("Failed to send Telegram startup message. Exiting.")
        sys.exit(1)

    # Create and run the two independent tasks
    analysis_task = asyncio.create_task(analysis_loop())
    signal_task = asyncio.create_task(signal_check_loop())
    
    logger.info("--- Bot is now running. Analysis and Signal loops are active. ---")
    await asyncio.gather(analysis_task, signal_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        asyncio.run(telegram_handler.close_session())
        logger.info("--- Bot shutdown complete. ---")

