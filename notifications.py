# notifications.py
import logging
from typing import List, Dict, Any
from telegram_handler import TelegramHandler
import config

class NotificationHandler:
    """
    Quản lý việc tạo và gửi tất cả các loại thông báo qua Telegram.
    """
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

    def _get_common_footer(self) -> str:
        """
        Tạo phần footer chung chứa link giới thiệu để sử dụng trong nhiều thông báo.
        Đã sửa lỗi Markdown bằng cách sử dụng raw string để giữ nguyên ký tự '\'.
        """
        # Sử dụng raw string (r"...") là cách tốt nhất để đảm bảo các ký tự escape
        # như '\' được gửi đi chính xác tới API của Telegram.
        separator = r"----------------------------------------"
        link = r"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
        
        return (
            f"\n{separator}\n\n"
            "💰 **New to Binance? Get a $100 Bonus!**\n\n"
            "Sign up on the world's largest crypto exchange platform and earn a **100 USD trading fee rebate voucher!**\n\n"
            "🔗 **Register Now:**\n"
            f"{link}"
        )

    async def send_startup_notification(self, symbols_count: int):
        """
        Gửi tin nhắn thông báo khi bot khởi động.
        """
        self.logger.info("Preparing startup notification...")

        message_body = (
            f"🚀 **AI Trading Bot has been successfully activated!**\n\n"
            f"✨ The bot is now live and analyzing **{symbols_count}** USDT pairs on the `{config.TIMEFRAME}` timeframe.\n"
            f"📡 Get ready for real-time market signals!"
        )
        
        # Ghép body và footer (lấy từ hàm chung)
        full_message = message_body + self._get_common_footer()

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=full_message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="MarkdownV2" # Sử dụng MarkdownV2 để tương thích tốt hơn với ký tự escape
            )
            self.logger.info("Startup notification sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}", exc_info=True)

    async def send_batch_trend_alert_notification(self, analysis_results: List[Dict[str, Any]]):
        """
        Gửi thông báo tín hiệu theo lô với cấu trúc Header, Body, Footer.
        """
        if not analysis_results:
            return

        self.logger.info(f"Preparing to send a batch of {len(analysis_results)} signals.")

        # --- Header ---
        header = f"🔥 *{len(analysis_results)} New Signal(s) Found\\!* 🔥\n"

        # --- Body ---
        message_lines = []
        for result in analysis_results:
            symbol = result.get('symbol', 'N/A')
            # Cần escape các ký tự đặc biệt trong symbol nếu có, ví dụ: 'BTC-USDT'
            safe_symbol = symbol.replace('-', '\\-')
            trend = result.get('trend', 'N/A').replace("_", " ").title()
            price = result.get('last_price', 0)
            
            trend_emoji = "🔼" if "Bullish" in trend else "🔽"
            # Định dạng giá để dễ đọc hơn và escape ký tự '.'
            formatted_price = str(price).replace('.', '\\.')
            formatted_line = f"{trend_emoji} *{safe_symbol}* \\- {trend} at `${formatted_price}`"
            message_lines.append(formatted_line)
        
        body = "\n".join(message_lines)

        # --- Ghép tất cả lại và thêm footer ---
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
            self.logger.error(f"Could not send signal batch due to an error: {e}", exc_info=True)

    async def send_summary_report(self, stats: Dict[str, Any]):
        """
        Định dạng và gửi báo cáo hiệu suất định kỳ.
        """
        self.logger.info("Preparing performance summary report...")
        
        header = "🏆 *Strategy Performance Report (All\\-Time)* 🏆\n"

        if 'error' in stats:
            body = "\nCould not generate statistics."
        elif stats.get('total_completed_trades', 0) > 0:
            # Escape các ký tự '.' trong tỷ lệ
            win_rate_str = str(stats['win_rate']).replace('.', '\\.')
            loss_rate_str = str(stats['loss_rate']).replace('.', '\\.')
            body = (
                f"\n✅ *Win Rate:* `{win_rate_str}`"
                f"\n❌ *Loss Rate:* `{loss_rate_str}`"
                f"\n📊 *Completed Trades:* `{stats['total_completed_trades']}`"
            )
        else:
            body = "\nNo completed trades to analyze yet."

        full_message = header + body
        
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
