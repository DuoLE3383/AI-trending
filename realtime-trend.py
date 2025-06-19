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

DEFAULT_CONFIG = { "binance": {}, "trading": {"symbols": ["BTCUSDT"], "timeframe": "15m", "ema_fast": 34, "ema_medium": 89, "ema_slow": 200, "loop_sleep_interval_seconds": 3600, "periodic_notification_interval_seconds": 600}, "dynamic_symbols": {"enabled": True, "quote_asset": "USDT", "update_interval_hours": 24, "exclude_substrings": ["UP", "DOWN", "BULL", "BEAR"]}, "sqlite": {"db_path": "trend_analysis.db"}, "telegram": {} }

def load_config(config_path="config.json"):
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f: file_config = json.load(f)
        for section, settings in file_config.items():
            if section in config: config[section].update(settings)
    except Exception: pass
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
TELEGRAM_MESSAGE_THREAD_ID = None
LOOP_SLEEP_INTERVAL_SECONDS = int(config_data["trading"]["loop_sleep_interval_seconds"])
SIGNAL_CHECK_INTERVAL_SECONDS = int(config_data["trading"]["periodic_notification_interval_seconds"])
DYN_SYMBOLS_ENABLED = config_data["dynamic_symbols"]["enabled"]
DYN_SYMBOLS_QUOTE_ASSET = config_data["dynamic_symbols"]["quote_asset"]
DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS = config_data["dynamic_symbols"]["update_interval_hours"] * 3600
DYN_SYMBOLS_EXCLUDE = config_data["dynamic_symbols"]["exclude_substrings"]

# Initialize Binance Client
binance_client = Client(API_KEY, API_SECRET) if API_KEY and API_KEY != API_KEY_PLACEHOLDER else None

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
    if not binance_client: return pd.DataFrame()
    required_candles = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=min(required_candles, 1000))
    if not klines: return pd.DataFrame()
    
    df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
    return df

async def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """Calculates all indicators and saves the complete record to the database."""
    if df.empty or len(df) < EMA_SLOW: return
    
    # Calculate Indicators
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    
    last = df.iloc[-1]
    price = last.get('close')
    ema_f, ema_m, ema_s = last.get(f'EMA_{EMA_FAST}'), last.get(f'EMA_{EMA_MEDIUM}'), last.get(f'EMA_{EMA_SLOW}')
    rsi, atr = last.get(f'RSI_{RSI_PERIOD}'), last.get(f'ATRr_{ATR_PERIOD}')
    bb_l, bb_m, bb_u = last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')

    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None
    if all(pd.notna(v) for v in [price, ema_f, ema_m, ema_s, atr]):
        if price > ema_f > ema_m > ema_s:
            trend, entry = TREND_STRONG_BULLISH, price
            sl, tp1, tp2, tp3 = entry * (1 + ATR_MULTIPLIER_SL * atr / price), entry * (1 - ATR_MULTIPLIER_TP1 * atr / price), entry * (1 - ATR_MULTIPLIER_TP2 * atr / price), entry * (1 - ATR_MULTIPLIER_TP3 * atr / price)
        elif price < ema_f < ema_m < ema_s:
            trend, entry = TREND_STRONG_BEARISH, price
            sl, tp1, tp2, tp3 = entry * (1 - ATR_MULTIPLIER_SL * atr / price), entry * (1 + ATR_MULTIPLIER_TP1 * atr / price), entry * (1 + ATR_MULTIPLIER_TP2 * atr / price), entry * (1 + ATR_MULTIPLIER_TP3 * atr / price)
        elif price > ema_s and price > ema_m: trend = TREND_BULLISH
        elif price < ema_s and price < ema_m: trend = TREND_BEARISH

    p_s_l, p_s_h = (price - ATR_MULTIPLIER_SHORT * atr, price + ATR_MULTIPLIER_SHORT * atr) if atr else (None, None)
    p_l_l, p_l_h = (price - ATR_MULTIPLIER_LONG * atr, price + ATR_MULTIPLIER_LONG * atr) if atr else (None, None)

    db_values = (
        pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
        EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, rsi, trend,
        last.name.isoformat(), bb_l, bb_m, bb_u, atr, p_s_l, p_s_h, p_l_l, p_l_h,
        entry, sl, tp1, tp2, tp3
    )
    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.execute("INSERT INTO trend_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", db_values)

def fetch_and_filter_binance_symbols() -> Set[str]:
    """Fetches and filters symbols from Binance based on config."""
    if not binance_client: return set()
    logger.info(f"Fetching symbols for quote asset: {DYN_SYMBOLS_QUOTE_ASSET}")
    try:
        all_symbols = {s['symbol'] for s in binance_client.get_exchange_info()['symbols'] if s['status'] == 'TRADING'}
        filtered = {s for s in all_symbols if s.endswith(DYN_SYMBOLS_QUOTE_ASSET)}
        final_symbols = {s for s in filtered if not any(ex in s for ex in DYN_SYMBOLS_EXCLUDE)}
        logger.info(f"Found {len(final_symbols)} symbols to monitor.")
        return final_symbols
    except Exception as e:
        logger.error(f"Failed to fetch symbols: {e}")
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
                    monitored_symbols_ref['symbols'].update(dynamic_symbols)
                    logger.info(f"--- Symbol list updated. Now monitoring {len(monitored_symbols_ref['symbols'])} symbols. ---")
                last_symbol_update_time = current_time

            logger.info(f"--- Starting analysis cycle for {len(monitored_symbols_ref['symbols'])} symbols ---")
            for symbol in list(monitored_symbols_ref['symbols']):
                try:
                    market_data = get_market_data(symbol)
                    if not market_data.empty: await perform_analysis(market_data, symbol)
                except Exception as symbol_error:
                    logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {symbol_error}")
            
            logger.info("--- Analysis cycle complete. ---")
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("❌ A critical error occurred in analysis_loop")
            await asyncio.sleep(60)

async def signal_check_loop():
    """LOOP 2 (10 MINUTES): The Signal Notifier."""
    logger.info(f"--- ✅ Signal Check Loop starting (interval: {SIGNAL_CHECK_INTERVAL_SECONDS} seconds) ---")
    last_notified_signal = {}
    await asyncio.sleep(15)
    while True:
        try:
            with sqlite3.connect(f'file:{SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM trend_analysis WHERE rowid IN (SELECT MAX(rowid) FROM trend_analysis GROUP BY symbol)"
                latest_records = conn.execute(query).fetchall()

            for record in latest_records:
                symbol, trend, timestamp = record['symbol'], record['trend'], record['analysis_timestamp_utc']
                if trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH] and timestamp > last_notified_signal.get(symbol, ''):
                    logger.info(f"🔥 New signal for {symbol}! Trend: {trend}. Notifying...")
                    await notifications.send_individual_trend_alert_notification(
                        bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID, message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                        analysis_result=dict(record), bbands_period_const=BBANDS_PERIOD, bbands_std_dev_const=BBANDS_STD_DEV,
                        atr_period_const=ATR_PERIOD, rsi_period_const=RSI_PERIOD, ema_fast_const=EMA_FAST,
                        ema_medium_const=EMA_MEDIUM, ema_slow_const=EMA_SLOW
                    )
                    last_notified_signal[symbol] = timestamp
        except Exception as e:
            logger.exception("❌ Error in signal_check_loop")
        await asyncio.sleep(SIGNAL_CHECK_INTERVAL_SECONDS)

async def main():
    """Initializes and runs the bot's concurrent loops."""
    logger.info("--- Initializing Bot ---")
    if not binance_client: logger.critical("Binance client not initialized. Exiting."), sys.exit(1)
    
    init_sqlite_db(SQLITE_DB_PATH)
    
    monitored_symbols_ref = {'symbols': set(STATIC_SYMBOLS)}

    if not await telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID,
        message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID, symbols_display="static list initially",
        timeframe_display=TIMEFRAME,
        loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS//60}m, Signal Check: {SIGNAL_CHECK_INTERVAL_SECONDS//60}m"
    ):
        logger.critical("Failed to send Telegram startup message. Exiting."), sys.exit(1)

    logger.info("--- Bot is now running. Analysis and Signal loops are active. ---")
    analysis_task = asyncio.create_task(analysis_loop(monitored_symbols_ref))
    signal_task = asyncio.create_task(signal_check_loop())
    await asyncio.gather(analysis_task, signal_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        asyncio.run(telegram_handler.close_session())
        logger.info("--- Bot shutdown complete. ---")
