import logging
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional

# Local imports - ensure these modules are in the same directory
import telegram_handler

# --- Constants for Trend Emojis/Text ---
TREND_STRONG_BULLISH = "✅ #StrongBullish"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_STRONG_BEARISH = "❌ #StrongBearish"
TREND_SIDEWAYS = "Sideways/Undetermined"

logger = logging.getLogger(__name__)

async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any],
    # FIX: Add all expected keyword arguments to the function definition
    bbands_period_const: int,
    bbands_std_dev_const: float,
    atr_period_const: int,
    rsi_period_const: int,
    ema_fast_const: int,
    ema_medium_const: int,
    ema_slow_const: int
) -> None:
    """Sends a detailed, individual alert for a strong trend signal."""
    symbol = analysis_result.get('symbol', 'N/A')
    trend = analysis_result.get('trend', 'N/A')
    price = analysis_result.get('price')
    timeframe = analysis_result.get('timeframe', 'N/A')

    signal_type = " (Contrarian SHORT)" if trend == TREND_STRONG_BULLISH else " (Contrarian LONG)"
    
    message_parts = [
        f"{trend} Signal for {symbol}{signal_type}",
        "_" * 25,
        f"*Analysis ({timeframe} Timeframe)*"
    ]

    price_str = f"${price:,.2f}" if price is not None else "N/A"
    ema_fast_str = f"${analysis_result.get('ema_fast_val'):,.2f}" if analysis_result.get('ema_fast_val') is not None else "N/A"
    ema_medium_str = f"${analysis_result.get('ema_medium_val'):,.2f}" if analysis_result.get('ema_medium_val') is not None else "N/A"
    ema_slow_str = f"${analysis_result.get('ema_slow_val'):,.2f}" if analysis_result.get('ema_slow_val') is not None else "N/A"
    rsi_val = analysis_result.get('rsi_val')
    rsi_str = f"{rsi_val:.2f} ({analysis_result.get('rsi_interpretation', '')})" if rsi_val is not None else "N/A"
    
    message_parts.extend([
        f"  `Price:    {price_str}`",
        f"  `EMA ({ema_fast_const:<3}):   {ema_fast_str}`",
        f"  `EMA ({ema_medium_const:<3}):   {ema_medium_str}`",
        f"  `EMA ({ema_slow_const:<3}):   {ema_slow_str}`",
        f"  `RSI ({rsi_period_const:<3}):   {rsi_str}`",
        "",
        "*Volatility & Projections*"
    ])
    
    bb_lower = analysis_result.get('bb_lower')
    bb_upper = analysis_result.get('bb_upper')
    atr_val = analysis_result.get('atr_value')

    if bb_lower is not None and bb_upper is not None:
        message_parts.append(f"  `BBands ({bbands_period_const}, {bbands_std_dev_const}): ${bb_lower:,.2f} - ${bb_upper:,.2f}`")

    if atr_val is not None:
        proj_low = analysis_result.get('proj_range_short_low')
        proj_high = analysis_result.get('proj_range_short_high')
        message_parts.append(f"  `ATR ({atr_period_const:<3}):    {atr_val:,.4f}`")
        if proj_low is not None and proj_high is not None:
            message_parts.append(f"  `Proj. Range:  ${proj_low:,.2f} - ${proj_high:,.2f}`")

    entry_price = analysis_result.get('entry_price')
    if entry_price is not None:
        sl = analysis_result.get('stop_loss')
        tp1 = analysis_result.get('take_profit_1')
        tp2 = analysis_result.get('take_profit_2')
        tp3 = analysis_result.get('take_profit_3')
        
        sl_str = f"${sl:,.2f}" if sl is not None else "N/A"
        tp1_str = f"${tp1:,.2f}" if tp1 is not None else "N/A"
        tp2_str = f"${tp2:,.2f}" if tp2 is not None else "N/A"
        tp3_str = f"${tp3:,.2f}" if tp3 is not None else "N/A"

        message_parts.extend([
            "",
            "*Contrarian Signal*",
            f"  `Entry: ${entry_price:,.2f}`",
            f"  `SL:    {sl_str}`",
            f"  `TP1:   {tp1_str}`",
            f"  `TP2:   {tp2_str}`",
            f"  `TP3:   {tp3_str}`"
        ])

    await telegram_handler.send_telegram_message(
        chat_id=chat_id, 
        message="\n".join(message_parts), 
        message_thread_id=message_thread_id
    )

async def send_periodic_summary_notification(
    db_path: str,
    symbols: List[str],
    timeframe: str,
    chat_id: str,
    message_thread_id: Optional[int]
) -> None:
    """Queries the latest analysis for each symbol from the DB and sends a summary."""
    if not db_path:
        logger.warning("Cannot send periodic summary: SQLite DB path is not configured.")
        return

    summary_parts = [f"📊 *Market Summary* ({timeframe})", "_" * 25, ""]
    found_data = False

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for symbol in symbols:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trend_analysis WHERE symbol = ? ORDER BY analysis_timestamp_utc DESC LIMIT 1", (symbol,))
            record = cursor.fetchone()
            if record:
                found_data = True
                price = record['price']
                trend = record['trend']
                rsi = record['rsi_value']
                price_str = f"${price:,.2f}" if price is not None else "N/A"
                rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
                summary_parts.append(f"*{symbol}*:\n  `Price: {price_str:<12}`\n  `RSI:   {rsi_str:<12}`\n  `Trend: {trend}`")
            else:
                summary_parts.append(f"*{symbol}*: `No analysis data yet.`")
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to query SQLite for periodic summary: {e}")
        summary_parts.append("_Error fetching data from database._")

    if not found_data:
        logger.info("Skipping periodic summary: no analysis data found in the database.")
        return

    timestamp_utc = pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')
    summary_parts.extend(["", f"<sub>Last Updated: {timestamp_utc}</sub>"])
    await telegram_handler.send_telegram_message(chat_id=chat_id, message="\n".join(summary_parts), message_thread_id=message_thread_id)
    logger.info("✅ Successfully sent periodic summary notification.")

async def send_shutdown_notification(chat_id: str, message_thread_id: Optional[int], symbols_list: List[str]):
    """Sends a notification that the bot is shutting down."""
    message = f"🛑 *Bot Shutdown*\nBot monitoring *{', '.join(symbols_list)}* is stopping."
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id)

