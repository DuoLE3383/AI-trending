# analysis_engine.py (Phiên bản cuối cùng, tích hợp AI, Rule-Based Fallback, và các chỉ báo mới)
import pandas as pd
import pandas_ta as ta 
import sqlite3
import logging
from typing import Dict, Any, List, Optional

# Import các type hint cho model
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# Import các biến và hàm cần thiết
from config import *
from market_data_handler import get_market_data
from binance import AsyncClient

logger = logging.getLogger(__name__)

def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
    """
    Lưu tín hiệu vào database SQLite.
    Đã được cập nhật để lưu tất cả các cột, bao gồm cả các chỉ báo mới.
    """
    # SỬA LỖI & HOÀN THIỆN: Câu lệnh INSERT đã được sửa và có đủ cột
    sql_insert = """
    INSERT INTO trend_analysis (
        analysis_timestamp_utc, symbol, timeframe, last_price, timestamp_utc,
        ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val,
        rsi_len, rsi_val, trend, kline_open_time,
        bbands_lower, bbands_middle, bbands_upper, atr_val,
        macd, macd_signal, macd_hist, adx,
        entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status, method
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    
    db_values = (
        signal_data.get('analysis_time'), signal_data.get('symbol'), signal_data.get('timeframe'), signal_data.get('price'),
        signal_data.get('kline_timestamp'),
        signal_data.get('ema_fast_len'), signal_data.get('ema_fast_val'), signal_data.get('ema_medium_len'), signal_data.get('ema_medium_val'), signal_data.get('ema_slow_len'), signal_data.get('ema_slow_val'),
        signal_data.get('rsi_len'), signal_data.get('rsi_val'), signal_data.get('trend'), signal_data.get('kline_time'),
        signal_data.get('bb_lower'), signal_data.get('bb_middle'), signal_data.get('bb_upper'), signal_data.get('atr'),
        signal_data.get('macd'), signal_data.get('macd_signal'), signal_data.get('macd_hist'), signal_data.get('adx'),
        signal_data.get('entry'), signal_data.get('sl'), signal_data.get('tp1'), signal_data.get('tp2'), signal_data.get('tp3'), 'ACTIVE',
        signal_data.get('method') # Lưu lại phương pháp đã dùng
    )

    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
        log_method = signal_data.get("method", "Unknown")
        logger.info(f"✅ ({log_method}) Signal Saved for {signal_data['symbol']}: Trend={signal_data['trend']}")
    except sqlite3.Error as e:
        logger.error(f"❌ Error saving analysis for {signal_data['symbol']} to DB: {e}", exc_info=True)


def _perform_analysis(
    df: pd.DataFrame, 
    symbol: str, 
    model: Optional[RandomForestClassifier], 
    label_encoder: Optional[LabelEncoder],
    model_features: Optional[List[str]]
) -> None:
    """
    Thực hiện phân tích với 2 chế độ: AI (nếu có model) hoặc Dựa trên quy tắc (dự phòng).
    """
    if df.empty or len(df) < EMA_SLOW: return

    # --- 1. Tính toán tất cả các chỉ báo kỹ thuật ---
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    df.ta.sma(length=VOLUME_SMA_PERIOD, close='volume', prefix='VOLUME', append=True)
    df.ta.macd(fast=MACD_FAST_PERIOD, slow=MACD_SLOW_PERIOD, signal=MACD_SIGNAL_PERIOD, append=True)
    df.ta.adx(length=ADX_PERIOD, append=True)
    
    last = df.iloc[-1]
    last_but_one = df.iloc[-2]
    price = last.get('close')
    if price is None: return

    # --- 2. Áp dụng các bộ lọc cơ bản ---
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    if atr_value is None or atr_value == 0: return
    if (atr_value / price) * 100 < MIN_ATR_PERCENT: return
    current_volume = last.get('volume')
    volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
    if current_volume is None or volume_sma is None or current_volume < (volume_sma * MIN_VOLUME_RATIO): return

    trend = TREND_SIDEWAYS
    analysis_method = ""

    # --- 3. CHỌN CHẾ ĐỘ PHÂN TÍCH ---
    if all([model, label_encoder, model_features]):
        # <<< CHẾ ĐỘ AI >>>
        analysis_method = "AI"
        features_for_prediction = [last.get(feature_name) for feature_name in model_features]
        if any(v is None for v in features_for_prediction): return

        prediction_encoded = model.predict([features_for_prediction])
        trend = label_encoder.inverse_transform(prediction_encoded)[0]
    else:
        # <<< CHẾ ĐỘ DỰ PHÒNG: DỰA TRÊN QUY TẮC EMA >>>
        analysis_method = "Rule-Based"
        if not all(k in last for k in [f'EMA_{EMA_FAST}', f'EMA_{EMA_MEDIUM}', f'EMA_{EMA_SLOW}']): return
        ema_f, ema_m, ema_s = last[f'EMA_{EMA_FAST}'], last[f'EMA_{EMA_MEDIUM}'], last[f'EMA_{EMA_SLOW}']
        
        if price > ema_f > ema_m > ema_s: trend = TREND_STRONG_BULLISH
        elif price < ema_f < ema_m < ema_s: trend = TREND_STRONG_BEARISH
        elif price > ema_s and ema_f > ema_m: trend = TREND_BULLISH
        elif price < ema_s and ema_f < ema_m: trend = TREND_BEARISH

    # --- 4. KIỂM TRA XÁC NHẬN VÀ LƯU TÍN HIỆU ---
    if trend.startswith("STRONG"):
        # Đối với tín hiệu AI, có thể thêm bộ lọc xác nhận MACD/ADX
        if analysis_method == "AI":
            macd = last.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}')
            macd_signal = last.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}')
            adx = last.get(f'ADX_{ADX_PERIOD}')
            if not all([macd, macd_signal, adx]): return # Bỏ qua nếu thiếu dữ liệu

            is_confirmed = False
            if trend == TREND_STRONG_BULLISH and adx > ADX_MIN_TREND_STRENGTH:
                if macd > macd_signal and last_but_one.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}') <= last_but_one.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'):
                    is_confirmed = True
            elif trend == TREND_STRONG_BEARISH and adx > ADX_MIN_TREND_STRENGTH:
                if macd < macd_signal and last_but_one.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}') >= last_but_one.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'):
                    is_confirmed = True
            
            if not is_confirmed:
                logger.info(f"{symbol}: AI predicted '{trend}', but confirmation (MACD/ADX) failed.")
                return

        # Tính toán Entry/SL/TP và tạo dữ liệu để lưu
        entry = price
        if trend == TREND_STRONG_BULLISH:
            sl = entry - (atr_value * ATR_MULTIPLIER_SL)
            tp1, tp2, tp3 = entry + (atr_value * ATR_MULTIPLIER_TP1), entry + (atr_value * ATR_MULTIPLIER_TP2), entry + (atr_value * ATR_MULTIPLIER_TP3)
        else: # TREND_STRONG_BEARISH
            sl = entry + (atr_value * ATR_MULTIPLIER_SL)
            tp1, tp2, tp3 = entry - (atr_value * ATR_MULTIPLIER_TP1), entry - (atr_value * ATR_MULTIPLIER_TP2), entry - (atr_value * ATR_MULTIPLIER_TP3)

        signal_data = {
            "analysis_time": pd.to_datetime('now', utc=True).isoformat(), "symbol": symbol, "timeframe": TIMEFRAME, "price": price,
            "kline_time": last.name.isoformat(), "kline_timestamp": last.name.timestamp(),
            "ema_fast_len": EMA_FAST, "ema_fast_val": last.get(f'EMA_{EMA_FAST}'),
            "ema_medium_len": EMA_MEDIUM, "ema_medium_val": last.get(f'EMA_{EMA_MEDIUM}'),
            "ema_slow_len": EMA_SLOW, "ema_slow_val": last.get(f'EMA_{EMA_SLOW}'),
            "rsi_len": RSI_PERIOD, "rsi_val": last.get(f'RSI_{RSI_PERIOD}'), "trend": trend, "method": analysis_method,
            "bb_lower": last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_middle": last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_upper": last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            "atr": atr_value, "macd": last.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "macd_signal": last.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "macd_hist": last.get(f'MACDh_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "adx": last.get(f'ADX_{ADX_PERIOD}'),
            "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
        }
        _save_signal_to_db(signal_data)
    else:
        logger.info(f"{symbol}: ({analysis_method}) Analysis complete. Trend is '{trend}', no strong signal generated.")


async def process_symbol(
    client: AsyncClient, 
    symbol: str, 
    model: Optional[RandomForestClassifier], 
    label_encoder: Optional[LabelEncoder],
    model_features: Optional[List[str]]
) -> None:
    """Hàm đầu vào: Lấy dữ liệu và gọi hàm phân tích."""
    try:
        df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        if df is not None and not df.empty:
             _perform_analysis(df, symbol, model, label_encoder, model_features)
    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {e}", exc_info=True)
