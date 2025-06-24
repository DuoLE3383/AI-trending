# updater.py
import logging
import sqlite3
from binance import AsyncClient as Client # Import AsyncClient để rõ ràng hơn
import config
from market_data_handler import get_market_data

logger = logging.getLogger(__name__)

def update_signal_outcome(db_path: str, row_id: int, new_status: str) -> None:
    """
    Cập nhật trạng thái của một tín hiệu trong database (SL_HIT hoặc TP1_HIT).
    Hàm này là đồng bộ (synchronous) vì nó chỉ tương tác với file local.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # Thêm cột outcome_timestamp_utc để ghi lại thời điểm trade kết thúc
            # Câu lệnh này sẽ không báo lỗi nếu cột đã tồn tại
            try:
                conn.execute("ALTER TABLE trend_analysis ADD COLUMN outcome_timestamp_utc TEXT;")
            except sqlite3.OperationalError:
                pass # Cột đã tồn tại, bỏ qua

            # Cập nhật trạng thái và thời gian kết thúc
            import pandas as pd
            timestamp_utc = pd.to_datetime('now', utc=True).isoformat()
            conn.execute(
                "UPDATE trend_analysis SET status = ?, outcome_timestamp_utc = ? WHERE rowid = ?",
                (new_status, timestamp_utc, row_id)
            )
        logger.info(f"✅ Updated signal (rowid: {row_id}) to status: {new_status}")
    except sqlite3.Error as e:
        logger.error(f"❌ Failed to update database for rowid {row_id}: {e}")

async def check_signal_outcomes(binance_client: Client) -> None:
    """
    Kiểm tra các tín hiệu đang 'ACTIVE' để xem chúng đã chạm Stop Loss hay Take Profit chưa.
    Hàm này là bất đồng bộ (asynchronous) vì nó gọi API của Binance.
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
        symbol = signal['symbol']
        trend = signal['trend']
        sl = signal['stop_loss']
        tp1 = signal['take_profit_1']

        if not all([symbol, trend, sl, tp1]):
            logger.warning(f"Signal (rowid: {signal['rowid']}) is missing critical data. Skipping.")
            continue

        try:
            # === KHỐI LỆNH ĐÃ ĐƯỢC SỬA LỖI ===
            market_data = await get_market_data(
                client=binance_client,
                symbol=symbol,
                timeframe=config.TIMEFRAME,  # 1. Thêm timeframe bị thiếu
                limit=15                      # 2. Sửa tên tham số và dùng giá trị nhỏ
            )
            # 3. Đã thêm 'await' ở đầu dòng

            if market_data.empty:
                logger.warning(f"Could not fetch market data for {symbol} in updater loop. Skipping.")
                continue

            # Lấy giá cao nhất và thấp nhất trong các nến gần đây
            recent_low = market_data['low'].min()
            recent_high = market_data['high'].max()
            
            # Logic kiểm tra SL/TP
            if trend == config.TREND_STRONG_BULLISH:
                if recent_low <= sl:
                    update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_high >= tp1:
                    update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')
            elif trend == config.TREND_STRONG_BEARISH:
                if recent_high >= sl:
                    update_signal_outcome(db_path, signal['rowid'], 'SL_HIT')
                elif recent_low <= tp1:
                    update_signal_outcome(db_path, signal['rowid'], 'TP1_HIT')

        except Exception as e:
            logger.error(f"An error occurred while checking signal for {symbol}: {e}", exc_info=True)
