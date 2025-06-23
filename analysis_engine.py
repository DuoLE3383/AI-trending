# analysis_engine.py
import pandas as pd
import pandas_ta as ta
import sqlite3
import logging
from config import * # Import tất cả cấu hình

logger = logging.getLogger(__name__)

async def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points.")
        return

    # 1. Tính toán các chỉ báo
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    df.ta.sma(length=20, close='volume', prefix='VOLUME', append=True) # Volume SMA

    last = df.iloc[-1]
    price = last.get('close')
    
    # 2. Áp dụng các bộ lọc chiến lược
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    atr_percent = (atr_value / price) * 100 if price > 0 else 0
    if atr_percent < MIN_ATR_PERCENT:
        logger.debug(f"{symbol}: Skipping. Low volatility (ATR: {atr_percent:.2f}%).")
        return

    current_volume = last.get('volume')
    volume_sma = last.get('VOLUME_SMA_20')
    if current_volume < volume_sma:
        logger.debug(f"{symbol}: Skipping. Low volume.")
        return

    # 3. Logic xác định xu hướng
    ema_f, ema_m, ema_s = last.get(f'EMA_{EMA_FAST}'), last.get(f'EMA_{EMA_MEDIUM}'), last.get(f'EMA_{EMA_SLOW}')
    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None

    if price > ema_f > ema_m > ema_s:
        trend, entry = TREND_STRONG_BULLISH, price
        sl = entry - (atr_value * ATR_MULTIPLIER_SL)
        tp1 = entry + (atr_value * ATR_MULTIPLIER_TP1)
        tp2 = entry + (atr_value * ATR_MULTIPLIER_TP2)
        tp3 = entry + (atr_value * ATR_MULTIPLIER_TP3)
    elif price < ema_f < ema_m < ema_s:
        trend, entry = TREND_STRONG_BEARISH, price
        sl = entry + (atr_value * ATR_MULTIPLIER_SL)
        tp1 = entry - (atr_value * ATR_MULTIPLIER_TP1)
        tp2 = entry - (atr_value * ATR_MULTIPLIER_TP2)
        tp3 = entry - (atr_value * ATR_MULTIPLIER_TP3)
    # ... (Các logic trend khác nếu có)

    # 4. Lưu kết quả vào database
    if trend.startswith("STRONG"):
        db_values = (
            pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
            EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, last.get(f'RSI_{RSI_PERIOD}'), trend,
            last.name.isoformat(), last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            atr_value, None, None, None, None, # Bỏ qua các proj_range cũ
            entry, sl, tp1, tp2, tp3, 'ACTIVE'
        )
        sql_insert = "INSERT INTO trend_analysis (analysis_timestamp_utc, symbol, timeframe, last_price, ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val, rsi_len, rsi_val, trend, kline_open_time, bbands_lower, bbands_middle, bbands_upper, atr_val, proj_range_short_low, proj_range_short_high, proj_range_long_low, proj_range_long_high, entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        try:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                conn.execute(sql_insert, db_values)
            logger.info(f"✅ Strong Signal Saved for {symbol}: Trend={trend}")
        except sqlite3.Error as e:
            logger.error(f"Error saving analysis for {symbol} to DB: {e}")
