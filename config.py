import os
import json
import logging

# --- Main Constants ---
TREND_STRONG_BULLISH = "🚨 #StrongBullish LONG 📈"
TREND_STRONG_BEARISH = "🚨 #StrongBearish SHORT 📉"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_SIDEWAYS = "Sideways/Undetermined"

# --- Placeholder Constants ---
API_KEY_PLACEHOLDER = 'YOUR_API_KEY_PLACEHOLDER'
API_SECRET_PLACEHOLDER = 'YOUR_API_SECRET_PLACEHOLDER'
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'

# --- Analysis Parameters ---
PRE_LOAD_CANDLE_COUNT = 300
ANALYSIS_CANDLE_BUFFER = 200
RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD = 14, 70, 30
BBANDS_PERIOD, BBANDS_STD_DEV = 20, 2.0
ATR_PERIOD, ATR_MULTIPLIER_SHORT, ATR_MULTIPLIER_LONG = 14, 1.5, 1.5
ATR_MULTIPLIER_SL, ATR_MULTIPLIER_TP1, ATR_MULTIPLIER_TP2, ATR_MULTIPLIER_TP3 = 1.2, 1.3, 2.3, 3.2

# --- Default Configuration Dictionary ---
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
    """Loads configuration from a file, using defaults as a fallback."""
    config = DEFAULT_CONFIG.copy()
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
        for section, settings in file_config.items():
            if section in config:
                config[section].update(settings)
    except Exception as e:
        logging.warning(f"Could not load config.json, using default settings. Error: {e}")
    return config

# --- Load All Configuration Variables on Import ---
config_data = load_config()

API_KEY = os.getenv('BINANCE_API_KEY', config_data["binance"].get("api_key"))
API_SECRET = os.getenv('BINANCE_API_SECRET', config_data["binance"].get("api_secret"))
STATIC_SYMBOLS = config_data["trading"]["symbols"]
TIMEFRAME = config_data["trading"]["timeframe"]
EMA_FAST = int(config_data["trading"]["ema_fast"])
EMA_MEDIUM = int(config_data["trading"]["ema_medium"])
EMA_SLOW = int(config_data["trading"]["ema_slow"])
SQLITE_DB_PATH = config_data["sqlite"]["db_path"]
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', config_data["telegram"].get("bot_token"))
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', config_data["telegram"].get("chat_id"))
TELEGRAM_MESSAGE_THREAD_ID = config_data["telegram"].get("message_thread_id")

LOOP_SLEEP_INTERVAL_SECONDS = int(config_data["trading"]["loop_sleep_interval_seconds"])
SIGNAL_CHECK_INTERVAL_SECONDS = int(config_data["trading"]["periodic_notification_interval_seconds"])
DYN_SYMBOLS_ENABLED = config_data["dynamic_symbols"]["enabled"]
DYN_SYMBOLS_QUOTE_ASSET = config_data["dynamic_symbols"]["quote_asset"]
DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS = config_data["dynamic_symbols"]["update_interval_hours"] * 3600
DYN_SYMBOLS_EXCLUDE = config_data["dynamic_symbols"]["exclude_substrings"]

