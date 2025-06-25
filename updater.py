# updater.py
import logging
import sqlite3
import pandas as pd
from binance import AsyncClient
import config
from market_data_handler import get_market_data

logger = logging.getLogger(__name__)

async def get_usdt_futures_symbols(client: AsyncClient) -> set:
    logger.info("🔍 Fetching all active USDT perpetual futures symbols...")
    try:
        exchange_info = await client.futures_exchange_info()
        symbols = {
            s['symbol'] for s in exchange_info['symbols']
            if s.get('contractType') == 'PERPETUAL' 
            and s.get('quoteAsset') == 'USDT'
            and s.get('status') == 'TRADING'
        }
        logger.info(f"✅ Fetched {len(symbols)} active symbols.")
        return symbols
    except Exception as e:
        logger.error(f"❌ Failed to fetch symbol list: {e}", exc_info=True)
        return set()

def _update_signal_outcome(conn: sqlite3.Connection, row_id: int, new_status: str) -> None:
    """
    Cập nhật trạng thái outcome và thời gian xảy ra.
    """
    try:
        timestamp_utc = pd.Timestamp.utcnow().isoformat()
        conn.execute(
            "UPDATE trend_analysis SET status = ?, outcome_timestamp_utc = ? WHERE rowid = ?",
            (new_status, timestamp_utc, row_id)
        )
        logger.info(f"✅ Updated rowid {row_id} to status: {new_status}")
    except sqlite3.Error as e:
        logger.error(f"❌ DB update failed (rowid {row_id}): {e}", exc_info=True)

async def check_signal_outcomes(client: AsyncClient) -> None:
    """
    Kiểm tra xem các tín hiệu đang hoạt động đã chạm TP/SL chưa. 
    Sử dụng một kết nối DB duy nhất cho cả đọc và ghi.
    """
    logger.info("🚨 Checking TP/SL outcomes...")
    db_path = config.SQLITE_DB_PATH
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            active_signals = conn.execute(
                "SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'"
            ).fetchall()

            if not active_signals:
                logger.info("ℹ️ No active signals to check.")
                return

            logger.info(f"🔍 Checking {len(active_signals)} active signal(s)...")
            for signal in active_signals:
                symbol = signal['symbol']
                trend = signal['trend']
                sl = signal['stop_loss']
                tp1 = signal['take_profit_1']

                if not all([symbol, trend, sl, tp1]):
                    logger.warning(f"⚠️ Missing SL/TP/symbol on rowid {signal['rowid']}. Skipping.")
                    continue

                try:
                    market_data = await get_market_data(
                        client=client,
                        symbol=symbol,
                        timeframe=config.TIMEFRAME,
                        limit=15
                    )

                    if market_data is None or market_data.empty:
                        logger.warning(f"⚠️ No market data for {symbol}.")
                        continue

                    recent_low = market_data['low'].min()
                    recent_high = market_data['high'].max()

                    # Xác định outcome dựa trên trend
                    if trend == config.TREND_STRONG_BULLISH:
                        if recent_low <= sl:
                            _update_signal_outcome(conn, signal['rowid'], 'SL_HIT')
                        elif recent_high >= tp1:
                            _update_signal_outcome(conn, signal['rowid'], 'TP1_HIT')

                    elif trend == config.TREND_STRONG_BEARISH:
                        if recent_high >= sl:
                            _update_signal_outcome(conn, signal['rowid'], 'SL_HIT')
                        elif recent_low <= tp1:
                            _update_signal_outcome(conn, signal['rowid'], 'TP1_HIT')

                except Exception as e:
                    logger.error(f"❌ Error checking signal ({symbol}): {e}", exc_info=True)
    except sqlite3.Error as e:
        logger.error(f"❌ DB operation failed: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ An unexpected error occurred in check_signal_outcomes: {e}", exc_info=True)
