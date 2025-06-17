import os
import logging
import pandas as pd
import asyncio # Import asyncio
import telegram
from telegram.request import HTTPXRequest
from typing import Optional

logger = logging.getLogger(__name__)

# Placeholder constants from the main script, used for checking if actual values are set
TELEGRAM_BOT_TOKEN_PLACEHOLDER = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
TELEGRAM_CHAT_ID_PLACEHOLDER = 'YOUR_TELEGRAM_CHAT_ID_PLACEHOLDER'

telegram_bot: Optional[telegram.Bot] = None

def _parse_custom_proxy_format(proxy_str: str, default_scheme: str = "http") -> str:
    """
    Parses "host:port:password" or "host:port:user:password" into a full URL.
    Returns the original string if it's already a full URL (contains "://")
    or if it doesn't match the custom formats.
    """
    if not proxy_str or "://" in proxy_str:
        return proxy_str # It's already a URL, empty, or None

    parts = proxy_str.split(':')
    num_parts = len(parts)

    if num_parts == 3: # Expected format: host:port:password
        host, port, password = parts[0], parts[1], parts[2]
        if port.isdigit() and host:
            logger.info(f"Interpreting custom proxy string '{proxy_str}' as {default_scheme} with password-only: {host}:{port}")
            return f"{default_scheme}://:{password}@{host}:{port}" # Empty username for password-only
    elif num_parts == 4: # Expected format: host:port:username:password
        host, port, username, password = parts[0], parts[1], parts[2], parts[3]
        if port.isdigit() and host and username: # Username should be present
            logger.info(f"Interpreting custom proxy string '{proxy_str}' as {default_scheme} with username/password: {host}:{port}")
            return f"{default_scheme}://{username}:{password}@{host}:{port}"
    
    logger.warning(
        f"Proxy string '{proxy_str}' is not a full URL and does not match expected custom formats "
        f"(host:port:password or host:port:username:password). Attempting to use as is."
    )
    return proxy_str # Fallback to original string if parsing fails

def _mask_url_credentials(url_str: str) -> str:
    """Masks credentials in a URL string for safe logging."""
    if url_str and "://" in url_str:
        try:
            scheme, rest_of_url = url_str.split("://", 1)
            if "@" in rest_of_url:
                credentials_part, host_part = rest_of_url.split("@", 1)
                if credentials_part: # Only mask if there was something before @
                    return f"{scheme}://[credentials masked]@{host_part}"
        except ValueError:
            logger.warning(f"Could not parse URL '{url_str}' for credential masking. Displaying as is or generic mask.")
            # Return a generic placeholder if parsing for masking fails, to avoid accidental credential exposure
            return f"{url_str.split('://')[0]}://[proxy_details_omitted_due_to_masking_error]"
    return url_str # Return original if no "://" or no "@" after "://", or if it's empty

async def init_telegram_bot(
    bot_token: str, 
    chat_id: str, 
    message_thread_id_for_startup: Optional[int], # Added message_thread_id specifically for startup
    proxy_url: Optional[str], 
    symbols_display: str, 
    timeframe_display: str, 
    loop_interval_display: str) -> bool:
    global telegram_bot

    if bot_token == TELEGRAM_BOT_TOKEN_PLACEHOLDER or \
       chat_id == TELEGRAM_CHAT_ID_PLACEHOLDER:
        logger.warning("Telegram Bot Token or Chat ID not configured. Notifications will not be sent.")
        return False

    try:
        logger.info("Initializing Telegram Bot...")
        request_instance = None
        processed_proxy_url_for_httpx = None

        if proxy_url and proxy_url.strip():
            # Step 1: Parse custom format or use as is (will return original if already a full URL)
            processed_proxy_url_for_httpx = _parse_custom_proxy_format(proxy_url.strip())

            # Step 2: Mask the (potentially transformed) URL for logging
            display_url_for_log = _mask_url_credentials(processed_proxy_url_for_httpx)
            logger.info(f"Using proxy for Telegram: {display_url_for_log}")
            
            request_instance = HTTPXRequest(proxy=processed_proxy_url_for_httpx)

        telegram_bot = telegram.Bot(token=bot_token, request=request_instance)
        bot_info = await telegram_bot.get_me() # Await the asynchronous method
        logger.info(f"✅ Successfully initialized Telegram Bot: {bot_info.username}")
        
        timestamp_str = pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S %Z')
        startup_message = (
            f"*📈 Trend Analysis Bot Started*\n\n"
            f"📊 *Monitoring:* #{symbols_display} 🎯Most #Binance Pair List\n"
            f"⚙️ *Settings:* Timeframe=`{timeframe_display}`\n"
            f"🕒 *Time:* `{timestamp_str}`\n\n"
            f"🔔 This will be updated 10 minutes later with the latest analysis results.🚨🚨"

        )
        # Send startup message to the main chat/group
        await send_telegram_notification(
            chat_id, startup_message, message_thread_id=None, suppress_print=True
        )
        # If a topic ID was provided for startup, also send to the topic
        if message_thread_id_for_startup is not None:
             await asyncio.sleep(0.5) # Add a small delay
             await send_telegram_notification(chat_id, startup_message, message_thread_id=message_thread_id_for_startup, suppress_print=True)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Telegram Bot: {e}")
        if "socks" in str(e).lower() and "httpx" in str(e).lower():
             logger.info("💡 If using a SOCKS proxy, ensure you have installed the SOCKS extra: python3 -m pip install \"httpx[socks]\"")
        telegram_bot = None
        return False

async def send_telegram_notification(
    chat_id: str,
    message_text: str,
    message_thread_id: Optional[int] = None, # Added message_thread_id with a default
    suppress_print: bool = False
) -> None:
    if not telegram_bot:
        if not suppress_print:
            logger.warning("Telegram bot not initialized. Cannot send notification.")
        return
    if chat_id == TELEGRAM_CHAT_ID_PLACEHOLDER: # Double check
        if not suppress_print:
            logger.warning("Telegram Chat ID is a placeholder. Cannot send notification.")
        return

    try:
        await telegram_bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode=telegram.constants.ParseMode.MARKDOWN,
            message_thread_id=message_thread_id # Pass it to the API call
        )
        if not suppress_print:
            logger.info(f"✅ Telegram notification sent to {chat_id}.")
    except telegram.error.BadRequest as e:
        logger.error(f"Failed to send Telegram notification (BadRequest): {e}. Check message formatting or chat ID.")
        logger.debug(f"Message content for failed Telegram notification: {message_text}")
    except telegram.error.TelegramError as e: # Catch more specific Telegram errors
        logger.error(f"Failed to send Telegram notification (TelegramError): {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram notification: {e}")