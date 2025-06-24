# notifications.py
import logging
import re
from typing import List, Dict, Any, Union
import config
from telegram_handler import TelegramHandler

logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger

    def format_and_escape(self, value: Union[float, int, str, None], precision: int = 5) -> str:
        if value is None:
            return '—'
        try:
            formatted_value = f"{float(value):.{precision}f}"
            return self.telegram_handler.escape_markdownv2(formatted_value)
        except (ValueError, TypeError):
            self.logger.warning(f"Could not format value '{value}' as float. Returning '—'.", exc_info=True)
            return '—'

    def strip_markdown(self, text: str) -> str:
        unescape_chars = r"_*~`>#+-=|{}!."
        for char in unescape_chars:
            text = text.replace(f"\\{char}", char)

        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        text = re.sub(r'~([^~]+)~', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'^>+\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        return text.replace('\\', '')

    async def _send_to_both(self, message: str, thread_id: Union[int, None] = None, parse_mode: str = "MarkdownV2") -> None:
        if not self.telegram_handler:
            self.logger.error("TelegramHandler is not initialized.")
            return
        if not config.TELEGRAM_CHAT_ID:
            self.logger.error("TELEGRAM_CHAT_ID not set.")
            return
        if not config.TELEGRAM_CHANNEL_ID:
            self.logger.error("TELEGRAM_CHANNEL_ID not set.")
            return

        try:
            # Send to group
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=message,
                message_thread_id=thread_id,
                parse_mode=parse_mode
            )
            self.logger.info(f"✅ Message sent to group {config.TELEGRAM_CHAT_ID}.")

            # Send plain version to channel
            plain_message = self.strip_markdown(message)
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHANNEL_ID,
                text=plain_message
            )
            self.logger.info(f"✅ Message sent to channel {config.TELEGRAM_CHANNEL_ID}.")
        except Exception as e:
            self.logger.error(f"❌ Failed to send message: {e}", exc_info=True)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: Union[int, None] = None, parse_mode: str = "MarkdownV2") -> None:
        if not self.telegram_handler:
            self.logger.error("TelegramHandler is not initialized.")
            return
        if not config.TELEGRAM_CHAT_ID:
            self.logger.error("TELEGRAM_CHAT_ID not set.")
            return
        if not config.TELEGRAM_CHANNEL_ID:
            self.logger.error("TELEGRAM_CHANNEL_ID not set.")
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

            plain_caption = self.strip_markdown(caption)
            await self.telegram_handler.send_photo(
                chat_id=config.TELEGRAM_CHANNEL_ID,
                photo=photo,
                caption=plain_caption
            )
            self.logger.info(f"✅ Photo sent to channel {config.TELEGRAM_CHANNEL_ID}.")
        except Exception as e:
            self.logger.error(f"❌ Failed to send photo: {e}", exc_info=True)

    async def send_startup_notification(self, symbols_count: int) -> None:
        self.logger.info("Sending startup notification...")
        try:
            timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
            caption_text = (
                f"🚀 *AI Trading Bot Activated* 🚀\n\n"
                f"The bot is now live and analyzing `{symbols_count}` pairs on the `{timeframe_escaped}` timeframe.\n\n"
                f"📡 Get ready for real-time market signals every 10 minutes!\n\n"
                f"💰 New to Binance? Get a $100 Bonus!*\n"
                f"🔗 https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P\n\n"
                f"----------------------------------------------"
            )
            photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
            await self._send_photo_to_both(photo=photo_url, caption=caption_text, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]) -> None:
        if not analysis_results:
            return
        self.logger.info(f"Sending {len(analysis_results)} trend alerts.")

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
                f"\n\n----------------------------------------\n\n"
                f" #{trend} // {trend_emoji} // {symbol} \n"
                f"📌Entry: {entry_price}\n"
                f"❌SL: {stop_loss}\n"
                f"🎯TP1: {tp1}\n"
                f"🎯TP2: {tp2}\n"
                f"🎯TP3: {tp3}"
            )

            message_parts.append(signal_detail)

        full_message = "".join(message_parts)
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_summary_report(self, stats: Dict[str, Any]) -> None:
        self.logger.info("Sending summary report...")
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
        self.logger.info("Sending heartbeat notification...")
        message = (
            f"✅ Bot Status: ALIVE\n\n"
            f"The bot is running correctly and currently monitoring `{symbols_count}` symbols. "
            f"No critical errors have been detected."
        )
        await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]) -> None:
        self.logger.info(f"Sending outcome for {trade_details['symbol']}...")
        try:
            symbol = TelegramHandler.escape_markdownv2(trade_details['symbol'])
            status = TelegramHandler.escape_markdownv2(trade_details['status'])

            is_win = "TP" in trade_details['status']
            outcome_emoji = "✅" if is_win else "❌"
            outcome_text = "WIN" if is_win else "LOSS"

            pnl_percent = trade_details.get('pnl_percent')
            if pnl_percent is not None:
                pnl_formatted = self.format_and_escape(pnl_percent, precision=2)
                pnl_line = f"\n📈 Result: `{pnl_formatted}%`"
            else:
                pnl_line = ""

            message = (
                f"{outcome_emoji} *Trade Closed: {outcome_text}* {outcome_emoji}\n\n"
                f"Symbol: `{symbol}`\n"
                f"Outcome: `{status}`"
                f"{pnl_line}"
            )

            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)
