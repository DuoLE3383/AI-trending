# telegram_handler.py
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
        """
        Initializes the TelegramHandler.

        Args:
            api_token (str): The Telegram Bot API token.

        Raises:
            ValueError: If the API token is empty.
        """
        if not api_token:
            logger.error("Telegram API token is missing.")
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
        # Escapes characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
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
                
                # Check for non-successful status codes
                if response.status_code != 200:
                    logger.error(
                        f"Telegram API Error for endpoint '{endpoint}': {response.status_code} - {response.text}"
                    )
                
                # Will raise an HTTPStatusError for 4xx/5xx responses
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}", exc_info=True)
            # Re-raise the exception to be handled by the caller
            raise
        except httpx.RequestError as e:
            logger.error(f"A request error occurred: {e}", exc_info=True)
            raise

    async def get_me(self) -> Dict[str, Any]:
        """
        Tests the bot's authentication token.

        Returns:
            A dictionary containing the bot's information if successful.
        """
        logger.info("Verifying bot token with getMe...")
        response_data = await self._make_request("GET", "getMe")
        logger.info(f"Bot verified successfully: {response_data.get('result', {}).get('username')}")
        return response_data

    async def send_message(self, chat_id: Union[str, int], text: str, **kwargs: Any):
        """
        Sends a text-only message with enhanced error logging.

        Args:
            chat_id (str or int): Unique identifier for the target chat.
            text (str): The text of the message to be sent.
            **kwargs: Other optional API parameters like 'parse_mode', 'message_thread_id'.
        """
        payload = {'chat_id': chat_id, 'text': text, **kwargs}
        await self._make_request("POST", "sendMessage", json=payload)
        logger.info(f"Telegram text message sent successfully to chat_id: {chat_id}.")

    async def send_photo(
        self,
        chat_id: Union[str, int],
        photo: Union[str, bytes],
        caption: str = "",
        **kwargs: Any
    ):
        """
        Sends a photo with a caption.

        Args:
            chat_id (str or int): Unique identifier for the target chat.
            photo (str or bytes): Photo to send. Can be a URL (str) or file content (bytes).
            caption (str, optional): Photo caption.
            **kwargs: Other optional API parameters like 'parse_mode', 'message_thread_id'.
        """
        data = {'chat_id': str(chat_id), 'caption': caption, **kwargs}
        files = None
        
        if isinstance(photo, str):
            # Photo is a URL or a file_id
            data['photo'] = photo
            await self._make_request("POST", "sendPhoto", json=data)
        elif isinstance(photo, bytes):
            # Photo is raw bytes, needs to be sent as multipart/form-data
            files = {'photo': ('image.png', photo, 'image/png')}
            await self._make_request("POST", "sendPhoto", data=data, files=files)
        else:
            logger.error(f"Invalid photo type: {type(photo)}. Must be a URL (str) or bytes.")
            raise TypeError("Invalid photo type. Must be a URL (str) or bytes.")
        
        logger.info(f"Telegram photo sent successfully to chat_id: {chat_id}.")