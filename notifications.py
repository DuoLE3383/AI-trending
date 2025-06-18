import logging
import pandas as pd
import asyncio
from typing import List, Dict, Any, Optional
import telegram_handler # To call the actual send function
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# --- MODIFIED ---
# In-memory stores for last notified data
# Structure: { "SYMBOL_TIMEFRAME": {"short_low": X, ...}, ... }
last_notified_ranges: Dict[str, Dict[str, Optional[float]]] = {}
# Structure: { "SYMBOL_TIMEFRAME": pd.Timestamp, ... }
last_notification_timestamp: Dict[str, pd.Timestamp] = {}


# --- ADDED ---
async def send_no_signal_status_update(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any]
):
    """
    Formats and sends a concise status update when no significant change is detected.
    """
    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    price_val: Optional[float] = analysis_result.get('price')
    price_str = f"${price_val:,.4f}" if pd.notna(price_val) else "N/A"
    rsi_val = analysis_result.get('rsi_val')
    rsi_str = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
    rsi_interpretation = analysis_result.get('rsi_interpretation', 'N/A')
    timestamp_str = pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')
    symbol_key = f"{symbol}_{timeframe}"

    message = (
        f"⏳ *{symbol} Status Update* ({timeframe})\n\n"
        f"No significant signal detected recently.\n\n"
        f"*Current Analytics:*\n"
        f"  • Price: `{price_str}`\n"
        f"  • RSI: `{rsi_str}` ({rsi_interpretation})\n\n"
        f"🕒 Time: `{timestamp_str}`"
    )

    logger.info(f"Sending 10-minute status update for {symbol_key}.")
    await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=message_thread_id)
    
    # Update the timestamp to reset the 10-minute timer
    last_notification_timestamp[symbol_key] = pd.to_datetime('now', utc=True)
    await asyncio.sleep(0.5)


async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any],
    bbands_period_const: int,
    atr_period_const: int,
    bbands_std_dev_const: float,
    rsi_period_const: int,
    ema_fast_const: int,
    ema_medium_const: int,
    ema_slow_const: int
):
    """
    Formats and sends an individual, detailed trend alert if the projected ranges
    have changed significantly since the last notification.
    
    If no significant change, it will send a status update every 10 minutes instead.
    """
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.debug("Telegram not configured or chat ID is placeholder; skipping individual trend alert.")
        return

    # --- Extract data from analysis result ---
    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    symbol_key = f"{symbol}_{timeframe}" # Define symbol_key early
    timestamp_str = analysis_result.get('analysis_timestamp_utc', pd.to_datetime('now', utc=True)).strftime('%Y-%m-%d %H:%M:%S %Z')
    price_val: Optional[float] = analysis_result.get('price')
    price_str = f"${price_val:,.4f}" if pd.notna(price_val) else "N/A"
    rsi_val = analysis_result.get('rsi_val')
    rsi_str = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
    rsi_interpretation = analysis_result.get('rsi_interpretation', 'N/A')
    ema_fast_val = analysis_result.get('ema_fast_val')
    ema_fast_str = f"${ema_fast_val:,.2f}" if pd.notna(ema_fast_val) else "N/A"
    ema_medium_val = analysis_result.get('ema_medium_val')
    ema_medium_str = f"${ema_medium_val:,.2f}" if pd.notna(ema_medium_val) else "N/A"
    ema_slow_val = analysis_result.get('ema_slow_val')
    ema_slow_str = f"${ema_slow_val:,.2f}" if pd.notna(ema_slow_val) else "N/A"
    atr_val = analysis_result.get('atr_value')
    atr_str = f"{atr_val:.4f}" if pd.notna(atr_val) else "N/A"
    proj_short_low_val = analysis_result.get('proj_range_short_low')
    proj_short_high_val = analysis_result.get('proj_range_short_high')
    proj_long_low_val = analysis_result.get('proj_range_long_low')
    proj_long_high_val = analysis_result.get('proj_range_long_high')
    entry_price_val = analysis_result.get('entry_price')
    sl_val = analysis_result.get('stop_loss')
    tp1_val = analysis_result.get('take_profit_1')
    tp2_val = analysis_result.get('take_profit_2')
    tp3_val = analysis_result.get('take_profit_3')
    trend = analysis_result.get('trend', 'N/A')

    # --- Conditional Notification Logic ---
    previous_ranges = last_notified_ranges.get(symbol_key)
    
    send_this_notification = False
    if previous_ranges is None:
        send_this_notification = True # Always send the first notification for a symbol
        logger.info(f"First notification for {symbol_key}, will send.")
    else:
        boundaries_to_check = [
            ("short_low", previous_ranges.get("short_low"), proj_short_low_val),
            ("short_high", previous_ranges.get("short_high"), proj_short_high_val),
        ]
        for name, prev_val, curr_val in boundaries_to_check:
            if prev_val is not None and curr_val is not None and prev_val != 0:
                percentage_diff = abs(curr_val - prev_val) / abs(prev_val)
                # --- MODIFIED --- Changed percentage diff to 0.30 for SL as requested ("around 30%")
                # Note: This checks for a 30% change in the projected range boundary, not the SL itself.
                if percentage_diff > 0.30: 
                    logger.info(f"Significant change for {symbol_key} in {name}: diff={percentage_diff:.2%}. Sending notification.")
                    send_this_notification = True
                    break
    
    # --- MODIFIED ---
    # If no significant change, check if it's time for a 10-minute status update
    if not send_this_notification:
        logger.info(f"No significant (>30%) change in projected ranges for {symbol_key}. Checking for status update.")
        last_time = last_notification_timestamp.get(symbol_key)
        # Send status if it's been more than 10 minutes or never sent before
        if last_time is None or (pd.to_datetime('now', utc=True) - last_time > timedelta(minutes=10)):
            await send_no_signal_status_update(chat_id, message_thread_id, analysis_result)
        else:
            logger.info(f"Skipping status update for {symbol_key}, last sent at {last_time}.")
        return # Do not proceed to send the main alert

    # --- Format Projected Ranges with Percentage ---
    def get_percentage_diff_str(current_price: Optional[float], boundary_price: Optional[float]) -> str:
        if current_price is None or boundary_price is None or current_price == 0:
            return ""
        percentage_diff = ((boundary_price - current_price) / current_price) * 100
        return f" ({percentage_diff:+.2f}%)"

    proj_short_range_str = f"${proj_short_low_val:,.4f}{get_percentage_diff_str(price_val, proj_short_low_val)} - ${proj_short_high_val:,.4f}{get_percentage_diff_str(price_val, proj_short_high_val)}"
    proj_long_range_str = f"${proj_long_low_val:,.4f}{get_percentage_diff_str(price_val, proj_long_low_val)} - ${proj_long_high_val:,.4f}{get_percentage_diff_str(price_val, proj_long_high_val)}"

    # --- Build The Message ---
    message = (
        f"*{symbol} Trend Alert* ({timeframe})\n\n"
        f"🕒 Time: `{timestamp_str}`\n"
        f"💲 Price: `{price_str}`\n"
        f"📊 RSI ({rsi_period_const}): `{rsi_str}` ({rsi_interpretation})\n"
        f"📉 ATR ({atr_period_const}): `{atr_str}`\n\n"
        f"📉 EMAs:\n"
        f"  • Fast ({ema_fast_const}): `{ema_fast_str}`\n"
        f"  • Medium ({ema_medium_const}): `{ema_medium_str}`\n"
        f"  • Slow ({ema_slow_const}): `{ema_slow_str}`\n\n"
    )

    if entry_price_val is not None:
        # --- MODIFIED ---
        # This function now formats SL differently from TP levels.
        def format_level(level_name: str, level_val: Optional[float], entry_val: float, emoji: str) -> str:
            if level_val is None: return ""
            # For SL, format without the percentage.
            if level_name == "SL":
                # Note: The request to "Edit SL around 30%" refers to the calculation
                # of `sl_val` which happens *before* this script. This code only
                # handles the display. We now remove the percentage display for SL.
                return f"{emoji} {level_name}: `${level_val:,.4f}`\n"
            
            # For TP levels, keep the percentage calculation.
            percentage_from_entry = ((level_val - entry_val) / entry_val) * 100 if entry_val != 0 else 0.0
            leveraged_percentage = percentage_from_entry * 5 # Apply 5x leverage
            return f"{emoji} {level_name}: `${level_val:,.4f}` ({leveraged_percentage:+.2f}%)\n"

        message += f"🎯 Entry Price: `${entry_price_val:,.4f}`\n"
        # Use the modified formatting function
        if sl_val: message += format_level("SL", sl_val, entry_price_val, "🛡️")
        if tp1_val: message += format_level("TP1", tp1_val, entry_price_val, "💰")
        if tp2_val: message += format_level("TP2", tp2_val, entry_price_val, "💰")
        if tp3_val: message += format_level("TP3", tp3_val, entry_price_val, "💰")
        message += "Leverage: x5 (Margin)\n\n"

    message += (
        f"💡 Trend: next 4 hour *{trend}* (Price range: `{proj_short_range_str}`)\n"
        f"💡 Trend: next 8 hour *{trend}* (Price range: `{proj_long_range_str}`)"
    )

    # --- Send Notification and Update State ---
    await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=message_thread_id)
    
    # --- MODIFIED ---
    # Update stored ranges AND the notification timestamp after successful send attempt
    last_notified_ranges[symbol_key] = {
        "short_low": proj_short_low_val,
        "short_high": proj_short_high_val,
        "long_low": proj_long_low_val,
        "long_high": proj_long_high_val
    }
    last_notification_timestamp[symbol_key] = pd.to_datetime('now', utc=True)
    await asyncio.sleep(0.5)


async def send_shutdown_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    symbols_list: List[str]
):
    """Formats and sends a shutdown notification."""
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.debug("Telegram not configured or chat ID is placeholder; skipping shutdown notification.")
        return
        
    shutdown_message = (
        f"🛑 Trend Analysis Bot for *{', '.join(symbols_list)}* stopped by user at "
        f"`{pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}`."
    )
    
    await telegram_handler.send_telegram_notification(
       chat_id, shutdown_message, message_thread_id=message_thread_id, suppress_print=True
    )
