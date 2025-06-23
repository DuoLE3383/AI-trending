# telegram_handler.py
import httpx
import logging

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"

    async def send_message(self, chat_id: str, message: str, message_thread_id: str = None, parse_mode: str = "Markdown"):
        url = f"{self.base_url}/sendMessage"
        params = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        if message_thread_id:
            params['message_thread_id'] = message_thread_id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=params, timeout=20)
                response.raise_for_status()
                logger.debug("Telegram message sent successfully.")
            except httpx.HTTPStatusError as e:
                logger.error(f"Telegram API Error: {e.response.status_code} - {e.response.text}")
                # Xử lý lỗi rate limit
                if e.response.status_code == 429:
                    retry_after = int(e.response.json().get('parameters', {}).get('retry_after', 30))
                    logger.warning(f"Flood control exceeded. Retrying in {retry_after} seconds.")
                    # Trong một hệ thống thực tế, bạn có thể muốn chờ và thử lại ở đây.
            except Exception as e:
                logger.error(f"An unexpected error occurred when sending Telegram message: {e}")

