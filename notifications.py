# notifications.py
import logging
from os import link
from typing import List, Dict, Any
from telegram_handler import TelegramHandler
import config

logger = logging.getLogger(__name__)

class NotificationHandler:
    """
    Handles the formatting and sending of all notifications to Telegram.
    """
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler

    def _get_common_footer(self) -> str:
        """Creates a common, escaped footer for messages."""
        separator = r"----------------------------------------"
        # The link does not need escaping as it's not part of the parsed text
        link = r"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
        return (
            f"\n{separator}\n\n"
            "💰 *New to Binance? Get a \\$100 Bonus\\!* 💰\n\n"
            "Sign up and earn a *100 USD trading fee rebate voucher\\!*\n\n"
            "🔗 *Register Now:*\n"
            f"{link}"
        )

    async def send_startup_notification(self, symbols_count: int):
        """Sends a notification message when the bot starts."""
        logger.info("Preparing startup notification...")
        # Escape characters for MarkdownV2
        timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
        
        message_body = (
            f"🚀 *AI Trading Bot has been successfully activated\\!* 🚀\n\n"
            f"✨ The bot is now live and analyzing `{symbols_count}` USDT pairs on the `{timeframe_escaped}` timeframe\\.\n"
            f"📡 Get ready for real\\-time market signals\\!"
        )
        link = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
        footer = (
            f"\n\n----------------------------------------\n"
            f"Receive a *100 USD trading fee rebate voucher* each: {link}"
        )
        full_message = message_body # Footer can be added if desired

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message, # Uses 'message'
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            logger.info("Startup notification sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """Sends a single notification for a batch of new signals."""
        if not analysis_results:
            return
            
        logger.info(f"Preparing to send a batch of {len(analysis_results)} signals.")
        header = f"🔥 *{len(analysis_results)} New Signal(s) Found\\!* 🔥\n"
        message_lines = []
        
        for result in analysis_results:
            symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
            trend = TelegramHandler.escape_markdownv2(result.get('trend', 'N/A').replace("_", " ").title())
            price = result.get('last_price', 0)
            formatted_price = TelegramHandler.escape_markdownv2(f"{price:.4f}") # Format and escape price
            
            trend_emoji = "🔼" if "Bullish" in result.get('trend', '') else "🔽"
            formatted_line = f"{trend_emoji} *{symbol}* \\- {trend} at `${formatted_price}`"
            message_lines.append(formatted_line)
        
        body = "\n".join(message_lines)
        full_message = header + "\n" + body

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message, # Uses 'message'
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")
        except Exception as e:
            logger.error(f"Could not send signal batch: {e}", exc_info=True)

    async def send_summary_report(self, stats: Dict[str, Any]):
        """Formats and sends a periodic performance report."""
        logger.info("Preparing performance summary report...")
        header = "🏆 *Strategy Performance Report (All\\-Time)* 🏆\n"
        
        if stats.get('total_completed_trades', 0) > 0:
            win_rate = TelegramHandler.escape_markdownv2(f"{stats.get('win_rate', 0.0):.2f}")
            body = (
                f"\n✅ *Win Rate:* `{win_rate}%`"
                f"\n📊 *Completed Trades:* `{stats.get('total_completed_trades', 0)}`"
                f"\n👍 *Wins:* `{stats.get('wins', 0)}`"
                f"\n👎 *Losses:* `{stats.get('losses', 0)}`"
                f"\n\n*Breakdown by Trend:* {link}"
            )
        else:
            body = "\nNo completed trades to analyze yet."
        
        full_message = header + body

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message, # Uses 'message'
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            logger.info("Successfully sent performance report to Telegram.")
        except Exception as e:
            logger.error(f"Failed to send performance report: {e}", exc_info=True)
            
    async def send_heartbeat_notification(self, symbols_count: int):
        """Sends a 'heartbeat' message to confirm that the bot is still running."""
        logger.info("Sending heartbeat notification...")
        message = (
            f"❤️ *Bot Status: ALIVE* ❤️\n\n"
            f"The bot is running correctly and currently monitoring `{symbols_count}` symbols\\. "
            f"No critical errors have been detected\\."
        )
        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=message, # Uses 'message'
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                disable_notification=True # Send silently
            )
            logger.info("Heartbeat notification sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send heartbeat notification: {e}", exc_info=True)