# run.py (Phiên bản đã sửa lỗi ImportError)
import sys
import logging
import asyncio
import sqlite3
import joblib
from dotenv import load_dotenv

load_dotenv()

# --- Project Module Imports ---
from binance import AsyncClient
import config
from database_handler import init_sqlite_db
# SỬA LỖI: Import đúng các hàm chiến lược từ analysis_engine
from analysis_engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
from telegram_handler import TelegramHandler
from notifications import NotificationHandler
from performance_analyzer import get_performance_stats
from updater import get_usdt_futures_symbols, check_signal_outcomes
from trainer import train_model
from training_loop import training_loop

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- BOT LOOPS ---

async def analysis_loop(client, symbols, model, label_encoder, model_features):
    """LOOP 1: Phân tích thị trường, chọn chiến lược từ config."""
    logger.info(f"✅ Analysis Loop starting (Strategy: {config.STRATEGY_MODE})")
    semaphore = asyncio.Semaphore(config.CONCURRENT_REQUESTS)
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            # KIỂM TRA VÀ GỌI ĐÚNG HÀM CHIẾN LƯỢC
            if config.STRATEGY_MODE == 'Elliotv8':
                await perform_elliotv8_analysis(client, symbol)
            else: # Mặc định là 'AI'
                await perform_ai_fallback_analysis(client, symbol, model, label_encoder, model_features)

    while True:
        try:
            logger.info(f"--- Starting analysis cycle for {len(symbols)} symbols ---")
            tasks = [process_with_semaphore(s) for s in list(symbols)]
            await asyncio.gather(*tasks)
            logger.info(f"--- Analysis cycle complete. Sleeping for {config.LOOP_SLEEP_INTERVAL_SECONDS} seconds. ---")
            await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"An error in analysis_loop: {e}", exc_info=True)
            await asyncio.sleep(60)

# ... (các hàm loop khác: signal_check_loop, updater_loop, outcome_check_loop giữ nguyên)

async def signal_check_loop(notifier: NotificationHandler):
    logger.info(f"✅ New Signal Alert Loop starting...")
    notified_signal_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            existing_ids = conn.execute("SELECT rowid FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
            notified_signal_ids.update(r[0] for r in existing_ids)
    except Exception as e:
        logger.error(f"❌ Error initializing signal_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                if not notified_signal_ids:
                    new_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
                else:
                    query = "SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE' AND rowid NOT IN ({})".format(','.join('?' for _ in notified_signal_ids))
                    new_signals = conn.execute(query, tuple(notified_signal_ids)).fetchall()
            for signal in new_signals:
                await notifier.send_batch_trend_alert_notification([dict(signal)])
                notified_signal_ids.add(signal['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def updater_loop(client: AsyncClient):
    logger.info(f"✅ Trade Updater Loop starting...")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"❌ A critical error in updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def outcome_check_loop(notifier: NotificationHandler):
    logger.info(f"✅ Trade Outcome Notification Loop starting...")
    notified_trade_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            closed_trades = conn.execute("SELECT rowid FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
            notified_trade_ids.update(r[0] for r in closed_trades)
    except Exception as e:
        logger.error(f"❌ Error initializing outcome_check_loop: {e}")
    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                if not notified_trade_ids:
                    newly_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
                else:
                    query = "SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE' AND rowid NOT IN ({})".format(','.join('?' for _ in notified_trade_ids))
                    newly_closed_trades = conn.execute(query, tuple(notified_trade_ids)).fetchall()
            for trade in newly_closed_trades:
                await notifier.send_trade_outcome_notification(dict(trade))
                notified_trade_ids.add(trade['rowid'])
        except Exception as e:
            logger.error(f"❌ Error in outcome_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

# --- MAIN FUNCTION ---
async def main():
    logger.info("--- 🚀 Initializing Bot ---")
    client = None
    try:
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        init_sqlite_db(config.SQLITE_DB_PATH)
        tg_handler = TelegramHandler(api_token=config.TELEGRAM_BOT_TOKEN)
        notifier = NotificationHandler(telegram_handler=tg_handler)
        
        logger.info("🧠 Loading AI Model...")
        model, label_encoder, model_features = None, None, None
        try:
            model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))
            logger.info("✅ AI Model loaded successfully.")
        except FileNotFoundError:
            logger.warning("⚠️ Model files not found. Attempting to train a new one...")
            
        loop = asyncio.get_running_loop()
        logger.info("💪 Performing initial model training...")
        initial_accuracy = await loop.run_in_executor(None, train_model)
        
        if initial_accuracy is not None:
            logger.info("Reloading model after initial training...")
            model, label_encoder, model_features = (joblib.load("model_trend.pkl"), joblib.load("trend_label_encoder.pkl"), joblib.load("model_features.pkl"))

        all_symbols = await get_usdt_futures_symbols(client)
        if not all_symbols:
            logger.critical("Could not fetch symbols. Exiting.")
            sys.exit(1)
            
        if all([model, label_encoder, model_features]):
            await notifier.send_startup_notification(len(all_symbols), initial_accuracy)
        else:
            logger.warning("Starting in FALLBACK MODE because AI model is not ready.")
            await notifier.send_fallback_mode_startup_notification(len(all_symbols))

        logger.info("--- 🟢 Bot is now running. All loops are active. ---")
        
        analysis_task = asyncio.create_task(analysis_loop(client, all_symbols, model, label_encoder, model_features))
        signal_task = asyncio.create_task(signal_check_loop(notifier))
        updater_task = asyncio.create_task(updater_loop(client))
        outcome_task = asyncio.create_task(outcome_check_loop(notifier))
        training_task = asyncio.create_task(training_loop(notifier))

        await asyncio.gather(
            analysis_task,
            signal_task,
            updater_task,
            outcome_task,
            training_task
        )
    except Exception as main_exc:
        logger.critical(f"A fatal error in main execution block: {main_exc}", exc_info=True)
    finally:
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")
        logger.info("--- ⭕ Bot application shutting down. ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
