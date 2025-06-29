# analysis_engine.py (Phiên bản đã hoàn thiện logic cho cả 2 chiến lược)
import pandas as pd
import pandas_ta as ta 
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from functools import reduce

# Import các type hint cho model
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# Import các biến và hàm cần thiết
from .config import *
from .market_data_handler import get_market_data
from binance import AsyncClient

logger = logging.getLogger(__name__)

# --- HÀM HELPER CHUNG ---

def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
    """Lưu tín hiệu được tạo ra từ bất kỳ chiến lược nào vào database."""
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
        signal_data.get('method', 'Unknown')
    )
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
        logger.info(f"✅ ({signal_data.get('method')}) Signal Saved for {signal_data['symbol']}: Trend={signal_data['trend']}")
    except sqlite3.Error as e:
        logger.error(f"❌ Error saving analysis for {signal_data['symbol']} to DB: {e}", exc_info=True)

# === CHIẾN LƯỢC 1: AI / FALLBACK =============================================

async def perform_ai_fallback_analysis(
    client: AsyncClient, 
    symbol: str, 
    model: Optional[RandomForestClassifier], 
    label_encoder: Optional[LabelEncoder],
    model_features: Optional[List[str]]
) -> None:
    """
    Hàm chính cho chiến lược AI/Fallback, đã được hoàn thiện.
    """
    try:
        df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        if df is None or df.empty or len(df) < EMA_SLOW: return

        # 1. Tính toán tất cả các chỉ báo kỹ thuật
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
        price = last.get('close')
        if price is None: return

        # 2. Áp dụng các bộ lọc cơ bản
        atr_value = last.get(f'ATRr_{ATR_PERIOD}')
        if atr_value is None or atr_value == 0: return
        if (atr_value / price) * 100 < MIN_ATR_PERCENT: return
        current_volume = last.get('volume')
        volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
        if current_volume is None or volume_sma is None or current_volume < (volume_sma * MIN_VOLUME_RATIO): return

        trend = TREND_SIDEWAYS
        analysis_method = ""

        # 3. CHỌN CHẾ ĐỘ PHÂN TÍCH
        if all([model, label_encoder, model_features]):
            analysis_method = "AI"
            features_for_prediction = [last.get(feature_name) for feature_name in model_features]
            if any(v is None for v in features_for_prediction): return
            prediction_encoded = model.predict([features_for_prediction])
            trend = label_encoder.inverse_transform(prediction_encoded)[0]
        else:
            analysis_method = "Rule-Based"
            if not all(k in last for k in [f'EMA_{EMA_FAST}', f'EMA_{EMA_MEDIUM}', f'EMA_{EMA_SLOW}']): return
            ema_f, ema_m, ema_s = last[f'EMA_{EMA_FAST}'], last[f'EMA_{EMA_MEDIUM}'], last[f'EMA_{EMA_SLOW}']
            if price > ema_f > ema_m > ema_s: trend = TREND_STRONG_BULLISH
            elif price < ema_f < ema_m < ema_s: trend = TREND_STRONG_BEARISH
            elif price > ema_s and ema_f > ema_m: trend = TREND_BULLISH
            elif price < ema_s and ema_f < ema_m: trend = TREND_BEARISH

        # 4. TÍNH TOÁN VÀ LƯU TÍN HIỆU
        if trend.startswith("STRONG"):
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
                "ema_fast_len": EMA_FAST, "ema_fast_val": last.get(f'EMA_{EMA_FAST}'), "ema_medium_len": EMA_MEDIUM, "ema_medium_val": last.get(f'EMA_{EMA_MEDIUM}'), "ema_slow_len": EMA_SLOW, "ema_slow_val": last.get(f'EMA_{EMA_SLOW}'),
                "rsi_len": RSI_PERIOD, "rsi_val": last.get(f'RSI_{RSI_PERIOD}'), "trend": trend, "method": analysis_method,
                "bb_lower": last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_middle": last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_upper": last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
                "atr": atr_value, "macd": last.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "macd_signal": last.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "macd_hist": last.get(f'MACDh_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "adx": last.get(f'ADX_{ADX_PERIOD}'),
                "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
            }
            _save_signal_to_db(signal_data)
        else:
            logger.info(f"{symbol}: ({analysis_method}) Analysis complete. Trend is '{trend}', no strong signal generated.")

    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL {symbol} with AI/Fallback: {e}", exc_info=True)


# === CHIẾN LƯỢC 2: ELLIOTV8 =================================================

def _ewo_indicator(dataframe, ema_length=5, ema2_length=35):
    """Hàm tính chỉ báo Elliot Wave Oscillator."""
    df = dataframe.copy(); ema1 = ta.ema(df["close"], length=ema_length); ema2 = ta.ema(df["close"], length=ema2_length)
    return (ema1 - ema2) / df['close'] * 100

async def perform_elliotv8_analysis(client: AsyncClient, symbol: str) -> None:
    """Hàm chính cho chiến lược Elliotv8."""
    try:
        df = await get_market_data(client, symbol, '15m', limit=400)
        if df is None or df.empty or len(df) < 200: return

        # 1. Lấy thông số
        base_nb_candles_buy, low_offset, ewo_low, ewo_high, rsi_buy_value, base_nb_candles_sell, high_offset_sell = 14, 0.975, -19.988, 2.327, 69, 24, 0.991

        # 2. Tính toán chỉ báo
        df[f'ma_buy_{base_nb_candles_buy}'] = ta.ema(df["close"], length=base_nb_candles_buy)
        df[f'ma_sell_{base_nb_candles_sell}'] = ta.ema(df["close"], length=base_nb_candles_sell)
        df['EWO'] = _ewo_indicator(df, 50, 200)
        df['rsi'] = ta.rsi(df["close"], length=13)
        df['rsi_fast'] = ta.rsi(df["close"], length=4)
        df['atr'] = ta.atr(df["high"], df["low"], df["close"], length=ATR_PERIOD)

        last, price = df.iloc[-1], df.iloc[-1]['close']
        
        # 3. Áp dụng logic vào lệnh
        buy_conditions = [
            ((last['rsi_fast'] < 35) & (last['close'] < (last[f'ma_buy_{base_nb_candles_buy}'] * low_offset)) & (last['EWO'] > ewo_high) & (last['rsi'] < rsi_buy_value)),
            ((last['rsi_fast'] < 35) & (last['close'] < (last[f'ma_buy_{base_nb_candles_buy}'] * low_offset)) & (last['EWO'] < ewo_low))
        ]
        should_buy = reduce(lambda x, y: x | y, buy_conditions)

        # 4. Tính toán và lưu tín hiệu nếu có
        if should_buy and last['volume'] > 0 and (last['close'] < (last[f'ma_sell_{base_nb_candles_sell}'] * high_offset_sell)):
            atr_value = last.get('atr')
            if atr_value is None or atr_value == 0: return
            entry, trend = price, TREND_STRONG_BULLISH
            sl = entry - (atr_value * ATR_MULTIPLIER_SL)
            tp1, tp2, tp3 = entry + (atr_value * ATR_MULTIPLIER_TP1), entry + (atr_value * ATR_MULTIPLIER_TP2), entry + (atr_value * ATR_MULTIPLIER_TP3)
            signal_data = {
                "analysis_time": pd.to_datetime('now', utc=True).isoformat(), "symbol": symbol, "timeframe": '5m', "price": price,
                "kline_time": last.name.isoformat(), "kline_timestamp": last.name.timestamp(),
                "trend": trend, "atr": atr_value, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "method": "Elliotv8"
            }
            _save_signal_to_db(signal_data)
        else:
            logger.info(f"{symbol}: (Elliotv8) Analysis complete. No buy signal generated.")
    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL {symbol} with Elliotv8: {e}", exc_info=True)
