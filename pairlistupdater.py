# Save this file as pairlist_updater.py
import json
import requests
import time
import logging
import asyncio
from typing import List, Set, Optional

# --- Configuration ---
# The path to your main configuration file.
CONFIG_FILE_PATH = 'config.json'

# How often to check for updates, in seconds. (3600 = 1 hour, 21600 = 6 hours)
CHECK_INTERVAL_SECONDS = 3600

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# --- Core Functions ---

def get_local_symbols(filepath: str) -> Optional[Set[str]]:
    """Reads the current list of symbols from the local config.json file."""
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        return set(config['trading']['symbols'])
    except FileNotFoundError:
        logger.error(f"Config file not found at: {filepath}")
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Error reading or parsing config file: {e}")
    return None


def get_latest_binance_symbols() -> Optional[Set[str]]:
    """Fetches the latest list of tradable perpetual futures from Binance."""
    api_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    logger.info("Fetching latest symbols from Binance API...")
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        symbols = {
            item['symbol'] for item in data['symbols']
            if item.get('contractType') == 'PERPETUAL' and item.get('status') == 'TRADING'
        }
        logger.info(f"Successfully fetched {len(symbols)} tradable symbols from Binance.")
        return symbols
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data from Binance API: {e}")
    return None


def update_config_file(filepath: str, new_symbol_list: List[str]):
    """Overwrites the symbols list in the config file, preserving other settings."""
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        
        # Update only the symbols list
        config['trading']['symbols'] = sorted(new_symbol_list)
        
        # Write the entire config back with nice formatting
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=4)
            
        logger.info(f"Successfully updated config file '{filepath}' with {len(new_symbol_list)} symbols.")
    except Exception as e:
        logger.error(f"FATAL: Failed to write update to config file: {e}")


async def notify_of_changes(added: Set[str], removed: Set[str]):
    """Formats and sends a Telegram notification about the updates."""
    message_parts = ["*📈 Binance Futures Pairlist Updated*"]
    
    if added:
        message_parts.append("\n*✅ Added:*")
        message_parts.extend([f"`{s}`" for s in sorted(list(added))])
    
    if removed:
        message_parts.append("\n*❌ Removed (Delisted):*")
        message_parts.extend([f"`{s}`" for s in sorted(list(removed))])

    final_message = "\n".join(message_parts)

    # --- Integration Point for Your Telegram Handler ---
    # This part requires your existing telegram_handler logic.
    # For this script to send notifications, you would need to initialize
    # your bot and call your send function here.
    try:
        # Example:
        # from telegram_handler import telegram_bot, send_telegram_notification, TELEGRAM_CHAT_ID_PLACEHOLDER
        # if telegram_bot and TELEGRAM_CHAT_ID_PLACEHOLDER != "YOUR_...":
        #    await send_telegram_notification(chat_id, final_message)
        # else:
        #    logger.warning("Telegram not configured. Cannot send update notification.")
        logger.info("--- TELEGRAM NOTIFICATION PREVIEW ---")
        logger.info(final_message)
        logger.info("-------------------------------------")

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


# --- Main Application Loop ---

async def main_loop():
    logger.info("Starting real-time pairlist updater script.")
    while True:
        logger.info("--- Running periodic check ---")
        
        local_symbols = get_local_symbols(CONFIG_FILE_PATH)
        latest_symbols = get_latest_binance_symbols()

        # Gracefully handle potential errors
        if local_symbols is None or latest_symbols is None:
            logger.warning("Skipping this cycle due to an error reading local file or fetching from API.")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            continue

        if local_symbols == latest_symbols:
            logger.info("No changes detected. Pairlist is up-to-date.")
        else:
            logger.warning("Change detected! Updating local pairlist.")
            added = latest_symbols - local_symbols
            removed = local_symbols - latest_symbols
            
            # Update the config.json file
            update_config_file(CONFIG_FILE_PATH, list(latest_symbols))
            
            # Send a notification about the update
            if added or removed:
                await notify_of_changes(added, removed)
            
        logger.info(f"Next check in {CHECK_INTERVAL_SECONDS / 3600:.1f} hour(s).")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Updater script stopped by user.")

