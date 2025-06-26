# notifications.py (Phiên bản cuối cùng, đã sửa lỗi cú pháp MarkdownV2 dứt điểm)
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
        # Lối tắt để gọi hàm escape, giúp code gọn hơn
        self.esc = self.telegram_handler.escape_markdownv2

    def format_and_escape(self, value: Any, precision: int = 5) -> str:
        """Định dạng một giá trị số và escape nó an toàn cho MarkdownV2."""
        if value is None: return '`—`'
        try:
            # Trả về chuỗi đã được định dạng và escape, nằm trong dấu ``
            return f"`{self.esc(f'{float(value):.{precision}f}')}`"
        except (ValueError, TypeError):
            return '`—`'

    async def _send_with_retry(self, send_func, **kwargs):
        """Hàm helper để gửi tin nhắn/ảnh với cơ chế thử lại."""
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
        """Gửi tin nhắn văn bản đến cả group và channel."""
        common_kwargs = {'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_web_page_preview}
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'message_thread_id': thread_id, **common_kwargs}
        # Bỏ gửi đến channel thứ 2 để tránh spam nếu không cần thiết, bạn có thể mở lại nếu muốn
        await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        """Gửi ảnh có chú thích đến cả group và channel."""
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2', 'message_thread_id': thread_id}
        await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)


    # === CÁC HÀM GỬI THÔNG BÁO (THEO PHONG CÁCH CŨ, ĐÃ SỬA LỖI) ===

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """Gửi một tin nhắn riêng cho mỗi tín hiệu mới."""
        if not analysis_results: return
        
        header = self.esc("🆘 1 New Signal(s) Found! 🔥")
        separator = self.esc("\n\n----------------------------------------\n\n")

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
        """Thông báo kết quả giao dịch theo định dạng chi tiết cũ."""
        try:
            status_raw = trade_details.get('status', 'N/A')
            trend_raw = trade_details.get('trend', '')
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
        """Xây dựng caption một cách an toàn để gửi thông báo khởi động."""
        self.logger.info("Preparing startup notification...")
        
        safe_accuracy_msg = ""
        if accuracy is not None:
            accuracy_str = self.esc(f"{accuracy:.2%}")
            safe_accuracy_msg = f"✅ *Initial Model Trained* \\| *Accuracy:* `{accuracy_str}`"
        else:
            safe_accuracy_msg = "⚠️ *Initial Model Training Failed/Skipped*"
        
        safe_timeframe_str = self.esc(config.TIMEFRAME)
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'

        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{safe_timeframe_str}` timeframe\\."
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        
        separator = self.esc("-----------------------------------------")

        caption = "\n\n".join([
            "🚀 *AI Trading Bot Activated*",
            safe_accuracy_msg,
            monitoring_msg,
            separator,
            promo_msg
        ])
        
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)


    async def send_training_complete_notification(self, accuracy: float | None, symbols_count: int):
        """CẬP NHẬT: Thông báo kết quả training định kỳ, có kèm status và promo."""
        self.logger.info("Preparing periodic training complete notification...")
        header = self.esc("🤖 AI Model Update")
        
        status_message = ""
        if accuracy is not None:
            accuracy_str = self.esc(f"{accuracy:.2%}")
            status_message = f"✅ *Periodic Training Complete*\\.\n*New Accuracy:* `{accuracy_str}`"
        else:
            status_message = "❌ *Periodic Training Failed*\\."
            
        # Thêm dòng trạng thái giám sát
        safe_timeframe_str = self.esc(config.TIMEFRAME)
        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{safe_timeframe_str}` timeframe\\."

        separator = self.esc("-----------------------------------------")
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"

        full_message = "\n\n".join([
            header,
            status_message,
            monitoring_msg,
            separator,
            promo_msg
        ])
        
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_fallback_mode_startup_notification(self, symbols_count: int):
        """Thông báo khi bot khởi động ở chế độ dự phòng (không có AI)."""
        self.logger.info("Preparing fallback mode startup notification...")
        
        safe_timeframe_str = self.esc(config.TIMEFRAME)
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        
        main_msg = (
            f"⚠️ *AI Model not available* \\- not enough training data\\.\n"
            f"✅ Bot is running in *Rule\\-Based Mode* and collecting data\\.\n\n"
            f"📡 Monitoring `{symbols_count}` pairs on the `{safe_timeframe_str}` timeframe\\."
        )
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        separator = self.esc("-----------------------------------------")
        
        caption = "\n\n".join([
            "🚀 *AI Trading Bot Activated \\(Fallback Mode\\)*",
            main_msg,
            separator,
            promo_msg
        ])
        
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
