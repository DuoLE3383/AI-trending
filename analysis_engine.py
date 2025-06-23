# analysis_engine.py
import pandas as pd
import pandas_ta as ta
import sqlite3
import logging
from typing import Dict, Any

# Import các biến cấu hình từ config.py
from config import *
# Import hàm lấy dữ liệu (giả định nó nằm trong market_data_handler.py)
from market_data_handler import get_market_data
# Import Client để dùng cho type hinting
from binance.client import Client

logger = logging.getLogger(__name__)

def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
    """
    Hàm riêng tư để lưu một tín hiệu vào database SQLite.
    Tách biệt logic này giúp hàm chính gọn gàng hơn.
    """
    # Câu lệnh SQL được định dạng lại cho dễ đọc
    sql_insert = """
    INSERT INTO trend_analysis (
        analysis_timestamp_utc, symbol, timeframe, last_price,
        ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val,
        rsi_len, rsi_val, trend, kline_open_time,
        bbands_lower, bbands_middle, bbands_upper, atr_val,
        entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    
    # Chuẩn bị tuple giá trị theo đúng thứ tự của câu lệnh INSERT
    db_values = (
        signal_data['analysis_time'], signal_data['symbol'], signal_data['timeframe'], signal_data['price'],
        signal_data['ema_fast_len'], signal_data['ema_fast_val'], signal_data['ema_medium_len'], signal_data['ema_medium_val'], signal_data['ema_slow_len'], signal_data['ema_slow_val'],
        signal_data['rsi_len'], signal_data['rsi_val'], signal_data['trend'], signal_data['kline_time'],
        signal_data['bb_lower'], signal_data['bb_middle'], signal_data['bb_upper'], signal_data['atr'],
        signal_data['entry'], signal_data['sl'], signal_data['tp1'], signal_data['tp2'], signal_data['tp3'], 'ACTIVE'
    )

    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
        logger.info(f"✅ Strong Signal Saved for {signal_data['symbol']}: Trend={signal_data['trend']}")
    except sqlite3.Error as e:
        logger.error(f"❌ Error saving analysis for {signal_data['symbol']} to DB: {e}", exc_info=True)

def _perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """
    Thực hiện phân tích kỹ thuật trên một DataFrame đã có.
    Hàm này là lõi xử lý, không chịu trách nhiệm lấy dữ liệu hay kết nối mạng.
    """
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points ({len(df)} rows).")
        return

    # --- 1. Tính toán các chỉ báo kỹ thuật ---
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    df.ta.sma(length=VOLUME_SMA_PERIOD, close='volume', prefix='VOLUME', append=True)

    # Lấy dòng dữ liệu cuối cùng để phân tích
    last = df.iloc[-1]
    price = last.get('close')
    if price is None:
        logger.error(f"Could not get 'close' price for {symbol}.")
        return

    # --- 2. Áp dụng các bộ lọc chiến lược ---
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    atr_percent = (atr_value / price) * 100 if price > 0 else 0
    if atr_percent < MIN_ATR_PERCENT:
        logger.debug(f"{symbol}: Skipping. Low volatility (ATR: {atr_percent:.2f}%).")
        return

    current_volume = last.get('volume')
    volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
    if current_volume < (volume_sma * MIN_VOLUME_RATIO):
        logger.debug(f"{symbol}: Skipping. Low volume (Current: {current_volume:.0f} < SMA: {volume_sma:.0f}).")
        return

    # --- 3. Logic xác định xu hướng (Đã được hoàn thiện) ---
    ema_f = last.get(f'EMA_{EMA_FAST}')
    ema_m = last.get(f'EMA_{EMA_MEDIUM}')
    ema_s = last.get(f'EMA_{EMA_SLOW}')
    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None

    # Điều kiện cho tín hiệu MẠNH
    if price > ema_f > ema_m > ema_s:
        trend = TREND_STRONG_BULLISH
    elif price < ema_f < ema_m < ema_s:
        trend = TREND_STRONG_BEARISH
    # Điều kiện cho tín hiệu THƯỜNG (không lưu vào DB nhưng có thể dùng để theo dõi)
    elif price > ema_s and ema_f > ema_m:
        trend = TREND_BULLISH
    elif price < ema_s and ema_f < ema_m:
        trend = TREND_BEARISH
    
    # --- 4. Tính toán Entry/SL/TP và Lưu kết quả vào DB nếu là tín hiệu MẠNH ---
    if trend.startswith("STRONG"):
        entry = price
        if trend == TREND_STRONG_BULLISH:
            sl = entry - (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry + (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry + (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry + (atr_value * ATR_MULTIPLIER_TP3)
        else: # TREND_STRONG_BEARISH
            sl = entry + (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry - (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry - (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry - (atr_value * ATR_MULTIPLIER_TP3)

        # Tạo một dictionary chứa tất cả dữ liệu tín hiệu
        signal_data = {
            "analysis_time": pd.to_datetime('now', utc=True).isoformat(),
            "symbol": symbol, "timeframe": TIMEFRAME, "price": price,
            "ema_fast_len": EMA_FAST, "ema_fast_val": ema_f,
            "ema_medium_len": EMA_MEDIUM, "ema_medium_val": ema_m,
            "ema_slow_len": EMA_SLOW, "ema_slow_val": ema_s,
            "rsi_len": RSI_PERIOD, "rsi_val": last.get(f'RSI_{RSI_PERIOD}'),
            "trend": trend, "kline_time": last.name.isoformat(),
            "bb_lower": last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            "bb_middle": last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            "bb_upper": last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            "atr": atr_value, "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3
        }
        # Gọi hàm để lưu vào DB
        _save_signal_to_db(signal_data)
    else:
        logger.debug(f"{symbol}: Analysis complete. Trend is '{trend}', no strong signal generated.")

async def process_symbol(client: Client, symbol: str) -> None:
    """
    Hàm entry-point: Lấy dữ liệu thị trường cho một symbol và sau đó thực hiện phân tích.
    Hàm này sẽ được gọi từ run.py.
    """
    try:
        # Bước 1: Lấy dữ liệu và tạo DataFrame
        df = await get_market_data(client, symbol, TIMEFRAME, limit=DATA_FETCH_LIMIT)
        
        # Bước 2: Gọi hàm phân tích lõi với DataFrame vừa có
        _perform_analysis(df, symbol)

    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {e}", exc_info=True)

