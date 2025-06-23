# report.py
import asyncio
import logging
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
import config

from updater import check_signal_outcomes
from results import get_win_loss_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

async def main():
    logger.info("--- Starting Performance Report Generator ---")
    if not config.API_KEY or not config.API_SECRET:
        logger.error("Binance API Key/Secret not found in .env file.")
        return

    binance_client = Client(config.API_KEY, config.API_SECRET)

    logger.info("Step 1: Updating trade outcomes (TP/SL)...")
    await check_signal_outcomes(binance_client)
    logger.info("Step 1: Finished updating.")

    logger.info("Step 2: Calculating win/loss statistics...")
    stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
    
    print("\n\n--- STRATEGY PERFORMANCE REPORT ---")
    if 'error' in stats:
        print(f"Could not generate stats: {stats['error']}")
    elif stats['total_completed_trades'] == 0:
        print("No completed trades to analyze yet.")
    else:
        print(f"  Total Completed Trades: {stats['total_completed_trades']}")
        print(f"  Win Rate: {stats['win_rate']}")
        print(f"  Loss Rate: {stats['loss_rate']}")
        print(f"  Breakdown: {stats['breakdown']}")
    print("---------------------------------\n")
    logger.info("--- Report generation complete. ---")

if __name__ == "__main__":
    asyncio.run(main())
