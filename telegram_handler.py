import logging
from telegram import Bot
from telegram.ext import Updater
from telegram.error import TelegramError
from typing import Optional

# --- Initialize Logger ---
logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self, api_token: str):
        self.bot: Optional[Bot] = None
        if api_token and api_token != 'YOUR_TELEGRAM_API_TOKEN':
            try:
                self.bot = Bot(token=api_token)
                logger.info("Telegram Bot initialized successfully.")
            except Exception as e:
                logger.critical(f"Failed to initialize Telegram Bot: {e}")
        else:
            logger.warning("Telegram API token is not configured. Notifications will be disabled.")

    def is_configured(self) -> bool:
        """Check if the bot was initialized successfully."""
        return self.bot is not None

    async def send_telegram_notification(
        self,
        chat_id: str,
        message: str,
        message_thread_id: Optional[int] = None,
        reply_markup: Optional[object] = None,
        suppress_print: bool = False
    ):
        """Sends a message to a specified Telegram chat."""
        if not self.is_configured():
            if not suppress_print:
                print("--- TELEGRAM (Not Sent) ---\n"
                      f"Chat ID: {chat_id}\n"
                      f"Message: {message}\n"
                      "-----------------------------")
            return

        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                message_thread_id=message_thread_id
            )
        except TelegramError as e:
            logger.error(f"Telegram Error: {e.message}")
        except Exception as e:
            logger.error(f"An unexpected error occurred when sending Telegram message: {e}")

# You would then create an instance of this handler in your main script
# config = configparser.ConfigParser()
# config.read('config.ini')
# telegram_api_token = config.get('telegram', 'api_token')
# telegram_handler_instance = TelegramHandler(telegram_api_token)
