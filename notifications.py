import logging
from typing import List, Dict, Any
from telegram_handler import TelegramHandler
import config

class NotificationHandler:
    """
    Handles the formatting and sending of all notifications to Telegram.
    This class centralizes message creation and dispatching logic, making it
    easier to manage different types of alerts and reports.
    """
    def __init__(self, telegram_handler: TelegramHandler):
        """
        Initializes the NotificationHandler.

        Args:
            telegram_handler (TelegramHandler): An instance of the Telegram handler
                                                 for sending messages.
        """
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

    def _get_common_footer(self) -> str:
        """
        Creates a common footer containing a referral link to be used in various notifications.
        
        Note: MarkdownV2 special characters like '.', '!', '-' must be escaped with a backslash.
        
        Returns:
            str: A formatted string for the message footer.
        """
        separator = r"----------------------------------------"
        link = r"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
        return (
            f"\n{separator}\n\n"
            "💰 *New to Binance? Get a \\$100 Bonus\\!* 💰\n\n"
            "Sign up and earn a *100 USD trading fee rebate voucher\\!*\n\n"
            "🔗 *Register Now:*\n"
            f"{link}"
        )

    async def send_startup_notification(self, symbols_count: int):
        """
        Sends a notification message when the bot starts.

        Args:
            symbols_count (int): The number of trading symbols being monitored.
        """
        self.logger.info("Preparing startup notification...")
        message_body = (
            f"🚀 *AI Trading Bot has been successfully activated\\!* 🚀\n\n"
            f"✨ The bot is now live and analyzing `{symbols_count}` USDT pairs on the `{config.TIMEFRAME}` timeframe\\.\n"
            f"📡 Get ready for real\\-time market signals\\!"
        )
        full_message = message_body + self._get_common_footer()
        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="MarkdownV2"
            )
            self.logger.info("Startup notification sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """
        Sends a batch of signal notifications. Retrieves chat_id from the config.

        Args:
            analysis_results (List[Dict[str, Any]]): A list of dictionaries,
                                                     each containing analysis results for a symbol.
        """
        # Customize your message here
        message = f"✅ Bot is running correctly.\nCurrently analyzing *{symbols_count}* symbols.\nNext status update in 10 minutes."
        
        # Use the escape function for any dynamic text if needed
        # safe_message = TelegramHandler.escape_markdownv2(message)

        await self.telegram_handler.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            message=message
        )
        
        if not analysis_results:
            return
        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} signals.")
        header = f"🔥 *{len(analysis_results)} New Signal(s) Found\\!* 🔥\n"
        message_lines = []
        for result in analysis_results:
            symbol = result.get('symbol', 'N/A').replace('-', '\\-')
            trend = result.get('trend', 'N/A').replace("_", " ").title()
            price = result.get('last_price', 0)
            # Escape the '.' character to avoid MarkdownV2 errors
            formatted_price = str(price).replace('.', '\\.')
            trend_emoji = "🔼" if "Bullish" in trend else "🔽"
            formatted_line = f"{trend_emoji} *{symbol}* \\- {trend} at `${formatted_price}`"
            message_lines.append(formatted_line)
        
        body = "\n".join(message_lines)
        full_message = header + "\n" + body + self._get_common_footer()
        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="MarkdownV2"
            )
            self.logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")
        except Exception as e:
            self.logger.error(f"Could not send signal batch: {e}", exc_info=True)

    async def send_summary_report(self, stats: Dict[str, Any]):
        """
        Formats and sends a periodic performance report.

        Args:
            stats (Dict[str, Any]): A dictionary containing performance statistics.
        """
        self.logger.info("Preparing performance summary report...")
        header = "🏆 *Strategy Performance Report (All\\-Time)* 🏆\n"
        if 'error' in stats:
            body = "\nCould not generate statistics due to an error."
        elif stats.get('total_completed_trades', 0) > 0:
            # Escape the '.' character in rates for MarkdownV2
            win_rate_str = str(stats.get('win_rate', '0.0')).replace('.', '\\.')
            loss_rate_str = str(stats.get('loss_rate', '0.0')).replace('.', '\\.')
            body = (
                f"\n✅ *Win Rate:* `{win_rate_str}%`"
                f"\n❌ *Loss Rate:* `{loss_rate_str}%`"
                f"\n📊 *Completed Trades:* `{stats.get('total_completed_trades', 0)}`"
            )
        else:
            body = "\nNo completed trades to analyze yet."
        
        full_message = header + body + self._get_common_footer()
        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="MarkdownV2"
            )
            self.logger.info("Successfully sent performance report to Telegram.")
        except Exception as e:
            self.logger.error(f"Failed to send performance report: {e}", exc_info=True)
            
    async def send_heartbeat_notification(self, symbols_count: int):
        """
        Sends a 'heartbeat' message to confirm that the bot is still running.
        This is sent silently to avoid disturbing the user.

        Args:
            symbols_count (int): The current number of symbols being monitored.
        """
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
                parse_mode="MarkdownV2",
                # Send silently to avoid user notification spam
                disable_notification=True 
            )
            self.logger.info("Heartbeat notification sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat notification: {e}", exc_info=True)

# In your notifications.py file, inside the NotificationHandler class

# You might need to import logging and config at the top of this file
import logging
import config

logger = logging.getLogger(__name__)

# ... inside the class ...
async def send_startup_notification(self, symbols_count: int):
    # --- ADD LOGS INSIDE THE FUNCTION ---
    logger.info(">>> STEP 3: Entered 'send_startup_notification' function.")
    
    hostname = socket.gethostname()
    safe_hostname = TelegramHandler.escape_markdownv2(hostname)
    message = f"🚀 Bot startup successful on host `{safe_hostname}`\nMonitoring *{symbols_count}* symbols."
    
    logger.info(f">>> STEP 4: Preparing to send message to chat_id: {config.TELEGRAM_CHAT_ID}")
    # ------------------------------------
    
    await self.telegram_handler.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        message=message
    )

