import logging
import pandas as pd
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from typing_extensions import TypedDict
import telegram_handler
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# --- Constants ---
NOTIFICATION_THRESHOLD_PERCENT = 0.05  # 5% change to trigger a new alert
STATUS_UPDATE_INTERVAL_MINUTES = 10
LEVERAGE_MULTIPLIER = 5

# --- In-memory State Stores ---
# Note: This state is lost on script restart. For persistence, consider Redis or a database.
last_notified_ranges: Dict[str, Dict[str, Optional[float]]] = {}
last_notification_timestamp: Dict[str, pd.Timestamp] = {}

# --- Define a structured type for analysis results for clarity ---
class AnalysisResult(TypedDict, total=False):
    symbol: str
    timeframe: str
    analysis_timestamp_utc: pd.Timestamp
    price: float
    rsi_val: float
    rsi_interpretation: str
    ema_fast_val: float
    ema_medium_val: float
    ema_slow_val: float
    atr_value: float
    proj_range_short_low: float
    proj_range_short_high: float
    proj_range_long_low: float
    proj_range_long_high: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    trend: str

# --- Helper Functions (Refactored for Clarity) ---

def _should_send_alert(symbol_key: str, new_ranges: Dict[str, Optional[float]]) -> bool:
    """Determines if a notification should be sent based on range changes."""
    previous_ranges = last_notified_ranges.get(symbol_key)
    if not previous_ranges:
        return True  # Always send if it's the first time

    for key, prev_val in previous_ranges.items():
        curr_val = new_ranges.get(key)
        if prev_val and curr_val and prev_val != 0:
            if abs(curr_val - prev_val) / abs(prev_val) > NOTIFICATION_THRESHOLD_PERCENT:
                logger.info(f"Threshold exceeded for {symbol_key} on '{key}'. Sending alert.")
                return True
    return False

def _determine_trade_info(entry: Optional[float], tp1: Optional[float], original_trend: str) -> Tuple[Optional[str], str, str]:
    """Determines trade direction and corrects the trend label if necessary."""
    if not entry or not tp1:
        return None, original_trend, ""

    if tp1 > entry:
        direction = "Long"
        corrected_label = "✅ Bullish"
    else:
        direction = "Short"
        corrected_label = "❌ Bearish"
    
    if original_trend not in corrected_label:
        logger.warning(f"Correcting trend! Original='{original_trend}', but levels indicate a '{direction}' trade.")
        
    return direction, corrected_label, f"({direction})"

def _format_level(level_name: str, level_val: Optional[float], entry_val: float, emoji: str, direction: str) -> str:
    """Formats a single SL or TP level with its percentage change."""
    if not all([level_val, entry_val, direction]):
        return ""
    
    percentage = ((level_val - entry_val) / entry_val if direction == "Long" else (entry_val - level_val) / entry_val) * 100
    leveraged_percentage = -abs(percentage * LEVERAGE_MULTIPLIER) if level_name == "SL" else abs(percentage * LEVERAGE_MULTIPLIER)
    
    return f"{emoji} {level_name}: `${level_val:,.4f}` ({leveraged_percentage:+.2f}%)\n"

def _format_alert_message(result: AnalysisResult, constants: Dict[str, Any]) -> str:
    """Builds the final, formatted Telegram message string."""
    # --- Data Extraction ---
    price_str = f"${result.get('price', 0):,.4f}"
    rsi_str = f"{result.get('rsi_val', 0):.2f}"
    atr_str = f"{result.get('atr_value', 0):.4f}"
    
    # --- Determine Trade Direction & Corrected Trend ---
    direction, corrected_trend, trade_type_str = _determine_trade_info(
        result.get('entry_price'), result.get('take_profit_1'), result.get('trend', 'N/A')
    )

    # --- Build Message Components ---
    message_parts = [
        f"*{result.get('symbol')} Trend Alert* ({result.get('timeframe')})\n",
        f"🕒 Time: `{result.get('analysis_timestamp_utc', pd.Timestamp.now(tz='UTC')).strftime('%Y-%m-%d %H:%M:%S %Z')}`",
        f"💲 Price: `{price_str}`",
        f"📊 RSI ({constants['rsi_period_const']}): `{rsi_str}` ({result.get('rsi_interpretation', 'N/A')})",
        f"📉 ATR ({constants['atr_period_const']}): `{atr_str}`\n",
        f"📉 EMAs:",
        f"  • Fast ({constants['ema_fast_const']}): `${result.get('ema_fast_val', 0):,.2f}`",
        f"  • Medium ({constants['ema_medium_const']}): `${result.get('ema_medium_val', 0):,.2f}`",
        f"  • Slow ({constants['ema_slow_const']}): `${result.get('ema_slow_val', 0):,.2f}`\n"
    ]

    # --- Add Trade Levels if they exist ---
    entry_price = result.get('entry_price')
    if entry_price and direction:
        message_parts.append("---") # Visual separator
        message_parts.append(f"🎯 Entry Price: `${entry_price:,.4f}` {trade_type_str}")
        message_parts.append(_format_level("SL", result.get('stop_loss'), entry_price, "🛡️", direction))
        message_parts.append(_format_level("TP1", result.get('take_profit_1'), entry_price, "💰", direction))
        message_parts.append(_format_level("TP2", result.get('take_profit_2'), entry_price, "💰", direction))
        message_parts.append(_format_level("TP3", result.get('take_profit_3'), entry_price, "💰", direction))
        message_parts.append(f"Leverage: x{LEVERAGE_MULTIPLIER} (Margin)\n")

    # --- Add Trend Projections ---
    def get_range_str(low: float, high: float, price: float) -> str:
        low_pct = f"({((low - price) / price) * 100:+.2f}%)" if price else ""
        high_pct = f"({((high - price) / price) * 100:+.2f}%)" if price else ""
        return f"`${low:,.4f}{low_pct} - ${high:,.4f}{high_pct}`"

    short_range_str = get_range_str(result.get('proj_range_short_low', 0), result.get('proj_range_short_high', 0), result.get('price', 0))
    long_range_str = get_range_str(result.get('proj_range_long_low', 0), result.get('proj_range_long_high', 0), result.get('price', 0))

    message_parts.append(f"💡 Trend (4h): *{corrected_trend}* (Range: {short_range_str})")
    message_parts.append(f"💡 Trend (8h): *{corrected_trend}* (Range: {long_range_str})")

    return "\n".join(message_parts)


# --- Main Notification Logic (Now Cleaner) ---

async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: AnalysisResult,
    constants: Dict[str, Any]
):
    """
    Main function to process an analysis result and send a Telegram alert if necessary.
    """
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        return

    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    symbol_key = f"{symbol}_{timeframe}"
    
    new_ranges = {
        "short_low": analysis_result.get("proj_range_short_low"), "short_high": analysis_result.get("proj_range_short_high"),
        "long_low": analysis_result.get("proj_range_long_low"), "long_high": analysis_result.get("proj_range_long_high")
    }

    if not _should_send_alert(symbol_key, new_ranges):
        # If no significant change, check if it's time for a simple status update
        last_ts = last_notification_timestamp.get(symbol_key)
        if not last_ts or (pd.Timestamp.now(tz='UTC') - last_ts > timedelta(minutes=STATUS_UPDATE_INTERVAL_MINUTES)):
            await send_no_signal_status_update(chat_id, message_thread_id, analysis_result)
        return

    # --- Format and Send ---
    message = _format_alert_message(analysis_result, constants)
    await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=message_thread_id)
    
    # --- Update State ---
    last_notified_ranges[symbol_key] = new_ranges
    last_notification_timestamp[symbol_key] = pd.Timestamp.now(tz='UTC')
    await asyncio.sleep(0.5)


# --- Status and Shutdown Notifications (Largely Unchanged) ---

async def send_no_signal_status_update(chat_id: str, message_thread_id: Optional[int], analysis_result: AnalysisResult):
    """Sends a simplified status update when no major signal is found for a while."""
    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    price_str = f"${analysis_result.get('price', 0):,.4f}"
    rsi_str = f"{analysis_result.get('rsi_val', 0):.2f}"
    
    message = (
        f"⏳ *{symbol} Status Update* ({timeframe})\n\n"
        f"No significant signal detected recently.\n\n"
        f"*Current Analytics:*\n"
        f"  • Price: `{price_str}`\n"
        f"  • RSI: `{rsi_str}` ({analysis_result.get('rsi_interpretation', 'N/A')})\n\n"
        f"🕒 Time: `{pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}`"
    )

    logger.info(f"Sending {STATUS_UPDATE_INTERVAL_MINUTES}-minute status update for {symbol}_{timeframe}.")
    await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=message_thread_id)
    last_notification_timestamp[f"{symbol}_{timeframe}"] = pd.Timestamp.now(tz='UTC')
    await asyncio.sleep(0.5)


async def send_shutdown_notification(chat_id: str, message_thread_id: Optional[int], symbols_list: List[str]):
    """Sends a notification when the bot is shut down."""
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        return
    shutdown_message = (f"🛑 Trend Analysis Bot for *{', '.join(symbols_list)}* stopped by user at "
                        f"`{pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')}`.")
    await telegram_handler.send_telegram_notification(chat_id, shutdown_message, message_thread_id=message_thread_id, suppress_print=True)
# Add these imports at the top of notifications.py
import sqlite3
import pandas as pd
from typing import List

# ... (keep all your existing functions like send_individual_trend_alert_notification) ...

# Add this new function at the end of the file
async def send_periodic_summary_notification(
    db_path: str,
    symbols: List[str],
    timeframe: str,
    chat_id: str,
    message_thread_id: int | None
) -> None:
    """
    Queries the latest analysis for each symbol from the DB and sends a summary.
    """
    if not db_path:
        logger.warning("Cannot send periodic summary: SQLite DB path is not configured.")
        return

    summary_parts = [
        f"📊 *Market Summary* ({timeframe})",
        "_" * 25, ""
    ]
    found_data = False

    try:
        conn = sqlite3.connect(db_path)
        # Set row_factory to easily convert rows to dictionaries
        conn.row_factory = sqlite3.Row

        for symbol in symbols:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM trend_analysis
                WHERE symbol = ?
                ORDER BY analysis_timestamp_utc DESC
                LIMIT 1
                """, (symbol,)
            )
            latest_record = cursor.fetchone()

            if latest_record:
                found_data = True
                # Convert the row object to a dictionary
                record_dict = dict(latest_record)
                price = record_dict.get('price', 0.0)
                trend = record_dict.get('trend', 'N/A')
                rsi = record_dict.get('rsi_value', 0.0)
                
                # Format the line for the summary
                price_str = f"${price:,.2f}" if price else "N/A"
                rsi_str = f"{rsi:.1f}" if rsi else "N/A"
                
                symbol_line = (
                    f"*{symbol}*:\n"
                    f"  `Price: {price_str:<12}`\n"
                    f"  `RSI:   {rsi_str:<12}`\n"
                    f"  `Trend: {trend}`"
                )
                summary_parts.append(symbol_line)
            else:
                summary_parts.append(f"*{symbol}*: `No analysis data available yet.`")
        
        conn.close()

    except sqlite3.Error as e:
        logger.error(f"Failed to query SQLite for periodic summary: {e}")
        summary_parts.append("_Error fetching data from database._")

    if not found_data:
        logger.info("Skipping periodic summary notification as no analysis data was found in the database.")
        return

    # Add a timestamp to the footer
    timestamp_utc = pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')
    summary_parts.extend(["", f"<sub>Last Updated: {timestamp_utc}</sub>"])

    message = "\n".join(summary_parts)

    # Use the existing telegram_handler to send the message
    from telegram_handler import send_telegram_message
    await send_telegram_message(
        chat_id=chat_id,
        message=message,
        message_thread_id=message_thread_id
    )
    logger.info("✅ Successfully sent periodic summary notification to Telegram.")


