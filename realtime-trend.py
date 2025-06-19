# Imports from your original file
from dotenv import load_dotenv
load_dotenv()
import pandas as pd
import pandas_ta as ta
from binance.client import Client
import time
import os, sqlite3
from binance.exceptions import BinanceAPIException, BinanceRequestException
import sys
import logging, asyncio
import json
from typing import Optional, Any, Dict, List

# Your project's modules
import telegram_handler
import notifications # Make sure to import your notifications module

# --- All your existing constants can remain the same ---
# (API_KEY_PLACEHOLDER, ANALYSIS_CANDLE_BUFFER, RSI_PERIOD, etc.)
# --- Placeholder Constants ---
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER = 'YOUR_TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER' # For topic/thread IDs
# --- Analysis Constants ---
PRE_LOAD_CANDLE_COUNT = 300
ANALYSIS_CANDLE_BUFFER = 200 # Additional candles to fetch beyond the slowest EMA period for analysis
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2.0
ATR_PERIOD = 14
ATR_MULTIPLIER_SHORT = 1.5
ATR_MULTIPLIER_LONG = 1.5
ATR_MULTIPLIER_SL = 1.2
ATR_MULTIPLIER_TP1 = 1.3
ATR_MULTIPLIER_TP2 = 2.3
ATR_MULTIPLIER_TP3 = 3.2
TREND_STRONG_BULLISH = "✅ #StrongBullish"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_STRONG_BEARISH = "❌ #StrongBearish"
TREND_SIDEWAYS = "Sideways/Undetermined"

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Configuration Loading (remains the same) ---
DEFAULT_CONFIG = {
    "binance": {"api_key_placeholder": API_KEY_PLACEHOLDER, "api_secret_placeholder": API_SECRET_PLACEHOLDER},
    "trading": {
        "symbols": ["BTCUSDT"], "timeframe": "15m", "ema_fast": 34, "ema_medium": 89, "ema_slow": 200,
        "loop_sleep_interval_seconds": 3600, "periodic_notification_interval_seconds": 600
    },
    "sqlite": {"db_path": "trend_analysis.db"},
    "telegram": {"bot_token_placeholder": TELEGRAM_BOT_TOKEN_PLACEHOLDER, "chat_id_placeholder": TELEGRAM_CHAT_ID_PLACEHOLDER, "proxy_url": None, "message_thread_id_placeholder": TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER}
}

def load_config(config_path="config.json") -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            for section, settings in file_config.items():
                if section in config: config[section].update(settings)
                else: config[section] = settings
        logger.info(f"Successfully loaded configuration from {config_path}")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Config file issue. Using default/env settings.")
    return config

config_data = load_config()

# --- Configuration Variables (remains mostly the same) ---
API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"]["api_key_placeholder"])
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"]["api_secret_placeholder"])
SYMBOLS_STR = os.getenv('TRADING_SYMBOLS', ",".join(config_data["trading"]["symbols"]))
SYMBOLS = [s.strip().upper() for s in SYMBOLS_STR.split(',') if s.strip()]
TIMEFRAME = os.getenv('TRADING_TIMEFRAME', config_data["trading"]["timeframe"])
EMA_FAST = int(os.getenv('EMA_FAST', config_data["trading"]["ema_fast"]))
EMA_MEDIUM = int(os.getenv('EMA_MEDIUM', config_data["trading"]["ema_medium"]))
EMA_SLOW = int(os.getenv('EMA_SLOW', config_data["trading"]["ema_slow"]))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", config_data["sqlite"]["db_path"])
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"]["bot_token_placeholder"])
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"]["chat_id_placeholder"])
raw_message_thread_id = os.getenv('TELEGRAM_MESSAGE_THREAD_ID', config_data["telegram"]["message_thread_id_placeholder"])
TELEGRAM_MESSAGE_THREAD_ID: Optional[int] = None
if raw_message_thread_id and str(raw_message_thread_id) != TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER:
    try: TELEGRAM_MESSAGE_THREAD_ID = int(raw_message_thread_id)
    except ValueError: logger.warning("Invalid TELEGRAM_MESSAGE_THREAD_ID.")

# --- NEW: Load both intervals from config ---
LOOP_SLEEP_INTERVAL_SECONDS = int(os.getenv('LOOP_SLEEP_INTERVAL_SECONDS', config_data["trading"]["loop_sleep_interval_seconds"]))
PERIODIC_NOTIFICATION_INTERVAL_SECONDS = int(os.getenv('PERIODIC_NOTIFICATION_INTERVAL_SECONDS', config_data["trading"]["periodic_notification_interval_seconds"]))

# --- Binance Client Initialization (remains the same) ---
binance_client: Optional[Client] = None
if API_KEY != API_KEY_PLACEHOLDER and API_SECRET != API_SECRET_PLACEHOLDER:
    try:
        binance_client = Client(API_KEY, API_SECRET)
        binance_client.get_server_time()
        logger.info("✅ Successfully connected to Binance.")
    except Exception as e:
        logger.error(f"Failed to connect to Binance: {e}")
        binance_client = None

# --- ALL YOUR HELPER FUNCTIONS (init_sqlite_db, get_market_data, perform_analysis) remain EXACTLY the same ---
# (I've omitted them here for brevity, but you should keep them in your file)

def init_sqlite_db(db_path: str) -> bool:
    # ... your existing function ...
    return True

def get_market_data(symbol: str, required_candles: int) -> pd.DataFrame:
    # ... your existing function ...
    return pd.DataFrame()

async def perform_analysis(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    # ... your existing function ...
    return {}


# ==============================================================================
# NEW SCRIPT STRUCTURE: Two independent loops
# ==============================================================================

async def analysis_loop():
    """
    This loop runs on the long interval (e.g., 1 hour).
    It fetches data from Binance, performs analysis, saves to the database,
    and sends ALERTS for strong trends.
    """
    logger.info(f"--- Analysis loop starting (interval: {LOOP_SLEEP_INTERVAL_SECONDS}s) ---")
    REQUIRED_CANDLES_FOR_ANALYSIS = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    
    while True:
        logger.info(f"--- Starting new analysis cycle ---")
        try:
            for symbol_to_analyze in SYMBOLS:
                logger.info(f"--- Analyzing {symbol_to_analyze} ---")
                market_data_df = get_market_data(symbol_to_analyze, required_candles=REQUIRED_CANDLES_FOR_ANALYSIS + max(RSI_PERIOD, ATR_PERIOD))

                if not market_data_df.empty:
                    analysis_result = await perform_analysis(market_data_df, symbol_to_analyze)
                    if analysis_result and analysis_result['trend'] in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                        # Only send individual ALERTS for strong trends from this loop
                        await notifications.send_individual_trend_alert_notification(
                            chat_id=TELEGRAM_CHAT_ID,
                            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                            analysis_result=analysis_result,
                            bbands_period_const=BBANDS_PERIOD,
                            atr_period_const=ATR_PERIOD,
                            bbands_std_dev_const=BBANDS_STD_DEV,
                            rsi_period_const=RSI_PERIOD, ema_fast_const=EMA_FAST,
                            ema_medium_const=EMA_MEDIUM, ema_slow_const=EMA_SLOW
                        )
                else:
                    logger.warning(f"Skipping analysis for {symbol_to_analyze} due to empty market data.")

            logger.info(f"--- Analysis cycle complete. Waiting for {LOOP_SLEEP_INTERVAL_SECONDS} seconds... ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)

        except Exception as e:
            logger.exception("An unexpected error occurred in the analysis_loop:")
            logger.info(f"Retrying analysis loop in 60 seconds...")
            await asyncio.sleep(60)

async def periodic_notification_loop():
    """
    This loop runs on the short interval (e.g., 10 minutes).
    It does NOT talk to Binance. It queries the local database and sends
    a periodic summary to Telegram.
    """
    logger.info(f"--- Periodic Notification loop starting (interval: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS}s) ---")
    # Wait a little bit on the first run to ensure the analysis loop has a chance to populate the DB
    await asyncio.sleep(20) 
    
    while True:
        try:
            logger.info("--- Preparing periodic summary notification ---")
            await notifications.send_periodic_summary_notification(
                db_path=SQLITE_DB_PATH,
                symbols=SYMBOLS,
                timeframe=TIMEFRAME,
                chat_id=TELEGRAM_CHAT_ID,
                message_thread_id=TELEGRAM_MESSAGE_THREAD_ID
            )
            
            logger.info(f"--- Periodic summary sent. Waiting for {PERIODIC_NOTIFICATION_INTERVAL_SECONDS} seconds... ---")
            await asyncio.sleep(PERIODIC_NOTIFICATION_INTERVAL_SECONDS)

        except Exception as e:
            logger.exception("An unexpected error occurred in the periodic_notification_loop:")
            logger.info(f"Retrying notification loop in 60 seconds...")
            await asyncio.sleep(60)

async def main():
    """
    Main function to initialize and orchestrate the bot's tasks.
    """
    logger.info("--- Starting Real-Time Market Analysis Bot ---")

    # Initialize services
    init_sqlite_db(SQLITE_DB_PATH)

    # Prepare display strings for startup message
    symbols_display_str = ", ".join(SYMBOLS) if SYMBOLS else "N/A"
    
    # Initialize Telegram and send startup message
    telegram_bot_initialized = await telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID,
        proxy_url=None, # Proxy is disabled in your code
        symbols_display=symbols_display_str,
        timeframe_display=TIMEFRAME,
        # Update the startup message to show both intervals
        loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS}s, Summary: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS}s"
    )

    if not telegram_bot_initialized:
        logger.critical("Failed to initialize Telegram Bot. Exiting.")
        sys.exit(1)

    if not SYMBOLS:
        logger.error("No trading symbols configured. Exiting.")
        sys.exit(1)

    # --- Pre-load initial data (same as before) ---
    logger.info("--- Pre-loading initial market data ---")
    for symbol_to_preload in SYMBOLS:
        pre_load_df = get_market_data(symbol_to_preload, required_candles=PRE_LOAD_CANDLE_COUNT)
        if pre_load_df.empty:
            logger.warning(f"Failed to pre-load data for {symbol_to_preload}.")
        else:
            logger.info(f"✅ Successfully pre-loaded data for {symbol_to_preload}.")

    # --- Create and run the two main tasks concurrently ---
    analysis_task = asyncio.create_task(analysis_loop())
    notification_task = asyncio.create_task(periodic_notification_loop())

    logger.info("--- Both analysis and notification loops are now running concurrently. ---")
    
    try:
        # This will run forever until one of the tasks fails or is cancelled
        await asyncio.gather(analysis_task, notification_task)
    except KeyboardInterrupt:
        logger.info("🛑 Analysis stopped by user. Shutting down...")
        # Cancel the tasks
        analysis_task.cancel()
        notification_task.cancel()
        # Send shutdown message
        await notifications.send_shutdown_notification(
            chat_id=TELEGRAM_CHAT_ID,
            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
            symbols_list=SYMBOLS
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during script execution: {e}", exc_info=True)
    
    logger.info("--- Bot shutdown complete. ---")

