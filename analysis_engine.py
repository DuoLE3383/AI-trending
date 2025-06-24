# analysis_engine.py
import pandas as pd
import pandas_ta as ta 
import sqlite3
import logging
from typing import Dict, Any

# Import a_variables from config.py
from config import *
# Ensure SIGNAL_TABLE_NAME is imported from config.py
try:
    SIGNAL_TABLE_NAME
except NameError:
    from config import SIGNAL_TABLE_NAME
# Import data retrieval function
from market_data_handler import get_market_data
# Import AsyncClient for correct type hinting
from binance import AsyncClient

logger = logging.getLogger(__name__)

def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
    """
    Private function to save a signal to the SQLite database.
    Separating this logic keeps the main function cleaner.
    """
    sql_insert = f"""
    INSERT INTO {SIGNAL_TABLE_NAME} (
        analysis_timestamp_utc, symbol, timeframe, last_price,
        ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val,
        rsi_len, rsi_val, trend, kline_open_time,
        bbands_lower, bbands_middle, bbands_upper, atr_val,
        entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

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
    Performs technical analysis on a given DataFrame.
    This is the core processing logic, with no network or I/O operations.
    """
    if df.empty or len(df) < EMA_SLOW:
        logger.warning(f"Skipping analysis for {symbol}: not enough data points ({len(df)} rows).")
        return

    # --- 1. Calculate technical indicators ---
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    df.ta.sma(length=VOLUME_SMA_PERIOD, close='volume', prefix='VOLUME', append=True)

    last = df.iloc[-1]
    price = last.get('close')
    if price is None:
        logger.error(f"Could not get 'close' price for {symbol}.")
        return

    # --- 2. Apply strategy filters ---
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    # ROBUSTNESS: Ensure atr_value is not None before using it
    if atr_value is None:
        logger.warning(f"Skipping analysis for {symbol}: ATR value is None.")
        return
        
    atr_percent = (atr_value / price) * 100 if price > 0 else 0
    if atr_percent < MIN_ATR_PERCENT:
        logger.debug(f"{symbol}: Skipping. Low volatility (ATR: {atr_percent:.2f}%).")
        return

    current_volume = last.get('volume')
    volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
    if current_volume is None or volume_sma is None or current_volume < (volume_sma * MIN_VOLUME_RATIO):
        logger.debug(f"{symbol}: Skipping. Low volume (Current: {current_volume} < SMA: {volume_sma}).")
        return

    # --- 3. Trend determination logic ---
    ema_f = last.get(f'EMA_{EMA_FAST}')
    ema_m = last.get(f'EMA_{EMA_MEDIUM}')
    ema_s = last.get(f'EMA_{EMA_SLOW}')
    trend = TREND_SIDEWAYS
    
    # ROBUSTNESS: Ensure EMA values exist before comparing them to prevent TypeError
    if any(v is None for v in [price, ema_f, ema_m, ema_s]):
        logger.warning(f"Skipping trend analysis for {symbol}: One or more EMA values are None.")
        return

    # Trend conditions
    if price > ema_f > ema_m > ema_s:
        trend = TREND_STRONG_BULLISH
    elif price < ema_f < ema_m < ema_s:
        trend = TREND_STRONG_BEARISH
    elif price > ema_s and ema_f > ema_m:
        trend = TREND_BULLISH
    elif price < ema_s and ema_f < ema_m:
        trend = TREND_BEARISH
    
    # --- 4. Calculate Entry/SL/TP and Save if a strong signal is found ---
    if trend.startswith("STRONG"):
        entry = price
        if trend == TREND_STRONG_BULLISH:
            sl = entry - (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry + (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry + (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry + (atr_value * ATR_MULTIPLIER_TP3)
        else:  # TREND_STRONG_BEARISH
            sl = entry + (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry - (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry - (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry - (atr_value * ATR_MULTIPLIER_TP3)

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
        _save_signal_to_db(signal_data)
    else:
        logger.debug(f"{symbol}: Analysis complete. Trend is '{trend}', no strong signal generated.")

async def process_symbol(client: AsyncClient, symbol: str) -> None:
    """
    Entry-point function: Fetches market data for a symbol and then performs analysis.
    This function will be called from run.py.
    """
    try:
        # Step 1: Get data and create DataFrame
        df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        
        # Step 2: Call the core analysis function with the DataFrame
        if df is not None:
             _perform_analysis(df, symbol)
        else:
            logger.warning(f"Did not perform analysis for {symbol} because no data was returned.")

    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {e}", exc_info=True)
