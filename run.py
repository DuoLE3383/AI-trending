# run.py (Phiên bản đã tái cấu trúc)
import sys
import logging
import asyncio
import joblib
import json
from dotenv import load_dotenv

# Tải các biến môi trường từ tệp .env
load_dotenv()

# --- Imports từ các module của dự án ---
from binance import AsyncClient
from src import config
from src.database_handler import init_sqlite_db
from src.telegram_handler import TelegramHandler
from src.notifications import NotificationHandler
from src.performance_analyzer import get_performance_stats
from src.updater import get_usdt_futures_symbols
from src.trainer import train_model
from src.training_loop import training_loop
from src.data_simulator import simulate_trade_data
from src.pairlist_updater import perform_single_pairlist_update, CONFIG_FILE_PATH as PAIRLIST_CONFIG_PATH

# CẢI TIẾN: Nhập tất cả các vòng lặp từ tệp src/run_loops.py
from src.run_loops import (
    analysis_loop,
    signal_check_loop,
    updater_loop,
    outcome_check_loop,
    notification_flush_loop,
    summary_loop,
    update_loop,
    run_api_server
)

# --- Cấu hình Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- HÀM MAIN CHÍNH ---
async def main():
    logger.info("--- 🚀 Khởi tạo Bot ---")
    client = None
    running_tasks = []
    initial_accuracy = None

    try:
        # --- BƯỚC 1: Kết nối và khởi tạo ---
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        init_sqlite_db(config.SQLITE_DB_PATH)

        # --- BƯỚC 2: Cập nhật pairlist, mô phỏng và huấn luyện ---
        logger.info("📊 Cập nhật pairlist trước khi mô phỏng...")
        await perform_single_pairlist_update()
        try:
            with open(PAIRLIST_CONFIG_PATH, 'r') as f:
                symbols_for_simulation = json.load(f).get('trading', {}).get('symbols', [])
        except Exception as e:
            logger.error(f"Không thể tải symbols từ {PAIRLIST_CONFIG_PATH}: {e}. Dùng fallback.")
            symbols_for_simulation = getattr(config.trading, 'symbols', [])
        
        logger.info("📊 Bắt đầu mô phỏng dữ liệu giao dịch...")
        await simulate_trade_data(client, config.SQLITE_DB_PATH, symbols_for_simulation)
        
        logger.info("🧠 Bắt đầu huấn luyện mô hình AI...")
        loop = asyncio.get_running_loop()
        initial_accuracy = await loop.run_in_executor(None, train_model)
        if initial_accuracy:
            logger.info(f"✅ Huấn luyện hoàn tất. Độ chính xác ban đầu: {initial_accuracy:.2%}")

        # --- BƯỚC 3: Tải model và khởi tạo thông báo ---
        model = joblib.load("model_trend.pkl")
        label_encoder = joblib.load("trend_label_encoder.pkl")
        model_features = joblib.load("model_features.pkl")

        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN, proxy_url=getattr(config, 'TELEGRAM_PROXY_URL', None))
        notifier = NotificationHandler(telegram_handler=tg_handler)

        # Gửi báo cáo kết quả mô phỏng và thông báo khởi động
        simulation_stats = await loop.run_in_executor(None, lambda: get_performance_stats(by_symbol=True))
        await notifier.send_simulation_summary_notification(simulation_stats)
        
        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("❌ Không lấy được danh sách symbol từ Binance. Bot sẽ thoát.")
            return
        await notifier.send_startup_notification(len(all_symbols), initial_accuracy)

        # --- BƯỚC 4: Khởi chạy tất cả các vòng lặp ---
        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        
        running_tasks = [
            asyncio.create_task(analysis_loop(client, model, label_encoder, model_features)),
            asyncio.create_task(signal_check_loop(notifier)),
            asyncio.create_task(updater_loop(client)),
            asyncio.create_task(outcome_check_loop(notifier)),
            asyncio.create_task(training_loop(notifier, len(all_symbols))), # Vòng lặp huấn luyện lại định kỳ
            asyncio.create_task(notification_flush_loop(notifier)),
            asyncio.create_task(summary_loop(notifier)),
            asyncio.create_task(update_loop(notifier)),
            loop.run_in_executor(None, run_api_server),
        ]

        await asyncio.gather(*running_tasks)

    except (Exception, KeyboardInterrupt) as main_exc:
        if isinstance(main_exc, KeyboardInterrupt):
            logger.info("🛑 Bot đã dừng bởi người dùng (Ctrl+C).")
        else:
            logger.critical(f"🔥 Lỗi nghiêm trọng trong hàm main(): {main_exc}", exc_info=True)
            if 'notifier' in locals() and notifier:
                await notifier.send_message_to_all(f"🔥 BOT GẶP LỖI NGHIÊM TRỌNG VÀ ĐÃ DỪNG LẠI!\n\nLỗi: `{main_exc}`")

    finally:
        logger.info("🔻 Bắt đầu quy trình tắt bot.")
        for task in running_tasks:
            task.cancel()
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
        if client:
            await client.close_connection()
        logger.info("--- ✅ Tắt bot hoàn tất. ---")


if __name__ == "__main__":
    asyncio.run(main())