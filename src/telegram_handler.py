# telegram_handler.py (Phiên bản đã sửa lỗi cú pháp và tối ưu)
import httpx
import logging
import re
from typing import Union, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    Handles interactions with the Telegram Bot API, including sending messages
    and photos, with robust error handling and logging.
    """
    def __init__(self, api_token: str, proxy_url: Optional[str] = None):
        if not api_token:
            logger.error("Telegram API token is missing.")
            raise ValueError("Telegram API token cannot be empty.")
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"
        # Store the proxy URL directly. The 'proxy' argument in httpx expects a string.
        # This change improves compatibility with various httpx versions.
        self.proxy_url = proxy_url
        if self.proxy_url:
            logger.info(f"Telegram handler configured to use proxy: {self.proxy_url}")


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
            # Use the 'proxy' argument for compatibility with older httpx versions
            # that do not recognize the 'proxies' dictionary argument.
            async with httpx.AsyncClient(proxy=self.proxy_url) as client:
                response = await client.request(method, url, timeout=30.0, **kwargs)
                response.raise_for_status()
                logger.debug(f"Telegram API request to '{endpoint}' successful: {response.status_code}")
                return response.json()

        except httpx.HTTPStatusError as e:
            # Log the detailed error response from Telegram for better debugging
            logger.critical(
                f"HTTP error for endpoint '{endpoint}': {e.response.status_code} - {e.response.text}"
            )
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
        await self._make_request("POST", "sendMessage", json=payload)
        logger.info(f"Telegram text message sent successfully to chat_id: {chat_id}.")


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
        
        if isinstance(photo, str):
            data['photo'] = photo
            await self._make_request("POST", "sendPhoto", json=data)
        elif isinstance(photo, bytes):
            files = {'photo': ('image.png', photo, 'image/png')}
            await self._make_request("POST", "sendPhoto", data=data, files=files)
        else:
            raise TypeError(f"Invalid photo type: {type(photo)}. Must be a URL (str) or bytes.")
        
        logger.info(f"Telegram photo sent successfully to chat_id: {chat_id}.")
