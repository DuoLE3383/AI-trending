# notifications.py
import logging
from telegram_handler import TelegramHandler

class NotificationHandler:
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

    async def send_batch_trend_alert_notification(self, chat_id: str, message_thread_id: str, analysis_results: list):
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
            message_lines.append(formatted_line)
        
        full_message = header + "\n".join(message_lines)
        
        await self.telegram_handler.send_message(
            chat_id=chat_id,
            message=full_message,
            message_thread_id=message_thread_id,
            parse_mode="Markdown"
        )
        self.logger.info(f"Successfully sent combined signal alert for {len(analysis_results)} symbols.")

    # Bạn có thể thêm lại hàm send_startup_notification ở đây nếu muốn
