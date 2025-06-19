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
    """Sends a detailed, individual alert for a new strong trend signal."""
    symbol = analysis_result.get('symbol', 'N/A')
    trend = analysis_result.get('trend', 'N/A')
    price = analysis_result.get('price')
    timeframe = analysis_result.get('timeframe', 'N/A')
    
    signal_type = " (Contrarian SHORT)" if "Bullish" in trend else " (Contrarian LONG)"
    
    price_str = f"${price:,.2f}" if price is not None else "N/A"
    rsi_str = f"{analysis_result.get('rsi_value'):.2f}" if analysis_result.get('rsi_value') is not None else "N/A"
    
    message = f"""{trend} New Signal for <b>{symbol}</b>{signal_type}
{'_'*25}

<b>Analysis ({timeframe} Timeframe)</b>
  <code>Price:    {price_str}</code>
  <code>EMA ({ema_fast_const:<3}):   ${analysis_result.get('ema_fast_value'):,.2f}</code>
  <code>EMA ({ema_medium_const:<3}):   ${analysis_result.get('ema_medium_value'):,.2f}</code>
  <code>EMA ({ema_slow_const:<3}):   ${analysis_result.get('ema_slow_value'):,.2f}</code>
  <code>RSI ({rsi_period_const:<3}):   {rsi_str} (<i>{analysis_result.get('rsi_interpretation', 'N/A')}</i>)</code>

<b>Contrarian Signal Details</b>
  <code>Entry: ${analysis_result.get('entry_price'):,.2f}</code>
  <code>SL:    ${analysis_result.get('stop_loss'):,.2f}</code>
  <code>TP1:   ${analysis_result.get('take_profit_1'):,.2f}</code>
"""
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)
    logger.info(f"✅ Successfully sent signal alert for {symbol} to Telegram.")


async def send_shutdown_notification(bot_token: str, chat_id: str, message_thread_id: Optional[int]):
    """Sends a notification that the bot is shutting down."""
    message = f"🛑 <b>Bot Shutdown</b>\nThe market analysis bot is stopping."
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)

