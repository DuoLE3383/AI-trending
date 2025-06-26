# telegram_handler.py (Phiên bản đã sửa lỗi cú pháp và tối ưu)
import httpx
import logging
import re
from typing import Union, Dict, Any

logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    Handles interactions with the Telegram Bot API, including sending messages
    and photos, with robust error handling and logging.
    """
    def __init__(self, api_token: str):
        if not api_token:
            logger.error("Telegram API token is missing.")
            raise ValueError("Telegram API token cannot be empty.")
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"

    @staticmethod
    def escape_markdownv2(text: str) -> str:
        """
        Escapes text for Telegram's MarkdownV2 parse mode using regex.
        This is safer and prevents double-escaping.
        """
        if not isinstance(text, str):
            text = str(text)
        # Characters to escape: _*[]()~`>#+-=|{}.!
        escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
        return re.sub(escape_chars, r'\\\1', text)

    async def _make_request(self, method: str, endpoint: str, **kwargs: Any):
        """
        A generic, internal method to make requests to the Telegram API.
        Handles client initialization, request sending, and error logging.
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, timeout=30.0, **kwargs)
                
                # Check for non-successful status codes and log the exact error from Telegram
                if response.status_code != 200:
                    logger.error(
                        f"Telegram API Error for endpoint '{endpoint}': {response.status_code} - {response.text}"
                    )
                else:
                    logger.debug(f"Telegram API request to '{endpoint}' successful: {response.status_code}")

                response.raise_for_status()
                
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while requesting '{endpoint}': {e}", exc_info=False)
            raise
        except httpx.RequestError as e:
            logger.error(f"A network request error occurred while requesting '{endpoint}': {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"An unexpected error in _make_request to '{endpoint}': {e}", exc_info=True)
            raise

    async def send_message(self, chat_id: Union[str, int], text: str, **kwargs: Any):
        """Sends a text-only message with enhanced error logging."""
        payload = {'chat_id': str(chat_id), 'text': text, **kwargs}
        try:
            await self._make_request("POST", "sendMessage", json=payload)
            logger.info(f"Telegram text message sent successfully to chat_id: {chat_id}.")
        except Exception:
            logger.error(f"Failed to send text message to chat_id: {chat_id}.")


    async def send_photo(
        self,
        chat_id: Union[str, int],
        photo: Union[str, bytes],
        caption: str = "",
        **kwargs: Any
    ):
        """Sends a photo with a caption."""
        data = {'chat_id': str(chat_id), 'caption': caption, **kwargs}
        files = None
        
        try:
            if isinstance(photo, str):
                data['photo'] = photo
                await self._make_request("POST", "sendPhoto", json=data)
            elif isinstance(photo, bytes):
                files = {'photo': ('image.png', photo, 'image/png')}
                await self._make_request("POST", "sendPhoto", data=data, files=files)
            else:
                raise TypeError(f"Invalid photo type: {type(photo)}. Must be a URL (str) or bytes.")
            
            logger.info(f"Telegram photo sent successfully to chat_id: {chat_id}.")
        except Exception:
            logger.error(f"Failed to send photo to chat_id: {chat_id}.")
