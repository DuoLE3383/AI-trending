import logging
import pandas as pd
import asyncio
import configparser
from typing import List, Dict, Any, Optional, Tuple
from typing_extensions import TypedDict
# --- MODIFIED: Import button classes ---
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram_handler
from datetime import datetime, timedelta

# --- Configuration Loading ---
config = configparser.ConfigParser()
config.read('config.ini')

# --- Settings ---
log_level = config.get('settings', 'log_level', fallback='INFO').upper()
NOTIFICATION_THRESHOLD_PERCENT = config.getfloat('settings', 'notification_threshold_percent', fallback=0.05)
STATUS_UPDATE_INTERVAL_MINUTES = config.getint('settings', 'status_update_interval_minutes', fallback=10)
LEVERAGE_MULTIPLIER = config.getint('settings', 'leverage_multiplier', fallback=5)

# --- Initialize Logger ---
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- In-memory State Stores ---
last_notified_ranges: Dict[str, Dict[str, Optional[float]]] = {}
last_notification_timestamp: Dict[str, pd.Timestamp] = {}

# --- Define a structured type for analysis results ---
class AnalysisResult(TypedDict, total=False):
    symbol: str
    timeframe: str
    # ... (rest of the class is unchanged) ...
    trend: str

# --- Helper Functions (Mostly Unchanged) ---
# _should_send_alert, _determine_trade_info, _format_level are unchanged.

def _should_send_alert(symbol_key: str, new_ranges: Dict[str, Optional[float]]) -> bool:
    """Determines if a notification should be sent based on range changes."""
    previous_ranges = last_notified_ranges.get(symbol_key)
    if not previous_ranges:
        return True

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
    
    bullish_emoji = config.get('messages', 'bullish_emoji', fallback='✅')
    bearish_emoji = config.get('messages', 'bearish_emoji', fallback='❌')

    if tp1 > entry:
        direction = "Long"
        corrected_label = f"{bullish_emoji} Bullish"
    else:
        direction = "Short"
        corrected_label = f"{bearish_emoji} Bearish"

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


def _format_alert_message(result: AnalysisResult) -> str:
    # This function is now simpler, as button creation is handled separately.
    # The logic inside this function is exactly the same as before.
    price_str = f"${result.get('price', 0):,.4f}"
    rsi_str = f"{result.get('rsi_val', 0):.2f}"
    atr_str = f"{result.get('atr_value', 0):.4f}"
    entry_emoji = config.get('messages', 'entry_emoji', fallback='🎯')
    sl_emoji = config.get('messages', 'sl_emoji', fallback='🛡️')
    tp_emoji = config.get('messages', 'tp_emoji', fallback='💰')
    
    consts = config['constants']
    direction, corrected_trend, trade_type_str = _determine_trade_info(
        result.get('entry_price'), result.get('take_profit_1'), result.get('trend', 'N/A')
    )

    message_parts = [
        f"*{result.get('symbol')} Trend Alert* ({result.get('timeframe')})\n",
        f"🕒 Time: `{result.get('analysis_timestamp_utc', pd.Timestamp.now(tz='UTC')).strftime('%Y-%m-%d %H:%M:%S %Z')}`",
        f"💲 Price: `{price_str}`",
        f"📊 RSI ({consts.get('rsi_period')}): `{rsi_str}` ({result.get('rsi_interpretation', 'N/A')})",
        f"📉 ATR ({consts.get('atr_period')}): `{atr_str}`\n",
        f"📉 EMAs:",
        f"  • Fast ({consts.get('ema_fast')}): `${result.get('ema_fast_val', 0):,.2f}`",
        f"  • Medium ({consts.get('ema_medium')}): `${result.get('ema_medium_val', 0):,.2f}`",
        f"  • Slow ({consts.get('ema_slow')}): `${result.get('ema_slow_val', 0):,.2f}`\n"
    ]

    entry_price = result.get('entry_price')
    if entry_price and direction:
        message_parts.append(f"{entry_emoji} Entry Price: `${entry_price:,.4f}` {trade_type_str}")
        message_parts.append(_format_level("SL", result.get('stop_loss'), entry_price, sl_emoji, direction))
        # ... (rest of the level formatting is the same) ...
        message_parts.append(f"Leverage: x{LEVERAGE_MULTIPLIER} (Margin)\n")

    def get_range_str(low: float, high: float, price: float) -> str:
        # ... (this inner function is the same) ...
        low_pct = f"({((low - price) / price) * 100:+.2f}%)" if price else ""
        high_pct = f"({((high - price) / price) * 100:+.2f}%)" if price else ""
        return f"`${low:,.4f}{low_pct} - ${high:,.4f}{high_pct}`"

    short_range_str = get_range_str(result.get('proj_range_short_low', 0), result.get('proj_range_short_high', 0), result.get('price', 0))
    long_range_str = get_range_str(result.get('proj_range_long_low', 0), result.get('proj_range_long_high', 0), result.get('price', 0))

    message_parts.append(f"💡 Trend (4h): *{corrected_trend}* (Range: {short_range_str})")
    message_parts.append(f"💡 Trend (8h): *{corrected_trend}* (Range: {long_range_str})")

    return "\n".join(part for part in message_parts if part)


# --- ADDED: New function to create the buttons ---
def _create_alert_keyboard(symbol: str) -> InlineKeyboardMarkup:
    """Creates the inline keyboard with buttons for an alert."""
    buttons = []
    
    # Get link templates from config
    tv_url_template = config.get('links', 'tradingview_url', fallback=None)
    info_url = config.get('links', 'signal_info_url', fallback=None)

    # Create TradingView button if the URL is configured
    if tv_url_template:
        # Replace the {symbol} placeholder with the actual symbol
        tv_url = tv_url_template.format(symbol=symbol)
        buttons.append(InlineKeyboardButton("📈 View on TradingView", url=tv_url))

    # Create Signal Info button if the URL is configured
    if info_url:
        buttons.append(InlineKeyboardButton("ℹ️ Signal Info", url=info_url))
        
    # The keyboard is a list of lists, where each inner list is a row.
    # We'll put the buttons in a single row here.
    return InlineKeyboardMarkup([buttons]) if buttons else None


# --- Main Notification Logic (MODIFIED) ---

async def send_individual_trend_alert_notification(
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: AnalysisResult,
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
        "short_low": analysis_result.get("proj_range_short_low"),
        "short_high": analysis_result.get("proj_range_short_high"),
        "long_low": analysis_result.get("proj_range_long_low"),
        "long_high": analysis_result.get("proj_range_long_high")
    }

    if not _should_send_alert(symbol_key, new_ranges):
        last_ts = last_notification_timestamp.get(symbol_key)
        if not last_ts or (pd.Timestamp.now(tz='UTC') - last_ts > timedelta(minutes=STATUS_UPDATE_INTERVAL_MINUTES)):
            await send_no_signal_status_update(chat_id, message_thread_id, analysis_result)
        return

    # --- Format message and create keyboard ---
    message = _format_alert_message(analysis_result)
    keyboard = _create_alert_keyboard(symbol) # <-- Create the buttons

    # --- Send notification with the keyboard ---
    await telegram_handler.send_telegram_notification(
        chat_id,
        message,
        message_thread_id=message_thread_id,
        reply_markup=keyboard  # <-- Pass the keyboard here
    )

    # --- Update State ---
    last_notified_ranges[symbol_key] = new_ranges
    last_notification_timestamp[symbol_key] = pd.Timestamp.now(tz='UTC')
    await asyncio.sleep(0.5)


# --- Status and Shutdown Notifications (Unchanged) ---
# ... (send_no_signal_status_update and send_shutdown_notification are unchanged) ...
async def send_no_signal_status_update(chat_id: str, message_thread_id: Optional[int], analysis_result: AnalysisResult):
    """Sends a simplified status update when no major signal is found for a while."""
    symbol = analysis_result.get('symbol', 'N/A')
    timeframe = analysis_result.get('timeframe', 'N/A')
    price_str = f"${analysis_result.get('price', 0):,.4f}"
    rsi_str = f"${analysis_result.get('rsi_val', 0):.2f}"
    
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
