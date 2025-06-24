import asyncio
import logging
from trainer import train_model

logger = logging.getLogger(__name__)

async def training_loop():
    while True:
        logger.info("🔁 Starting scheduled model training (every 8 hours)...")
        try:
            train_model()
        except Exception as e:
            logger.error(f"❌ Failed during scheduled training: {e}", exc_info=True)
        await asyncio.sleep(8 * 60 * 60)  # 8 hours