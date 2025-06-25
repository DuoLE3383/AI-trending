# training_loop.py

import asyncio
import logging
from trainer import train_model
from notifications import NotificationHandler

logger = logging.getLogger(__name__)

async def training_loop(notification_handler: NotificationHandler):
    """
    Vòng lặp chạy việc huấn luyện model định kỳ, sau đó gửi thông báo kết quả.
    """
    while True:
        try:
            logger.info("🔁 Starting scheduled model training cycle (every 8 hours)...")
            
            loop = asyncio.get_running_loop()

            # Bước 1: Huấn luyện model và nhận về accuracy
            logger.info("🚀 Offloading model training to a separate thread...")
            accuracy = await loop.run_in_executor(None, train_model)
            logger.info("✅ Training task finished.")

            # Bước 2: Gửi thông báo kết quả huấn luyện
            if notification_handler:
                await notification_handler.send_training_complete_notification(accuracy)
            else:
                logger.warning("Notification handler not provided, skipping result notification.")

        except Exception as e:
            logger.error(f"❌ An error occurred in the training loop: {e}", exc_info=True)
            # Gửi thông báo lỗi nếu có thể
            if notification_handler:
                await notification_handler.send_training_complete_notification(None)
        
        logger.info("Training cycle finished. Sleeping for 8 hours.")
        await asyncio.sleep(8 * 60 * 60) # 8 tiếng