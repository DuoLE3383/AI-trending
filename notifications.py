# notifications.py (Phiên bản cuối cùng, ổn định và đã sửa tất cả lỗi)
import logging
from typing import List, Dict, Any
import asyncio
from telegram_handler import TelegramHandler
import config
import re
import pandas as pd

logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger
        self.esc = self.telegram_handler.escape_markdownv2

    def format_and_escape(self, value: Any, precision: int = 5) -> str:
        if value is None: return '`—`'
        try:
            return f"`{self.esc(f'{float(value):.{precision}f}')}`"
        except (ValueError, TypeError):
            return '`—`'

    async def _send_with_retry(self, send_func, **kwargs):
        max_retries = 3; delay = 2
        for attempt in range(max_retries):
            try:
                await send_func(**kwargs)
                return True
            except Exception as e:
                self.logger.error(f"Lỗi khi gửi (lần {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1: await asyncio.sleep(delay); delay *= 2
                else: self.logger.critical(f"❌ Thất bại sau {max_retries} lần thử.")
        return False

    async def _send_to_both(self, message: str, thread_id: int = None, disable_web_page_preview: bool = False):
        common_kwargs = {'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_web_page_preview}
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'message_thread_id': thread_id, **common_kwargs}
        await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2', 'message_thread_id': thread_id}
        await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)

    # === CÁC HÀM GỬI THÔNG BÁO ===

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        if not analysis_results: return
        header = self.esc("🆘 1 New Signal(s) Found! 🔥")
        separator = self.esc("\n----------------------------------------\n")
        for result in analysis_results:
            trend_raw = result.get('trend', '').replace("_", " ").title()
            trend_emoji = "🔼 LONG" if "Bullish" in trend_raw else "🔽 SHORT"
            signal_detail = (
                f"\\#{self.esc(trend_raw)} // {trend_emoji} // {self.esc(result.get('symbol', 'N/A'))}\n"
                f"📌Entry: {self.format_and_escape(result.get('entry_price'))}\n"
                f"❌SL: {self.format_and_escape(result.get('stop_loss'))}\n"
                f"🎯TP1: {self.format_and_escape(result.get('take_profit_1'))}"
            )
            full_message = header + separator + signal_detail
            await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
            await asyncio.sleep(0.5)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        try:
            status_raw, trend_raw = trade_details.get('status', 'N/A'), trade_details.get('trend', '')
            is_win = "TP" in status_raw
            outcome_emoji, outcome_text = ("✅", "WIN") if is_win else ("❌", "LOSS")
            header = f"{outcome_emoji} *Trade Closed: {self.esc(outcome_text)}* {outcome_emoji}"
            symbol = self.esc(trade_details.get('symbol', 'N/A'))
            direction = f"LONG 🔼" if 'BULLISH' in trend_raw else f"SHORT 🔽"
            pnl_without_leverage_str, pnl_with_leverage_str = "`—`", "`—`"
            entry_p, closing_p = trade_details.get('entry_price'), trade_details.get('exit_price')
            if entry_p and closing_p:
                try:
                    pnl = ((float(closing_p) - float(entry_p)) / float(entry_p)) * 100
                    if 'BEARISH' in trend_raw: pnl *= -1
                    pnl_without_leverage_str = f"`{self.esc(f'{pnl:+.2f}%')}`"
                    pnl_with_leverage_str = f"`{self.esc(f'{pnl * config.LEVERAGE:+.2f}%')}`"
                except (ValueError, TypeError): pass
            message = (
                f"{header}\n\n"
                f"Symbol: `{symbol}`\n"
                f"Direction: `{self.esc(direction)}`\n"
                f"Outcome: `{self.esc(status_raw)}`\n\n"
                f"Entry Price: {self.format_and_escape(trade_details.get('entry_price'))}\n"
                f"Closing Price: {self.format_and_escape(closing_p)}\n"
                f"PNL \\(1x\\): {pnl_without_leverage_str}\n"
                f"PNL \\(x{config.LEVERAGE}\\): {pnl_with_leverage_str}"
            )
            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)

    async def send_startup_notification(self, symbols_count: int, accuracy: float | None):
        if accuracy is not None:
            accuracy_str = self.esc(f"{accuracy:.2%}")
            training_msg = f"✅ *Initial Model Trained* \\| *Accuracy:* `{accuracy_str}`"
        else:
            training_msg = "⚠️ *Initial Model Training Failed/Skipped*"
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        separator = self.esc("-----------------------------------------")
        caption = "\n\n".join(["🚀 *AI Trading Bot Activated*", training_msg, monitoring_msg, separator, promo_msg])
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_training_and_summary_notification(self, stats: Dict[str, Any], accuracy: float | None):
        """
        CẬP NHẬT: Gửi thông báo kết hợp: trạng thái training và tổng kết hiệu suất.
        """
        self.logger.info("Preparing training status and summary report notification...")
        header = self.esc("🤖 AI Model Update & Performance Report")
        
        training_status = ""
        if accuracy is not None:
            training_status = f"✅ *Periodic Training Complete*\\.\n*New Accuracy:* `{self.esc(f'{accuracy:.2%}')}`"
        else:
            training_status = "❌ *Periodic Training Failed*\\."

        summary_body = "No completed trades to analyze yet."
        if stats and stats.get('total_completed_trades', 0) > 0:
            summary_body = (
                f"📊 *Lifetime Performance:*\n"
                f"  » Win Rate: `{self.esc(f'{stats.get("win_rate", 0.0):.2f}%')}`\n"
                f"  » Total Trades: `{stats.get('total_completed_trades', 0)}` "
                f"\\({stats.get('wins', 0)}W / {stats.get('losses', 0)}L\\)"
            )
        
        full_message = "\n\n".join([header, training_status, summary_body])
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_fallback_mode_startup_notification(self, symbols_count: int):
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        main_msg = (
            f"⚠️ *AI Model not available* \\- not enough training data\\.\n"
            f"✅ Bot is running in *Rule\\-Based Mode* and collecting data\\.\n\n"
            f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        )
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        separator = self.esc("-----------------------------------------")
        caption = "\n\n".join(["🚀 *AI Trading Bot Activated \\(Fallback Mode\\)*", main_msg, separator, promo_msg])
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

