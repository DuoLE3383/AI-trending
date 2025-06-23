import pandas as pd
import pandas_ta as ta
import sqlite3
import logging

# Import constants and config needed for analysis
from config import (
    EMA_FAST, EMA_MEDIUM, EMA_SLOW,
    RSI_PERIOD, BBANDS_PERIOD, BBANDS_STD_DEV, ATR_PERIOD,
    TREND_STRONG_BULLISH, TREND_STRONG_BEARISH, TREND_BULLISH, TREND_BEARISH, TREND_SIDEWAYS,
    ATR_MULTIPLIER_SL, ATR_MULTIPLIER_TP1, ATR_MULTIPLIER_TP2, ATR_MULTIPLIER_TP3,
    ATR_MULTIPLIER_SHORT, ATR_MULTIPLIER_LONG, TIMEFRAME, SQLITE_DB_PATH,
    MIN_ATR_PERCENT  # <-- Make sure to import the new config value
)

logger = logging.getLogger(__name__)

async def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """
    Calculates all indicators, applies strategy filters, 
    and saves the complete record to the database.
    """
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points.")
        return

    # --- 1. Indicator Calculation ---
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    
    # Add Volume SMA for our new strategy rule
    df.ta.sma(length=20, close='volume', prefix='VOLUME', append=True)

    # --- 2. Data Validation and Extraction ---
    required_cols = [
        f'EMA_{EMA_FAST}', f'EMA_{EMA_MEDIUM}', f'EMA_{EMA_SLOW}', f'RSI_{RSI_PERIOD}',
        f'ATRr_{ATR_PERIOD}', f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}', f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        'VOLUME_SMA_20'
    ]
    if not all(col in df.columns for col in required_cols) or df.isnull().values.any():
        logger.warning(f"Missing one or more indicator columns for {symbol} after calculation. Skipping.")
        return

    last = df.iloc[-1]
    price = last.get('close')
    
    # --- 3. STRATEGY UPGRADE: APPLY FILTERS ---

    # -- VOLATILITY FILTER --
    # Purpose: Avoid trading in sideways or "choppy" markets with no clear momentum.
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    atr_percent = (atr_value / price) * 100 if price > 0 else 0
    
    if atr_percent < MIN_ATR_PERCENT:
        logger.debug(f"{symbol}: Skipping. Low volatility (ATR: {atr_percent:.2f}%) below threshold ({MIN_ATR_PERCENT}%).")
        # We don't save anything to the database because the market is not worth trading.
        return

    # -- VOLUME FILTER --
    # Purpose: Ensure that price movements are supported by significant trading activity.
    current_volume = last.get('volume')
    volume_sma = last.get('VOLUME_SMA_20')

    if current_volume < volume_sma:
        logger.debug(f"{symbol}: Skipping. Low volume ({current_volume:.0f}) below 20-period average ({volume_sma:.0f}).")
        # We don't save anything because the move is not confirmed by volume.
        return

    # --- 4. Core Trend Logic (Only runs if filters pass) ---
    logger.info(f"{symbol}: Passed all strategy filters. Evaluating trend.")
    ema_f, ema_m, ema_s = last.get(f'EMA_{EMA_FAST}'), last.get(f'EMA_{EMA_MEDIUM}'), last.get(f'EMA_{EMA_SLOW}')
    rsi = last.get(f'RSI_{RSI_PERIOD}')
    bb_l, bb_m, bb_u = last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')

    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None

    if all(pd.notna(v) for v in [price, ema_f, ema_m, ema_s, atr_value]):
        # Your original EMA Crossover logic is here
        if price > ema_f > ema_m > ema_s:
            trend, entry = TREND_STRONG_BULLISH, price
            sl, tp1, tp2, tp3 = entry * (1 - ATR_MULTIPLIER_SL * atr_value / price), entry * (1 + ATR_MULTIPLIER_TP1 * atr_value / price), entry * (1 + ATR_MULTIPLIER_TP2 * atr_value / price), entry * (1 + ATR_MULTIPLIER_TP3 * atr_value / price)
        elif price < ema_f < ema_m < ema_s:
            trend, entry = TREND_STRONG_BEARISH, price
            sl, tp1, tp2, tp3 = entry * (1 + ATR_MULTIPLIER_SL * atr_value / price), entry * (1 - ATR_MULTIPLIER_TP1 * atr_value / price), entry * (1 - ATR_MULTIPLIER_TP2 * atr_value / price), entry * (1 - ATR_MULTIPLIER_TP3 * atr_value / price)
        elif price > ema_s and price > ema_m:
            trend = TREND_BULLISH
        elif price < ema_s and price < ema_m:
            trend = TREND_BEARISH

    p_s_l, p_s_h = (price - ATR_MULTIPLIER_SHORT * atr_value, price + ATR_MULTIPLIER_SHORT * atr_value)
    p_l_l, p_l_h = (price - ATR_MULTIPLIER_LONG * atr_value, price + ATR_MULTIPLIER_LONG * atr_value)

    # --- 5. Save Results to Database ---
    db_values = (
        pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
        EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, rsi, trend,
        last.name.isoformat(), bb_l, bb_m, bb_u, atr_value, p_s_l, p_s_h, p_l_l, p_l_h,
        entry, sl, tp1, tp2, tp3, 'ACTIVE' # Added 'ACTIVE' for the new status column
    )
    
    # Note: Make sure your INSERT statement matches the number of columns (27 with the new 'status' column)
    sql_insert = "INSERT INTO trend_analysis (analysis_timestamp_utc, symbol, timeframe, last_price, ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val, rsi_len, rsi_val, trend, kline_open_time, bbands_lower, bbands_middle, bbands_upper, atr_val, proj_range_short_low, proj_range_short_high, proj_range_long_low, proj_range_long_high, entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
        if trend.startswith("STRONG"):
             logger.info(f"✅ Strong Signal Saved for {symbol} ({TIMEFRAME}): Trend={trend}")
        else:
             logger.debug(f"💾 Analysis saved for {symbol} ({TIMEFRAME}): Trend={trend}")
    except sqlite3.Error as e:
        logger.error(f"Error saving analysis for {symbol} to DB: {e}", exc_info=True)

