# telegram_handler.py
import httpx
import logging
import re

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self, api_token: str):
        if not api_token:
            raise ValueError("Telegram API token cannot be empty.")
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"

    @staticmethod
    def escape_markdownv2(text: str) -> str:
        """
        Escapes text for Telegram's MarkdownV2 parse mode.
        """
        if not isinstance(text, str):
            text = str(text)
        escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
        return re.sub(escape_chars, r'\\\1', text)

    async def send_message(self, chat_id: str, message: str, message_thread_id: str = None, parse_mode: str = "MarkdownV2"):
        """
        Sends a message to a given Telegram chat.
        This version uses 'message' as the parameter name.
        """
        url = f"{self.base_url}/sendMessage"
        params = {
            'chat_id': chat_id,
            'text': message,  # The API requires the key 'text', but our function uses 'message'
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        if message_thread_id:
            params['message_thread_id'] = message_thread_id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=params, timeout=20)
                response.raise_for_status()
                logger.info("Telegram message sent successfully.")
            except httpx.HTTPStatusError as e:
                logger.error(f"Telegram API Error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"An error occurred while requesting Telegram API: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred when sending Telegram message: {e}")