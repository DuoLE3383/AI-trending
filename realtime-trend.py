from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

import pandas as pd
import pandas_ta as ta
from binance.client import Client
import time
import os, sqlite3
from binance.exceptions import BinanceAPIException, BinanceRequestException # Removed BinanceSocketManagerError
import sys
import logging, asyncio # Added asyncio
import json # Added for loading config file
from typing import Optional, Any, Dict
import telegram_handler # Import the new module_handler
import notifications # Import the new notifications module

# --- Placeholder Constants ---
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER' # Added this line
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER = 'YOUR_TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER' # For topic/thread IDs

# --- Analysis Constants ---

# --- Script Constants ---
PRE_LOAD_CANDLE_COUNT = 300
ANALYSIS_CANDLE_BUFFER = 200 # Additional candles to fetch beyond the slowest EMA period for analysis

# RSI Constants
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Bollinger Bands Constants
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2.0

# ATR and Projected Range Constants
ATR_PERIOD = 14
ATR_MULTIPLIER_SHORT = 2.5 # Multiplier for a shorter-term volatility projection
ATR_MULTIPLIER_LONG = 2.5  # Multiplier for a longer-term volatility projection

# TP/SL ATR Multiplier Constants
ATR_MULTIPLIER_SL = 1.2    # Stop Loss: 1.5 * ATR
ATR_MULTIPLIER_TP1 = 1.3   # Take Profit 1: 1.5 * ATR (Risk/Reward ~1:1)
ATR_MULTIPLIER_TP2 = 2.3   # Take Profit 2: 3.0 * ATR (Risk/Reward ~1:2)
ATR_MULTIPLIER_TP3 = 3.2   # Take Profit 3: 4.5 * ATR (Risk/Reward ~1:3)


# Notification Constants
PERIODIC_NOTIFICATION_INTERVAL_SECONDS = 10 * 60  # Set to 600 seconds (10 minutes)

# --- Trend Constants ---
TREND_STRONG_BULLISH = "✅ #StrongBullish"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_STRONG_BEARISH = "❌ #StrongBearish"
TREND_SIDEWAYS = "Sideways/Undetermined"

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
        "timeframe": "15m",
        "ema_fast": 34,
        "ema_medium": 89,
        "ema_slow": 200,
        "loop_sleep_interval_seconds": 3600
    },
    "sqlite": {
        "db_path": "trend_analysis.db" # SQLite DB in script directory
    },
    "telegram": {
        "bot_token_placeholder": TELEGRAM_BOT_TOKEN_PLACEHOLDER,
        "chat_id_placeholder": TELEGRAM_CHAT_ID_PLACEHOLDER,
        "proxy_url": None,
        "message_thread_id_placeholder": TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER
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
LOOP_SLEEP_INTERVAL_SECONDS = 3600  # Set to 3600 seconds (60 minutes = 1 hour)

# Load SQLite DB Path
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", config_data["sqlite"]["db_path"])
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"]["bot_token_placeholder"])
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"]["chat_id_placeholder"])

# Load Telegram Message Thread ID (Topic ID)
raw_message_thread_id = os.getenv('TELEGRAM_MESSAGE_THREAD_ID', config_data["telegram"]["message_thread_id_placeholder"])
TELEGRAM_MESSAGE_THREAD_ID: Optional[int] = None

if raw_message_thread_id is not None and str(raw_message_thread_id) != TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER:
    try:
        TELEGRAM_MESSAGE_THREAD_ID = int(raw_message_thread_id)
    except ValueError:
        logger.warning(
            f"Invalid TELEGRAM_MESSAGE_THREAD_ID: '{raw_message_thread_id}'. Must be an integer. "
            "Topic-specific messaging will be disabled; messages will go to the main chat (if configured)."
        )
        # TELEGRAM_MESSAGE_THREAD_ID remains None
elif str(raw_message_thread_id) == TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER:
    logger.info(
        "TELEGRAM_MESSAGE_THREAD_ID is set to its placeholder. "
        "Messages will be sent to the main chat/group (if chat_id is configured)."
    )
    # TELEGRAM_MESSAGE_THREAD_ID remains None
# PROXY_URL = os.getenv('PROXY_URL', config_data["telegram"].get("proxy_url")) # Commented out to disable proxy
PROXY_URL = None # Explicitly disable proxy usage

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

def init_sqlite_db(db_path: str) -> bool:
    """Initializes the SQLite database and creates the table if it doesn't exist."""
    if not db_path:
        logger.warning("SQLite database path not configured. Database will not be initialized or used.")
        return False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trend_analysis (
                analysis_timestamp_utc TEXT,
                symbol TEXT,
                timeframe TEXT,
                price REAL,
                ema_fast_period INTEGER,
                ema_fast_value REAL,
                ema_medium_period INTEGER,
                ema_medium_value REAL,
                ema_slow_period INTEGER,
                ema_slow_value REAL,
                rsi_period INTEGER, -- Added RSI columns
                rsi_value REAL,     -- Added RSI columns
                trend TEXT,
                last_candle_open_time_utc TEXT,
                bb_lower REAL,      -- Bollinger Band Lower
                bb_middle REAL,     -- Bollinger Band Middle
                bb_upper REAL,      -- Bollinger Band Upper
                atr_value REAL,                 -- ATR Value
                proj_range_short_low REAL,      -- Projected Short-Term Range Low
                proj_range_short_high REAL,     -- Projected Short-Term Range High
                proj_range_long_low REAL,       -- Projected Long-Term Range Low
                proj_range_long_high REAL,      -- Projected Long-Term Range High
                entry_price REAL,               -- Entry Price for the signal
                stop_loss REAL,                 -- Stop Loss level
                take_profit_1 REAL,             -- Take Profit level 1
                take_profit_2 REAL,             -- Take Profit level 2
                take_profit_3 REAL              -- Take Profit level 3
            )
        ''')
        conn.commit()
        conn.close()
        logger.info(f"✅ Successfully initialized/verified SQLite database at {db_path}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize SQLite database at {db_path}: {e}")
        return False

def get_market_data(symbol: str, required_candles: int) -> pd.DataFrame:
    """
    Fetches a specific number of historical k-line (candle) data from Binance.
    :param symbol: The trading symbol (e.g., BTCUSDT).
    :param required_candles: The number of candles to fetch.
    :return: A pandas DataFrame with the market data, or an empty DataFrame on error.
    """
    if not binance_client:
        logger.error("Binance client not initialized or connection failed. Cannot fetch market data.")
        return pd.DataFrame()

    logger.info(f"Fetching {required_candles} candles of {TIMEFRAME} data for {symbol}...")
    try:
        # Fetch the most recent 'required_candles' klines. Max limit is 1000.
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=min(required_candles, 1000))
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

async def perform_analysis(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """Calculates EMAs and determines the trend."""
    if df.empty:
        logger.warning(f"Dataframe is empty for {symbol}, cannot perform analysis.")
        return None

    logger.info(f"Performing analysis for {symbol} with {len(df)} data points.")

    # Check for EMA data sufficiency
    if len(df) < EMA_SLOW: # This check is for EMA
        logger.warning(f"Not enough data ({len(df)} points) for {symbol} to calculate EMA_{EMA_SLOW}. Need at least {EMA_SLOW} points.")
        return None # Cannot proceed without EMAs
    
    if len(df) < RSI_PERIOD + 1: # Check for RSI, log warning if not enough, but proceed as RSI can be N/A
        logger.warning(f"Not enough data ({len(df)} points) for {symbol} to calculate RSI_{RSI_PERIOD}. Need at least {RSI_PERIOD + 1} points. RSI will be N/A.")

    # --- Calculate EMAs ---
    # Define EMA column names for clarity and reusability
    ema_fast_col_name = f'EMA_{EMA_FAST}'
    ema_medium_col_name = f'EMA_{EMA_MEDIUM}'
    ema_slow_col_name = f'EMA_{EMA_SLOW}'
    # Define RSI column name
    rsi_col_name = f'RSI_{RSI_PERIOD}'
    # Define Bollinger Bands column name prefix (pandas_ta will append period and std)
    bbands_lower_col_name = f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'
    bbands_middle_col_name = f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'
    bbands_upper_col_name = f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'
    # Define ATR column name
    atr_col_name = f'ATRr_{ATR_PERIOD}' # pandas_ta appends 'r' for RMA-based ATR


    df.ta.ema(length=EMA_FAST, append=True, col_names=(ema_fast_col_name,))
    df.ta.ema(length=EMA_MEDIUM, append=True, col_names=(ema_medium_col_name,))
    df.ta.ema(length=EMA_SLOW, append=True, col_names=(ema_slow_col_name,))

    # --- Calculate RSI ---
    df.ta.rsi(length=RSI_PERIOD, append=True, col_names=(rsi_col_name,))

    # --- Calculate Bollinger Bands ---
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)

    # --- Calculate ATR ---
    df.ta.atr(length=ATR_PERIOD, append=True, col_names=(atr_col_name,)) # ATR calculation

    # Get the last row AFTER all indicators are calculated and appended
    last_row = df.iloc[-1]
    price: Optional[float] = last_row.get('close')
    ema_fast_val: Optional[float] = last_row.get(ema_fast_col_name)
    ema_medium_val: Optional[float] = last_row.get(ema_medium_col_name)
    ema_slow_val: Optional[float] = last_row.get(ema_slow_col_name)
    rsi_val: Optional[float] = last_row.get(rsi_col_name)
    bb_lower_val: Optional[float] = last_row.get(bbands_lower_col_name)
    bb_middle_val: Optional[float] = last_row.get(bbands_middle_col_name)
    bb_upper_val: Optional[float] = last_row.get(bbands_upper_col_name)
    atr_val: Optional[float] = last_row.get(atr_col_name)

    # --- Interpret RSI ---
    rsi_interpretation = "N/A" # Default if RSI could not be calculated
    if pd.notna(rsi_val):
        if rsi_val >= RSI_OVERBOUGHT:
            rsi_interpretation = "Overbought"
        elif rsi_val <= RSI_OVERSOLD:
            rsi_interpretation = "Oversold"
        else:
            # RSI is a valid number and it's in the neutral zone
            rsi_interpretation = "Neutral"

    price_str = f"${price:,.2f}" if pd.notna(price) else "N/A"
    ema_fast_str = f"${ema_fast_val:,.2f}" if pd.notna(ema_fast_val) else "N/A"
    ema_medium_str = f"${ema_medium_val:,.2f}" if pd.notna(ema_medium_val) else "N/A"
    ema_slow_str = f"${ema_slow_val:,.2f}" if pd.notna(ema_slow_val) else "N/A"
    rsi_str = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
    bb_lower_str = f"${bb_lower_val:,.2f}" if pd.notna(bb_lower_val) else "N/A"
    bb_middle_str = f"${bb_middle_val:,.2f}" if pd.notna(bb_middle_val) else "N/A"
    bb_upper_str = f"${bb_upper_val:,.2f}" if pd.notna(bb_upper_val) else "N/A"
    atr_str = f"{atr_val:.4f}" if pd.notna(atr_val) else "N/A" # ATR might be small, more precision

    # Calculate projected ranges based on ATR
    proj_short_low_val, proj_short_high_val = None, None
    proj_long_low_val, proj_long_high_val = None, None

    if pd.notna(price) and pd.notna(atr_val):
        proj_short_low_val = price - (ATR_MULTIPLIER_SHORT * atr_val)
        proj_short_high_val = price + (ATR_MULTIPLIER_SHORT * atr_val)
        proj_long_low_val = price - (ATR_MULTIPLIER_LONG * atr_val)
        proj_long_high_val = price + (ATR_MULTIPLIER_LONG * atr_val)

    proj_short_range_str = f"${proj_short_low_val:,.2f} - ${proj_short_high_val:,.2f}" if proj_short_low_val is not None else "N/A"
    proj_long_range_str = f"${proj_long_low_val:,.2f} - ${proj_long_high_val:,.2f}" if proj_long_low_val is not None else "N/A"

    # --- Calculate TP/SL based on ATR if a strong trend is detected ---
    entry_price_val: Optional[float] = None
    sl_val: Optional[float] = None
    tp1_val: Optional[float] = None
    tp2_val: Optional[float] = None
    tp3_val: Optional[float] = None

    # Determine Trend based on EMAs (moved here to use for TP/SL calculation)
    trend = TREND_SIDEWAYS
    if all(pd.notna(val) for val in [price, ema_fast_val, ema_medium_val, ema_slow_val]):
        if price > ema_fast_val and ema_fast_val > ema_medium_val and ema_medium_val > ema_slow_val:
            trend = TREND_STRONG_BULLISH
        elif price > ema_fast_val and price > ema_medium_val and price > ema_slow_val: # General bullish conditions
            trend = TREND_BULLISH
        elif price < ema_fast_val and price < ema_medium_val and price < ema_slow_val: # General bearish conditions
            trend = TREND_BEARISH
        elif price < ema_fast_val and ema_fast_val < ema_medium_val and ema_medium_val < ema_slow_val:
            trend = TREND_STRONG_BEARISH

    
    current_time_utc = pd.to_datetime('now', utc=True)
    analysis_header_content = f" Analysis for {symbol} at {current_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} "
    logger.info(f"\n{'='*15}{analysis_header_content}{'='*15}") # Correctly uses the 'symbol' parameter
    logger.info(f"Current Price: {price_str}")
    logger.info(f"EMA {EMA_FAST:<{len(str(EMA_SLOW))}}:       {ema_fast_str}")
    logger.info(f"EMA {EMA_MEDIUM:<{len(str(EMA_SLOW))}}:     {ema_medium_str}")
    logger.info(f"EMA {EMA_SLOW:<{len(str(EMA_SLOW))}}:       {ema_slow_str}")
    logger.info(f"RSI {RSI_PERIOD:<{len(str(EMA_SLOW))}}:       {rsi_str} ({rsi_interpretation})") # Log RSI
    logger.info(f"BBands ({BBANDS_PERIOD},{BBANDS_STD_DEV}): Low: {bb_lower_str}, Mid: {bb_middle_str}, High: {bb_upper_str}")
    logger.info(f"ATR ({ATR_PERIOD}):        {atr_str}")
    logger.info(f"Proj. Range (Short, ATRx{ATR_MULTIPLIER_SHORT}): {proj_short_range_str}")
    logger.info(f"Proj. Range (Long, ATRx{ATR_MULTIPLIER_LONG}):  {proj_long_range_str}")

    if trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH] and pd.notna(price) and pd.notna(atr_val):
        entry_price_val = price # Current price is the entry price
        # TP levels are still based on entry price and ATR
        # New TP levels based on fixed percentage from entry price
        if trend == TREND_STRONG_BULLISH:
            # New SL: 10% below the short-term projected low
            if proj_short_low_val is not None:
                sl_val = proj_short_low_val * 0.90 
            # TP levels: +2%, +4%, +6% actual gain from entry price
            tp1_val = entry_price_val * (1 + 0.02)
            tp2_val = entry_price_val * (1 + 0.04)
            tp3_val = entry_price_val * (1 + 0.06)
        elif trend == TREND_STRONG_BEARISH:
            # New SL: 10% above the short-term projected high
            if proj_short_high_val is not None:
                sl_val = proj_short_high_val * 1.10
            # TP levels: -2%, -4%, -6% actual loss from entry price
            tp1_val = entry_price_val * (1 - 0.02)
            tp2_val = entry_price_val * (1 - 0.04)
            tp3_val = entry_price_val * (1 - 0.06)
        
        logger.info(f"Entry Price: ${entry_price_val:,.4f}")
        logger.info(f"SL: ${sl_val:,.4f}, TP1: ${tp1_val:,.4f}, TP2: ${tp2_val:,.4f}, TP3: ${tp3_val:,.4f}")
    else:
        # Log that TP/SL are not calculated if not a strong trend or data is missing
        logger.debug(f"TP/SL not calculated for {symbol}: Trend is '{trend}', Price is {'valid' if pd.notna(price) else 'N/A'}, ATR is {'valid' if pd.notna(atr_val) else 'N/A'}.")

    logger.info(f"Trend: {trend}")
    logger.info("=" * (30 + len(analysis_header_content)) + "\n") # Adjusted to match the actual logged header length)

    # Save to SQLite
    if SQLITE_DB_PATH:  # Make sure we have a DB path
        last_candle_open_time: Optional[pd.Timestamp] = last_row.name if pd.notna(last_row.name) else None
        data_to_save = {
            'symbol': symbol, # Include symbol in data_to_save dict
            'analysis_timestamp_utc': current_time_utc,
            'timeframe': TIMEFRAME,
            'price': price if pd.notna(price) else None,
            'ema_fast_val': ema_fast_val if pd.notna(ema_fast_val) else None,
            'ema_medium_val': ema_medium_val if pd.notna(ema_medium_val) else None,
            'ema_slow_val': ema_slow_val if pd.notna(ema_slow_val) else None,
            'rsi_val': rsi_val if pd.notna(rsi_val) else None, # Include RSI value
            'rsi_interpretation': rsi_interpretation, # Include RSI interpretation
            'trend': trend,
            'last_candle_open_time_utc': last_candle_open_time,
            'bb_lower': bb_lower_val if pd.notna(bb_lower_val) else None,
            'bb_middle': bb_middle_val if pd.notna(bb_middle_val) else None,
            'bb_upper': bb_upper_val if pd.notna(bb_upper_val) else None,
            'atr_value': atr_val if pd.notna(atr_val) else None,
            'proj_range_short_low': proj_short_low_val,
            'proj_range_short_high': proj_short_high_val,
            'proj_range_long_low': proj_long_low_val,
            'proj_range_long_high': proj_long_high_val,
            'entry_price': entry_price_val,
            'stop_loss': sl_val,
            'take_profit_1': tp1_val,
            'take_profit_2': tp2_val,
            'take_profit_3': tp3_val,
        }
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()

            # Insert the analysis data
            cursor.execute('''
                INSERT INTO trend_analysis ( -- Updated INSERT statement
                    analysis_timestamp_utc, symbol, timeframe, price,
                    ema_fast_period, ema_fast_value,
                    ema_medium_period, ema_medium_value,
                    rsi_period, rsi_value, -- Added RSI columns
                    ema_slow_period, ema_slow_value, trend,
                    last_candle_open_time_utc, bb_lower, bb_middle, bb_upper, -- BBands
                    atr_value, proj_range_short_low, proj_range_short_high,   -- ATR & Proj Short
                    proj_range_long_low, proj_range_long_high,                -- Proj Long
                    entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3 -- TP/SL
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data_to_save['analysis_timestamp_utc'].isoformat(),  # Convert datetime to string for SQLite
                symbol,  # Include the symbol being analyzed
                data_to_save['timeframe'],
                data_to_save['price'],
                EMA_FAST, data_to_save['ema_fast_val'],
                EMA_MEDIUM, data_to_save['ema_medium_val'],
                # Correct order and values for ema_slow and rsi
                EMA_SLOW, data_to_save['ema_slow_val'], # ema_slow_period, ema_slow_value
                RSI_PERIOD, data_to_save['rsi_val'],    # rsi_period, rsi_value
                data_to_save['trend'],
                data_to_save['last_candle_open_time_utc'].isoformat() if data_to_save['last_candle_open_time_utc'] else None,  # Convert datetime to string
                data_to_save['bb_lower'],
                data_to_save['bb_middle'],
                data_to_save['bb_upper'],
                data_to_save['atr_value'],
                data_to_save['proj_range_short_low'],
                data_to_save['proj_range_short_high'],
                data_to_save['proj_range_long_low'],
                data_to_save['proj_range_long_high'],
                data_to_save['entry_price'],
                data_to_save['stop_loss'],
                data_to_save['take_profit_1'],
                data_to_save['take_profit_2'],
                data_to_save['take_profit_3']
            ))

            conn.commit()
            conn.close()
            logger.info(f"✅ Successfully saved analysis to SQLite for {symbol} at {SQLITE_DB_PATH}.")

        except sqlite3.Error as e:  # Catch SQLite-specific errors
            logger.error(f"Failed to save data to SQLite: {e}")

    else:
        logger.warning("SQLite database path not configured. Data will not be saved.")
    
    return data_to_save # Return the analysis results

async def main():
    """Main asynchronous function to run the bot."""
    logger.info("--- Starting Real-Time Market Analysis Bot ---")
    
    # Check if at least Binance or Telegram is configured
    binance_configured = binance_client is not None
    telegram_configured = TELEGRAM_BOT_TOKEN != TELEGRAM_BOT_TOKEN_PLACEHOLDER and TELEGRAM_CHAT_ID != TELEGRAM_CHAT_ID_PLACEHOLDER
    if not (binance_configured or telegram_configured): # Check if at least one service is configured
        logger.critical("Neither Binance nor Telegram services are properly configured. The script may not perform any useful actions.")
        # sys.exit("Exiting due to lack of service configurations.") # Optional: exit if no services configured
    
    # Initialize SQLite DB
    init_sqlite_db(SQLITE_DB_PATH)

    # Prepare display strings for Telegram startup message
    MAX_SYMBOLS_TO_DISPLAY_IN_STARTUP = 3
    if SYMBOLS:
        if len(SYMBOLS) > MAX_SYMBOLS_TO_DISPLAY_IN_STARTUP:
            displayed_symbols_list = ", ".join(SYMBOLS[:MAX_SYMBOLS_TO_DISPLAY_IN_STARTUP])
            symbols_display_str = f"{displayed_symbols_list} (+{len(SYMBOLS) - MAX_SYMBOLS_TO_DISPLAY_IN_STARTUP} more)"
        else:
            symbols_display_str = ", ".join(SYMBOLS)
    else:
        symbols_display_str = "N/A"

    def format_seconds_for_display(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours}h"
    loop_interval_display_str = format_seconds_for_display(LOOP_SLEEP_INTERVAL_SECONDS)

    # Initialize Telegram bot using the new handler
    telegram_bot_initialized = await telegram_handler.init_telegram_bot( # Added await
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID, # Pass the topic ID for startup message
        proxy_url=PROXY_URL,
        symbols_display=symbols_display_str,
        timeframe_display=TIMEFRAME,
        loop_interval_display=loop_interval_display_str
    )
    
    if not telegram_bot_initialized and TELEGRAM_BOT_TOKEN != TELEGRAM_BOT_TOKEN_PLACEHOLDER:
        logger.critical("Failed to initialize Telegram Bot. Exiting as Telegram notifications are configured but could not be started.")
        sys.exit("Exiting due to Telegram initialization failure.")

    if not SYMBOLS:
        logger.error("No trading symbols configured. Please check your config.json or TRADING_SYMBOLS environment variable.")
        sys.exit("Exiting due to no symbols configured.")

    # --- Pre-load initial data ---
    logger.info("--- Pre-loading initial market data (300 points per symbol) ---")
    all_symbols_preloaded_successfully = True
    for symbol_to_preload in SYMBOLS:
        logger.info(f"Pre-loading 300 data points for {symbol_to_preload}...")
        pre_load_df = get_market_data(symbol_to_preload, required_candles=PRE_LOAD_CANDLE_COUNT)
        if pre_load_df.empty or len(pre_load_df) < PRE_LOAD_CANDLE_COUNT:
            logger.warning(f"Failed to pre-load sufficient data ({PRE_LOAD_CANDLE_COUNT} points) for {symbol_to_preload}. Found {len(pre_load_df)} points.")
            all_symbols_preloaded_successfully = False
        else:
            logger.info(f"✅ Successfully pre-loaded {len(pre_load_df)} points for {symbol_to_preload}.")
    
    if not all_symbols_preloaded_successfully:
        logger.warning("One or more symbols failed to pre-load sufficient initial data. Analysis may be affected for these symbols initially.")
    else:
        logger.info("--- All symbols successfully pre-loaded with initial data ---")

    logger.info(f"--- Analysis loop starting for symbols: {', '.join(SYMBOLS)} ({TIMEFRAME}) every {LOOP_SLEEP_INTERVAL_SECONDS}s ---")
    logger.info("Press CTRL+C to stop.")
    
    cycle_count = 0
    # Determine the number of candles needed for analysis based on the slowest EMA + a buffer
    REQUIRED_CANDLES_FOR_ANALYSIS = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    while True:

        cycle_count += 1
        logger.info(f"--- Cycle {cycle_count} ({pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}) ---")
        cycle_analysis_results = [] # Initialize for each cycle
        try:
            for symbol_to_analyze in SYMBOLS:
                logger.info(f"--- Analyzing {symbol_to_analyze} ---")
                # Fetch data - get_market_data is synchronous
                market_data_df = get_market_data(symbol_to_analyze, required_candles=REQUIRED_CANDLES_FOR_ANALYSIS + max(RSI_PERIOD, ATR_PERIOD)) # Fetch enough data for RSI/ATR

                if not market_data_df.empty:
                    # Perform analysis and get results - perform_analysis is async now
                    analysis_result = await perform_analysis(market_data_df, symbol_to_analyze)
                    if analysis_result: # Check if analysis was successful and returned data
                        cycle_analysis_results.append(analysis_result)
                else:
                    logger.warning(f"Skipping analysis for {symbol_to_analyze} due to empty market data.")

            # --- Prepare lists for different notification types ---
            # strong_trend_results_for_summary = [] # No longer sending summaries
            individual_alerts_to_send_details = []
            
            for result in cycle_analysis_results:
                trend = result['trend']
                if trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                    # Only send individual detailed alerts for strong trends
                    individual_alerts_to_send_details.append(result)
                # Regular TREND_BULLISH and TREND_BEARISH will no longer trigger notifications

            # --- Send All Notifications for the current cycle ---
            # The strong trend summary notification is removed as per the request to "only notify strong next trend"
            # with the detailed individual format.

            for analysis_detail in individual_alerts_to_send_details:
                await notifications.send_individual_trend_alert_notification(
                    chat_id=TELEGRAM_CHAT_ID,
                    # Pass the configured topic ID to the notification function
                    message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                    analysis_result=analysis_detail, # This now includes BBands
                    bbands_period_const=BBANDS_PERIOD, # Pass BBands period
                    atr_period_const=ATR_PERIOD, # Pass ATR period
                    bbands_std_dev_const=BBANDS_STD_DEV, # Pass BBands std dev
                    rsi_period_const=RSI_PERIOD, ema_fast_const=EMA_FAST,
                    ema_medium_const=EMA_MEDIUM, ema_slow_const=EMA_SLOW
                )

            logger.info(f"--- Cycle {cycle_count} complete. Waiting for {LOOP_SLEEP_INTERVAL_SECONDS} seconds... ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS) # Use asyncio.sleep in async code
        except KeyboardInterrupt:
            logger.info("🛑 Analysis stopped by user. Shutting down...")
            await notifications.send_shutdown_notification(
                chat_id=TELEGRAM_CHAT_ID,
                # Pass the configured topic ID to the notification function
                message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                symbols_list=SYMBOLS
            )
            break
        except Exception as e:
            logger.exception("An unexpected error occurred in the main loop:") # logger.exception automatically includes traceback
            logger.info(f"Retrying in {LOOP_SLEEP_INTERVAL_SECONDS} seconds...")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS) # Use asyncio.sleep in async code
    
    logger.info("--- Bot shutdown complete. ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during script execution: {e}", exc_info=True)