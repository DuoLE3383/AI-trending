import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import telegram_handler # To call the actual send function

logger = logging.getLogger(__name__)

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

        # Send to main chat/channel
        await telegram_handler.send_telegram_notification(chat_id, full_message, message_thread_id=None)

        # If a topic ID is provided, also send to the topic
        if message_thread_id is not None:
             # Add a small delay to avoid potential API rate limits or processing issues
            await asyncio.sleep(0.5)
            await telegram_handler.send_telegram_notification(chat_id, full_message, message_thread_id=message_thread_id)

async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any],
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
    price_val = analysis_result.get('price')
    price_str = f"${price_val:,.2f}" if pd.notna(price_val) else "N/A"
    rsi_val = analysis_result.get('rsi_val')
    rsi_str = f"{rsi_val:.2f}" if pd.notna(rsi_val) else "N/A"
    rsi_interpretation = analysis_result.get('rsi_interpretation', 'N/A')
    ema_fast_val = analysis_result.get('ema_fast_val')
    ema_fast_str = f"${ema_fast_val:,.2f}" if pd.notna(ema_fast_val) else "N/A"
    ema_medium_val = analysis_result.get('ema_medium_val')
    ema_medium_str = f"${ema_medium_val:,.2f}" if pd.notna(ema_medium_val) else "N/A"
    ema_slow_val = analysis_result.get('ema_slow_val')
    ema_slow_str = f"${ema_slow_val:,.2f}" if pd.notna(ema_slow_val) else "N/A"
    trend = analysis_result.get('trend', 'N/A')

    message = (
        f"*{symbol} Trend Alert* ({timeframe})\n\n"
        f"🕒 Time: `{timestamp_str}`\n"
        f"💲 Price: `{price_str}`\n"
        f"📊 RSI ({rsi_period_const}): `{rsi_str}` ({rsi_interpretation})\n\n"
        f"📉 EMAs:\n"
        f"  • Fast ({ema_fast_const}): `{ema_fast_str}`\n"
        f"  • Medium ({ema_medium_const}): `{ema_medium_str}`\n"
        f"  • Slow ({ema_slow_const}): `{ema_slow_str}`\n\n"
        f"💡 Trend: *{trend}*"
    )

    # Send to main chat/channel
    await telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=None)

    # If a topic ID is provided, also send to the topic
    if message_thread_id is not None:
        # Add a small delay
        await asyncio.sleep(0.5)
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
    await telegram_handler.send_telegram_notification(
        chat_id, shutdown_message, message_thread_id=message_thread_id, suppress_print=True
    )