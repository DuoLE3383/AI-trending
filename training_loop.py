# training_loop.py (Phiên bản đã sửa lỗi TypeError)
import asyncio
import logging
from trainer import train_model
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats

logger = logging.getLogger(__name__)

async def training_loop(notification_handler: NotificationHandler, symbols_count: int):
    """
    Vòng lặp chạy việc huấn luyện model định kỳ mỗi 8 giờ.
    SỬA LỖI: Hàm này giờ đây nhận 'symbols_count' để có thể gửi thông báo đầy đủ.
    """
    while True:
        try:
            logger.info("🔁 Starting scheduled model training cycle (every 8 hours)...")
            
            # Lấy thông tin thống kê để gửi kèm (tùy chọn)
            stats = get_performance_stats() 
            await notification_handler.send_training_and_summary_notification(stats)

            # Chạy training trong một thread riêng
            loop = asyncio.get_running_loop()
            logger.info("🚀 Offloading model training to a separate thread...")
            accuracy = await loop.run_in_executor(None, train_model)
            logger.info("✅ Training task finished.")

            # Gửi thông báo kết quả training
            # SỬA LỖI: Truyền cả accuracy và symbols_count vào
            await notification_handler.send_training_complete_notification(accuracy, symbols_count)

        except Exception as e:
            logger.error(f"❌ An error occurred in the training loop: {e}", exc_info=True)
            # Gửi thông báo lỗi nếu có thể
            await notification_handler.send_training_complete_notification(None, symbols_count)
        
        logger.info("Training cycle finished. Sleeping for 8 hours.")
        await asyncio.sleep(8 * 60 * 60) # 8 tiếng
