# report.py - Standalone Performance Reporting Script
import asyncio
import logging
import sys
import os

# --- IMPORTANT: Setup path to load modules from the root ---
# This allows the script to be run directly and still find the 'src' package
# It finds the root directory (AI-trending) and adds it to the path.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Now we can do standard imports
from dotenv import load_dotenv
from binance import AsyncClient

# --- Load environment variables BEFORE importing config ---
load_dotenv()

from src import config # Now this works because the root is in the path
from src.updater import check_signal_outcomes
from src.result import get_win_loss_stats

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def generate_report():
    """
    Main function to connect to Binance, update trade outcomes, 
    and generate a performance report.
    """
    logger.info("--- 📊 Starting Performance Report Generator ---")
    client = None

    try:
        if not config.API_KEY or not config.API_SECRET:
            logger.error("❌ Binance API Key/Secret not found in .env file. Please check your .env file.")
            return

        # Use AsyncClient for consistency with the main bot
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        logger.info("✅ Connected to Binance.")

        logger.info("Step 1: Updating trade outcomes (TP/SL) from live data...")
        await check_signal_outcomes(client)
        logger.info("Step 1: Finished updating outcomes.")

        logger.info("Step 2: Calculating win/loss statistics from the database...")
        # Use a synchronous function wrapper for DB access if needed, or ensure get_win_loss_stats is sync
        stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
        
        # --- Print the report to the console ---
        print("\n\n" + "="*40)
        print("--- 📈 STRATEGY PERFORMANCE REPORT 📈 ---")
        print("="*40)

        if 'error' in stats:
            print(f"❌ Could not generate stats: {stats['error']}")
        elif stats['total_completed_trades'] == 0:
            print("📊 No completed trades to analyze yet.")
        else:
            print(f"  Total Completed Trades: {stats['total_completed_trades']}")
            print(f"  Wins: {stats['breakdown'].get('WIN', 0)}")
            print(f"  Losses: {stats['breakdown'].get('LOSS', 0)}")
            print(f"  Win Rate: {stats['win_rate']:.2f}%") # Format to 2 decimal places
            print(f"  Loss Rate: {stats['loss_rate']:.2f}%")
        
        print("="*40 + "\n")
        logger.info("--- ✅ Report generation complete. ---")

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if client:
            await client.close_connection()
            logger.info("🔌 Disconnected from Binance.")


if __name__ == "__main__":
    # This allows the script to be run directly
    asyncio.run(generate_report())
