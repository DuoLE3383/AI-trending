# training_loop.py (Phiên bản Hoàn thiện)
import asyncio
import logging
from trainer import train_model
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats

logger = logging.getLogger(__name__)

async def training_loop(notification_handler: NotificationHandler):
    """
    Vòng lặp chạy việc huấn luyện model định kỳ và gửi một thông báo kết hợp duy nhất.
    """
    while True:
        try:
            logger.info("🔁 Starting scheduled model training cycle (every 8 hours)...")
            
            # Bước 1: Lấy dữ liệu thống kê hiệu suất
            stats = get_performance_stats()
            
            # Bước 2: Huấn luyện model (tác vụ nặng, chạy trên thread riêng)
            loop = asyncio.get_running_loop()
            logger.info("🚀 Offloading model training to a separate thread...")
            accuracy = await loop.run_in_executor(None, train_model)
            logger.info("✅ Training task finished.")

            # Bước 3: Gọi MỘT hàm thông báo duy nhất, truyền cả stats và accuracy
            await notification_handler.send_training_and_summary_notification(stats, accuracy)

        except Exception as e:
            logger.error(f"❌ An error occurred in the training loop: {e}", exc_info=True)
            # Nếu có lỗi, vẫn cố gắng gửi thông báo lỗi
            try:
                stats = get_performance_stats()
                await notification_handler.send_training_and_summary_notification(stats, None) # Gửi accuracy là None
            except Exception as notify_err:
                logger.error(f"❌ Also failed to send error notification: {notify_err}")
        
        logger.info("Training cycle finished. Sleeping for 8 hours.")
        await asyncio.sleep(8 * 60 * 60) # 8 tiếng