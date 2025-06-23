# report.py
import asyncio
import logging
from binance.client import Client
from dotenv import load_dotenv

# Tải các biến môi trường và config
load_dotenv()
import config

# Import các hàm cần thiết
from updater import check_signal_outcomes
from results import get_win_loss_stats

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

async def main():
    """
    Script này sẽ:
    1. Cập nhật trạng thái của các trade cũ (TP/SL).
    2. In ra báo cáo thống kê hiệu suất.
    """
    logger.info("--- Starting Performance Report Generator ---")

    # Khởi tạo Binance Client
    if config.API_KEY and config.API_SECRET:
        binance_client = Client(config.API_KEY, config.API_SECRET)
        logger.info("Binance client initialized.")
    else:
        logger.error("Binance API Key/Secret not found. Cannot update outcomes.")
        return

    # 1. Chạy updater để kiểm tra và cập nhật kết quả TP/SL
    logger.info("Step 1: Checking for trade outcomes (TP/SL)...")
    await check_signal_outcomes(binance_client)
    logger.info("Step 1: Finished updating trade outcomes.")

    # 2. Chạy hàm thống kê để lấy kết quả
    logger.info("Step 2: Calculating win/loss statistics...")
    stats = get_win_loss_stats(db_path=config.SQLITE_DB_PATH)
    
    # 3. In kết quả ra màn hình
    logger.info("--- PERFORMANCE REPORT ---")
    if 'error' in stats:
        logger.error(f"Could not generate stats: {stats['error']}")
    elif stats.get('total_completed_trades', 0) == 0:
        logger.info("No completed trades to analyze yet.")
    else:
        print(f"\n--- Strategy Performance ---")
        print(f"  Total Completed Trades: {stats['total_completed_trades']}")
        print(f"  Win Rate: {stats['win_rate']}")
        print(f"  Loss Rate: {stats['loss_rate']}")
        print(f"  Breakdown: {stats['breakdown']}")
        print(f"--------------------------\n")

    logger.info("--- Report generation complete. ---")


if __name__ == "__main__":
    asyncio.run(main())
