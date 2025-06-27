# config.py
import os
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# ==============================================================================
# === 1. API & BOT CREDENTIALS (Lấy từ file .env)
# ==============================================================================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_MESSAGE_THREAD_ID = os.getenv("TELEGRAM_MESSAGE_THREAD_ID") # ID của topic trong group (nếu có)

# ==============================================================================
# === 2. DATABASE
# ==============================================================================
SQLITE_DB_PATH = "trend_analysis.db"

# ==============================================================================
# === 3. SYMBOL & MARKET DATA SETTINGS
# ==============================================================================
TIMEFRAME = "15m"
# Số lượng nến tối đa để tải về mỗi lần phân tích
DATA_FETCH_LIMIT = 500 # Đã cập nhật theo yêu cầu trong file cũ của bạn

# --- Cài đặt cho việc lấy symbol động ---
# Đã BẬT chế độ lấy cặp giao dịch tự động từ Binance.
DYN_SYMBOLS_ENABLED = True 
# Danh sách tĩnh này không còn được sử dụng khi DYN_SYMBOLS_ENABLED = True
# STATIC_SYMBOLS = ["BTCUSDT", "ETHUSDT"] 
CONCURRENT_REQUESTS = 10 # Số lượng yêu cầu đồng thời tối đa khi lấy dữ liệu từ Binance
# ==============================================================================
# === 4. ANALYSIS STRATEGY PARAMETERS
# ==============================================================================
# In config.py
LEVERAGE = 5 # Or whatever your default leverage is
STRATEGY_MODE = 'AI' 

# --- New Indicators Parameters ---
# MACD Settings
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
# ADX Settings
ADX_PERIOD = 13
ADX_MIN_TREND_STRENGTH = 28 # Example threshold for strong trend
# EMA Settings
EMA_FAST = 34
EMA_MEDIUM = 89
EMA_SLOW = 200

# RSI Settings
RSI_PERIOD = 13

# Bollinger Bands Settings
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2.0

# ATR Settings
ATR_PERIOD = 13

# Volume SMA Settings
VOLUME_SMA_PERIOD = 20
MIN_VOLUME_RATIO = 1.0 # Volume hiện tại phải >= 1.0 * Volume SMA

# Volatility Filter: Tín hiệu sẽ bị bỏ qua nếu biến động (ATR) dưới mức này
MIN_ATR_PERCENT = 0.7

# Trade Parameter Multipliers (dựa trên ATR)
ATR_MULTIPLIER_SL = 2.8   # StopLoss = 1.5 * ATR
ATR_MULTIPLIER_TP1 = 2.2 # TakeProfit 1 = 1.0 * ATR
ATR_MULTIPLIER_TP2 = 3.8  # TakeProfit 2 = 2.0 * ATR
ATR_MULTIPLIER_TP3 = 5.2  # TakeProfit 3 = 3.0 * ATR

# ==============================================================================
# === 5. TREND DEFINITIONS
# ==============================================================================
TREND_STRONG_BULLISH = "STRONG_BULLISH"
TREND_STRONG_BEARISH = "STRONG_BEARISH"
TREND_BULLISH = "BULLISH"
TREND_BEARISH = "BEARISH"
TREND_SIDEWAYS = "SIDEWAYS"

# ==============================================================================
# === 6. LOOP INTERVALS (tính bằng giây)
# ==============================================================================
# Thời gian nghỉ của vòng lặp phân tích chính
LOOP_SLEEP_INTERVAL_SECONDS = 600 # 10 phút

# Tần suất vòng lặp kiểm tra tín hiệu mới trong DB để gửi (Đã rút ngắn)
SIGNAL_CHECK_INTERVAL_SECONDS = 60 # 1 phút (Để nhận thông báo tín hiệu nhanh hơn)

# Tần suất vòng lặp cập nhật trạng thái trade TP/SL (Đã rút ngắn)
UPDATER_INTERVAL_SECONDS = 300 # 5 phút (Để kiểm tra thắng/thua nhanh hơn)

# Tần suất vòng lặp gửi báo cáo tổng kết (Đã tăng lên)
SUMMARY_INTERVAL_SECONDS = 14400 # 4 giờ (Để tránh spam báo cáo)

# Tần suất gửi tin nhắn "nhịp tim" báo bot còn sống
HEARTBEAT_INTERVAL_SECONDS = 1800 # 30 p
# ==============================================================================
# === 7. PLACEHOLDER VALUES (Dùng để kiểm tra an toàn)
# ==============================================================================
# Các giá trị này dùng để cảnh báo nếu người dùng quên điền key vào file .env
API_KEY_PLACEHOLDER = "YOUR_API_KEY_HERE"
API_SECRET_PLACEHOLDER = "YOUR_API_SECRET_HERE"
TELEGRAM_BOT_TOKEN_PLACEHOLDER = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_PLACEHOLDER = "YOUR_TELEGRAM_CHAT_ID"
TELEGRAM_CHANNEL_ID=-1002788090700