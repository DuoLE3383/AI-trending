# training_loop.py
import asyncio
import logging
from .trainer import train_model
from . import config

logger = logging.getLogger(__name__)

async def training_loop(notifier, total_symbols):
    """Periodically retrains the AI model and sends a notification with the result."""
    logger.info("✅ Periodic AI Model Training Loop starting...")
    while True:
        # Wait for the configured interval before starting the next training cycle.
        await asyncio.sleep(config.TRAINING_INTERVAL_SECONDS)
        logger.info("🤖 Starting periodic model training cycle...")
        new_accuracy = None # Initialize accuracy to None
        try:
            # Run the synchronous training function in a separate thread to avoid blocking the event loop.
            loop = asyncio.get_running_loop()
            new_accuracy = await loop.run_in_executor(None, train_model)
            
            if new_accuracy is not None:
                logger.info(f"✅ Periodic training complete. New accuracy: {new_accuracy:.2%}")
            else:
                # This case handles when train_model returns None (e.g., not enough data).
                logger.warning("Periodic training did not produce a new model (insufficient data).")

        except Exception as e:
            # Log the full exception traceback for debugging.
            logger.error(f"❌ An exception occurred during periodic training: {e}", exc_info=True)
            # new_accuracy remains None, which will signal a failure in the notification.
        
        finally:
            # Always send a notification, whether training succeeded, was skipped, or failed.
            # The notification function is designed to handle `new_accuracy` being a float or None.
            logger.info("Sending training result notification...")
            await notifier.send_training_complete_notification(new_accuracy, total_symbols)