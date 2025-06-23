# results.py
import sqlite3
import logging
from collections import Counter
import config

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
    if not conn: return {"error": "DB connection failed."}

    try:
        outcomes = [row['status'] for row in conn.execute("SELECT status FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()]
        if not outcomes:
            return {"total_completed_trades": 0, "win_rate": "0%", "loss_rate": "0%", "breakdown": {}}
        
        counts = Counter(outcomes)
        wins = sum(count for status, count in counts.items() if 'TP' in status)
        losses = counts.get('SL_HIT', 0)
        total = wins + losses
        
        win_rate = (wins / total) * 100 if total > 0 else 0
        loss_rate = (losses / total) * 100 if total > 0 else 0
        
        return {
            "total_completed_trades": total,
            "win_rate": f"{win_rate:.2f}%",
            "loss_rate": f"{loss_rate:.2f}%",
            "breakdown": dict(counts)
        }
    except sqlite3.Error as e:
        logger.error(f"Failed to query stats: {e}")
        return {"error": "Failed to query stats."}
    finally:
        if conn: conn.close()
