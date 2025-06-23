# telegram_handler.py
import httpx
import logging
import re
from typing import Optional, Dict, Any

# It's good practice to have a logger configured at the application level.
# If not, the following line will prevent "No handler found" warnings.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    A modern, asynchronous handler for sending messages via the Telegram Bot API.

    This class manages an efficient, persistent httpx.AsyncClient session and
    provides a robust method for sending messages, complete with detailed error
    handling and support for various message options like custom keyboards.

    Usage as a context manager (recommended):
    async with TelegramHandler(api_token="YOUR_TOKEN") as bot:
        await bot.send_message(chat_id="@mychannel", text="Hello world!")

    Usage with manual close:
    bot = TelegramHandler(api_token="YOUR_TOKEN")
    await bot.send_message(chat_id="@mychannel", text="Hello world!")
    await bot.close()
    """
    def __init__(self, api_token: str):
        """
        Initializes the TelegramHandler.

        Args:
            api_token: Your Telegram Bot API token.
        """
        if not api_token:
            raise ValueError("Telegram API token cannot be empty.")
        self.api_token = api_token
        self.base_url = f"https://api.telegram.org/bot{self.api_token}"
        # For efficiency, create a single client session to be reused.
        self._client = httpx.AsyncClient(timeout=20.0)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escapes text for Telegram's MarkdownV2 parse mode.

        This method should be used on any dynamic part of a message before
        including it in a message that uses MarkdownV2.

        Args:
            text: The string to escape.

        Returns:
            The escaped string, safe for Telegram's MarkdownV2.
        """
        # Telegram MarkdownV2 reserved characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
        escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
        return re.sub(escape_chars, r'\\\1', str(text))

    async def send_message(
        self,
        chat_id: str,
        text: str,
        message_thread_id: Optional[str] = None,
        parse_mode: Optional[str] = "MarkdownV2",
        disable_web_page_preview: bool = True,
        disable_notification: bool = False,
        protect_content: bool = False,
        reply_markup: Optional[Dict[str, Any]] = None
    ):
        """
        Sends a message to a given Telegram chat with extended options.

        Args:
            chat_id: The ID of the target chat (e.g., a user ID, or @channelusername).
            text: The message text to send.
            message_thread_id: The ID of a topic/thread if sending to a group with topics.
            parse_mode: Message format, e.g., "MarkdownV2" or "HTML".
            disable_web_page_preview: Disables link previews in the message.
            disable_notification: Sends the message silently.
            protect_content: Protects the message from being forwarded or saved.
            reply_markup: A JSON-serialized object for an inline keyboard, custom reply keyboard, etc.
        """
        url = f"{self.base_url}/sendMessage"
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': disable_web_page_preview,
            'disable_notification': disable_notification,
            'protect_content': protect_content,
        }
        # Only include optional parameters if they have a value to keep the payload clean.
        if message_thread_id:
            params['message_thread_id'] = message_thread_id
        if reply_markup:
            params['reply_markup'] = reply_markup
        # Remove params with None value, as Telegram API expects them to be absent.
        params = {k: v for k, v in params.items() if v is not None}

        try:
            response = await self._client.post(url, json=params)
            response.raise_for_status()
            logger.info(f"Telegram message successfully sent to chat_id: {chat_id}.")
            return response.json()
        except httpx.HTTPStatusError as e:
            error_response = e.response.json()
            error_description = error_response.get('description', 'No description')
            logger.error(
                f"Telegram API Error: {e.response.status_code} - {error_description}. "
                f"Request to {e.request.url} failed."
            )
            # Handle rate-limiting specifically
            if e.response.status_code == 429:
                retry_after = error_response.get('parameters', {}).get('retry_after', 30)
                logger.warning(f"Flood control exceeded. Telegram suggests waiting {retry_after} seconds.")
                # For a real-world application, you might implement a wait-and-retry mechanism here.
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting the Telegram API: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending a Telegram message: {e}")

    async def close(self):
        """Gracefully closes the httpx client session."""
        await self._client.aclose()
        logger.info("TelegramHandler session closed.")

    async def __aenter__(self):
        """Enables usage of the class as an async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the client session on exiting the context manager."""
        await self.close()

