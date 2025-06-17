from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

import pandas as pd
import pandas_ta as ta
from binance.client import Client
import time
import os, sqlite3 # Updated imports
from binance.exceptions import BinanceAPIException, BinanceRequestException
import sys
import logging
import json # Added for loading config file
from typing import Optional, Any, Dict
import telegram_handler # Import the new module

# --- Placeholder Constants ---
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
MONGO_URI_PLACEHOLDER = 'YOUR_MONGO_CONNECTION_STRING_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Configuration Loading Function ---
DEFAULT_CONFIG = {
    "binance": {
        "api_key_placeholder": API_KEY_PLACEHOLDER,
        "api_secret_placeholder": API_SECRET_PLACEHOLDER
    },
    "trading": {
        "symbols": ["BTCUSDT"], # Default to a list with one symbol
        "timeframe": "1m",
        "ema_fast": 34,
        "ema_medium": 89,
        "ema_slow": 200,
        "loop_sleep_interval_seconds": 60
    },
    "sqlite": {
        "db_path": "trend_analysis.db" # SQLite DB in script directory
        # To specify full path:  "db_path": "/path/to/trend_analysis.db"
    },
    # Remove the MongoDB settings
    # "mongodb": {
    #     "uri_placeholder": MONGO_URI_PLACEHOLDER,
    #     "db_name": "trading_analysis",
    #     "collection_name": "trends"
    },
    "telegram": {
        "bot_token_placeholder": TELEGRAM_BOT_TOKEN_PLACEHOLDER,
        "chat_id_placeholder": TELEGRAM_CHAT_ID_PLACEHOLDER,
        "proxy_url": None
    }
}

def load_config(config_path="config.json") -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            for section, settings in file_config.items():
                if section in config:
                    config[section].update(settings)
                else:
                    config[section] = settings
        logger.info(f"Successfully loaded configuration from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Configuration file {config_path} not found. Using default script settings and environment variables.")
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {config_path}. Using default script settings and environment variables.")
    return config

config_data = load_config()

# --- Configuration ---
# ⚠️ IMPORTANT: These are loaded from environment variables (or .env file)
API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"]["api_key_placeholder"])
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"]["api_secret_placeholder"])

# Load symbols as a list. If TRADING_SYMBOLS env var is set, it should be comma-separated.
SYMBOLS_STR = os.getenv('TRADING_SYMBOLS', ",".join(config_data["trading"]["symbols"]))
SYMBOLS = [s.strip().upper() for s in SYMBOLS_STR.split(',') if s.strip()]
TIMEFRAME = os.getenv('TRADING_TIMEFRAME', config_data["trading"]["timeframe"])
EMA_FAST = int(os.getenv('EMA_FAST', config_data["trading"]["ema_fast"]))
EMA_MEDIUM = int(os.getenv('EMA_MEDIUM', config_data["trading"]["ema_medium"]))
EMA_SLOW = int(os.getenv('EMA_SLOW', config_data["trading"]["ema_slow"]))
LOOP_SLEEP_INTERVAL_SECONDS = int(os.getenv('LOOP_SLEEP_INTERVAL', config_data["trading"]["loop_sleep_interval_seconds"]))

# Load SQLite DB Path
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", config_data["sqlite"]["db_path"])
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"]["bot_token_placeholder"])
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"]["chat_id_placeholder"])
PROXY_URL = os.getenv('PROXY_URL', config_data["telegram"]["proxy_url"])

# --- Initialize Binance Client ---
binance_client: Optional[Client] = None
if API_KEY == API_KEY_PLACEHOLDER or API_SECRET == API_SECRET_PLACEHOLDER:
    logger.critical("Binance API keys are not set or are using default placeholders.")
    logger.critical("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
    logger.info("Binance functionality will be disabled.")
    # Depending on script criticality, you might want to exit:
    # sys.exit("Exiting due to missing Binance API keys.")
else:
    try:
        binance_client = Client(API_KEY, API_SECRET)
        binance_client.get_server_time()
        logger.info("✅ Successfully connected to Binance.")
    except (BinanceAPIException, BinanceRequestException) as e:
        logger.error(f"Failed to connect to Binance or validate API keys (Binance Error): {e}")
        binance_client = None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Binance client initialization: {e}")
        binance_client = None

def get_market_data(symbol: str) -> pd.DataFrame:
    """Fetches historical and live market data from Binance."""
    if not binance_client:
        logger.error("Binance client not initialized or connection failed. Cannot fetch market data.")
        return pd.DataFrame()

    logger.info(f"Fetching {TIMEFRAME} data for {symbol}...")
    try:
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, f"{EMA_SLOW * 2 + 50} minutes ago UTC")
        if not klines:
            logger.warning(f"No kline data received from Binance for {symbol} and {TIMEFRAME}.")
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'number_of_trades', 
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        return df
    except (BinanceAPIException, BinanceRequestException) as e:
        logger.error(f"Error fetching market data for {symbol} from Binance (Binance Error): {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching market data for {symbol} from Binance: {e}")
        return pd.DataFrame()

def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """Calculates EMAs and determines the trend."""
    if df.empty:
        logger.warning("Dataframe is empty, cannot perform analysis.")
        return

    if len(df) < EMA_SLOW:
        logger.warning(f"Not enough data ({len(df)} points) to calculate EMA_{EMA_SLOW}. Need at least {EMA_SLOW} points.")
        return

    df.ta.ema(length=EMA_FAST, append=True, col_names=(f'EMA_{EMA_FAST}',))
    df.ta.ema(length=EMA_MEDIUM, append=True, col_names=(f'EMA_{EMA_MEDIUM}',))
    df.ta.ema(length=EMA_SLOW, append=True, col_names=(f'EMA_{EMA_SLOW}',))
    
    last_row = df.iloc[-1]
    price: Optional[float] = last_row.get('close')
    ema_fast_val: Optional[float] = last_row.get(f'EMA_{EMA_FAST}')
    ema_medium_val: Optional[float] = last_row.get(f'EMA_{EMA_MEDIUM}')
    ema_slow_val: Optional[float] = last_row.get(f'EMA_{EMA_SLOW}')

    price_str = f"${price:,.2f}" if pd.notna(price) else "N/A"
    ema_fast_str = f"${ema_fast_val:,.2f}" if pd.notna(ema_fast_val) else "N/A"
    ema_medium_str = f"${ema_medium_val:,.2f}" if pd.notna(ema_medium_val) else "N/A"
    ema_slow_str = f"${ema_slow_val:,.2f}" if pd.notna(ema_slow_val) else "N/A"
    
    current_time_utc = pd.to_datetime('now', utc=True)
    log_header = f"\n{'='*15} Analysis for {SYMBOL} at {current_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} {'='*15}"
    logger.info(f"\n{'='*15} Analysis for {symbol} at {current_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} {'='*15}")
    logger.info(f"Current Price: {price_str}")
    logger.info(f"EMA {EMA_FAST:<{len(str(EMA_SLOW))}}:       {ema_fast_str}")
    logger.info(f"EMA {EMA_MEDIUM:<{len(str(EMA_SLOW))}}:     {ema_medium_str}")
    logger.info(f"EMA {EMA_SLOW:<{len(str(EMA_SLOW))}}:       {ema_slow_str}")
    
    trend = "Sideways/Undetermined"
    if all(pd.notna(val) for val in [price, ema_fast_val, ema_medium_val, ema_slow_val]):
        if price > ema_fast_val and ema_fast_val > ema_medium_val and ema_medium_val > ema_slow_val:
            trend = "✅ Strong Bullish"
        elif price > ema_fast_val and price > ema_medium_val and price > ema_slow_val: # General bullish conditions
            trend = "Bullish"
        elif price < ema_fast_val and price < ema_medium_val and price < ema_slow_val: # General bearish conditions
            trend = "Bearish"
        elif price < ema_fast_val and ema_fast_val < ema_medium_val and ema_medium_val < ema_slow_val:
            trend = "❌ Strong Bearish"
        
    logger.info(f"Trend: {trend}")
    logger.info("=" * len(log_header.strip()) + "\n")

    if telegram_bot and TELEGRAM_CHAT_ID != TELEGRAM_CHAT_ID_PLACEHOLDER:
        message = (
            f"*{symbol} Trend Alert* ({TIMEFRAME})\n\n"
            f"Time: {current_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"Price: `{price_str}`\n"
            f"EMA {EMA_FAST}: `{ema_fast_str}`\n"
            f"EMA {EMA_MEDIUM}: `{ema_medium_str}`\n"
            f"EMA {EMA_SLOW}: `{ema_slow_str}`\n\n"
            f"Trend: *{trend}*"
        )
        telegram_handler.send_telegram_notification(TELEGRAM_CHAT_ID, message)

    # Save to SQLite
    if SQLITE_DB_PATH:  # Make sure we have a DB path
        last_candle_open_time: Optional[pd.Timestamp] = last_row.name if pd.notna(last_row.name) else None
        data_to_save = {
            'analysis_timestamp_utc': current_time_utc,
            'timeframe': TIMEFRAME,
            'price': price if pd.notna(price) else None,
            f'ema_{EMA_FAST}': ema_fast_val if pd.notna(ema_fast_val) else None,
            f'ema_{EMA_MEDIUM}': ema_medium_val if pd.notna(ema_medium_val) else None,
            f'ema_{EMA_SLOW}': ema_slow_val if pd.notna(ema_slow_val) else None,
            'trend': trend,
            'last_candle_open_time_utc': last_candle_open_time
        }
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()

            # Create the table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trend_analysis (
                    analysis_timestamp_utc TEXT,
                    symbol TEXT,  -- Added symbol column
                    timeframe TEXT,
                    price REAL,
                    ema_34 REAL,
                    ema_89 REAL,
                    ema_200 REAL,
                    trend TEXT,
                    last_candle_open_time_utc TEXT
                )
            ''')
            
            # Insert the analysis data
            cursor.execute('''
                INSERT INTO trend_analysis (analysis_timestamp_utc, symbol, timeframe, price, ema_34, ema_89, ema_200, trend, last_candle_open_time_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data_to_save['analysis_timestamp_utc'].isoformat(),  # Convert datetime to string for SQLite
                symbol,  # Include the symbol being analyzed
                data_to_save['timeframe'],
                data_to_save['price'],
                data_to_save['ema_34'],
                data_to_save['ema_89'],
                data_to_save['ema_200'],
                data_to_save['trend'],
                data_to_save['last_candle_open_time_utc'].isoformat() if data_to_save['last_candle_open_time_utc'] else None  # Convert datetime to string
            ))

            conn.commit()
            conn.close()
            logger.info(f"✅ Successfully saved analysis to SQLite for {symbol} at {SQLITE_DB_PATH}.")

        except sqlite3.Error as e:  # Catch SQLite-specific errors
            logger.error(f"Failed to save data to SQLite: {e}")

    else:
        logger.warning("SQLite database path not configured. Data will not be saved.")

# --- Main Loop ---
if __name__ == "__main__":
    logger.info("--- Starting Real-Time Market Analysis Bot ---")
    
    if not (binance_client or (MONGO_URI != MONGO_URI_PLACEHOLDER) or (TELEGRAM_BOT_TOKEN != TELEGRAM_BOT_TOKEN_PLACEHOLDER)):
        logger.critical("No services (Binance, MongoDB, Telegram) are properly configured. The script may not perform any useful actions.")
        # sys.exit("Exiting due to lack of service configurations.") # Optional: exit if no services configured

    mongodb_connected = init_mongodb()
    # Initialize Telegram bot using the new handler
    telegram_bot_initialized = telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        proxy_url=PROXY_URL,
        symbol_for_startup=", ".join(SYMBOLS) if SYMBOLS else "N/A") # Pass all symbols for startup message

    if not SYMBOLS:
        logger.error("No trading symbols configured. Please check your config.json or TRADING_SYMBOLS environment variable.")
        sys.exit("Exiting due to no symbols configured.")

    logger.info(f"--- Analysis loop starting for symbols: {', '.join(SYMBOLS)} ({TIMEFRAME}) every {LOOP_SLEEP_INTERVAL_SECONDS}s ---")
    logger.info("Press CTRL+C to stop.")
    
    cycle_count = 0
    while True:
        cycle_count += 1
        logger.info(f"--- Cycle {cycle_count} ({pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}) ---")
        try:
            for symbol_to_analyze in SYMBOLS:
                logger.info(f"--- Analyzing {symbol_to_analyze} ---")
                market_data_df = get_market_data(symbol_to_analyze)
                if not market_data_df.empty:
                    perform_analysis(market_data_df, symbol_to_analyze)
                else:
                    logger.warning(f"Skipping analysis for {symbol_to_analyze} due to empty market data.")
            
            logger.info(f"--- Cycle {cycle_count} complete. Waiting for {LOOP_SLEEP_INTERVAL_SECONDS} seconds... ---")
            time.sleep(LOOP_SLEEP_INTERVAL_SECONDS) 
        except KeyboardInterrupt:
            logger.info("🛑 Analysis stopped by user. Shutting down...")
            if telegram_handler.telegram_bot and TELEGRAM_CHAT_ID != TELEGRAM_CHAT_ID_PLACEHOLDER: # Check bot instance in handler
                shutdown_message = f"🛑 Trend Analysis Bot for {', '.join(SYMBOLS)} stopped by user at {pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}."
                telegram_handler.send_telegram_notification(TELEGRAM_CHAT_ID, shutdown_message, suppress_print=True)
            break
        except ConnectionFailure as e: # More specific error for MongoDB
            logger.error(f"MongoDB Connection Failure in main loop: {e}.")
            logger.info(f"Attempting to re-initialize MongoDB in {LOOP_SLEEP_INTERVAL_SECONDS} seconds...")
            time.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
            mongodb_connected = init_mongodb() # Try to re-initialize
        except Exception as e:
            logger.exception("An unexpected error occurred in the main loop:") # logger.exception automatically includes traceback
            logger.info(f"Retrying in {LOOP_SLEEP_INTERVAL_SECONDS} seconds...")
            time.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
    
    logger.info("--- Bot shutdown complete. ---")