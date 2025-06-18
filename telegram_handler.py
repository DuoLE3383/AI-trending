import os
import logging
import pandas as pd
import asyncio
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
from typing import Optional

# --- Basic Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- <<<<< IMPORTANT: FILL IN YOUR DETAILS HERE >>>>> ---
# Replace these with your actual token, or load from environment variables
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER'
PROXY_URL = None # Optional: e.g., 'http://user:pass@host:port'


# --- Application State (This is what your commands will control) ---
monitoring_status = {
    "is_active": True,
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "timeframe": "1h"
}

# --- Helper functions (no changes needed here) ---
def _parse_custom_proxy_format(proxy_str: str, default_scheme: str = "http") -> str:
    if not proxy_str or "://" in proxy_str:
        return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 3:
        host, port, password = parts
        return f"{default_scheme}://:{password}@{host}:{port}"
    elif len(parts) == 4:
        host, port, username, password = parts
        return f"{default_scheme}://{username}:{password}@{host}:{port}"
    logger.warning(f"Proxy string '{proxy_str}' format not recognized. Using as is.")
    return proxy_str

def _mask_url_credentials(url_str: str) -> str:
    if url_str and "://" in url_str and "@" in url_str:
        scheme, rest = url_str.split("://", 1)
        creds, host = rest.split("@", 1)
        return f"{scheme}://[credentials_masked]@{host}"
    return url_str

# --- Command Handler Functions ---
# These functions define what happens when a user sends a command.

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message for the /start command."""
    user_name = update.effective_user.first_name
    welcome_message = (
        f"👋 Hello, {user_name}!\n\n"
        "I am the Trend Analysis Bot. I am now interactive!\n\n"
        "*/start* - Show this welcome message\n"
        "*/status* - Get the current monitoring status\n"
        "*/stop* - Pause the monitoring process\n"
        "*/resume* - Resume the monitoring process\n"
        "*/set_timeframe <tf>* - Change analysis timeframe (e.g., /set_timeframe 4h)"
    )
    await update.message.reply_text(welcome_message, parse_mode=telegram.constants.ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the current status of the bot."""
    status_text = (
        f"📊 *Current Status*\n\n"
        f"Monitoring Active: *{'✅ Active' if monitoring_status['is_active'] else '❌ Paused'}*\n"
        f"Symbols: `{'`, `'.join(monitoring_status['symbols'])}`\n"
        f"Timeframe: `{monitoring_status['timeframe']}`"
    )
    await update.message.reply_text(status_text, parse_mode=telegram.constants.ParseMode.MARKDOWN)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stops the monitoring process."""
    monitoring_status['is_active'] = False
    logger.info(f"Monitoring stopped by user {update.effective_user.name}.")
    await update.message.reply_text("🔴 Monitoring has been paused.")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumes the monitoring process."""
    monitoring_status['is_active'] = True
    logger.info(f"Monitoring resumed by user {update.effective_user.name}.")
    await update.message.reply_text("🟢 Monitoring has been resumed.")

async def set_timeframe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets a new timeframe from user input."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a timeframe. Usage: `/set_timeframe 1h`")
        return

    new_timeframe = context.args[0]
    monitoring_status['timeframe'] = new_timeframe
    logger.info(f"Timeframe changed to {new_timeframe} by user {update.effective_user.name}.")
    await update.message.reply_text(f"✅ Timeframe has been updated to `{new_timeframe}`.")


# --- Main Application Logic ---
# This is the new entry point for your script. Run this file directly.
def main() -> None:
    """Builds the application, registers handlers, and starts the bot."""
    if TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_PLACEHOLDER':
        logger.error("FATAL: Telegram Bot Token not configured. Please edit the script and add your token.")
        return

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)

    if PROXY_URL:
        processed_proxy_url = _parse_custom_proxy_format(PROXY_URL)
        logger.info(f"Using proxy: {_mask_url_credentials(processed_proxy_url)}")
        request = HTTPXRequest(proxy=processed_proxy_url)
        builder.request(request)

    application = builder.build()

    # Register all the command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("resume", resume_command))
    application.add_handler(CommandHandler("set_timeframe", set_timeframe_command))

    logger.info("Bot is starting... Press Ctrl-C to stop.")

    # Start the Bot's polling loop
    application.run_polling()


if __name__ == '__main__':
    # This ensures that the main() function is called when you run the script
    main()
