# notifications.py
import logging
from typing import List, Dict, Any
from telegram_handler import TelegramHandler
import config
import socket

logger = logging.getLogger(__name__)

class NotificationHandler:
    """
    Handles the formatting and sending of all notifications to Telegram.
    """
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler

    async def send_startup_notification(self, symbols_count: int):
        """Sends a startup notification with a photo."""
        self.logger.info("Preparing startup notification with photo...")
        try:
            timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
            caption_text = (
                f"🚀 *AI Trading Bot Activated* 🚀\n\n"
                f"The bot is now live and analyzing `{symbols_count}` pairs on the `{timeframe_escaped}` timeframe\\."
            )
            photo_url = "https://i.imgur.com/8z8hL4T.png"
            
            await self.telegram_handler.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=photo_url,
                caption=caption_text,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="MarkdownV2"
            )
            self.logger.info("Startup notification with photo sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """Sends a single notification for a batch of new signals."""
        if not analysis_results:
            return
        
        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} signals.")
        header = f"� *{len(analysis_results)} New Signal(s) Found\\!* 🔥\n"
        message_lines = []
        
        for result in analysis_results:
            symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
            trend = TelegramHandler.escape_markdownv2(result.get('trend', 'N/A').replace("_", " ").title())
            price = result.get('last_price', 0)
            formatted_price = TelegramHandler.escape_markdownv2(f"{price:.4f}")
            
            trend_emoji = "🔼" if "Bullish" in result.get('trend', '') else "🔽"
            formatted_line = f"{trend_emoji} *{symbol}* \\- {trend} at `${formatted_price}`"
            message_lines.append(formatted_line)
        
        body = "\n".join(message_lines)
        full_message = header + "\n" + body

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            self.logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")
        except Exception as e:
            self.logger.error(f"Could not send signal batch: {e}", exc_info=True)

    async def send_summary_report(self, stats: Dict[str, Any]):
        """Formats and sends a periodic performance report."""
        self.logger.info("Preparing performance summary report...")
        header = "🏆 *Strategy Performance Report (All\\-Time)* 🏆\n"
        
        if stats.get('total_completed_trades', 0) > 0:
            win_rate = TelegramHandler.escape_markdownv2(f"{stats.get('win_rate', 0.0):.2f}")
            body = (
                f"\n✅ *Win Rate:* `{win_rate}%`"
                f"\n📊 *Completed Trades:* `{stats.get('total_completed_trades', 0)}`"
                f"\n👍 *Wins:* `{stats.get('wins', 0)}`"
                f"\n👎 *Losses:* `{stats.get('losses', 0)}`"
            )
        else:
            body = "\nNo completed trades to analyze yet."
        
        full_message = header + body

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            self.logger.info("Successfully sent performance report to Telegram.")
        except Exception as e:
            self.logger.error(f"Failed to send performance report: {e}", exc_info=True)
            
    async def send_heartbeat_notification(self, symbols_count: int):
        """Sends a 'heartbeat' message to confirm that the bot is still running."""
        self.logger.info("Sending heartbeat notification...")
        message = (
            f"❤️ *Bot Status: ALIVE* ❤️\n\n"
            f"The bot is running correctly and currently monitoring `{symbols_count}` symbols\\. "
            f"No critical errors have been detected\\."
        )
        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                disable_notification=True
            )
            self.logger.info("Heartbeat notification sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat notification: {e}", exc_info=True)

    # --- NEW FUNCTION TO SEND WIN/LOSS NOTIFICATIONS ---
    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        """Sends a notification for a single closed trade (win or loss)."""
        self.logger.info(f"Preparing outcome notification for {trade_details['symbol']}...")
        try:
            symbol = TelegramHandler.escape_markdownv2(trade_details['symbol'])
            status = TelegramHandler.escape_markdownv2(trade_details['status'])
            
            is_win = "TP" in trade_details['status']
            outcome_emoji = "✅" if is_win else "❌"
            outcome_text = "WIN" if is_win else "LOSS"
            
            message = (
                f"{outcome_emoji} *Trade Closed: {outcome_text}* {outcome_emoji}\n\n"
                f"Symbol: `{symbol}`\n"
                f"Outcome: `{status}`"
            )
            
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            self.logger.info(f"Successfully sent outcome notification for {symbol}.")
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification for {trade_details['symbol']}: {e}", exc_info=True)