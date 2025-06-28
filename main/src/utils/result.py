# results.py

import sqlite3
import logging
from collections import Counter
import main.config

logger = logging.getLogger(__name__)

def get_db_connection(db_path: str):
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_win_loss_stats(db_path: str):
    conn = get_db_connection(db_path)
    if not conn:
        return {"error": "Could not connect to the database."}

    try:
        query = "SELECT status FROM trend_analysis WHERE status != 'ACTIVE'"
        cursor = conn.cursor()
        cursor.execute(query)
        outcomes = [row['status'] for row in cursor.fetchall()]
        
        if not outcomes:
            return {"total_completed_trades": 0, "win_rate": "0.00%", "loss_rate": "0.00%", "breakdown": {}}

        status_counts = Counter(outcomes)
        wins = sum(count for status, count in status_counts.items() if 'TP' in status)
        losses = status_counts.get('SL_HIT', 0)
        total_completed = wins + losses
        win_rate = (wins / total_completed) * 100 if total_completed > 0 else 0
        loss_rate = (losses / total_completed) * 100 if total_completed > 0 else 0
        
        return {
            "total_completed_trades": total_completed,
            "win_rate": f"{win_rate:.2f}%",
            "loss_rate": f"{loss_rate:.2f}%",
            "breakdown": dict(status_counts)
        }
    except sqlite3.Error as e:
        logger.error(f"❌ Failed to query database for stats: {e}")
        return {"error": "Failed to query for stats."}
    finally:
        if conn:
            conn.close()

