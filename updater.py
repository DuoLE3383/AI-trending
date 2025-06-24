# updater.py
import logging
import sqlite3
import pandas as pd
from binance import AsyncClient
import config
from market_data_handler import get_market_data

logger = logging.getLogger(__name__)


# In updater.py

async def get_usdt_futures_symbols(client: AsyncClient) -> set:
    """
    Fetches all actively trading USDT-margined perpetual futures symbols from Binance.
    """
    logger.info("Fetching all active USDT perpetual futures symbols from Binance...")
    try:
        # --- THIS IS THE FINAL, CORRECTED METHOD NAME ---
        # The correct method for the Futures API is api_get_exchange_info()
        exchange_info = await client.api_get_exchange_info()
        
        # The rest of this logic is correct and will work with the data returned.
        symbols = {
            s['symbol'] for s in exchange_info['symbols']
            if s.get('contractType') == 'PERPETUAL' 
            and s.get('quoteAsset') == 'USDT'
            and s.get('status') == 'TRADING'
        }
        
        logger.info(f"Successfully fetched {len(symbols)} active symbols.")
        return symbols
    except Exception as e:
        logger.error(f"Failed to fetch symbol list from Binance: {e}", exc_info=True)
        return set()


def _update_signal_outcome(db_path: str, row_id: int, new_status: str) -> None:
    """
    Private helper function to update a signal's status in the database (e.g., SL_HIT or TP1_HIT).
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # This will add the column if it doesn't exist, and do nothing if it does.
            try:
                conn.execute("ALTER TABLE trend_analysis ADD COLUMN outcome_timestamp_utc TEXT;")
            except sqlite3.OperationalError:
                pass # Column already exists, which is fine.

            # Update status and the outcome timestamp
            timestamp_utc = pd.to_datetime('now', utc=True).isoformat()
            conn.execute(
                "UPDATE trend_analysis SET status = ?, outcome_timestamp_utc = ? WHERE rowid = ?",
                (new_status, timestamp_utc, row_id)
            )
        logger.info(f"✅ Updated signal (rowid: {row_id}) to status: {new_status}")
    except sqlite3.Error as e:
        logger.error(f"❌ Failed to update database for rowid {row_id}: {e}", exc_info=True)


async def check_signal_outcomes(client: AsyncClient) -> None:
    """
    Checks all 'ACTIVE' signals in the database to see if they have hit Stop Loss or Take Profit.
    """
    logger.info("--- Checking for trade outcomes (TP/SL)... ---")
    db_path = config.SQLITE_DB_PATH
    try:
        with sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            active_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
    except sqlite3.Error as e:
        logger.error(f"❌ Failed to fetch active signals from DB: {e}")
        return

    if not active_signals:
        logger.info("--- No active signals to check. ---")
        return

    logger.info(f"Found {len(active_signals)} active signal(s) to check.")
    for signal in active_signals:
        # Using .get() provides a default value to prevent errors if a key is missing
        symbol = signal['symbol']
        trend = signal.get('trend')
        sl = signal.get('stop_loss')
        tp1 = signal.get('take_profit_1')

        if not all([symbol, trend, sl, tp1]):
            logger.warning(f"Signal (rowid: {signal['rowid']}) is missing critical data. Skipping.")
            continue

        try:
            market_data = await get_market_data(
                client=client,
                symbol=symbol,
                timeframe=config.TIMEFRAME,
                limit=15 
            )

            if market_data is None or market_data.empty:
                logger.warning(f"Could not fetch market data for {symbol} in updater loop. Skipping.")
                continue

            recent_low = market_data['low'].min()
            recent_high = market_data['high'].max()
            
            if trend == config.TREND_STRONG_BULLISH:
                if recent_low <= sl:
                    _update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_high >= tp1:
                    _update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')
            elif trend == config.TREND_STRONG_BEARISH:
                if recent_high >= sl:
                    _update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_low <= tp1:
                    _update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')

        except Exception as e:
            logger.error(f"An error occurred while checking signal for {symbol}: {e}", exc_info=True)