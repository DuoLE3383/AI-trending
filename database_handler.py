import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_sqlite_db(db_path: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Tạo bảng chính
        create_table_query = """
        CREATE TABLE IF NOT EXISTS trend_analysis (
            analysis_timestamp_utc TEXT,
            symbol TEXT,
            timeframe TEXT,
            last_price REAL,

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

            -- Dữ liệu dành cho Machine Learning
            entry_timestamp_utc TEXT,
            exit_timestamp_utc TEXT,
            exit_price REAL,
            pnl_percent REAL,
            holding_duration INTEGER,
            exit_reason TEXT,
            ml_label TEXT
        );
        """
        cursor.execute(create_table_query)

        # Tạo index giúp truy vấn nhanh hơn
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_time ON trend_analysis(symbol, analysis_timestamp_utc);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON trend_analysis(status);")

        conn.commit()
        logger.info(f"✅ SQLite DB initialized successfully at: {db_path}")
    except sqlite3.Error as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()
