from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import pandas_ta as ta
from binance.client import Client
import os, sqlite3
from binance.exceptions import BinanceAPIException, BinanceRequestException
import sys, logging, asyncio, json
from typing import Optional, Any, Dict, List

import telegram_handler
import notifications

# --- All Constants (remain the same) ---
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'
TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER = 'YOUR_TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER'
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

# --- Logging & Config Loading (remain the same) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = { "binance": {"api_key_placeholder": API_KEY_PLACEHOLDER, "api_secret_placeholder": API_SECRET_PLACEHOLDER}, "trading": {"symbols": ["BTCUSDT"], "timeframe": "15m", "ema_fast": 34, "ema_medium": 89, "ema_slow": 200, "loop_sleep_interval_seconds": 3600, "periodic_notification_interval_seconds": 600}, "sqlite": {"db_path": "trend_analysis.db"}, "telegram": {"bot_token_placeholder": TELEGRAM_BOT_TOKEN_PLACEHOLDER, "chat_id_placeholder": TELEGRAM_CHAT_ID_PLACEHOLDER, "proxy_url": None, "message_thread_id_placeholder": TELEGRAM_MESSAGE_THREAD_ID_PLACEHOLDER} }

def load_config(config_path="config.json"):
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            for section, settings in file_config.items():
                if section in config: config[section].update(settings)
    except Exception: pass
    return config

config_data = load_config()

# --- Load Configuration from config/env ---
API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"]["api_key_placeholder"])
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"]["api_secret_placeholder"])
SYMBOLS = [s.strip().upper() for s in os.getenv('TRADING_SYMBOLS', ",".join(config_data["trading"]["symbols"])).split(',') if s.strip()]
TIMEFRAME = os.getenv('TRADING_TIMEFRAME', config_data["trading"]["timeframe"])
EMA_FAST, EMA_MEDIUM, EMA_SLOW = int(os.getenv('EMA_FAST', config_data["trading"]["ema_fast"])), int(os.getenv('EMA_MEDIUM', config_data["trading"]["ema_medium"])), int(os.getenv('EMA_SLOW', config_data["trading"]["ema_slow"]))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", config_data["sqlite"]["db_path"])
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"]["bot_token_placeholder"])
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"]["chat_id_placeholder"])
raw_thread_id = os.getenv('TELEGRAM_MESSAGE_THREAD_ID', config_data["telegram"]["message_thread_id_placeholder"])
TELEGRAM_MESSAGE_THREAD_ID = int(raw_thread_id) if raw_thread_id and raw_thread_id.isdigit() else None
LOOP_SLEEP_INTERVAL_SECONDS = int(os.getenv('LOOP_SLEEP_INTERVAL_SECONDS', config_data["trading"]["loop_sleep_interval_seconds"]))
PERIODIC_NOTIFICATION_INTERVAL_SECONDS = int(os.getenv('PERIODIC_NOTIFICATION_INTERVAL_SECONDS', config_data["trading"]["periodic_notification_interval_seconds"]))

# --- Initialize Binance Client ---
binance_client = Client(API_KEY, API_SECRET) if API_KEY != API_KEY_PLACEHOLDER else None

# --- CORE FUNCTIONS ---

def init_sqlite_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trend_analysis (
                analysis_timestamp_utc TEXT, symbol TEXT, timeframe TEXT, price REAL,
                ema_fast_period INTEGER, ema_fast_value REAL, ema_medium_period INTEGER, ema_medium_value REAL,
                ema_slow_period INTEGER, ema_slow_value REAL, rsi_period INTEGER, rsi_value REAL, trend TEXT,
                last_candle_open_time_utc TEXT, bb_lower REAL, bb_middle REAL, bb_upper REAL, atr_value REAL,
                proj_range_short_low REAL, proj_range_short_high REAL, proj_range_long_low REAL, proj_range_long_high REAL,
                entry_price REAL, stop_loss REAL, take_profit_1 REAL, take_profit_2 REAL, take_profit_3 REAL
            )''')
    logger.info(f"✅ DB initialized at {db_path}")

def get_market_data(symbol: str, required_candles: int) -> pd.DataFrame:
    if not binance_client: return pd.DataFrame()
    try:
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=min(required_candles, 1000))
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']: df[col] = pd.to_numeric(df[col])
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

async def perform_analysis(df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
    if df.empty or len(df) < EMA_SLOW: return None
    
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

    # Determine Trend & Contrarian Signals
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

    # Projected Ranges
    p_s_l, p_s_h = (price - ATR_MULTIPLIER_SHORT * atr, price + ATR_MULTIPLIER_SHORT * atr) if atr else (None, None)
    p_l_l, p_l_h = (price - ATR_MULTIPLIER_LONG * atr, price + ATR_MULTIPLIER_LONG * atr) if atr else (None, None)

    # FIX: Ensure all 27 values are present for the database insert
    db_values = (
        pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
        EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, rsi, trend,
        last.name.isoformat(), bb_l, bb_m, bb_u, atr, p_s_l, p_s_h, p_l_l, p_l_h,
        entry, sl, tp1, tp2, tp3
    )

    with sqlite3.connect(SQLITE_DB_PATH) as conn:
        conn.execute("INSERT INTO trend_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", db_values)
    
    return {k: v for k, v in zip([c[0] for c in conn.execute("PRAGMA table_info(trend_analysis)")], db_values)}


# --- MAIN LOOPS & EXECUTION ---

async def analysis_loop():
    logger.info(f"--- Analysis loop starting (interval: {LOOP_SLEEP_INTERVAL_SECONDS}s) ---")
    while True:
        try:
            for symbol in SYMBOLS:
                market_data = get_market_data(symbol, EMA_SLOW + ANALYSIS_CANDLE_BUFFER)
                if not market_data.empty:
                    result = await perform_analysis(market_data, symbol)
                    if result and result.get('trend') in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
                        await notifications.send_individual_trend_alert_notification(
                            bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID, message_thread_id=TELEGRAM_MESSAGE_THREAD_ID,
                            analysis_result=result, bbands_period_const=BBANDS_PERIOD, bbands_std_dev_const=BBANDS_STD_DEV,
                            atr_period_const=ATR_PERIOD, rsi_period_const=RSI_PERIOD, ema_fast_const=EMA_FAST,
                            ema_medium_const=EMA_MEDIUM, ema_slow_const=EMA_SLOW
                        )
            await asyncio.sleep(LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("Error in analysis_loop")
            await asyncio.sleep(60)

async def periodic_notification_loop():
    logger.info(f"--- Periodic Notification loop starting (interval: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS}s) ---")
    await asyncio.sleep(20) # Initial delay
    while True:
        try:
            await notifications.send_periodic_summary_notification(
                bot_token=TELEGRAM_BOT_TOKEN, db_path=SQLITE_DB_PATH, symbols=SYMBOLS,
                timeframe=TIMEFRAME, chat_id=TELEGRAM_CHAT_ID, message_thread_id=TELEGRAM_MESSAGE_THREAD_ID
            )
            await asyncio.sleep(PERIODIC_NOTIFICATION_INTERVAL_SECONDS)
        except Exception:
            logger.exception("Error in periodic_notification_loop")
            await asyncio.sleep(60)

async def main():
    logger.info("--- Initializing Bot ---")
    if not binance_client:
        logger.critical("Binance client not initialized. Check API keys. Exiting.")
        sys.exit(1)
    
    init_sqlite_db(SQLITE_DB_PATH)
    
    if not await telegram_handler.init_telegram_bot(
        bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID, message_thread_id_for_startup=TELEGRAM_MESSAGE_THREAD_ID,
        symbols_display=", ".join(SYMBOLS), timeframe_display=TIMEFRAME,
        loop_interval_display=f"Analysis: {LOOP_SLEEP_INTERVAL_SECONDS//60}m, Summary: {PERIODIC_NOTIFICATION_INTERVAL_SECONDS//60}m"
    ):
        logger.critical("Failed to send Telegram startup message. Check token/chat_id. Exiting.")
        sys.exit(1)
    
    logger.info("--- Bot is now running with concurrent loops. ---")
    analysis_task = asyncio.create_task(analysis_loop())
    notification_task = asyncio.create_task(periodic_notification_loop())
    await asyncio.gather(analysis_task, notification_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        asyncio.run(telegram_handler.close_session())
        logger.info("--- Bot shutdown complete. ---")

