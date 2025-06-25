# notifications.py (Phiên bản cuối cùng, đã sửa tất cả các lỗi)
import logging
from typing import List, Dict, Any
import asyncio
from telegram_handler import TelegramHandler
import config
import re

logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger
        # Viết tắt để code gọn hơn
        self.esc = self.telegram_handler.escape_markdownv2

    # CẢI THIỆN: Hàm này giờ sử dụng hàm escape đáng tin cậy từ handler
    def format_and_escape(self, value, precision=5):
        if value is None:
            return '—'
        try:
            formatted_value = f"{float(value):.{precision}f}"
            return self.esc(formatted_value)
        except (ValueError, TypeError):
            return '—'

    # CẢI THIỆN: Giữ lại logic retry rất hay của bạn, đã sửa lỗi và làm gọn
    async def _send_with_retry(self, send_func, **kwargs):
        max_retries = 3
        delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                await send_func(**kwargs)
                return True  # Gửi thành công
            except Exception as e:
                log_msg = kwargs.get('text', kwargs.get('caption', 'N/A'))
                self.logger.error(f"Lỗi khi gửi (lần {attempt + 1}/{max_retries}): {e}")
                self.logger.debug(f"Nội dung lỗi: {log_msg[:200]}...") # Log 200 ký tự đầu của tin nhắn
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    self.logger.critical(f"❌ Thất bại sau {max_retries} lần thử. Bỏ qua tin nhắn.")
        return False

    async def _send_to_both(self, message: str, thread_id: int = None):
        group_kwargs = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'MarkdownV2',
            'message_thread_id': thread_id
        }
        channel_kwargs = {
            'chat_id': config.TELEGRAM_CHANNEL_ID,
            'text': message,
            'parse_mode': 'MarkdownV2'
        }

        group_success = await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)
        if group_success: self.logger.info("✅ Đã gửi tới group.")

        channel_success = await self._send_with_retry(self.telegram_handler.send_message, **channel_kwargs)
        if channel_success: self.logger.info("✅ Đã gửi tới channel.")

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        group_kwargs = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'photo': photo,
            'caption': caption,
            'parse_mode': 'MarkdownV2',
            'message_thread_id': thread_id
        }
        channel_kwargs = {
            'chat_id': config.TELEGRAM_CHANNEL_ID,
            'photo': photo,
            'caption': caption,
            'parse_mode': 'MarkdownV2'
        }
        group_success = await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)
        if group_success: self.logger.info("✅ Đã gửi ảnh tới group.")
        
        channel_success = await self._send_with_retry(self.telegram_handler.send_photo, **channel_kwargs)
        if channel_success: self.logger.info("✅ Đã gửi ảnh tới channel.")

    # === CÁC HÀM GỬI THÔNG BÁO (Đã được viết lại hoàn toàn cho an toàn và chính xác) ===

    async def send_startup_notification(self, symbols_count: int):
        self.logger.info("Preparing startup notification with photo...")
        separator = self.esc("-----------------------------------------")
        caption_text = (
            f" *AI 🧠 Model TRADING training every 8h Activated* \n\n"
            f"The bot is now live and analyzing `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\.\n\n"
            f"📡 Get ready for real\\-time market signals every 10 minutes\\!\n\n"
            f"💰 *New \\#Binance\\? Get a \\$100 Bonus\\!*\\n"
            f"Sign up and earn a *100 USD trading fee rebate voucher\\!*\\n\n"
            f"🔗 *Register Now\\:*\n"
            f"{self.esc('https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P')}\n\n"
            f"{separator}"
        )
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption_text, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        if not analysis_results: return
        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} detailed signals.")

        separator = self.esc("\n\n----------------------------------------\n\n")
        header = self.esc(f"🆘 {len(analysis_results)} New Signal(s) Found! 🔥")
        message_parts = [header]

        for result in analysis_results:
            trend_raw = result.get('trend', 'N/A').replace("_", " ").title()
            trend_emoji = "🔼 LONG" if "Bullish" in trend_raw else "🔽 SHORT"
            signal_detail = (
                f"{separator}"
                f"\\#{self.esc(trend_raw)} // {trend_emoji} // {self.esc(result.get('symbol', 'N/A'))}\n"
                f"📌*Entry:* {self.format_and_escape(result.get('entry_price'))}\n"
                f"❌*SL:* {self.format_and_escape(result.get('stop_loss'))}\n"
                f"🎯*TP1:* {self.format_and_escape(result.get('take_profit_1'))}\n"
                f"🎯*TP2:* {self.format_and_escape(result.get('take_profit_2'))}\n"
                f"🎯*TP3:* {self.format_and_escape(result.get('take_profit_3'))}"
            )
            message_parts.append(signal_detail)

        await self._send_to_both("".join(message_parts), thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_summary_report(self, stats: Dict[str, Any]):
        self.logger.info("Preparing performance summary report...")
        header = self.esc("🏆 *Strategy Performance Report (All-Time)* 🏆\n")

        if stats.get('total_completed_trades', 0) > 0:
            win_rate_val = f"{stats.get('win_rate', 0.0):.2f}%"
            body = (
                f"\n✅ *Win Rate:* `{self.esc(win_rate_val)}`"
                f"\n📊 *Completed Trades:* `{stats.get('total_completed_trades', 0)}`"
                f"\n👍 *Wins:* `{stats.get('wins', 0)}`"
                f"\n👎 *Losses:* `{stats.get('losses', 0)}`"
            )
        else:
            body = "\nNo completed trades to analyze yet."

        await self._send_to_both(header + body, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_heartbeat_notification(self, symbols_count: int):
        self.logger.info("Sending heartbeat notification...")
        message_text = (
            f"✅ *Bot Status: ALIVE*\n\n"
            f"The bot is running correctly and currently monitoring `{symbols_count}` symbols. "
            f"No critical errors have been detected."
        )
        await self._send_to_both(self.esc(message_text), thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        self.logger.info(f"Preparing outcome notification for {trade_details.get('symbol', 'N/A')}...")
        try:
            status_raw = trade_details.get('status', 'N/A')
            trend_raw = trade_details.get('trend', 'N/A').replace("_", " ").title()
            entry_price_raw = trade_details.get('entry_price')
            closing_price_raw = None

            if status_raw == 'SL_HIT':
                closing_price_raw = trade_details.get('stop_loss')
            elif 'TP' in status_raw:
                tp_map = {'TP1_HIT': 'take_profit_1', 'TP2_HIT': 'take_profit_2', 'TP3_HIT': 'take_profit_3'}
                closing_price_raw = trade_details.get(tp_map.get(status_raw))

            pnl_without_leverage_str = "—"
            pnl_with_leverage_str = "—"
            if entry_price_raw is not None and closing_price_raw is not None:
                try:
                    entry_p = float(entry_price_raw)
                    closing_p = float(closing_price_raw)
                    if entry_p != 0:
                        pnl_percent = ((closing_p - entry_p) / entry_p) * 100
                        if "Bearish" in trend_raw: pnl_percent *= -1 # Invert for shorts
                        
                        pnl_with_leverage = pnl_percent * config.LEVERAGE
                        
                        pnl_without_leverage_str = self.esc(f"{pnl_percent:+.2f}%")
                        pnl_with_leverage_str = self.esc(f"{pnl_with_leverage:+.2f}%")
                except (ValueError, TypeError):
                    self.logger.warning("Could not calculate PNL due to invalid price data.")

            is_win = "TP" in status_raw
            outcome_emoji, outcome_text = ("✅", "WIN") if is_win else ("❌", "LOSS")
            trade_direction_text = "LONG" if "Bullish" in trend_raw else "SHORT"
            trend_emoji = "🔼 LONG" if "Bullish" in trend_raw else "🔽 SHORT"

            message = (
                f"{outcome_emoji} *Trade Closed: {self.esc(outcome_text)}* {outcome_emoji}\n\n"
                f"Symbol: `{self.esc(trade_details.get('symbol', 'N/A'))}`\n"
                f"Direction: `{self.esc(trade_direction_text)}` {trend_emoji}\n"
                f"Outcome: `{self.esc(status_raw)}`\n\n"
                f"Entry Price: `{self.format_and_escape(entry_price_raw)}`\n"
                f"Closing Price: `{self.format_and_escape(closing_price_raw)}`\n"
                f"PNL \\(1x\\): `{pnl_without_leverage_str}`\n"
                f"PNL \\(x{config.LEVERAGE}\\): `{pnl_with_leverage_str}`"
            )
            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)