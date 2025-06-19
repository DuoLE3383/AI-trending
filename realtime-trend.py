from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

import pandas as pd
import pandas_ta as ta
from binance.client import Client
import os, sqlite3
from binance.exceptions import BinanceAPIException, BinanceRequestException
import sys
import logging, asyncio
import json
from typing import Optional, Any, Dict, List

# Local imports
import telegram_handler
import notifications

# --- Placeholder Constants ---
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER = 'YOUR_TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER'

# --- Analysis & Script Constants ---
PRE_LOAD_CANDLE_COUNT = 300
ANALYSIS_CANDLE_BUFFER = 200
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

# --- Configuration Loading ---
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
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Config file issue: {e}. Using default/env settings.")
    return config

config_data = load_config()

# --- Load Configuration from config/env ---
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
LOOP_SLEEP_INTERVAL_SECONDS = int(os.getenv('LOOP_SLEEP_INTERVAL_SECONDS', config_data["trading"]["loop_sleep_interval_seconds"]))
PERIODIC_NOTIFICATION_INTERVAL_SECONDS = int(os.getenv('PERIODIC_NOTIFICATION_INTERVAL_SECONDS', config_data["trading"]["periodic_notification_interval_seconds"]))

# --- Initialize Binance Client ---
binance_client: Optional[Client] = None
if API_KEY != API_KEY_PLACEHOLDER and API_SECRET != API_SECRET_PLACEHOLDER:
    try:
        binance_client = Client(API_KEY, API_SECRET)
        binance_client.get_server_time()
        logger.info("✅ Successfully connected to Binance.")
    except Exception as e:
        logger.error(f"Failed to connect to Binance: {e}")
        binance_client = None

# --- Database, Data Fetching, and Analysis Functions ---
# (These functions are assumed to be correct from previous steps)

def init_sqlite_db(db_path: str) -> bool:
    """Initializes the SQLite database and creates the table if it doesn't exist."""
    # (Your existing init_sqlite_db function here)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trend_analysis (
                analysis_timestamp_utc TEXT, symbol TEXT, timeframe TEXT, price REAL,
                ema_fast_period INTEGER, ema_fast_value REAL, ema_medium_period INTEGER, ema_medium_value REAL,
                ema_slow_period INTEGER, ema_slow_value REAL, rsi_period INTEGER, rsi_value REAL, trend TEXT,
                last_candle_open_time_utc TEXT, bb_lower REAL, bb_middle REAL, bb_upper REAL, atr_value REAL,
                proj_range_short_low REAL, proj_range_short_high REAL, proj_range_long_low REAL, proj_range_long_high REAL,
                entry_price REAL, stop_loss REAL, take_profit_1 REAL, take_profit_2 REAL, take_profit_3 REAL
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
    """Fetches historical k-line data from Binance."""
    # (Your existing get_market_data function here)
    if not binance_client:
        logger.error("Binance client not initialized. Cannot fetch market data.")
        return pd.DataFrame()
    try:
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=min(required_candles, 1000))
        if not klines: return pd.DataFrame()
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        return df
    except (BinanceAPIException, BinanceRequestException) as e:
        logger.error(f"Error fetching market data for {symbol}: {e}")
        return pd.DataFrame()


async def perform_analysis(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    """Calculates indicators and determines the trend."""
    # (Your existing perform_analysis function here, ensuring it saves to DB)
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Not enough data for {symbol} to perform full analysis.")
        return None
    
    # Calculate Indicators
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    
    last_row = df.iloc[-1]
    price = last_row.get('close')
    ema_fast_val = last_row.get(f'EMA_{EMA_FAST}')
    ema_medium_val = last_row.get(f'EMA_{EMA_MEDIUM}')
    ema_slow_val = last_row.get(f'EMA_{EMA_SLOW}')
    rsi_val = last_row.get(f'RSI_{RSI_PERIOD}')
    bb_lower_val = last_row.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')
    bb_middle_val = last_row.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')
    bb_upper_val = last_row.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')
    atr_val = last_row.get(f'ATRr_{ATR_PERIOD}')
    
    # Determine Trend
    trend = TREND_SIDEWAYS
    if all(pd.notna(val) for val in [price, ema_fast_val, ema_medium_val, ema_slow_val]):
        if price > ema_fast_val > ema_medium_val > ema_slow_val: trend = TREND_STRONG_BULLISH
        elif price < ema_fast_val < ema_medium_val < ema_slow_val: trend = TREND_STRONG_BEARISH
        elif price > ema_fast_val and price > ema_medium_val and price > ema_slow_val: trend = TREND_BULLISH
        elif price < ema_fast_val and price < ema_medium_val and price < ema_slow_val: trend = TREND_BEARISH
        
    # Build result dictionary
    analysis_result = {
        'symbol': symbol, 'timeframe': TIMEFRAME, 'price': price,
        'ema_fast_val': ema_fast_val, 'ema_medium_val': ema_medium_val, 'ema_slow_val': ema_slow_val,
        'rsi_val': rsi_val, 'rsi_interpretation': "Overbought" if rsi_val and rsi_val >= RSI_OVERBOUGHT else "Oversold" if rsi_val and rsi_val <= RSI_OVERSOLD else "Neutral",
        'trend': trend, 'bb_lower': bb_lower_val, 'bb_middle': bb_middle_val, 'bb_upper': bb_upper_val,
        'atr_value': atr_val,
        # ... (add TP/SL and other calculations here) ...
    }
    
    # Save to SQLite
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        # Your INSERT statement here...
        cursor.execute("INSERT INTO trend_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
                        EMA_FAST, ema_fast_val, EMA_MEDIUM, ema_medium_val, EMA_SLOW, ema_slow_val,
                        RSI_PERIOD, rsi_val, trend, last_row.name.isoformat(),
                        bb_lower_val, bb_middle_val, bb_upper_val, atr_val,
                        None, None, None, None, # Proj ranges
                        None, None, None, None, None)) # TP/SL
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to save data to SQLite for {symbol}: {e}")
        # Even if DB save fails, return result for potential alerting
    
    return analysis_result

# --- Main Application Loops ---

async def analysis_loop():
    """Main analysis loop: Fetches data, analyzes, saves to DB, and sends critical alerts."""
    logger.info(f"--- Analysis loop starting (interval: {LOOP_SLEEP_INTERVAL_SECONDS}s) ---")
    REQUIRED_CANDLES_FOR_ANALYSIS = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    while True:
        try:
            logger.info("--- Starting new analysis cycle ---")
            for symbol in SYMBOLS:
                market_data_df = get_market_data(symbol, required_candles=REQUIRED_CANDLES_FOR_ANALYSIS)
                if not market_data_df.empty:
                    analysis_result = await perform_analysis(market_data_df, symbol)
                    if analysis_result and analysis_result['trend'] in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                        await notifications.send_individual_trend_alert_notification(
                            chat_id=TELEGRAM_CHAT_ID,
                            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                            analysis_result=analysis_result,
                            bbands_period_const=BBANDS_PERIOD,
                            bbands_std_dev_const=BBANDS_STD_DEV,
                            atr_period_const=ATR_PERIOD,
                            rsi_period_const=RSI_PERIOD,
                            ema_fast_const=EMA_FAST,
                            ema_medium_const=EMA_MEDIUM,
                            ema_slow_const=EMA_SLOW
                        )
            logger.info(f"--- Analysis cycle complete. Waiting for {LOOP_SLEEP_INTERVAL_SECONDS} seconds... ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("An unexpected error occurred in the analysis_loop:")
            await asyncio.sleep(60) # Wait a minute before retrying on error

async def periodic_notification_loop():
    """Sends periodic summary notifications based on the latest DB data."""
    logger.info(f"--- Periodic Notification loop starting (interval: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS}s) ---")
    await asyncio.sleep(15) # Initial delay to allow first analysis to complete
    while True:
        try:
            await notifications.send_periodic_summary_notification(
                db_path=SQLITE_DB_PATH,
                symbols=SYMBOLS,
                timeframe=TIMEFRAME,
                chat_id=TELEGRAM_CHAT_ID,
                message_thread_id=TELEGRAM_MESSAGE_THREAD_ID
            )
            await asyncio.sleep(PERIODIC_NOTIFICATION_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("An unexpected error occurred in the periodic_notification_loop:")
            await asyncio.sleep(60)

async def main():
    """Initializes and runs the bot's concurrent tasks."""
    logger.info("--- Starting Real-Time Market Analysis Bot ---")
    
    init_sqlite_db(SQLITE_DB_PATH)
    
    # Initialize Telegram and send startup message
    telegram_bot_initialized = await telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID,
        message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID, proxy_url=None,
        symbols_display=", ".join(SYMBOLS), timeframe_display=TIMEFRAME,
        loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS}s, Summary: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS}s"
    )

    if not (telegram_bot_initialized and SYMBOLS):
        logger.critical("Failed to initialize Telegram or no symbols configured. Exiting.")
        sys.exit(1)

    # Pre-load data
    for symbol in SYMBOLS:
        get_market_data(symbol, PRE_LOAD_CANDLE_COUNT)
    
    # Create and run concurrent tasks
    analysis_task = asyncio.create_task(analysis_loop())
    notification_task = asyncio.create_task(periodic_notification_loop())
    logger.info("--- Bot is now running with concurrent analysis and notification loops. ---")
    
    try:
        await asyncio.gather(analysis_task, notification_task)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user.")
        analysis_task.cancel()
        notification_task.cancel()
        await notifications.send_shutdown_notification(TELEGRAM_CHAT_ID, TELEGRAM_MESSAGE_THREAD_ID, SYMBOLS)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
    logger.info("--- Bot shutdown complete. ---")
