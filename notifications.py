# notifications.py
import logging
from typing import List, Dict, Any
from telegram_handler import TelegramHandler
import config

logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger

    def escape_markdownv2_without_dot(self, text: str) -> str:
        escape_chars = r"_*[]()~`>#+-=|{}!"
        for ch in escape_chars:
            text = text.replace(ch, f"\\{ch}")
        return text

    def format_and_escape(self, value, precision=5):
        if value is None:
            return '—'
        try:
            formatted_value = f"{float(value):.{precision}f}"
            return self.escape_markdownv2_without_dot(formatted_value)
        except Exception:
            return '—'

    async def send_startup_notification(self, symbols_count: int):
        self.logger.info("Preparing startup notification with photo...")
        try:
            timeframe_escaped = TelegramHandler.escape_markdownv2(config.TIMEFRAME)
            caption_text = (
                f"🚀 *AI Trading Bot Activated* 🚀\n\n"
                f"The bot is now live and analyzing `{symbols_count}` pairs on the `{timeframe_escaped}` timeframe\\.\n\n"
                f"📡 Get ready for real\-time market signals every 10 minutes\\!\n\n"
                f"💰 *New to Binance\\? Get a \\$100 Bonus\\!*\\n"
                f"Sign up and earn a *100 USD trading fee rebate voucher\\!*\\n\n"
                f"🔗 *Register Now\:*\n"
                f"https://www\.binance\.com/activity/referral\-entry/CPA\?ref\=CPA\_006MBW985P\n\n"
                f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-"
            )
            photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"

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
        if not analysis_results:
            return

        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} detailed signals.")

        message_parts = [f"🆘 {len(analysis_results)} New Signal(s) Found! 🔥"]

        for result in analysis_results:
            symbol = TelegramHandler.escape_markdownv2(result.get('symbol', 'N/A'))
            trend_raw = result.get('trend', 'N/A').replace("_", " ").title()
            trend = TelegramHandler.escape_markdownv2(trend_raw)

            entry_price = self.format_and_escape(result.get('entry_price'))
            stop_loss = self.format_and_escape(result.get('stop_loss'))
            tp1 = self.format_and_escape(result.get('take_profit_1'))
            tp2 = self.format_and_escape(result.get('take_profit_2'))
            tp3 = self.format_and_escape(result.get('take_profit_3'))

            trend_emoji = "🔼" if "Bullish" in trend_raw else "🔽"

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
