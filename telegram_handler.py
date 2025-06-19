import logging
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# --- Global session for connection pooling ---
_session: Optional[aiohttp.ClientSession] = None

async def _get_session() -> aiohttp.ClientSession:
    """Initializes and returns a single aiohttp session."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def send_telegram_message(
    chat_id: str,
    message: str,
    message_thread_id: Optional[int] = None,
    bot_token: Optional[str] = None
) -> bool:
    """
    Sends a message to a specified Telegram chat using a bot token.
    This function is now self-contained and gets the token from the main script.
    """
    if not bot_token or bot_token == 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER':
        logger.error("Telegram bot token is not configured. Cannot send message.")
        return False
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML', # Use HTML for rich formatting like <b>, <i>, <code>
        'disable_web_page_preview': True
    }
    
    if message_thread_id is not None:
        payload['message_thread_id'] = message_thread_id

    try:
        session = await _get_session()
        async with session.post(api_url, json=payload) as response:
            if response.status == 200:
                logger.info(f"Successfully sent message to chat_id: {chat_id}")
                return True
            else:
                error_text = await response.text()
                logger.error(
                    f"Failed to send Telegram message. Status: {response.status}, "
                    f"Response: {error_text}"
                )
                return False
    except aiohttp.ClientError as e:
        logger.error(f"An aiohttp client error occurred while sending Telegram message: {e}")
        return False
    except Exception as e:
        logger.exception("An unexpected error occurred in send_telegram_message:")
        return False

async def init_telegram_bot(
    bot_token: str,
    chat_id: str,
    message_thread_id_for_startup: Optional[int],
    symbols_display: str,
    timeframe_display: str,
    loop_interval_display: str
) -> bool:
    """Initializes the bot and sends a startup message."""
    startup_message = (
        f"✅ *Bot Started*\n\n"
        f"Monitoring `{len(symbols_display.split(','))}` symbols on `{timeframe_display}` timeframe.\n"
        f"*Symbols:* {symbols_display}\n"
        f"*Intervals:* {loop_interval_display}\n\n"
        f"The bot is now active."
    )
    logger.info("Sending bot startup notification...")
    return await send_telegram_message(
        chat_id=chat_id,
        message=startup_message,
        message_thread_id=message_thread_id_for_startup,
        bot_token=bot_token
    )

async def close_session():
    """Closes the aiohttp session during shutdown."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        logger.info("Aiohttp session closed.")
