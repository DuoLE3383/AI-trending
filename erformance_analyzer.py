# performance_analyzer.py

import sqlite3
import logging
from typing import Dict, Any
import pandas as pd
import config

logger = logging.getLogger(__name__)

def get_performance_stats() -> Dict[str, Any]:
    """
    Kết nối vào database SQLite, phân tích các giao dịch đã đóng
    và trả về một từ điển chứa các thống kê hiệu suất.
    """
    logger.info("Analyzing performance of completed trades...")
    stats = {
        'total_completed_trades': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0.0
    }

    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            # Truy vấn tất cả các giao dịch đã hoàn thành (không còn 'ACTIVE')
            query = "SELECT status FROM trend_analysis WHERE status != 'ACTIVE'"
            df = pd.read_sql_query(query, conn)

        if df.empty:
            logger.info("No completed trades found to analyze.")
            return stats

        total_completed = len(df)
        # Đếm số lần thắng (status có chứa 'TP')
        wins = df[df['status'].str.contains('TP', na=False)].shape[0]
        # Đếm số lần thua (status có chứa 'SL')
        losses = df[df['status'].str.contains('SL', na=False)].shape[0]

        # Tính toán tỷ lệ thắng
        win_rate = (wins / total_completed) * 100 if total_completed > 0 else 0.0

        stats.update({
            'total_completed_trades': total_completed,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate
        })
        
        logger.info(f"Performance stats calculated: {stats}")

    except sqlite3.Error as e:
        logger.error(f"Database error during performance analysis: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during performance analysis: {e}", exc_info=True)
        
    return stats

# Ví dụ cách chạy file này để kiểm tra
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("Running performance analysis directly...")
    performance_data = get_performance_stats()
    print("Analysis complete. Results:")
    print(performance_data)