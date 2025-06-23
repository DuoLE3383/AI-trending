# updater.py
import logging
import sqlite3
from binance.client import Client
import config
from market_data_handler import get_market_data

logger = logging.getLogger(__name__)

def update_signal_outcome(db_path: str, row_id: int, new_status: str):
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE trend_analysis SET status = ? WHERE rowid = ?", (new_status, row_id))
        logger.info(f"Updated signal (rowid: {row_id}) to status: {new_status}")
    except sqlite3.Error as e:
        logger.error(f"Failed to update database for rowid {row_id}: {e}")

async def check_signal_outcomes(binance_client: Client):
    logger.info("--- Checking for trade outcomes (TP/SL)... ---")
    db_path = config.SQLITE_DB_PATH
    try:
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            active_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
    except sqlite3.Error as e:
        logger.error(f"Failed to fetch active signals: {e}")
        return

    if not active_signals:
        logger.info("No active signals to check.")
        return

    for signal in active_signals:
        symbol, trend, sl, tp1 = signal['symbol'], signal['trend'], signal['stop_loss'], signal['take_profit_1']
        market_data = get_market_data(binance_client, symbol, kline_limit=10)
        if market_data.empty: continue
        
        recent_low, recent_high = market_data['low'].min(), market_data['high'].max()
        
        if trend == config.TREND_STRONG_BULLISH and sl and tp1:
            if recent_low <= sl: update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
            elif recent_high >= tp1: update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')
        elif trend == config.TREND_STRONG_BEARISH and sl and tp1:
            if recent_high >= sl: update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
            elif recent_low <= tp1: update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')

