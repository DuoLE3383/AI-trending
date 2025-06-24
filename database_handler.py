# database_handler.py
import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_sqlite_db(db_path: str):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Tạo bảng nếu chưa có
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
            take_profit_3 REAL
            -- cột 'status' sẽ được kiểm tra thêm sau
        );
        """
        cursor.execute(create_table_query)

        # Kiểm tra nếu cột 'status' chưa có thì thêm vào
        cursor.execute("PRAGMA table_info(trend_analysis);")
        columns = [row[1] for row in cursor.fetchall()]
        if "status" not in columns:
            cursor.execute("ALTER TABLE trend_analysis ADD COLUMN status TEXT DEFAULT 'ACTIVE';")
            logger.info("✅ Cột 'status' đã được thêm vào bảng trend_analysis.")
        else:
            logger.info("ℹ️ Cột 'status' đã tồn tại trong bảng trend_analysis.")

        conn.commit()
        logger.info(f"✅ Database '{db_path}' initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"❌ Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()
            logger.info("✅ Database connection closed.")