# notifications.py
import logging
import re # Added for regex in strip_markdown
from typing import List, Dict, Any, Union # Added Union for type hinting
import config
from telegram_handler import TelegramHandler
logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger # Using the module-level logger

    def format_and_escape(self, value: Union[float, int, str, None], precision: int = 5) -> str:
        """
        Formats a numerical value to a string with specified precision and
        then escapes it for MarkdownV2, ensuring dots are preserved.

        Args:
            value (Union[float, int, str, None]): The value to format and escape.
                                                  Can be a number or a string that can be converted to float.
            precision (int): The number of decimal places for formatting.

        Returns:
            str: The formatted and MarkdownV2-escaped string, or '—' if value is None or invalid.
        """
        if value is None:
            return '—'
        try:
            formatted_value = f"{float(value):.{precision}f}"
            # Use the TelegramHandler's robust MarkdownV2 escaping
            return self.telegram_handler.escape_markdownv2(formatted_value)
        except (ValueError, TypeError): # Catch specific exceptions for float conversion
            self.logger.warning(f"Could not format value '{value}' as float. Returning '—'.", exc_info=True)
            return '—'

    async def _send_to_both(self, message: str, thread_id: Union[int, None] = None, parse_mode: str = "MarkdownV2") -> None:
        """
        Sends a message to both the configured Telegram group and channel.
        The message is sent with MarkdownV2 formatting to the group and
        as plain text (stripped of Markdown) to the channel.

        Args:
            message (str): The message content (expected to be MarkdownV2 escaped for the group).
            thread_id (Union[int, None]): The message thread ID for the group, if applicable.
            parse_mode (str): The parse mode for the group message (default: "MarkdownV2").
        """
        if not self.telegram_handler:
            self.logger.error("TelegramHandler is not initialized. Cannot send message.")
            return

        if not config.TELEGRAM_CHAT_ID:
            self.logger.error("config.TELEGRAM_CHAT_ID is not set. Cannot send to group.")
            return

        if not config.TELEGRAM_CHANNEL_ID:
            self.logger.error("config.TELEGRAM_CHANNEL_ID is not set. Cannot send to channel.")
            return

        try:
            # Send to group with MarkdownV2 formatting
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=message,
                message_thread_id=thread_id,
                parse_mode=parse_mode
            )
            self.logger.info(f"✅ Message sent to group {config.TELEGRAM_CHAT_ID}.")

            # Send to channel with plain content (no Markdown)
            # This function attempts to remove Markdown syntax and unescape characters.
            # Note: A full Markdown to plain text conversion is complex and might require a dedicated library.
            # This implementation provides a reasonable effort for common cases.
            plain_message = self.strip_markdown(message)
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHANNEL_ID,
                message=plain_message
            )
            self.logger.info(f"✅ Message sent to channel {config.TELEGRAM_CHANNEL_ID}.")
        except Exception as e:
            self.logger.error(f"❌ Failed to send to both group and channel: {e}", exc_info=True)

    def strip_markdown(self, text: str) -> str:
        """
        Strips MarkdownV2 formatting and unescapes characters to produce plain text.
        This function attempts to remove common Markdown syntax and backslashes
        used for escaping special characters in MarkdownV2.

        Args:
            text (str): The input string, potentially containing MarkdownV2 formatting.

        Returns:
            str: The string with MarkdownV2 formatting and escaping removed.
        """
        # Step 1: Unescape characters that TelegramHandler.escape_markdownv2 would escape.
        # This list should match the characters escaped by TelegramHandler.escape_markdownv2.
        # Note: Some characters are regex special characters and need to be escaped for re.sub.
        unescape_chars = r"_*~`>#+-=|{}!."
        for char in unescape_chars:
            # Replace escaped char (e.g., "\*") with unescaped char (e.g., "*")
            # Use re.escape to handle characters that are special in regex patterns.
            text = text.replace(f"\\{char}", char)

        # Step 2: Remove Markdown formatting syntax.
        # This uses regex to remove common Markdown patterns.
        # Bold/Italic: *text*, _text_
        text = re.sub(r'\*([^*]+)\*', r'\1', text) # *text* -> text
        text = re.sub(r'_([^_]+)_', r'\1', text)   # _text_ -> text
        # Strikethrough: ~text~
        text = re.sub(r'~([^~]+)~', r'\1', text)
        # Inline code: `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Links: text -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Blockquotes: > text
        text = re.sub(r'^>+\s*', '', text, flags=re.MULTILINE)
        # Headers: # text
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

        # Remove any remaining backslashes that might not have been part of an escape sequence
        # (e.g., if a literal backslash was in the original text and not escaped by TelegramHandler)
        text = text.replace('\\', '')

        return text

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: Union[int, None] = None, parse_mode: str = "MarkdownV2") -> None:
        """
        Sends a photo with a caption to both the configured Telegram group and channel.
        The caption is sent with MarkdownV2 formatting to the group and
        as plain text (stripped of Markdown) to the channel.

        Args:
            photo (str): The URL or file ID of the photo.
            caption (str): The caption content (expected to be MarkdownV2 escaped for the group).
            thread_id (Union[int, None]): The message thread ID for the group, if applicable.
            parse_mode (str): The parse mode for the group caption (default: "MarkdownV2").
        """
        if not self.telegram_handler:
            self.logger.error("TelegramHandler is not initialized. Cannot send photo.")
            return

        if not config.TELEGRAM_CHAT_ID:
            self.logger.error("config.TELEGRAM_CHAT_ID is not set. Cannot send photo to group.")
            return

        if not config.TELEGRAM_CHANNEL_ID:
            self.logger.error("config.TELEGRAM_CHANNEL_ID is not set. Cannot send photo to channel.")
            return

        try:
            await self.telegram_handler.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=photo,
                caption=caption,
                message_thread_id=thread_id,
                parse_mode=parse_mode
            )
            self.logger.info(f"✅ Photo sent to group {config.TELEGRAM_CHAT_ID}.")

            # Caption for channel should remove Markdown if present
            plain_caption = self.strip_markdown(caption)
            await self.telegram_handler.send_photo(
                chat_id=config.TELEGRAM_CHANNEL_ID,
                photo=photo,
                caption=plain_caption
            )
            self.logger.info(f"✅ Photo sent to channel {config.TELEGRAM_CHANNEL_ID}.")
        except Exception as e:
            self.logger.error(f"❌ Failed to send photo to both group and channel: {e}", exc_info=True)

    async def send_startup_notification(self, symbols_count: int) -> None:
        """
        Sends a startup notification with a photo to Telegram.

        Args:
            symbols_count (int): The number of symbols the bot is monitoring.
        """
        self.logger.info("Preparing startup notification with photo...")
        try:
            timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
            caption_text = (
                f"🚀 *AI Trading Bot Activated* 🚀\n\n"
                f"The bot is now live and analyzing `{symbols_count}` pairs on the `{timeframe_escaped}` timeframe.\n\n"
                f"📡 Get ready for real-time market signals every 10 minutes!\n\n"
                f"💰 New to Binance? Get a $100 Bonus!*\n"
                f"Sign up and earn a 100 USD trading fee rebate voucher!*\n\n"
                f"🔗 Register Now:\n"
                f"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P\n\n"
                f"------------------------------------"
            )
            photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
            self.logger.debug(f"Startup notification photo URL: {photo_url}")
            self.logger.debug(f"Startup notification caption text (MarkdownV2): {caption_text}")
            await self._send_photo_to_both(photo=photo_url, caption=caption_text, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]) -> None:
        """
        Sends a batch of trend alert notifications to Telegram.
        Each alert includes symbol, trend, entry, stop loss, and take profit levels.

        Args:
            analysis_results (List[Dict[str, Any]]): A list of dictionaries, each containing analysis results for a symbol.
        """
        if not analysis_results:
            return

        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} detailed signals.")

        message_parts = [f"🖘 {len(analysis_results)} New Signal(s) Found! 🔥"]

        for result in analysis_results:
            symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
            trend_raw = result.get('trend', 'N/A').replace("_", " ").title()
            trend = TelegramHandler.escape_markdownv2(trend_raw)

            entry_price = self.format_and_escape(result.get('entry_price'))
            stop_loss = self.format_and_escape(result.get('stop_loss'))
            tp1 = self.format_and_escape(result.get('take_profit_1'))
            tp2 = self.format_and_escape(result.get('take_profit_2'))
            tp3 = self.format_and_escape(result.get('take_profit_3'))

            trend_emoji = "💹" if "Bullish" in trend_raw else "🛑"

            signal_detail = (
                
                f" 📣 #{trend} // {trend_emoji} // {symbol} \n"
                f"\n\n-----------------------------\n\n"
                f"📌Entry: {entry_price}\n"
                f"⛔️SL: {stop_loss}\n"
                f"🎯TP1: {tp1}\n"
                f"🎯TP2: {tp2}\n"
                f"🎯TP3: {tp3}"
            )

            message_parts.append(signal_detail)

        full_message = "".join(message_parts)
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_summary_report(self, stats: Dict[str, Any]) -> None:
        """
        Sends a performance summary report to Telegram.

        Args:
            stats (Dict[str, Any]): A dictionary containing performance statistics.
        """
        self.logger.info("Preparing performance summary report...")
        header = "🏆 *Strategy Performance Report (All-Time)* 🏆\n"

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
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_heartbeat_notification(self, symbols_count: int) -> None:
        """
        Sends a heartbeat notification to Telegram, indicating the bot is alive and monitoring.

        Args:
            symbols_count (int): The number of symbols the bot is currently monitoring.
        """
        self.logger.info("Sending heartbeat notification...")
        message = (
            f"✅ Bot Status: ALIVE\n\n"
            f"The bot is running correctly and currently monitoring `{symbols_count}` symbols. "
            f"AI traning signal."
        )
        await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]) -> None:
        """
        Sends a trade outcome notification (win/loss) to Telegram.

        Args:
            trade_details (Dict[str, Any]): A dictionary containing details about the trade outcome.
        """
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

            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification for {trade_details['symbol']}: {e}", exc_info=True)
