# performance_analyzer.py

import sqlite3
import logging
from typing import Dict, Any
import pandas as pd
from . import config

logger = logging.getLogger(__name__)

def get_performance_stats(by_symbol: bool = False) -> Dict[str, Any]:
    """
    Connects to the SQLite database, analyzes completed trades,
    and returns a dictionary of performance statistics.

    :param by_symbol: If True, returns a dictionary of stats for each symbol.
                      If False, returns a dictionary of global stats.
    """
    logger.info(f"Analyzing performance of completed trades... (by_symbol={by_symbol})")
    
    try:
        with sqlite3.connect(config.SQLITE_DB_PATH) as conn:
            # Query all completed trades, including pnl_percentage for accurate win/loss assessment
            query = "SELECT symbol, status, pnl_percentage FROM trend_analysis WHERE status != 'ACTIVE'"
            df = pd.read_sql_query(query, conn)

        if df.empty:
            logger.info("No completed trades found to analyze.")
            return {}

        # Define a win condition: A trade is a win if it hits TP or has a positive PnL
        # This correctly handles manually closed trades.
        df['is_win'] = (df['status'].str.contains('TP', na=False)) | (df['pnl_percentage'] > 0)

        if by_symbol:
            # Group by symbol and calculate stats for each group
            symbol_stats_df = df.groupby('symbol').apply(lambda x: pd.Series({
                'total_trades': len(x),
                'wins': int(x['is_win'].sum()),
                'losses': int(len(x) - x['is_win'].sum()),
                'win_rate': (x['is_win'].sum() / len(x)) * 100 if len(x) > 0 else 0.0,
                'net_pnl_percentage': x['pnl_percentage'].sum() if 'pnl_percentage' in x else 0.0
            }))
            
            symbol_stats = symbol_stats_df.to_dict('index')
            logger.info(f"Per-symbol performance stats calculated for {len(symbol_stats)} symbols.")
            return symbol_stats
        else:
            # Calculate global stats
            total_completed = len(df)
            wins = int(df['is_win'].sum())
            losses = total_completed - wins
            win_rate = (wins / total_completed) * 100 if total_completed > 0 else 0.0

            stats = {
                'total_completed_trades': total_completed,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate
            }
            logger.info(f"Global performance stats calculated: {stats}")
            return stats

    except sqlite3.Error as e:
        logger.error(f"Database error during performance analysis: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during performance analysis: {e}", exc_info=True)
        
    return {}

# Ví dụ cách chạy file này để kiểm tra
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("Running performance analysis directly...")
    performance_data = get_performance_stats()
    print("Analysis complete. Results:")
    print(performance_data)