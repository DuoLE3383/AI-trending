import os
import logging
import pandas as pd
import telegram
from telegram.request import HTTPXRequest
from typing import Optional

logger = logging.getLogger(__name__)

# Placeholder constants from the main script, used for checking if actual values are set
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'

telegram_bot: Optional[telegram.Bot] = None

def init_telegram_bot(bot_token: str, chat_id: str, proxy_url: Optional[str], symbol_for_startup: str) -> bool:
    global telegram_bot
    if bot_token == TELEGRAM_BOT_TOKEN_PLACEHOLDER or \
       chat_id == TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.warning("Telegram Bot Token or Chat ID not configured. Notifications will not be sent.")
        return False

    try:
        logger.info("Initializing Telegram Bot...")
        request_instance = None
        if proxy_url and proxy_url.strip(): # Ensure proxy_url is not None or empty
            logger.info(f"Using proxy for Telegram: {proxy_url}")
            # For python-telegram-bot v20+ with httpx, proxy is a dict
            proxies = {
                "all://": proxy_url # Applies to http, https, socks5 etc.
            }
            request_instance = HTTPXRequest(proxy=proxies) # This is the standard httpx way
        
        telegram_bot = telegram.Bot(token=bot_token, request=request_instance)
        bot_info = telegram_bot.get_me()
        logger.info(f"✅ Successfully initialized Telegram Bot: {bot_info.username}")
        startup_message = f"📈 Trend Analysis Bot for {symbol_for_startup} started successfully at {pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')}."
        send_telegram_notification(chat_id, startup_message, suppress_print=True) # Pass chat_id here
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Telegram Bot: {e}")
        if "socks" in str(e).lower() and "httpx" in str(e).lower():
             logger.info("💡 If using a SOCKS proxy, ensure you have installed the SOCKS extra: python3 -m pip install \"httpx[socks]\"")
        telegram_bot = None
        return False

def send_telegram_notification(chat_id: str, message_text: str, suppress_print: bool = False) -> None:
    if not telegram_bot:
        if not suppress_print:
            logger.warning("Telegram bot not initialized. Cannot send notification.")
        return
    if chat_id == TELEGRAM_CHAT_ID_PLACEHOLDER: # Double check
        if not suppress_print:
            logger.warning("Telegram Chat ID is a placeholder. Cannot send notification.")
        return

    try:
        telegram_bot.send_message(chat_id=chat_id, text=message_text, parse_mode=telegram.constants.ParseMode.MARKDOWN)
        if not suppress_print:
            logger.info(f"✅ Telegram notification sent to {chat_id}.")
    except telegram.error.BadRequest as e:
        logger.error(f"Failed to send Telegram notification (BadRequest): {e}. Check message formatting or chat ID.")
        logger.debug(f"Message content for failed Telegram notification: {message_text}")
    except telegram.error.TelegramError as e: # Catch more specific Telegram errors
        logger.error(f"Failed to send Telegram notification (TelegramError): {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram notification: {e}")