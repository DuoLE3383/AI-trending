# database_handler.py
import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_sqlite_db(db_path: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Câu lệnh SQL để tạo bảng với tất cả các cột cần thiết
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
            trend TEXT,
            kline_open_time TEXT,
            bbands_lower REAL,
            bbands_middle REAL,
            bbands_upper REAL,
            atr_val REAL,
            proj_range_short_low REAL,
            proj_range_short_high REAL,
            proj_range_long_low REAL,
            proj_range_long_high REAL,
            entry_price REAL,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            take_profit_3 REAL,
            status TEXT DEFAULT 'ACTIVE'
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        logger.info(f"Database '{db_path}' initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()
