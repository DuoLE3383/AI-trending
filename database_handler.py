import sqlite3
import logging

# It's good practice to have the logger setup available
# in case this script is run standalone.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_sqlite_db(db_path: str):
    """
    Initializes the SQLite database and ensures the table schema is correct.
    This version includes the 'outcome_timestamp_utc' column to prevent errors.
    """
    conn = None  # Initialize conn to None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # --- Corrected CREATE TABLE statement ---
        # I have added the `outcome_timestamp_utc` column that your updater.py needs.
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
            entry_timestamp_utc TEXT,
            
            -- This column was added from your existing schema
            exit_timestamp_utc TEXT, 
            
            -- This is the column that was missing and causing the error
            outcome_timestamp_utc TEXT, 

            exit_price REAL,
            pnl_percent REAL,
            holding_duration INTEGER,
            exit_reason TEXT,
            ml_label TEXT
        );
        """
        cursor.execute(create_table_query)

        # Creating indexes helps speed up queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_time ON trend_analysis(symbol, analysis_timestamp_utc);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON trend_analysis(status);")

        conn.commit()
        logger.info(f"✅ SQLite DB initialized successfully at: {db_path}")
        logger.info("Table 'trend_analysis' schema is up-to-date.")

    except sqlite3.Error as e:
        logger.error(f"❌ Failed to initialize database: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

# Example of how to run this if the file is executed directly
if __name__ == '__main__':
    # You would import your DB path from your config file
    # from config import SQLITE_DB_PATH
    SQLITE_DB_PATH = 'your_database_name.db' # <--- IMPORTANT: Replace with your actual DB file path
    print(f"Initializing database at {SQLITE_DB_PATH}...")
    init_sqlite_db(SQLITE_DB_PATH)

