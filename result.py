# results.py

import sqlite3
import logging
from collections import Counter
import config

logger = logging.getLogger(__name__)

def get_db_connection(db_path: str):
    """Thiết lập kết nối chỉ đọc đến database SQLite."""
    try:
        # Kết nối ở chế độ chỉ đọc (read-only) để an toàn
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_win_loss_stats(db_path: str):
    """
    Truy vấn database để tính toán thống kê thắng/thua dựa trên kết quả của tín hiệu.
    """
    conn = get_db_connection(db_path)
    if not conn:
        return {"error": "Could not connect to the database."}

    try:
        # Chúng ta chỉ quan tâm đến các trade đã hoàn thành (không phải 'ACTIVE')
        query = "SELECT status FROM trend_analysis WHERE status != 'ACTIVE'"
        cursor = conn.cursor()
        cursor.execute(query)
        
        outcomes = [row['status'] for row in cursor.fetchall()]
        
        if not outcomes:
            return {
                "total_completed_trades": 0,
                "win_rate": "0.00%",
                "loss_rate": "0.00%",
                "breakdown": {}
            }

        # Đếm số lần xuất hiện của mỗi trạng thái
        status_counts = Counter(outcomes)
        
        # Định nghĩa "thắng" là các trạng thái có chứa 'TP'
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
        return {"error": f"Failed to query database for stats: {e}"}
    finally:
        if conn:
            conn.close()

# Bạn có thể thêm lại hàm get_analysis_summary ở đây nếu cần trong tương lai
