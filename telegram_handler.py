# In your telegram_handler.py file
from typing import Optional

import logging
from telegram import Bot, InlineKeyboardMarkup # <-- Import InlineKeyboardMarkup
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Assume telegram_bot = Bot(token="YOUR_TOKEN") is initialized elsewhere

async def send_telegram_notification(
    chat_id: str,
    message: str,
    message_thread_id: Optional[int] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None, # <-- ADD THIS ARGUMENT
    suppress_print: bool = False
):
    """
    Sends a message to a specified Telegram chat, now with button support.
    """
    if not suppress_print:
        logger.info(f"Sending Telegram notification to chat_id: {chat_id} (Topic: {message_thread_id})")

    try:
        await telegram_bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            message_thread_id=message_thread_id,
            reply_markup=reply_markup  # <-- PASS IT HERE
        )
    except TelegramError as e:
        logger.error(f"Failed to send Telegram message: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in send_telegram_notification: {e}")

