# notifications.py (Phiên bản được thiết kế lại chuyên nghiệp)
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
        """
        Khởi tạo handler, chịu trách nhiệm định dạng và gửi tất cả các loại thông báo.
        """
        self.telegram_handler = telegram_handler
        self.logger = logger
        self.esc = self.telegram_handler.escape_markdownv2

    def format_and_escape(self, value: Any, precision: int = 5) -> str:
        """Định dạng một giá trị số và escape nó một cách an toàn."""
        if value is None: return '—'
        try:
            return self.esc(f"{float(value):.{precision}f}")
        except (ValueError, TypeError):
            return '—'

    async def _send_with_retry(self, send_func, **kwargs):
        """Hàm helper để gửi tin nhắn/ảnh với cơ chế thử lại."""
        # ... (Hàm này giữ nguyên như phiên bản chuẩn trước đó)
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
        """Gửi tin nhắn văn bản đến cả group và channel."""
        common_kwargs = {'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_web_page_preview}
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'message_thread_id': thread_id, **common_kwargs}
        channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'text': message, **common_kwargs}
        await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)
        await self._send_with_retry(self.telegram_handler.send_message, **channel_kwargs)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        """Gửi ảnh có chú thích đến cả group và channel."""
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2', 'message_thread_id': thread_id}
        channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2'}
        await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)

    # === CÁC HÀM GỬI THÔNG BÁO (THIẾT KẾ MỚI) ===

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """
        THIẾT KẾ MỚI: Gửi một tin nhắn duy nhất cho một loạt tín hiệu.
        """
        if not analysis_results: return
        self.logger.info(f"Preparing a batch of {len(analysis_results)} new signals.")

        header = f"📈 *New AI Trading Signals \\({self.esc(config.TIMEFRAME)}\\)*"
        message_parts = [header]
        separator = self.esc("\n\n" + "-"*25 + "\n")

        for result in analysis_results:
            symbol = self.esc(result.get('symbol', 'N/A'))
            trend_raw = result.get('trend', '')
            direction = "LONG 🔼" if 'BULLISH' in trend_raw else "SHORT 🔽"
            
            # Tạo link TradingView
            tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE%3A{result.get('symbol', 'N/A')}.P"
            
            signal_block = (
                f"\n*{symbol}* \\| [Chart]({self.esc(tv_link)})"
                f"\n🧭 *Direction:* {self.esc(direction)}"
                f"\n👉 *Entry:* `{self.format_and_escape(result.get('entry_price'))}`"
                f"\n🛡️ *Stop Loss:* `{self.format_and_escape(result.get('stop_loss'))}`"
                f"\n🎯 *Take Profit 1:* `{self.format_and_escape(result.get('take_profit_1'))}`"
            )
            message_parts.append(signal_block)

        full_message = separator.join(message_parts)
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID, disable_web_page_preview=True)


    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        """
        THIẾT KẾ MỚI: Thông báo kết quả giao dịch gọn gàng và chuyên nghiệp hơn.
        """
        self.logger.info(f"Preparing outcome notification for {trade_details.get('symbol', 'N/A')}...")
        try:
            status_raw = trade_details.get('status', 'N/A')
            trend_raw = trade_details.get('trend', 'N/A')
            is_win = "TP" in status_raw
            
            header_icon, header_text = ("🟢", "WIN") if is_win else ("🔴", "LOSS")
            header = f"{header_icon} *Trade Closed: {self.esc(header_text)}*"

            symbol = self.esc(trade_details.get('symbol', 'N/A'))
            direction = "LONG 🔼" if 'BULLISH' in trend_raw else "SHORT 🔽"
            
            # Tính toán thời gian giữ lệnh (nếu có)
            entry_time_str = trade_details.get('entry_timestamp_utc')
            outcome_time_str = trade_details.get('outcome_timestamp_utc')
            duration_str = ""
            if entry_time_str and outcome_time_str:
                try:
                    duration = pd.to_datetime(outcome_time_str) - pd.to_datetime(entry_time_str)
                    total_seconds = duration.total_seconds()
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    duration_str = f" \\| ⏳ {int(hours)}h {int(minutes)}m"
                except Exception:
                    pass # Bỏ qua nếu không thể tính toán

            # Tính PNL
            entry_p = trade_details.get('entry_price')
            closing_p = trade_details.get('exit_price') # Sử dụng cột exit_price
            pnl_str = "—"
            if entry_p and closing_p:
                try:
                    pnl = ((float(closing_p) - float(entry_p)) / float(entry_p)) * 100
                    if 'BEARISH' in trend_raw: pnl *= -1
                    pnl_str = self.esc(f"{pnl * config.LEVERAGE:+.2f}%")
                except (ValueError, TypeError): pass

            message = (
                f"{header}\n\n"
                f"*{symbol}* \\| {self.esc(direction)}\n"
                f"📋:* {self.esc(status_raw)}{self.esc(duration_str)}\n"
                f"� *PNL \\(x{config.LEVERAGE}\\):* `{pnl_str}`"
            )
            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)


    async def send_startup_notification(self, symbols_count: int, accuracy: float | None):
        """THIẾT KẾ MỚI: Thông báo khởi động gọn gàng."""
        self.logger.info("Preparing startup notification...")
        if accuracy is not None:
            training_msg = f"✅ *Initial Model Trained* \\| *Accuracy:* `{accuracy:.2%}`"
        else:
            training_msg = "⚠️ *Initial Model Training Failed/Skipped*"

        caption = (
            f"🚀 *AI Trading Bot Activated*\n\n"
            f"{self.esc(training_msg)}\n\n"
            f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        )
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)


    async def send_training_complete_notification(self, accuracy: float | None):
        """THIẾT KẾ MỚI: Thông báo cập nhật training."""
        header = self.esc("🤖 AI Model Update")
        if accuracy is not None:
            status_message = f"✅ *Periodic Training Complete*\\.\n*New Accuracy:* `{accuracy:.2%}`"
        else:
            status_message = "❌ *Periodic Training Failed*\\."
        
        await self._send_to_both(f"{header}\n\n{status_message}", thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
