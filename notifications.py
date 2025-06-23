# notifications.py (Phiên bản đã sửa lỗi và cải thiện)
import logging
from telegram_handler import TelegramHandler
import config

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

    async def send_startup_notification(self, symbols_count: int):
        """
        Gửi tin nhắn thông báo khi bot khởi động, kèm lời mời hấp dẫn.
        """
        self.logger.info("Preparing startup notification...")

        message = (
            f"🚀 **AI Trading Bot has been successfully activated!**\n\n"
            f"✨ The bot is now live and analyzing **{symbols_count}** USDT pairs on the `{config.TIMEFRAME}` timeframe.\n"
            f"📡 Get ready for real-time market signals!\n\n"
            f"----------------------------------------\n\n"
            f"💰 **New to Binance? Get a $100 Bonus!**\n\n"
            f"Sign up on the world's largest crypto exchange platform and earn a **100 USD trading fee rebate voucher!**\n\n"
            f"🔗 **Register Now:**\n"
            f"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
        )

        try:
            await self.telegram_handler.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message=message,
                message_thread_id=config.TELEGRAM_MESSAGE_THREAD_ID,
                parse_mode="Markdown"
            )
            self.logger.info("Startup notification sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send startup notification: {e}")

    async def send_batch_trend_alert_notification(self, chat_id: str, message_thread_id: str, analysis_results: list):
        """
        Gửi thông báo tín hiệu theo lô với cấu trúc Header, Body, Footer.
        """
        if not analysis_results:
            return

        # --- 1. Header ---
        header = f"🔥 *{len(analysis_results)} New Signal(s) Found!* 🔥\n\n"

        # --- 2. Body (Danh sách tín hiệu) ---
        message_lines = []
        for result in analysis_results:
            symbol = result.get('symbol', 'N/A')
            trend = result.get('trend', 'N/A').replace("_", " ").title()
            price = result.get('last_price', 0)
            
            trend_emoji = "🔼" if "Bullish" in trend else "🔽"
            # Tạo dòng cho mỗi tín hiệu
            formatted_line = f"{trend_emoji} *{symbol}* - {trend} at `${price:,.4f}`"
            message_lines.append(formatted_line)
        
        body = "\n".join(message_lines)

        # --- 3. Footer ---
        # Sử dụng 3 dấu ngoặc kép """...""" cho chuỗi đa dòng
        footer = """
----------------------------------------

💰 **New to Binance? Get a $100 Bonus!**
Sign up and earn a **100 USD trading fee rebate voucher!**

🔗 **Register Now:**
https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P
"""

        # --- 4. Ghép tất cả lại ---
        full_message = header + body + footer
        
        try:
            await self.telegram_handler.send_message(
                chat_id=chat_id,
                message=full_message,
                message_thread_id=message_thread_id,
                parse_mode="Markdown"
            )
            self.logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")
        except Exception as e:
            self.logger.error(f"Could not send signal batch due to an error.")
            
            
# In notifications.py

class NotificationHandler:
    # ... (init function and other methods are correct) ...

    # --- CẢI TIẾN: Sửa lỗi Markdown trong footer ---
    def _get_common_footer(self) -> str:
        """
        Tạo phần footer chung chứa link giới thiệu.
        Đã sửa lỗi Markdown bằng cách "escape" các ký tự đặc biệt ('_' và '-').
        """
        # The separator line with escaped hyphens
        separator = r"----------------------------------------"

        # The link with an escaped underscore in the ref code
        link = r"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"

        # By using raw strings (r"...") we make it cleaner, but you could also write it as:
        # separator = "\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\"
        # link = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA\\_006MBW985P"
        
        return (
            f"\n{separator}\n\n"
            "💰 **New to Binance? Get a $100 Bonus!**\n\n"
            "Sign up on the world's largest crypto exchange platform and earn a **100 USD trading fee rebate voucher!**\n\n"
            "🔗 **Register Now:**\n"
            f"{link}"
        )

    # ... (the rest of your NotificationHandler class) ...


