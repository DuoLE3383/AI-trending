import logging
import pandas as pd
import asyncio # Import asyncio
from typing import List, Dict, Any, Optional
import telegram_handler # To call the actual send function

logger = logging.getLogger(__name__)

# In-memory store for the last notified projected ranges for each symbol
# Structure: { "SYMBOL": {"short_low": X, "short_high": Y, "long_low": A, "long_high": B}, ... }
last_notified_ranges: Dict[str, Dict[str, Optional[float]]] = {}

async def send_strong_trend_summary_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    strong_trend_results: List[Dict[str, Any]] # Expects list of analysis_result dicts
):
    """Formats and sends a summary of strong trend alerts."""
    if not strong_trend_results:
        return

    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.debug("Telegram not configured or chat ID is placeholder; skipping strong trend summary.")
        return

    strong_trend_alerts_details = []
    for result in strong_trend_results:
        symbol = result.get('symbol', 'N/A')
        timeframe = result.get('timeframe', 'N/A')
        price_val = result.get('price')
        trend = result.get('trend', 'N/A')
        
        price_str = f"${price_val:,.4f}" if pd.notna(price_val) else "N/A" # Increased precision
        message_line = (
            f"*{symbol}* ({timeframe}): Price `{price_str}`, Trend *{trend}*"
        )
        strong_trend_alerts_details.append(message_line)

    if strong_trend_alerts_details:
        header = f"⚡️ *Strong Trend Alerts* ({pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}) ⚡️\n\n"
        full_message = header + "\n".join(strong_trend_alerts_details)

        # Commented out: Send to main chat/channel
        # await telegram_handler.send_telegram_notification(chat_id, full_message, message_thread_id=None)

        # If a topic ID is provided, also send to the topic
        if message_thread_id is not None:
             # Add a small delay to avoid potential API rate limits or processing issues
            await asyncio.sleep(0.5)
            await telegram_handler.send_telegram_notification(chat_id, full_message, message_thread_id=message_thread_id)

async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any],
    bbands_period_const: int, # Added
    atr_period_const: int, # Added
    bbands_std_dev_const: float, # Added
    rsi_period_const: int,
    ema_fast_const: int,
    ema_medium_const: int,
    ema_slow_const: int
):
    """Formats and sends an individual trend alert."""
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.debug("Telegram not configured or chat ID is placeholder; skipping individual trend alert.")
        return

    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    timestamp_str = analysis_result.get('analysis_timestamp_utc', pd.to_datetime('now', utc=True)).strftime('%Y-%m-%d %H:%M:%S %Z')
    price_val: Optional[float] = analysis_result.get('price') # Added type hint for clarity
    price_str = f"${price_val:,.4f}" if pd.notna(price_val) else "N/A" # Increased precision for current price
    rsi_val = analysis_result.get('rsi_val')
    rsi_str = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
    rsi_interpretation = analysis_result.get('rsi_interpretation', 'N/A')
    ema_fast_val = analysis_result.get('ema_fast_val')
    ema_fast_str = f"${ema_fast_val:,.2f}" if pd.notna(ema_fast_val) else "N/A"
    ema_medium_val = analysis_result.get('ema_medium_val')
    ema_medium_str = f"${ema_medium_val:,.2f}" if pd.notna(ema_medium_val) else "N/A"
    ema_slow_val = analysis_result.get('ema_slow_val')
    ema_slow_str = f"${ema_slow_val:,.2f}" if pd.notna(ema_slow_val) else "N/A"
    bb_lower_val = analysis_result.get('bb_lower')
    bb_lower_str = f"${bb_lower_val:,.2f}" if pd.notna(bb_lower_val) else "N/A"
    bb_upper_val = analysis_result.get('bb_upper')
    bb_upper_str = f"${bb_upper_val:,.2f}" if pd.notna(bb_upper_val) else "N/A"
    atr_val = analysis_result.get('atr_value') # Get ATR value
    atr_str = f"{atr_val:.4f}" if pd.notna(atr_val) else "N/A"
    proj_short_low_val = analysis_result.get('proj_range_short_low')
    proj_short_high_val = analysis_result.get('proj_range_short_high')
    proj_long_low_val = analysis_result.get('proj_range_long_low')
    proj_long_high_val = analysis_result.get('proj_range_long_high')
    proj_short_range_str = f"${proj_short_low_val:,.4f} - ${proj_short_high_val:,.4f}" if proj_short_low_val is not None and proj_short_high_val is not None else "N/A"
    proj_long_range_str = f"${proj_long_low_val:,.4f} - ${proj_long_high_val:,.4f}" if proj_long_low_val is not None and proj_long_high_val is not None else "N/A"

    # Calculate percentage difference from current price to projected range boundaries
    def get_percentage_diff_str(current_price: Optional[float], boundary_price: Optional[float]) -> str:
        if current_price is None or boundary_price is None or current_price == 0:
            return "" # Return empty if not calculable or current price is zero
        percentage_diff = ((boundary_price - current_price) / current_price) * 100
        return f" ({percentage_diff:+.2f}%)" # Show sign and 2 decimal places

    proj_short_low_pct_str = get_percentage_diff_str(price_val, proj_short_low_val)
    proj_short_high_pct_str = get_percentage_diff_str(price_val, proj_short_high_val)
    proj_long_low_pct_str = get_percentage_diff_str(price_val, proj_long_low_val)
    proj_long_high_pct_str = get_percentage_diff_str(price_val, proj_long_high_val)

    # Update range strings to include percentages
    if proj_short_low_val is not None and proj_short_high_val is not None:
        proj_short_range_str = f"${proj_short_low_val:,.4f}{proj_short_low_pct_str} - ${proj_short_high_val:,.4f}{proj_short_high_pct_str}"
    if proj_long_low_val is not None and proj_long_high_val is not None:
        proj_long_range_str = f"${proj_long_low_val:,.4f}{proj_long_low_pct_str} - ${proj_long_high_val:,.4f}{proj_long_high_pct_str}"

    # Get TP/SL values
    entry_price_val = analysis_result.get('entry_price')
    sl_val = analysis_result.get('stop_loss')
    tp1_val = analysis_result.get('take_profit_1')
    tp2_val = analysis_result.get('take_profit_2')
    tp3_val = analysis_result.get('take_profit_3')

    trend = analysis_result.get('trend', 'N/A')

    # --- Conditional Notification Logic ---
    symbol_key = f"{symbol}_{timeframe}" # Unique key per symbol and timeframe
    previous_ranges = last_notified_ranges.get(symbol_key)
    current_ranges_for_storage = {
        "short_low": proj_short_low_val,
        "short_high": proj_short_high_val,
        "long_low": proj_long_low_val,
        "long_high": proj_long_high_val
    }

    send_this_notification = False
    if previous_ranges is None:
        send_this_notification = True # Always send the first notification for a symbol
        logger.info(f"First notification for {symbol_key}, will send.")
    else:
        significant_change_detected = False
        # Compare current ranges with previous ranges
        boundaries_to_check = [
            ("short_low", previous_ranges.get("short_low"), proj_short_low_val),
            ("short_high", previous_ranges.get("short_high"), proj_short_high_val),
            ("long_low", previous_ranges.get("long_low"), proj_long_low_val),
            ("long_high", previous_ranges.get("long_high"), proj_long_high_val),
        ]

        for name, prev_val, curr_val in boundaries_to_check:
            if prev_val is None and curr_val is not None: # Was N/A, now has value
                significant_change_detected = True; break
            if prev_val is not None and curr_val is None: # Had value, now N/A
                significant_change_detected = True; break
            if prev_val is not None and curr_val is not None:
                if prev_val == 0: # Avoid division by zero if previous was 0
                    if curr_val != 0: # Changed from 0 to non-zero
                        significant_change_detected = True; break
                else:
                    percentage_diff = abs(curr_val - prev_val) / abs(prev_val)
                    if percentage_diff > 0.05: # More than 5% change
                        logger.info(f"Significant change for {symbol_key} in {name}: prev={prev_val:.4f}, curr={curr_val:.4f}, diff={percentage_diff:.2%}")
                        significant_change_detected = True; break
        
        if significant_change_detected:
            send_this_notification = True
        else:
            logger.info(f"No significant (>5%) change in projected ranges for {symbol_key}. Skipping notification.")

    if not send_this_notification:
        return # Do not send if conditions are not met

    message = (
        f"*{symbol} Trend Alert* ({timeframe})\n\n"
        f"🕒 Time: `{timestamp_str}`\n"
        f"💲 Price: `{price_str}`\n"
        f"📊 RSI ({rsi_period_const}): `{rsi_str}` ({rsi_interpretation})\n\n"
        # f"📈 BBands ({bbands_period_const}, {bbands_std_dev_const}): `{bb_lower_str} - {bb_upper_str}`\n" # Removed as per request
        f"📉 ATR ({atr_period_const}): `{atr_str}`\n\n"
        f"📉 EMAs:\n"
        f"  • Fast ({ema_fast_const}): `{ema_fast_str}`\n"
        f"  • Medium ({ema_medium_const}): `{ema_medium_str}`\n"
        f"  • Slow ({ema_slow_const}): `{ema_slow_str}`\n\n"
    )

    # Add TP/SL info if available (typically for strong trends)
    if entry_price_val is not None: # Check if entry_price was calculated
        
        # Helper to calculate and format percentage change from entry
        def format_level_with_percentage(level_name: str, level_val: Optional[float], entry_val: float, emoji: str) -> str:
            if level_val is None:
                return "" # Return empty string if level_val is None
            # Ensure entry_val is not None and not zero before calculating percentage
            percentage_from_entry = 0.0
            if entry_val != 0: # entry_price_val is already checked for None before this block
                percentage_from_entry = ((level_val - entry_val) / entry_val) * 100
            leveraged_percentage = percentage_from_entry * 5 # Apply 5x leverage
            return f"{emoji} {level_name}: `${level_val:,.4f}` ({leveraged_percentage:+.2f}%)\n"

        message += f"🎯 Entry Price: `${entry_price_val:,.4f}`\n"
        if sl_val is not None:
            message += format_level_with_percentage("SL", sl_val, entry_price_val, "🛡️")
        if tp1_val is not None:
            message += format_level_with_percentage("TP1", tp1_val, entry_price_val, "💰")
        if tp2_val is not None:
            message += format_level_with_percentage("TP2", tp2_val, entry_price_val, "💰")
        if tp3_val is not None:
            message += format_level_with_percentage("TP3", tp3_val, entry_price_val, "💰")
        message += "Leverage: x5 (Margin)\n\n" # Add the leverage line

    message += (
        f"💡 Trend: next 4 hour *{trend}* (Price range: `{proj_short_range_str}`)\n"
        f"💡 Trend: next 8 hour *{trend}* (Price range: `{proj_long_range_str}`)"
    )
    # Commented out: Send to main chat/channel
    # await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=None)

    # If a topic ID is provided, also send to the topic
    if message_thread_id is not None:
        # Add a small delay
        await asyncio.sleep(0.5)
        last_notified_ranges[symbol_key] = current_ranges_for_storage # Update stored ranges AFTER successful send attempt
        await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=message_thread_id)

async def send_shutdown_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    symbols_list: List[str]
):
    """Formats and sends a shutdown notification."""
    if not telegram_handler.telegram_bot or chat_id == telegram_handler.TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.debug("Telegram not configured or chat ID is placeholder; skipping shutdown notification.")
        return
        
    shutdown_message = f"🛑 Trend Analysis Bot for {', '.join(symbols_list)} stopped by user at {pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}."
    # Commented out, because the logic of this function sends only to topic:  await telegram_handler.send_telegram_notification(
    #    chat_id, shutdown_message, message_thread_id=message_thread_id, suppress_print=True
    #)