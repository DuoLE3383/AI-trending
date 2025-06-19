import logging
from typing import Dict, Any, Optional, List

# Local imports
import telegram_handler

# --- Constants for Trend Emojis/Text ---
TREND_STRONG_BULLISH = "✅ #StrongBullish"
TREND_BULLISH = "📈 #Bullish"
TREND_BEARISH = "📉 #Bearish"
TREND_STRONG_BEARISH = "❌ #StrongBearish"

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
    """Sends a detailed, individual alert for a strong trend signal."""
    symbol = analysis_result.get('symbol', 'N/A')
    trend = analysis_result.get('trend', 'N/A')
    price = analysis_result.get('price')
    timeframe = analysis_result.get('timeframe', 'N/A')
    signal_type = " (Contrarian SHORT)" if trend == TREND_STRONG_BULLISH else " (Contrarian LONG)"
    
    price_str = f"${price:,.2f}" if price is not None else "N/A"
    rsi_str = f"{analysis_result.get('rsi_val'):.2f}" if analysis_result.get('rsi_val') is not None else "N/A"
    
    message = f"""{trend} Signal for <b>{symbol}</b>{signal_type}
{'_'*25}

<b>Analysis ({timeframe} Timeframe)</b>
  <code>Price:    {price_str}</code>
  <code>EMA ({ema_fast_const:<3}):   ${analysis_result.get('ema_fast_val'):,.2f}</code>
  <code>EMA ({ema_medium_const:<3}):   ${analysis_result.get('ema_medium_val'):,.2f}</code>
  <code>EMA ({ema_slow_const:<3}):   ${analysis_result.get('ema_slow_val'):,.2f}</code>
  <code>RSI ({rsi_period_const:<3}):   {rsi_str} ({analysis_result.get('rsi_interpretation', 'N/A')})</code>

<b>Volatility & Projections</b>
  <code>BBands ({bbands_period_const}, {bbands_std_dev_const}): ${analysis_result.get('bb_lower'):,.2f} - ${analysis_result.get('bb_upper'):,.2f}</code>
  <code>Proj. Range:  ${analysis_result.get('proj_range_short_low'):,.2f} - ${analysis_result.get('proj_range_short_high'):,.2f}</code>

<b>Contrarian Signal</b>
  <code>Entry: ${analysis_result.get('entry_price'):,.2f}</code>
  <code>SL:    ${analysis_result.get('stop_loss'):,.2f}</code>
  <code>TP1:   ${analysis_result.get('take_profit_1'):,.2f}</code>
  <code>TP2:   ${analysis_result.get('take_profit_2'):,.2f}</code>
  <code>TP3:   ${analysis_result.get('take_profit_3'):,.2f}</code>
"""
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)

async def send_periodic_summary_notification(
    bot_token: str,
    db_path: str,
    symbols: List[str],
    timeframe: str,
    chat_id: str,
    message_thread_id: Optional[int]
) -> None:
    """Queries the latest analysis from the DB and sends a summary."""
    summary_parts = [f"📊 <b>Market Summary</b> (<i>{timeframe}</i>)", "_"*25]
    found_data = False
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True) # Read-only connection
        conn.row_factory = sqlite3.Row
        for symbol in symbols:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trend_analysis WHERE symbol = ? ORDER BY analysis_timestamp_utc DESC LIMIT 1", (symbol,))
            record = cursor.fetchone()
            if record:
                found_data = True
                trend = record['trend']
                summary_parts.append(f"<b>{record['symbol']}</b>: <code>${record['price']:,.2f}</code> ({trend})")
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to query SQLite for periodic summary: {e}")
        return

    if not found_data: return

    message = "\n".join(summary_parts)
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)
    logger.info("✅ Successfully sent periodic summary notification.")

async def send_shutdown_notification(bot_token: str, chat_id: str, message_thread_id: Optional[int], symbols_list: List[str]):
    """Sends a notification that the bot is shutting down."""
    message = f"🛑 <b>Bot Shutdown</b>\nBot monitoring <i>{', '.join(symbols_list)}</i> is stopping."
    await telegram_handler.send_telegram_message(chat_id, message, message_thread_id, bot_token)
