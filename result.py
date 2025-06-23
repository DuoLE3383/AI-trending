# In file: results.py

import sqlite3
import logging
from collections import Counter
from datetime import datetime, timedelta

# --- Logging ---
# It's good practice for each module to have its own logger
logger = logging.getLogger(__name__)

def get_db_connection(db_path):
    """Establishes a read-only connection to the SQLite database."""
    try:
        # Connect in read-only mode to prevent accidental writes
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def get_analysis_summary(db_path: str, time_period_hours: int = None):
    """
    Analyzes the trend_analysis table to count entries and their results.

    This function directly addresses your request to analyze how many entries
    exist and what their results (trends) are.

    Args:
        db_path (str): The path to the SQLite database file.
        time_period_hours (int, optional): If provided, summarizes data only from the 
                                           last X hours. Defaults to None (all time).

    Returns:
        A dictionary containing the analysis summary or an error message.
    """
    conn = get_db_connection(db_path)
    if not conn:
        return {"error": "Could not connect to the database."}

    try:
        cursor = conn.cursor()
        
        query = "SELECT trend FROM trend_analysis"
        params = []

        # If a time period is specified, modify the query
        if time_period_hours:
            start_time = datetime.utcnow() - timedelta(hours=time_period_hours)
            query += " WHERE analysis_timestamp_utc >= ?"
            params.append(start_time.strftime('%Y-%m-%d %H:%M:%S'))
            logger.info(f"Fetching results from the last {time_period_hours} hours.")
        else:
            logger.info("Fetching all-time results.")

        cursor.execute(query, params)
        
        # Fetch all results; cursor returns a list of tuples, e.g., [('STRONG_BULLISH',), ('BEARISH',)]
        all_trends = [row['trend'] for row in cursor.fetchall()]

        if not all_trends:
            return {
                "total_entries": 0,
                "trend_counts": {},
                "message": "No analysis entries found in the specified period."
            }
        
        # Use collections.Counter to easily count the occurrences of each trend
        trend_counts = Counter(all_trends)

        summary = {
            "total_entries": len(all_trends),
            "trend_counts": dict(trend_counts) # Convert Counter to a regular dict
        }
        
        return summary

    except sqlite3.Error as e:
        logger.error(f"❌ Failed to query database for summary: {e}")
        return {"error": f"Failed to query database: {e}"}
    finally:
        if conn:
            conn.close()

