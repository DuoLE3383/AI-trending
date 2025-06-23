# notifications.py
import logging
from telegram_handler import TelegramHandler
import config  # Import config để lấy các thông tin cần thiết

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

    async def send_startup_notification(self, symbols_count: int):
        """
        Gửi tin nhắn thông báo khi bot khởi động, kèm lời mời hấp dẫn.
        """
        self.logger.info("Preparing startup notification...")

        # Đây là nội dung tin nhắn bằng tiếng Anh
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
        Gửi thông báo tín hiệu theo lô (không thay đổi).
        """
        if not analysis_results:
            return

        header = f"🔥 *{len(analysis_results)} New Signal(s) Found!* 🔥\n\n"
        message_lines = []
        for result in analysis_results:
            symbol = result.get('symbol', 'N/A')
            trend = result.get('trend', 'N/A').replace("_", " ").title()
            price = result.get('last_price', 0)
            
            trend_emoji = "🔼" if "Bullish" in trend else "🔽"
            formatted_line = f"{trend_emoji} *{symbol}* - {trend} at `${price:,.4f}`"
            f"📡 Get ready for real-time market signals!\n\n"
            f"----------------------------------------\n\n"
            f"💰 **New to Binance? Get a $100 Bonus!**\n\n"
            f"Sign up on the world's largest crypto exchange platform and earn a **100 USD trading fee rebate voucher!**\n\n"
            f"🔗 **Register Now:**\n"
            f"https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P"
            message_lines.append(formatted_line)
        
        full_message = header + "\n".join(message_lines)
        
        await self.telegram_handler.send_message(
            chat_id=chat_id,
            message=full_message,
            message_thread_id=message_thread_id,
            parse_mode="Markdown"
        )
        self.logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")

