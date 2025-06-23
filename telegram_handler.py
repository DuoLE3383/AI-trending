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

        This method should be used on any dynamic part of a message
        (like symbol names, prices, hostnames) before including it in a message
        that uses MarkdownV2.

        Args:
            text: The string to escape.

        Returns:
            The escaped string, safe for Telegram.
        """
        # List of characters that need to be escaped in MarkdownV2
        # _ * [ ] ( ) ~ ` > # + - = | { } . !
        escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
        return re.sub(escape_chars, r'\\\1', text)

    async def send_message(self, chat_id: str, message: str, message_thread_id: str = None, parse_mode: str = "MarkdownV2"):
        """
        Sends a message to a given Telegram chat.

        Args:
            chat_id: The ID of the target chat.
            message: The message text to send.
            message_thread_id: The ID of a topic/thread if sending to a group with topics.
            parse_mode: The parse mode for the message. Defaults to "MarkdownV2".
                        If using MarkdownV2, remember to escape dynamic content with
                        `TelegramHandler.escape_markdownv2()`.
        """
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
                response.raise_for_status()  # Raises an exception for 4xx or 5xx status codes
                logger.info("Telegram message sent successfully.")
            except httpx.HTTPStatusError as e:
                # Log the specific error from Telegram's response body
                logger.error(f"Telegram API Error: {e.response.status_code} - {e.response.text}")
                # Special handling for rate-limiting
                if e.response.status_code == 429:
                    retry_after = int(e.response.json().get('parameters', {}).get('retry_after', 30))
                    logger.warning(f"Flood control exceeded. Retrying in {retry_after} seconds.")
                    # In a real system, you might want to wait and retry here.
            except httpx.RequestError as e:
                logger.error(f"An error occurred while requesting Telegram API: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred when sending Telegram message: {e}")

