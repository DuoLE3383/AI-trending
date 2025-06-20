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
    ATR_MULTIPLIER_SHORT, ATR_MULTIPLIER_LONG, TIMEFRAME, SQLITE_DB_PATH
)

logger = logging.getLogger(__name__)

async def perform_analysis(df: pd.DataFrame, symbol: str) -> None:
    """Calculates all indicators and saves the complete record to the database."""
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points.")
        return

    # Calculate Indicators
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)

    required_cols = [
        f'EMA_{EMA_FAST}', f'EMA_{EMA_MEDIUM}', f'EMA_{EMA_SLOW}',
        f'RSI_{RSI_PERIOD}', f'ATRr_{ATR_PERIOD}',
        f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}',
        f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'
    ]
    if not all(col in df.columns for col in required_cols):
        logger.error(f"Missing one or more indicator columns for {symbol}. Skipping analysis.")
        return

    last = df.iloc[-1]
    price = last.get('close')
    ema_f, ema_m, ema_s = last.get(f'EMA_{EMA_FAST}'), last.get(f'EMA_{EMA_MEDIUM}'), last.get(f'EMA_{EMA_SLOW}')
    rsi, atr = last.get(f'RSI_{RSI_PERIOD}'), last.get(f'ATRr_{ATR_PERIOD}')
    bb_l, bb_m, bb_u = last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}')

    trend, entry, sl, tp1, tp2, tp3 = TREND_SIDEWAYS, None, None, None, None, None

    if all(pd.notna(v) for v in [price, ema_f, ema_m, ema_s, atr]):
        if price > ema_f > ema_m > ema_s:
            trend, entry = TREND_STRONG_BULLISH, price
            sl, tp1, tp2, tp3 = entry * (1 - ATR_MULTIPLIER_SL * atr / price), entry * (1 + ATR_MULTIPLIER_TP1 * atr / price), entry * (1 + ATR_MULTIPLIER_TP2 * atr / price), entry * (1 + ATR_MULTIPLIER_TP3 * atr / price)
        elif price < ema_f < ema_m < ema_s:
            trend, entry = TREND_STRONG_BEARISH, price
            sl, tp1, tp2, tp3 = entry * (1 + ATR_MULTIPLIER_SL * atr / price), entry * (1 - ATR_MULTIPLIER_TP1 * atr / price), entry * (1 - ATR_MULTIPLIER_TP2 * atr / price), entry * (1 - ATR_MULTIPLIER_TP3 * atr / price)
        elif price > ema_s and price > ema_m:
            trend = TREND_BULLISH
        elif price < ema_s and price < ema_m:
            trend = TREND_BEARISH

    p_s_l, p_s_h = (price - ATR_MULTIPLIER_SHORT * atr, price + ATR_MULTIPLIER_SHORT * atr) if pd.notna(atr) and pd.notna(price) else (None, None)
    p_l_l, p_l_h = (price - ATR_MULTIPLIER_LONG * atr, price + ATR_MULTIPLIER_LONG * atr) if pd.notna(atr) and pd.notna(price) else (None, None)

    db_values = (
        pd.to_datetime('now', utc=True).isoformat(), symbol, TIMEFRAME, price,
        EMA_FAST, ema_f, EMA_MEDIUM, ema_m, EMA_SLOW, ema_s, RSI_PERIOD, rsi, trend,
        last.name.isoformat(), bb_l, bb_m, bb_u, atr, p_s_l, p_s_h, p_l_l, p_l_h,
        entry, sl, tp1, tp2, tp3
    )
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute("INSERT INTO trend_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", db_values)
        logger.info(f"💾 Analysis saved for {symbol} ({TIMEFRAME}): Trend={trend}")
    except sqlite3.Error as e:
        logger.error(f"Error saving analysis for {symbol} to DB: {e}", exc_info=True)