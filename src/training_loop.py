# training_loop.py (Phiên bản đã sửa lỗi gọi hàm)
import asyncio
import logging
from .ml.trainer import train_model
from .notifications import NotificationHandler
from .performance_analyzer import get_performance_stats
from . import config as config
logger = logging.getLogger(__name__)

async def training_loop(notifier, total_symbols):
    logger.info("✅ Periodic AI Model Training Loop starting...")
    while True:
        await asyncio.sleep(config.TRAINING_INTERVAL_SECONDS)
        logger.info("🤖 Starting periodic model training...")
        try:
            # Chạy hàm huấn luyện đồng bộ trong một executor riêng
            loop = asyncio.get_running_loop()
            new_accuracy = await loop.run_in_executor(None, train_model)
            
            if new_accuracy is not None:
                logger.info(f"✅ Periodic training complete. New accuracy: {new_accuracy:.2f}%")
                await notifier.send_training_success_notification(new_accuracy, total_symbols)
            else:
                # Trường hợp train_model trả về None (ví dụ: không đủ dữ liệu)
                logger.warning("Periodic training did not produce a new model (e.g., insufficient data).")
                await notifier.send_training_failed_notification(error="Insufficient data for training.")

        except Exception as e:
            # === ĐÂY LÀ THAY ĐỔI QUAN TRỌNG NHẤT ===
            # Thêm exc_info=True để in ra toàn bộ lỗi chi tiết vào console.
            logger.error(f"❌ An exception occurred during periodic training: {e}", exc_info=True)
            # Gửi thông báo lỗi tới Telegram
            await notifier.send_training_failed_notification(error=str(e))