# notifications.py (Phiên bản đã sửa lỗi cú pháp MarkdownV2 dứt điểm)
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
        if value is None: return '—'
        try:
            return self.esc(f"{float(value):.{precision}f}")
        except (ValueError, TypeError):
            return '—'

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

    async def _send_to_both(self, message: str, thread_id: int = None, disable_web_page_preview=False):
        common_kwargs = {'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_web_page_preview}
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'message_thread_id': thread_id, **common_kwargs}
        channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'text': message, **common_kwargs}
        await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)
        await self._send_with_retry(self.telegram_handler.send_message, **channel_kwargs)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2', 'message_thread_id': thread_id}
        channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2'}
        await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)

    # === CÁC HÀM GỬI THÔNG BÁO (ĐÃ SỬA LỖI) ===

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        if not analysis_results: return
        header = f"📈 *New AI Trading Signals \\({self.esc(config.TIMEFRAME)}\\)*"
        message_parts = [header]
        separator = self.esc("\n\n" + "-"*25 + "\n")
        for result in analysis_results:
            symbol = result.get('symbol', 'N/A')
            direction = "LONG 🔼" if 'BULLISH' in result.get('trend', '') else "SHORT 🔽"
            tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{symbol}.P"
            signal_block = (
                f"\n*{self.esc(symbol)}* \\| [Chart]({tv_link})"
                f"\n🧭 *Direction:* {self.esc(direction)}"
                f"\n👉 *Entry:* `{self.format_and_escape(result.get('entry_price'))}`"
                f"\n🛡️ *Stop Loss:* `{self.format_and_escape(result.get('stop_loss'))}`"
                f"\n🎯 *Take Profit 1:* `{self.format_and_escape(result.get('take_profit_1'))}`"
            )
            message_parts.append(signal_block)
        await self._send_to_both(separator.join(message_parts), thread_id=config.TELEGRAM_MESSAGE_THREAD_ID, disable_web_page_preview=True)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        try:
            status_raw = trade_details.get('status', 'N/A')
            trend_raw = trade_details.get('trend', '')
            is_win = "TP" in status_raw
            header_icon, header_text = ("🟢", "WIN") if is_win else ("🔴", "LOSS")
            header = f"{header_icon} *Trade Closed: {self.esc(header_text)}*"
            symbol = trade_details.get('symbol', 'N/A')
            direction = "LONG 🔼" if 'BULLISH' in trend_raw else "SHORT 🔽"
            duration_str = ""
            entry_time, outcome_time = trade_details.get('entry_timestamp_utc'), trade_details.get('outcome_timestamp_utc')
            if entry_time and outcome_time:
                try:
                    duration = pd.to_datetime(outcome_time) - pd.to_datetime(entry_time)
                    h, rem = divmod(duration.total_seconds(), 3600); m, _ = divmod(rem, 60)
                    duration_str = f" \\| ⏳ {int(h)}h {int(m)}m"
                except Exception: pass
            pnl_str = "—"
            entry_p, closing_p = trade_details.get('entry_price'), trade_details.get('exit_price')
            if entry_p and closing_p:
                try:
                    pnl = ((float(closing_p) - float(entry_p)) / float(entry_p)) * 100
                    if 'BEARISH' in trend_raw: pnl *= -1
                    pnl_str = self.esc(f"{pnl * config.LEVERAGE:+.2f}%")
                except Exception: pass
            message = (
                f"{header}\n\n"
                f"*{self.esc(symbol)}* \\| {self.esc(direction)}\n"
                f"🏁 *Result:* {self.esc(status_raw)}{self.esc(duration_str)}\n"
                f"💰 *PNL \\(x{config.LEVERAGE}\\):* `{pnl_str}`"
            )
            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)

    async def send_startup_notification(self, symbols_count: int, accuracy: float | None):
        """SỬA LỖI: Xây dựng caption một cách an toàn tuyệt đối."""
        self.logger.info("Preparing startup notification...")
        
        # 1. Chuẩn bị các phần động và escape chúng
        safe_accuracy_msg = ""
        if accuracy is not None:
            safe_accuracy_msg = f"✅ *Initial Model Trained* \\| *Accuracy:* `{self.esc(f'{accuracy:.2%}')}`"
        else:
            safe_accuracy_msg = "⚠️ *Initial Model Training Failed/Skipped*"
        
        safe_timeframe_str = self.esc(config.TIMEFRAME)
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'

        # 2. Xây dựng các khối văn bản tĩnh (đã được escape thủ công)
        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{safe_timeframe_str}` timeframe\\."
        promo_msg = (
            f"💰 *New \\#Binance\\? Get a \\$100 Bonus\\!*\n"
            f"Sign up and earn a *100 USD trading fee rebate voucher\\!*\n\n"
            f"🔗 [Register Now]({binance_link})"
        )
        separator = self.esc("-----------------------------------------")

        # 3. Ghép nối tất cả các phần lại
        caption = (
            f"🚀 *AI Trading Bot Activated*\n\n"
            f"{safe_accuracy_msg}\n\n"
            f"{monitoring_msg}\n\n"
            f"{separator}\n\n"
            f"{promo_msg}"
        )
        
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_fallback_mode_startup_notification(self, symbols_count: int):
        """SỬA LỖI: Xây dựng caption an toàn cho chế độ dự phòng."""
        self.logger.info("Preparing fallback mode startup notification...")
        
        safe_timeframe_str = self.esc(config.TIMEFRAME)
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        
        main_msg = (
            f"⚠️ *AI Model not available* \\- not enough training data\\.\n\n"
            f"✅ Bot is now running in *Rule\\-Based Mode* and will collect data for future training\\.\n\n"
            f"📡 Monitoring `{symbols_count}` pairs on the `{safe_timeframe_str}` timeframe\\."
        )
        promo_msg = (
            f"💰 *New \\#Binance\\? Get a \\$100 Bonus\\!*\\n"
            f"Sign up and earn a *100 USD trading fee rebate voucher\\!*\n\n"
            f"🔗 [Register Now]({binance_link})"
        )
        separator = self.esc("-----------------------------------------")

        caption = (
            f"🚀 *AI Trading Bot Activated \\(Fallback Mode\\)*\n\n"
            f"{main_msg}\n\n"
            f"{separator}\n\n"
            f"{promo_msg}"
        )
        
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_training_complete_notification(self, accuracy: float | None):
        header = self.esc("🤖 AI Model Update")
        if accuracy is not None:
            status_message = f"✅ *Periodic Training Complete*\\.\n*New Accuracy:* `{self.esc(f'{accuracy:.2%}')}`"
        else:
            status_message = "❌ *Periodic Training Failed*\\."
        await self._send_to_both(f"{header}\n\n{status_message}", thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

