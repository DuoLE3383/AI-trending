# analysis_engine.py (Phiên bản tích hợp 2 chiến lược: AI/Fallback và Elliotv8)
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
from config import *
from market_data_handler import get_market_data
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
    Hàm chính cho chiến lược AI/Fallback.
    Nó lấy dữ liệu và thực hiện phân tích.
    """
    try:
        df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        if df is None or df.empty: return

        # Tính toán tất cả các chỉ báo cần thiết cho chiến lược này
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

        # Logic lọc và xác định trend (như code cũ của bạn)
        # ... (bộ lọc ATR, Volume) ...

        trend = TREND_SIDEWAYS
        analysis_method = ""

        if all([model, label_encoder, model_features]):
            analysis_method = "AI"
            # ... (logic dự đoán của AI) ...
        else:
            analysis_method = "Rule-Based"
            # ... (logic dự phòng bằng EMA) ...
        
        if trend.startswith("STRONG"):
            # ... (logic tính SL/TP và lưu vào DB) ...
            pass # Giữ lại logic chi tiết của bạn ở đây
        
        logger.info(f"{symbol}: (AI/Fallback) Analysis complete. Trend is '{trend}'.")

    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL {symbol} with AI/Fallback: {e}", exc_info=True)


# === CHIẾN LƯỢC 2: ELLIOTV8 =================================================

def _ewo_indicator(dataframe, ema_length=5, ema2_length=35):
    """Hàm tính chỉ báo Elliot Wave Oscillator."""
    df = dataframe.copy()
    ema1 = ta.ema(df["close"], length=ema_length)
    ema2 = ta.ema(df["close"], length=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif

async def perform_elliotv8_analysis(client: AsyncClient, symbol: str) -> None:
    """
    Hàm chính cho chiến lược Elliotv8.
    """
    try:
        # Chiến lược này dùng timeframe 5m và cần nhiều nến hơn
        df = await get_market_data(client, symbol, '5m', limit=400)
        if df is None or df.empty or len(df) < 200: return

        # --- 1. Lấy thông số (có thể đưa vào config.py) ---
        base_nb_candles_buy = 14
        low_offset = 0.975
        ewo_low = -19.988
        ewo_high = 2.327
        rsi_buy_value = 69
        base_nb_candles_sell = 24
        high_offset_sell = 0.991

        # --- 2. Tính toán các chỉ báo cần thiết ---
        df[f'ma_buy_{base_nb_candles_buy}'] = ta.ema(df["close"], length=base_nb_candles_buy)
        df[f'ma_sell_{base_nb_candles_sell}'] = ta.ema(df["close"], length=base_nb_candles_sell)
        df['EWO'] = _ewo_indicator(df, 50, 200)
        df['rsi'] = ta.rsi(df["close"], length=14)
        df['rsi_fast'] = ta.rsi(df["close"], length=4)
        df['atr'] = ta.atr(df["high"], df["low"], df["close"], length=ATR_PERIOD)

        last = df.iloc[-1]
        price = last['close']
        
        # --- 3. Áp dụng logic vào lệnh của Elliotv8 ---
        buy_conditions = [
            (
                (last['rsi_fast'] < 35) &
                (last['close'] < (last[f'ma_buy_{base_nb_candles_buy}'] * low_offset)) &
                (last['EWO'] > ewo_high) &
                (last['rsi'] < rsi_buy_value) &
                (last['volume'] > 0) &
                (last['close'] < (last[f'ma_sell_{base_nb_candles_sell}'] * high_offset_sell))
            ),
            (
                (last['rsi_fast'] < 35) &
                (last['close'] < (last[f'ma_buy_{base_nb_candles_buy}'] * low_offset)) &
                (last['EWO'] < ewo_low) &
                (last['volume'] > 0) &
                (last['close'] < (last[f'ma_sell_{base_nb_candles_sell}'] * high_offset_sell))
            )
        ]
        should_buy = reduce(lambda x, y: x | y, buy_conditions)

        # --- 4. Tính toán và lưu tín hiệu nếu có ---
        if should_buy:
            trend = TREND_STRONG_BULLISH
            atr_value = last.get('atr')
            if atr_value is None or atr_value == 0: return

            entry = price
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
