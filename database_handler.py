# init_db.py (Phiên bản cuối cùng, đã đồng bộ với analysis_engine.py)
import sqlite3
import logging
from typing import List

# Cấu hình logging cơ bản để có thể chạy file một cách độc lập
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_existing_columns(cursor: sqlite3.Cursor, table_name: str) -> List[str]:
    """Lấy danh sách các cột hiện có của một bảng."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return [row[1] for row in cursor.fetchall()]

def init_sqlite_db(db_path: str):
    """
    Khởi tạo hoặc cập nhật database SQLite.
    Đảm bảo cấu trúc bảng 'trend_analysis' luôn đúng và đầy đủ.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Câu lệnh CREATE TABLE với đầy đủ tất cả các cột cần thiết
        # Bao gồm cả các cột bạn đã định nghĩa và các cột MACD/ADX mới
        create_table_query = """
        CREATE TABLE IF NOT EXISTS trend_analysis (
            analysis_timestamp_utc TEXT,
            symbol TEXT NOT NULL,
            timeframe TEXT,
            last_price REAL,
            timestamp_utc INTEGER, -- MỚI: Dùng để lưu unix timestamp của nến

            ema_fast_len INTEGER,
            ema_fast_val REAL,
            ema_medium_len INTEGER,
            ema_medium_val REAL,
            ema_slow_len INTEGER,
            ema_slow_val REAL,

            rsi_len INTEGER,
            rsi_val REAL,
            atr_val REAL,

            bbands_lower REAL,
            bbands_middle REAL,
            bbands_upper REAL,

            -- MỚI: Thêm các cột cho chỉ báo mới
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            adx REAL,

            proj_range_short_low REAL,
            proj_range_short_high REAL,
            proj_range_long_low REAL,
            proj_range_long_high REAL,

            entry_price REAL,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            take_profit_3 REAL,

            trend TEXT,
            kline_open_time TEXT,
            status TEXT DEFAULT 'ACTIVE',
            entry_timestamp_utc TEXT,
            exit_timestamp_utc TEXT, 
            outcome_timestamp_utc TEXT,
            exit_price REAL,
            pnl_percent REAL,
            holding_duration INTEGER,
            exit_reason TEXT,
            ml_label TEXT
        );
        """
        cursor.execute(create_table_query)
        logger.info("Bảng 'trend_analysis' đã được tạo hoặc đã tồn tại.")

        # --- Cơ chế cập nhật cấu trúc bảng một cách an toàn ---
        # Lấy các cột hiện có và định nghĩa các cột cần có
        existing_columns = get_existing_columns(cursor, "trend_analysis")
        required_columns = {
            "timestamp_utc": "INTEGER",
            "macd": "REAL",
            "macd_signal": "REAL",
            "macd_hist": "REAL",
            "adx": "REAL"
        }

        # Thêm các cột còn thiếu
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                logger.info(f"Cột '{col_name}' không tồn tại. Đang thêm vào bảng...")
                cursor.execute(f"ALTER TABLE trend_analysis ADD COLUMN {col_name} {col_type};")
                logger.info(f"✅ Đã thêm cột '{col_name}'.")

        # Tạo các chỉ mục (index) để tăng tốc độ truy vấn
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_time ON trend_analysis(symbol, kline_open_time);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON trend_analysis(status);")

        conn.commit()
        logger.info(f"✅ SQLite DB initialized successfully at: {db_path}")

    except sqlite3.Error as e:
        logger.error(f"❌ Failed to initialize database: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

# --- Cách sử dụng ---
if __name__ == '__main__':
    # Khi chạy file này, nó sẽ sử dụng đường dẫn DB từ file config của bạn
    try:
        from config import SQLITE_DB_PATH
        logger.info(f"Initializing database at {SQLITE_DB_PATH}...")
        init_sqlite_db(SQLITE_DB_PATH)
    except ImportError:
        logger.error("Không thể import SQLITE_DB_PATH từ config.py. Vui lòng tạo file config.py với biến này.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

