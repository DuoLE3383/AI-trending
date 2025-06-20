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
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TREND_STRONG_BULLISH = " 🚨 #StrongBullish LONG 📈"
TREND_STRONG_BEARISH = "🚨 #StrongBearish SHORT 📉"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_SIDEWAYS = "Sideways/Undetermined"
PRE_LOAD_CANDLE_COUNT = 300
ANALYSIS_CANDLE_BUFFER = 200
RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD = 14, 70, 30
BBANDS_PERIOD, BBANDS_STD_DEV = 20, 2.0
ATR_PERIOD, ATR_MULTIPLIER_SHORT, ATR_MULTIPLIER_LONG = 14, 1.5, 1.5
ATR_MULTIPLIER_SL, ATR_MULTIPLIER_TP1, ATR_MULTIPLIER_TP2, ATR_MULTIPLIER_TP3 = 1.2, 1.3, 2.3, 3.2

# --- Logging & Config ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "binance": {},
    "trading": {
        "symbols": ["BTCUSDT"],
        "timeframe": "15m",
        "ema_fast": 34,
        "ema_medium": 89,
        "ema_slow": 200,
        "loop_sleep_interval_seconds": 3600,
        "periodic_notification_interval_seconds": 600
    },
    "dynamic_symbols": {
        "enabled": True,
        "quote_asset": "USDT",
        "update_interval_hours": 24,
        "exclude_substrings": ["UP", "DOWN", "BULL", "BEAR"]
    },
    "sqlite": {
        "db_path": "trend_analysis.db"
    },
    "telegram": {}
}

def load_config(config_path="config.json"):
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
        for section, settings in file_config.items():
            if section in config:
                config[section].update(settings)
    except Exception as e:
        logger.warning(f"Could not load config.json, using default settings. Error: {e}")
    return config

config_data = load_config()

# --- Load All Configuration Variables ---
API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"].get("api_key_placeholder"))
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"].get("api_secret_placeholder"))
STATIC_SYMBOLS = config_data["trading"]["symbols"]
TIMEFRAME = config_data["trading"]["timeframe"]
EMA_FAST, EMA_MEDIUM, EMA_SLOW = int(config_data["trading"]["ema_fast"]), int(config_data["trading"]["ema_medium"]), int(config_data["trading"]["ema_slow"])
SQLITE_DB_PATH = config_data["sqlite"]["db_path"]
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"].get("bot_token_placeholder"))
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"].get("chat_id_placeholder"))
TELEGRAM_MESSAGE_THREAD_ID: Optional[int] = None # Or load from config if you use it

LOOP_SLEEP_INTERVAL_SECONDS = int(config_data["trading"]["loop_sleep_interval_seconds"])
SIGNAL_CHECK_INTERVAL_SECONDS = int(config_data["trading"]["periodic_notification_interval_seconds"])
DYN_SYMBOLS_ENABLED = config_data["dynamic_symbols"]["enabled"]
DYN_SYMBOLS_QUOTE_ASSET = config_data["dynamic_symbols"]["quote_asset"]
DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS = config_data["dynamic_symbols"]["update_interval_hours"] * 3600
DYN_SYMBOLS_EXCLUDE = config_data["dynamic_symbols"]["exclude_substrings"]

# Initialize Binance Client
# Check if API_KEY and API_SECRET are actual values before initializing client
if API_KEY and API_KEY != API_KEY_PLACEHOLDER and API_SECRET and API_SECRET != API_SECRET_PLACEHOLDER:
    binance_client = Client(API_KEY, API_SECRET)
    logger.info("Binance client initialized with API keys.")
else:
    binance_client = None
    logger.warning("Binance API Key or Secret is missing/placeholder. Binance client not initialized. Market data fetching will not work.")


# --- COMPLETE CORE FUNCTIONS ---

def init_sqlite_db(db_path: str):
    """Initializes the SQLite database and creates the table with all 27 columns."""
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trend_analysis (
                analysis_timestamp_utc TEXT, symbol TEXT, timeframe TEXT, price REAL,
                ema_fast_period INTEGER, ema_fast_value REAL, ema_medium_period INTEGER, ema_medium_value REAL,
                ema_slow_period INTEGER, ema_slow_value REAL, rsi_period INTEGER, rsi_value REAL, trend TEXT,
                last_candle_open_time_utc TEXT, bb_lower REAL, bb_middle REAL, bb_upper REAL, atr_value REAL,
                proj_range_short_low REAL, proj_range_short_high REAL, proj_range_long_low REAL, proj_range_long_high REAL,
                entry_price REAL, stop_loss REAL, take_profit_1 REAL, take_profit_2 REAL, take_profit_3 REAL
            )
        ''')
    logger.info(f"✅ DB initialized at {db_path}")

def get_market_data(symbol: str) -> pd.DataFrame:
    """Fetches and prepares market data for a single symbol."""
    if not binance_client:
        logger.error("Binance client not initialized. Cannot fetch market data.")
        return pd.DataFrame()

    # Calculate the exact limit needed based on EMA_SLOW and ANALYSIS_CANDLE_BUFFER
    # Max limit for get_historical_klines is typically 1000.
    required_candles = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    limit = min(required_candles, 1000)

    try:
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=limit)
        if not klines:
            logger.warning(f"No klines data received for {symbol} with limit {limit}.")
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

        # Ensure we have enough data after conversion
        if len(df) < EMA_SLOW:
            logger.warning(f"Not enough data for {symbol} ({len(df)} candles) after fetching to calculate all EMAs (need {EMA_SLOW}).")
            return pd.DataFrame()

        return df

    except BinanceAPIException as e:
        logger.error(f"Binance API error fetching data for {symbol}: {e}")
    except BinanceRequestException as e:
        logger.error(f"Binance request error fetching data for {symbol}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching market data for {symbol}: {e}", exc_info=True)
    return pd.DataFrame()


async def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """Calculates all indicators and saves the complete record to the database."""
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points ({len(df)} candles, need at least {EMA_SLOW}).")
        return

    # Calculate Indicators
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)

    # Ensure all calculated columns exist before trying to access them
    required_cols = [
        f'EMA_{EMA_FAST}', f'EMA_{EMA_MEDIUM}', f'EMA_{EMA_SLOW}',
        f'RSI_{RSI_PERIOD}', f'ATRr_{ATR_PERIOD}',
        f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'
    ]
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Missing one or more calculated indicator columns for {symbol}. Skipping analysis for this candle.")
        return

    last = df.iloc[-1]
    price = last.get('close')
    ema_f, ema_m, ema_s = last.get(f'EMA_{EMA_FAST}'), last.get(f'EMA_{EMA_MEDIUM}'), last.get(f'EMA_{EMA_SLOW}')
    rsi, atr = last.get(f'RSI_{RSI_PERIOD}'), last.get(f'ATRr_{ATR_PERIOD}')
    bb_l, bb_m, bb_u = last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')

    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None

    # Check for NaN values in core indicators before trend calculation
    if not all(pd.notna(v) for v in [price, ema_f, ema_m, ema_s, atr]):
        logger.warning(f"Skipping trend calculation for {symbol} due to NaN indicator values (price={price}, ema_f={ema_f}, ema_m={ema_m}, ema_s={ema_s}, atr={atr}).")
        # Proceed to save to DB with whatever values are available, or skip completely
        # For now, we'll continue, but without trend/entry/SL/TP if core values are NaN
    else:
        # Trend and Trade Signal Logic
        if price > ema_f and ema_f > ema_m and ema_m > ema_s: # Strong Bullish
            trend, entry = TREND_STRONG_BULLISH, price
            sl = entry * (1 - ATR_MULTIPLIER_SL * atr / price) # Stop Loss is below entry for long
            tp1 = entry * (1 + ATR_MULTIPLIER_TP1 * atr / price)
            tp2 = entry * (1 + ATR_MULTIPLIER_TP2 * atr / price)
            tp3 = entry * (1 + ATR_MULTIPLIER_TP3 * atr / price)
        elif price < ema_f and ema_f < ema_m and ema_m < ema_s: # Strong Bearish
            trend, entry = TREND_STRONG_BEARISH, price
            sl = entry * (1 + ATR_MULTIPLIER_SL * atr / price) # Stop Loss is above entry for short
            tp1 = entry * (1 - ATR_MULTIPLIER_TP1 * atr / price)
            tp2 = entry * (1 - ATR_MULTIPLIER_TP2 * atr / price)
            tp3 = entry * (1 - ATR_MULTIPLIER_TP3 * atr / price)
        elif price > ema_s and price > ema_m: # Bullish
            trend = TREND_BULLISH
        elif price < ema_s and price < ema_m: # Bearish
            trend = TREND_BEARISH

    p_s_l, p_s_h = (price - ATR_MULTIPLIER_SHORT * atr, price + ATR_MULTIPLIER_SHORT * atr) if pd.notna(atr) and pd.notna(price) else (None, None)
    p_l_l, p_l_h = (price - ATR_MULTIPLIER_LONG * atr, price + ATR_MULTIPLIER_LONG * atr) if pd.notna(atr) and pd.notna(price) else (None, None)

    db_values = (
        pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
        EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, rsi, trend,
        last.name.isoformat(), bb_l, bb_m, bb_u, atr, p_s_l, p_s_h, p_l_l, p_l_h,
        entry, sl, tp1, tp2, tp3
    )
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute("INSERT INTO trend_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", db_values)
        logger.info(f"💾 Analysis saved for {symbol} ({TIMEFRAME}): Trend={trend}")
    except sqlite3.Error as e:
        logger.error(f"Error saving analysis for {symbol} to DB: {e}", exc_info=True)


def fetch_and_filter_binance_symbols() -> Set[str]:
    """Fetches and filters symbols from Binance based on config."""
    if not binance_client:
        logger.error("Binance client not initialized. Cannot fetch symbols.")
        return set()
    logger.info(f"Fetching symbols for quote asset: {DYN_SYMBOLS_QUOTE_ASSET}")
    try:
        # Get all symbols with TRADING status
        exchange_info = binance_client.get_exchange_info()
        all_symbols = {s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING'}

        # Filter by quote asset (e.g., USDT)
        filtered_by_quote = {s for s in all_symbols if s.endswith(DYN_SYMBOLS_QUOTE_ASSET)}

        # Exclude symbols based on substrings
        final_symbols = {s for s in filtered_by_quote if not any(ex in s for ex in DYN_SYMBOLS_EXCLUDE)}

        logger.info(f"Found {len(final_symbols)} symbols to monitor (after filtering).")
        return final_symbols
    except Exception as e:
        logger.error(f"Failed to fetch or filter symbols from Binance: {e}", exc_info=True)
        return set()

# --- MAIN LOOPS & EXECUTION ---

async def analysis_loop(monitored_symbols_ref: Dict[str, Set]):
    """LOOP 1 (HOURLY): The Data Collector."""
    logger.info(f"--- ✅ Analysis Loop starting (interval: {LOOP_SLEEP_INTERVAL_SECONDS / 60:.0f} minutes) ---")
    last_symbol_update_time = 0
    while True:
        try:
            current_time = time.time()
            if DYN_SYMBOLS_ENABLED and (current_time - last_symbol_update_time > DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS):
                logger.info("--- Updating symbol list from Binance ---")
                dynamic_symbols = fetch_and_filter_binance_symbols()
                if dynamic_symbols:
                    # Update the set of symbols. Use .update() to add new ones, existing ones stay.
                    monitored_symbols_ref['symbols'].update(dynamic_symbols)
                    logger.info(f"--- Symbol list updated. Now monitoring {len(monitored_symbols_ref['symbols'])} symbols. ---")
                last_symbol_update_time = current_time
            else:
                if DYN_SYMBOLS_ENABLED:
                    logger.info(f"--- Next dynamic symbol update in {int((last_symbol_update_time + DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS - current_time)/3600)} hours ---")


            logger.info(f"--- Starting analysis cycle for {len(monitored_symbols_ref['symbols'])} symbols ---")
            # Convert set to list for iteration to avoid "set changed size during iteration" if updated mid-loop
            for symbol in list(monitored_symbols_ref['symbols']):
                try:
                    market_data = get_market_data(symbol)
                    if not market_data.empty:
                        await perform_analysis(market_data, symbol)
                    else:
                        logger.warning(f"No valid market data to analyze for {symbol}. Skipping.")
                except Exception as symbol_error:
                    logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {symbol_error}", exc_info=True)

            logger.info("--- Analysis cycle complete. ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("❌ A critical error occurred in analysis_loop. Restarting in 60 seconds...")
            await asyncio.sleep(60)

async def signal_check_loop():
    """LOOP 2 (10 MINUTES): The Signal Notifier."""
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal: Dict[str, str] = {} # Store symbol -> last_notified_timestamp_utc
    await asyncio.sleep(SIGNAL_CHECK_INTERVAL_SECONDS / 2) # Offset from analysis loop start

    while True:
        try:
            # Connect in read-only mode for safety
            with sqlite3.connect(f'file:{SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row # Allows accessing columns by name
                query = "SELECT * FROM trend_analysis WHERE rowid IN (SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol)"
                latest_records = conn.execute(query).fetchall()

            for record in latest_records:
                symbol, trend, timestamp = record['symbol'], record['trend'], record['analysis_timestamp_utc']
                
                # Only notify for strong signals and if the signal is newer than the last notification
                if trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                    # Using ISO format for comparison, so direct string comparison works for timestamps
                    if timestamp > last_notified_signal.get(symbol, ''):
                        logger.info(f"🔥 New signal for {symbol}! Trend: {trend}. Notifying...")
                        
                        # Convert sqlite3.Row to dict for easier passing
                        analysis_result_dict = dict(record)

                        await notifications.send_individual_trend_alert_notification(
                            bot_token=TELEGRAM_BOT_TOKEN,
                            chat_id=TELEGRAM_CHAT_ID,
                            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                            analysis_result=analysis_result_dict,
                            bbands_period_const=BBANDS_PERIOD,
                            bbands_std_dev_const=BBANDS_STD_DEV,
                            atr_period_const=ATR_PERIOD,
                            rsi_period_const=RSI_PERIOD,
                            ema_fast_const=EMA_FAST,
                            ema_medium_const=EMA_MEDIUM,
                            ema_slow_const=EMA_SLOW
                        )
                        last_notified_signal[symbol] = timestamp
                    else:
                        logger.debug(f"Signal for {symbol} ({trend}) already notified or older than last check.")
                else:
                    logger.debug(f"Current trend for {symbol} is {trend}, not a strong signal for notification.")

        except Exception as e:
            logger.exception("❌ Error in signal_check_loop. Will retry in next interval.")
        await asyncio.sleep(SIGNAL_CHECK_INTERVAL_SECONDS)

async def main():
    """Initializes and runs the bot's concurrent loops."""
    logger.info("--- Initializing Bot ---")

    # Check for Binance client initialization
    if not binance_client:
        logger.critical("Binance client not initialized. Cannot fetch market data. Exiting.")
        sys.exit(1)
    
    # Check for Telegram credentials
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == TELEGRAM_BOT_TOKEN_PLACEHOLDER or \
       not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.critical("Telegram BOT_TOKEN or CHAT_ID is missing or is a placeholder. Please set environment variables or update config.json. Exiting.")
        sys.exit(1)

    init_sqlite_db(SQLITE_DB_PATH)
    
    monitored_symbols_ref = {'symbols': set(STATIC_SYMBOLS)}

    # Attempt to send startup notification
    try:
        initial_symbols_display = "dynamic (fetching from Binance)" if DYN_SYMBOLS_ENABLED else "static list"
        await notifications.send_startup_message(
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
            symbols_display=initial_symbols_display, # Reflect if dynamic is enabled
            timeframe_display=TIMEFRAME,
            loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS//60}m, Signal Check: {SIGNAL_CHECK_INTERVAL_SECONDS//60}m"
        )
    except Exception as e:
        logger.critical(f"Failed to send Telegram startup message: {e}. Exiting."), sys.exit(1)

    logger.info("--- Bot is now running. Analysis and Signal loops are active. ---")
    
    # Create and run concurrent tasks
    analysis_task = asyncio.create_task(analysis_loop(monitored_symbols_ref))
    signal_task = asyncio.create_task(signal_check_loop())
    
    await asyncio.gather(analysis_task, signal_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user via KeyboardInterrupt.")
    except Exception as e:
        logger.exception("An unhandled exception occurred in the main bot execution.")
    finally:
        logger.info("Bot application shutting down.")
        # Add any necessary cleanup here, e.g., closing database connections, client sessions.

