# training_loop.py (Phiên bản đã sửa lỗi gọi hàm)
import asyncio
import logging
from trainer import train_model
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats

logger = logging.getLogger(__name__)

async def training_loop(notification_handler: NotificationHandler, symbols_count: int):
    """
    Vòng lặp chạy việc huấn luyện model định kỳ và gửi thông báo.
    """
    while True:
        try:
            logger.info("🔁 Starting scheduled model training cycle (every 8 hours)...")
            
            # 1. Huấn luyện model
            loop = asyncio.get_running_loop()
            logger.info("🚀 Offloading model training to a separate thread...")
            accuracy = await loop.run_in_executor(None, train_model)
            logger.info("✅ Training task finished.")

            # 2. Gửi thông báo kết quả training, truyền cả accuracy và symbols_count
            await notification_handler.send_training_complete_notification(accuracy, symbols_count)

        except Exception as e:
            logger.error(f"❌ An error occurred in the training loop: {e}", exc_info=True)
            # Nếu có lỗi, vẫn cố gắng gửi thông báo lỗi
            try:
                await notification_handler.send_training_complete_notification(None, symbols_count)
            except Exception as notify_err:
                logger.error(f"❌ Also failed to send error notification: {notify_err}")
        
        logger.info("Training cycle finished. Sleeping for 8 hours.")
        await asyncio.sleep(8 * 60 * 60) # 8 tiếng
