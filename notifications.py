# # notifications.py
# import logging
# from os import link
# from typing import List, Dict, Any
# from telegram_handler import TelegramHandler
# import config

# logger = logging.getLogger(__name__)

# class NotificationHandler:
#     """
#     Handles the formatting and sending of all notifications to Telegram.
#     """
#     def __init__(self, telegram_handler: TelegramHandler):
#         self.telegram_handler = telegram_handler

#     def _get_common_footer(self) -> str:
#         """Creates a common, escaped footer for messages."""
#         separator = r"----------------------------------------"
#         # The link does not need escaping as it's not part of the parsed text
#         link = r"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
#         return (
#             f"\n{separator}\n\n"
#             "💰 *New to Binance? Get a \\$100 Bonus\\!* 💰\n\n"
#             "Sign up and earn a *100 USD trading fee rebate voucher\\!*\n\n"
#             "🔗 *Register Now:*\n"
#             f"{link}"
#         )

#     async def send_startup_notification(self, symbols_count: int):
#         """Sends a notification message when the bot starts."""
#         logger.info("Preparing startup notification...")
#         # Escape characters for MarkdownV2
#         timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
        
#         message_body = (
#             f"🚀 *AI Trading Bot has been successfully activated\\!* 🚀\n\n"
#             f"✨ The bot is now live and analyzing `{symbols_count}` USDT pairs on the `{timeframe_escaped}` timeframe\\.\n"
#             f"📡 Get ready for real\\-time market signals every 10 minute\\!"
#         )
#         link = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
#         footer = (
#             f"\n\n\\----------------------------------------\\\n"
#             f"Receive a *100 USD trading fee rebate voucher* each: {link}"
#         )
#         full_message = message_body + footer# Footer can be added if desired

#         try:
#             await self.telegram_handler.send_message(
#                 chat_id=config.TELEGRAM_CHAT_ID,
#                 message=full_message, # Uses 'message'
#                 message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
#             )
#             logger.info("Startup notification sent successfully.")
#         except Exception as e:
#             logger.error(f"Failed to send startup notification: {e}", exc_info=True)

#     async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
#         """Sends a single notification for a batch of new signals."""
#         if not analysis_results:
#             return
            
#         logger.info(f"Preparing to send a batch of {len(analysis_results)} signals.")
#         message_parts = [f"🆘 {len(analysis_results)} New Signal Found! 🔥 \n"]

#         header = f"🔥 {len(analysis_results)} New Signal Found!* 🔥\n"
#         message_lines = []
        
#         for result in analysis_results:
#             symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
#             trend = TelegramHandler.escape_markdownv2(result.get('trend', 'N/A').replace("_", " ").title())
#             price = result.get('last_price', 0)
#             formatted_price = TelegramHandler.escape_markdownv2(f"{price:.5f}") # Format and escape price
            
#             trend_emoji = "💹" if "Bullish" in result.get('trend', '') else "🔻"
#             formatted_line = f"🆘  {trend} {trend_emoji} {symbol} \n📌 ENTRY: ${formatted_price}"
#             message_lines.append(formatted_line)
#             stop_loss = (result.get('stop_loss'))
#             tp1 = (result.get('take_profit_1'))
#             tp2 = (result.get('take_profit_2'))
#             tp3 = (result.get('take_profit_3'))
#         body = "\n".join(message_lines)
#         full_message = header + "\n" + body

#         try:
#             await self.telegram_handler.send_message(
#                 chat_id=config.TELEGRAM_CHAT_ID,
#                 message=full_message, # Uses 'message'
#                 message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
#             )
#             logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")
#         except Exception as e:
#             logger.error(f"Could not send signal batch: {e}", exc_info=True)

#     async def send_summary_report(self, stats: Dict[str, Any]):
#         """Formats and sends a periodic performance report."""
#         logger.info("Preparing performance summary report...")
#         header = "🏆 *Strategy Performance Report (All\\-Time)* 🏆\n"
        
#         if stats.get('total_completed_trades', 0) > 0:
#             win_rate = TelegramHandler.escape_markdownv2(f"{stats.get('win_rate', 0.0):.2f}")
#             body = (
#                 f"\n✅ *Win Rate:* `{win_rate}%`"
#                 f"\n📊 *Completed Trades:* `{stats.get('total_completed_trades', 0)}`"
#                 f"\n👍 *Wins:* `{stats.get('wins', 0)}`"
#                 f"\n👎 *Losses:* `{stats.get('losses', 0)}`"
#                 f"\n\n*Breakdown by Trend:* {link}"
#             )
#         else:
#             body = "\nNo completed trades to analyze yet."
        
#         full_message = header + body

#         try:
#             await self.telegram_handler.send_message(
#                 chat_id=config.TELEGRAM_CHAT_ID,
#                 message=full_message, # Uses 'message'
#                 message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
#             )
#             logger.info("Successfully sent performance report to Telegram.")
#         except Exception as e:
#             logger.error(f"Failed to send performance report: {e}", exc_info=True)
            
#     async def send_heartbeat_notification(self, symbols_count: int):
#         """Sends a 'heartbeat' message to confirm that the bot is still running."""
#         logger.info("Sending heartbeat notification...")
#         message = (
#             f"❤️ *Bot Status: ALIVE* ❤️\n\n"
#             f"The bot is running correctly and currently monitoring `{symbols_count}` symbols\\. "
#             f"No critical errors have been detected\\."
#         )
#         try:
#             await self.telegram_handler.send_message(
#                 chat_id=config.TELEGRAM_CHAT_ID,
#                 message=message, # Uses 'message'
#                 message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
#                 disable_notification=True # Send silently
#             )
#             logger.info("Heartbeat notification sent successfully.")
#         except Exception as e:
#             logger.error(f"Failed to send heartbeat notification: {e}", exc_info=True)

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
            photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png"
            
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

    # --- THIS IS THE UPDATED FUNCTION ---
    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """
        Sends a detailed notification for new signals, including SL and TP levels.
        """
        if not analysis_results:
            return
        
        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} detailed signals.")
        
        message_parts = [f"✅ *{len(analysis_results)} New Signal(s) Found\\!* 🔥"]
        
        for result in analysis_results:
            # Helper function to safely format and escape numbers
            def format_and_escape(value, precision=4):
                if value is None:
                    return 'N/A'
                formatted_value = f"{value:.{precision}f}"
                return TelegramHandler.escape_markdownv2(formatted_value)

            # Extract and format all necessary data
            symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
            trend = TelegramHandler.escape_markdownv2(result.get('trend', 'N/A').replace("_", " ").title())
            entry_price = format_and_escape(result.get('entry_price'))
            stop_loss = format_and_escape(result.get('stop_loss'))
            tp1 = format_and_escape(result.get('take_profit_1'))
            tp2 = format_and_escape(result.get('take_profit_2'))
            tp3 = format_and_escape(result.get('take_profit_3'))
            
            trend_emoji = "🔼" if "Bullish" in result.get('trend', '') else "🔽"

            # Build the detailed message string for one signal
            signal_detail = (
                f"\n\n----------------------------------------\n\n"
                f"{trend_emoji} *{symbol}* \\- {trend}\n"
                f"*Entry:* `{entry_price}`\n"
                f"*SL:* `{stop_loss}`\n"
                f"*TP1:* `{tp1}`\n"
                f"*TP2:* `{tp2}`\n"
                f"*TP3:* `{tp3}`"
            )
            message_parts.append(signal_detail)
        
        full_message = "".join(message_parts)

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID
            )
            self.logger.info(f"Successfully sent detailed signal alert for {len(analysis_results)} symbols.")
        except Exception as e:
            self.logger.error(f"Could not send detailed signal batch: {e}", exc_info=True)

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
            f"✅ Bot Status: ALIVE\n\n"
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
