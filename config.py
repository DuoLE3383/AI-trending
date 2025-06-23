# config.py
import os
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# === API & Bot Credentials (Lấy từ file .env) ===
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_MESSAGE_THREAD_ID = os.getenv("TELEGRAM_MESSAGE_THREAD_ID") # Có thể có hoặc không

# === Database ===
SQLITE_DB_PATH = "trend_analysis.db"

# === Symbol & Market Data Settings ===
TIMEFRAME = "15m"
STATIC_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
DYN_SYMBOLS_ENABLED = True
DYN_SYMBOLS_UPDATE_INTERVAL_SECONDS = 6 * 3600  # 6 giờ

# === Analysis Strategy Parameters ===
# EMA Settings
EMA_FAST = 34
EMA_MEDIUM = 89
EMA_SLOW = 200

# RSI Settings
RSI_PERIOD = 13

# Bollinger Bands Settings
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2

# ATR Settings
ATR_PERIOD = 14

# --- Cài đặt cho chiến lược nâng cao ---
# Volatility Filter: Tín hiệu sẽ bị bỏ qua nếu biến động (ATR) dưới mức này
MIN_ATR_PERCENT = 0.8  # Yêu cầu biến động tối thiểu 0.4%

# Trade Parameter Multipliers (dựa trên ATR)
ATR_MULTIPLIER_SL = 1.5   # StopLoss = 1.5 * ATR
ATR_MULTIPLIER_TP1 = 1.0  # TakeProfit 1 = 1.0 * ATR
ATR_MULTIPLIER_TP2 = 2.0  # TakeProfit 2 = 2.0 * ATR
ATR_MULTIPLIER_TP3 = 3.0  # TakeProfit 3 = 3.0 * ATR

# === Trend Definitions ===
TREND_STRONG_BULLISH = "STRONG_BULLISH"
TREND_STRONG_BEARISH = "STRONG_BEARISH"
TREND_BULLISH = "BULLISH"
TREND_BEARISH = "BEARISH"
TREND_SIDEWAYS = "SIDEWAYS"

# === Loop Intervals ===
UPDATER_INTERVAL_SECONDS = 10 * 60  # 10 phút
LOOP_SLEEP_INTERVAL_SECONDS = 10 * 60  # 10 phút
SIGNAL_CHECK_INTERVAL_SECONDS = 60    # 1 phút

# --- Placeholder values for safety check ---
API_KEY_PLACEHOLDER = "YOUR_API_KEY_HERE"
API_SECRET_PLACEHOLDER = "YOUR_API_SECRET_HERE"
TELEGRAM_BOT_TOKEN_PLACEHOLDER = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_PLACEHOLDER = "YOUR_TELEGRAM_CHAT_ID"
