# In a new file named: updater.py

import logging
import sqlite3
from binance.client import Client
import config
from market_data_handler import get_market_data # We reuse this from your existing file

logger = logging.getLogger(__name__)

def update_signal_outcome(db_path: str, row_id: int, new_status: str):
    """Updates the status of a specific signal in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE trend_analysis SET status = ? WHERE rowid = ?", (new_status, row_id))
        conn.commit()
        logger.info(f"Updated signal (rowid: {row_id}) to status: {new_status}")
    except sqlite3.Error as e:
        logger.error(f"Failed to update database for rowid {row_id}: {e}")
    finally:
        if conn:
            conn.close()

async def check_signal_outcomes(binance_client: Client):
    """
    Fetches active signals and checks if they have hit TP or SL.
    """
    logger.info("--- Starting signal outcome check cycle ---")
    db_path = config.SQLITE_DB_PATH
    
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        # Fetch signals that are still 'ACTIVE'
        active_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to fetch active signals: {e}")
        return

    if not active_signals:
        logger.info("No active signals to check.")
        return

    logger.info(f"Found {len(active_signals)} active signals to check for outcomes.")

    for signal in active_signals:
        try:
            symbol = signal['symbol']
            trend = signal['trend']
            sl = signal['stop_loss']
            tp1 = signal['take_profit_1']
            
            # Get the latest market data for the symbol
            # We only need a few recent candles to check for highs and lows
            market_data = get_market_data(binance_client, symbol, kline_limit=10)
            if market_data.empty:
                continue

            recent_low = market_data['low'].min()
            recent_high = market_data['high'].max()

            # Check for outcome based on the trend
            if trend == config.TREND_STRONG_BULLISH: # This is a LONG trade
                if recent_low <= sl:
                    update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_high >= tp1:
                    update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')

            elif trend == config.TREND_STRONG_BEARISH: # This is a SHORT trade
                if recent_high >= sl:
                    update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_low <= tp1:
                    update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')

        except Exception as e:
            logger.error(f"Error checking outcome for signal {signal['symbol']} (rowid: {signal['rowid']}): {e}")

