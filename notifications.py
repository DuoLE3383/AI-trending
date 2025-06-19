import logging
from typing import Dict, Any, Optional, List

# Local import
import telegram_handler

logger = logging.getLogger(__name__)

async def send_individual_trend_alert_notification(
    bot_token: str,
    chat_id: str,
    message_thread_id: Optional[int],
    analysis_result: Dict[str, Any],
    bbands_period_const: int,
    bbands_std_dev_const: float,
    atr_period_const: int,
    rsi_period_const: int,
    ema_fast_const: int,
    ema_medium_const: int,
    ema_slow_const: int
) -> None:
    """Sends a detailed, individual alert using the old plain-text template."""
    symbol = analysis_result.get('symbol', 'N/A')
    trend = analysis_result.get('trend', 'N/A')
    price = analysis_result.get('price')
    timeframe = analysis_result.get('timeframe', 'N/A')
    rsi_val = analysis_result.get('rsi_value')
    atr_val = analysis_result.get('atr_value')
    proj_low = analysis_result.get('proj_range_short_low')
    proj_high = analysis_result.get('proj_range_short_high')
    
    # --- Start building the message with the old template ---
    message = (
        f"{trend} Signal for {symbol}\n"
        f"-----------------------------\n"
        f"Analysis ({timeframe} Timeframe):\n"
        f"  Price: ${price:,.2f}\n"
        f"  EMA ({ema_fast_const}): ${analysis_result.get('ema_fast_value'):,.2f}\n"
        f"  EMA ({ema_medium_const}): ${analysis_result.get('ema_medium_value'):,.2f}\n"
        f"  EMA ({ema_slow_const}): ${analysis_result.get('ema_slow_value'):,.2f}\n"
        f"  RSI ({rsi_period_const}): {rsi_val:.2f} ({analysis_result.get('rsi_interpretation', 'N/A')})\n\n"
        f"Volatility (ATR {atr_period_const}):\n"
        f"  ATR: {atr_val:.4f}\n"
        f"  Projected Range: ${proj_low:,.2f} - ${proj_high:,.2f}\n"
    )

    # Append the Contrarian Signal details if they exist
    entry_price = analysis_result.get('entry_price')
    if entry_price is not None:
        signal_type = "(📉 ENTRY SHORT)" if "Bullish" in trend else "(📈ENTRY LONG)"
        sl = analysis_result.get('stop_loss')
        tp1 = analysis_result.get('take_profit_1')
        
        signal_details = (
            f"\nContrarian Signal {signal_type}:\n"
            f"  Entry: ${entry_price:,.2f}\n"
            f"  Stop Loss: ${sl:,.2f}\n"
            f"  Take Profit 1: ${tp1:,.2f}\n"
        )
        message += signal_details

    # Send the final message
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)
    logger.info(f"✅ Successfully sent signal alert for {symbol} to Telegram (Old Template).")


async def send_shutdown_notification(bot_token: str, chat_id: str, message_thread_id: Optional[int]):
    """Sends a shutdown notification in plain text."""
    message = f"🛑 Bot Shutdown\nThe market analysis bot is stopping."
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)

