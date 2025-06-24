# report.py
import asyncio
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

load_dotenv()
import config

from updater import check_signal_outcomes
from result import get_win_loss_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def print_report(stats: dict):
    """Prints the performance report to the console."""
    print("\n\n--- STRATEGY PERFORMANCE REPORT ---")
    if 'error' in stats:
        print(f"Could not generate stats: {stats['error']}")
    elif stats.get('total_completed_trades', 0) == 0:
        print("No completed trades to analyze yet.")
    else:
        print(f"  Total Completed Trades: {stats.get('total_completed_trades', 'N/A')}")
        print(f"  Win Rate: {stats.get('win_rate', 'N/A')}")
        print(f"  Loss Rate: {stats.get('loss_rate', 'N/A')}")
        print(f"  Breakdown: {stats.get('breakdown', 'N/A')}")
    print("---------------------------------\n")

async def main():
    """Main function to generate and display the performance report."""
    logger.info("--- Starting Performance Report Generator ---")
    if not config.API_KEY or not config.API_SECRET:
        logger.error("Binance API Key/Secret not found. Please check your .env file or config.")
        return

    try:
        binance_client = Client(config.API_KEY, config.API_SECRET)
        binance_client.ping()
        logger.info("Successfully connected to Binance.")
    except BinanceAPIException as e:
        logger.error(f"Binance API error: {e}")
        return
    except Exception as e:
        logger.error(f"Failed to initialize Binance client: {e}")
        return

    logger.info("Step 1: Updating trade outcomes (TP/SL)...")
    await check_signal_outcomes(binance_client)
    logger.info("Step 1: Finished updating.")

    logger.info("Step 2: Calculating win/loss statistics...")
    stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
    print_report(stats)
    logger.info("--- Report generation complete. ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Report generation cancelled by user.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred: {e}", exc_info=True)
