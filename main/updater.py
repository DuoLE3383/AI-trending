# updater.py (Phiên bản tối ưu với asyncio.gather và logic multi-TP)
import logging
import sqlite3
import pandas as pd
from binance import AsyncClient
import main.src.config as config
from market_data_handler import get_market_data
import asyncio
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

async def get_usdt_futures_symbols(client: AsyncClient) -> set:
    """Lấy tất cả các mã futures USDT đang hoạt động."""
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

def _update_signal_outcome(conn: sqlite3.Connection, signal_data: Dict[str, Any], new_status: str, exit_price: float) -> None:
    """
    Cập nhật trạng thái, giá thoát lệnh, PnL và thời gian xảy ra cho một tín hiệu.
    """
    try:
        timestamp_utc = pd.Timestamp.utcnow().isoformat()
        row_id = signal_data.get('rowid')

        # --- LOGIC MỚI: TÍNH TOÁN PNL KHI ĐÓNG LỆNH ---
        entry_price = signal_data.get('entry_price')
        trend = signal_data.get('trend')
        pnl_percentage = None
        pnl_with_leverage = None

        if entry_price and exit_price and trend:
            try:
                pnl = ((float(exit_price) - float(entry_price)) / float(entry_price)) * 100
                if 'BEARISH' in trend:
                    pnl *= -1 # Đảo dấu PnL cho lệnh short
                pnl_percentage = pnl
                pnl_with_leverage = pnl * config.LEVERAGE
            except (ValueError, TypeError, ZeroDivisionError) as pnl_e:
                logger.error(f"Could not calculate PnL for rowid {row_id}: {pnl_e}")
        # --- KẾT THÚC LOGIC MỚI ---

        conn.execute(
            """UPDATE trend_analysis 
               SET status = ?, outcome_timestamp_utc = ?, exit_price = ?, pnl_percentage = ?, pnl_with_leverage = ?
               WHERE rowid = ?""",
            (new_status, timestamp_utc, exit_price, pnl_percentage, pnl_with_leverage, row_id)
        )
        logger.info(f"✅ Updated rowid {row_id} to status: {new_status} at price {exit_price} with PnL: {pnl_percentage:.2f}%")
    except sqlite3.Error as e:
        logger.error(f"❌ DB update failed (rowid {row_id}): {e}", exc_info=True)

async def check_signal_outcomes(client: AsyncClient) -> None:
    """
    Kiểm tra các tín hiệu đang hoạt động đã chạm TP/SL chưa.
    Sử dụng asyncio.gather để tăng hiệu năng.
    """
    logger.info("🚨 Checking TP/SL outcomes...")
    db_path = config.SQLITE_DB_PATH
    
    active_signals: List[sqlite3.Row] = []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            active_signals = conn.execute(
                "SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'"
            ).fetchall()
    except sqlite3.Error as e:
        logger.error(f"❌ DB read failed: {e}", exc_info=True)
        return

    if not active_signals:
        logger.info("ℹ️ No active signals to check.")
        return

    # CẢI THIỆN: Tạo các tác vụ lấy dữ liệu để chạy đồng thời
    logger.info(f"🔍 Concurrently fetching market data for {len(active_signals)} active signal(s)...")
    tasks = [
        get_market_data(client, signal['symbol'], config.TIMEFRAME, limit=15)
        for signal in active_signals
    ]
    # Chạy tất cả các tác vụ cùng lúc và nhận kết quả
    market_data_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Dùng một kết nối duy nhất để ghi tất cả các thay đổi
    try:
        with sqlite3.connect(db_path) as conn:
            # Xử lý kết quả sau khi đã có tất cả dữ liệu
            for signal, market_data in zip(active_signals, market_data_results):
                try:
                    if isinstance(market_data, Exception):
                        logger.error(f"Error fetching data for {signal['symbol']}: {market_data}")
                        continue
                    if market_data is None or market_data.empty:
                        logger.warning(f"⚠️ No market data returned for {signal['symbol']}.")
                        continue

                    trend = signal['trend']
                    sl, tp1, tp2, tp3 = signal['stop_loss'], signal['take_profit_1'], signal['take_profit_2'], signal['take_profit_3']

                    recent_low = market_data['low'].min()
                    recent_high = market_data['high'].max()
                    
                    # CẢI THIỆN: Logic kiểm tra Multi-TP, ưu tiên SL rồi đến TP cao nhất.
                    # Điều này đảm bảo các lệnh được cắt lỗ một cách an toàn trong trường hợp nến biến động mạnh.
                    if 'BULLISH' in trend: # For LONG trades
                        if recent_low <= sl: # 1. Kiểm tra Stop Loss trước tiên
                            _update_signal_outcome(conn, dict(signal), 'SL_HIT', sl)
                        elif recent_high >= tp3: # 2. Sau đó kiểm tra các mức Take Profit từ cao đến thấp
                            _update_signal_outcome(conn, dict(signal), 'TP3_HIT', tp3)
                        elif recent_high >= tp2: _update_signal_outcome(conn, dict(signal), 'TP2_HIT', tp2)
                        elif recent_high >= tp1: _update_signal_outcome(conn, dict(signal), 'TP1_HIT', tp1)

                    elif 'BEARISH' in trend: # For SHORT trades
                        if recent_high >= sl: # 1. Kiểm tra Stop Loss trước tiên
                            _update_signal_outcome(conn, dict(signal), 'SL_HIT', sl)
                        elif recent_low <= tp3: # 2. Sau đó kiểm tra các mức Take Profit từ cao đến thấp
                            _update_signal_outcome(conn, dict(signal), 'TP3_HIT', tp3)
                        elif recent_low <= tp2: _update_signal_outcome(conn, dict(signal), 'TP2_HIT', tp2)
                        elif recent_low <= tp1: _update_signal_outcome(conn, dict(signal), 'TP1_HIT', tp1)
                            
                except Exception as e:
                    logger.error(f"❌ Error processing signal outcome ({signal['symbol']}): {e}", exc_info=True)
    except sqlite3.Error as e:
        logger.error(f"❌ DB write operation failed: {e}", exc_info=True)
