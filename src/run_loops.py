# src/run_loops.py
# Tệp này chứa tất cả các hàm vòng lặp của bot.

import logging
import asyncio
import sqlite3
import os
import sys

# Imports từ các module của dự án và thư viện bên ngoài
from binance import AsyncClient
from . import config # Dùng .config vì đang ở trong thư mục src
from .analysis_engine import perform_ai_fallback_analysis, perform_elliotv8_analysis
from .notifications import NotificationHandler
from .updater import get_usdt_futures_symbols, check_signal_outcomes
from .api_server import app as flask_app

logger = logging.getLogger(__name__)

# --- CÁC VÒNG LẶP CỦA BOT ---

async def analysis_loop(client: AsyncClient, model, label_encoder, model_features):
    """LOOP 1: Phân tích thị trường liên tục, chọn chiến lược từ config."""
    logger.info(f"✅ Analysis Loop starting (Strategy: {config.STRATEGY_MODE})")
    semaphore = asyncio.Semaphore(config.CONCURRENT_REQUESTS)

    async def process_with_semaphore(symbol: str):
        async with semaphore:
            if config.STRATEGY_MODE == 'Elliotv8':
                await perform_elliotv8_analysis(client, symbol)
            else:
                await perform_ai_fallback_analysis(client, symbol, model, label_encoder, model_features)

    while True:
        try:
            current_symbols = await get_usdt_futures_symbols(client)
            if not current_symbols:
                logger.warning("Không tìm thấy symbol nào để phân tích. Bỏ qua chu kỳ này.")
                await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
                continue
            
            logger.info(f"--- Bắt đầu chu kỳ phân tích cho {len(current_symbols)} symbols ---")
            tasks = [process_with_semaphore(s) for s in current_symbols]
            await asyncio.gather(*tasks)
            logger.info(f"--- Chu kỳ phân tích hoàn tất. Tạm nghỉ {config.LOOP_SLEEP_INTERVAL_SECONDS} giây. ---")
            await asyncio.sleep(config.LOOP_SLEEP_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Lỗi trong analysis_loop: {e}", exc_info=True)
            await asyncio.sleep(60)

async def signal_check_loop(notifier: NotificationHandler):
    """LOOP 2: Kiểm tra tín hiệu mới trong DB để gửi thông báo."""
    logger.info("✅ New Signal Alert Loop starting...")
    notified_signal_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            existing_ids = conn.execute("SELECT rowid FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
            notified_signal_ids.update(row[0] for row in existing_ids)
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo signal_check_loop: {e}")

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                all_active_signals = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status = 'ACTIVE'").fetchall()
            new_signals_to_notify = [s for s in all_active_signals if s['rowid'] not in notified_signal_ids]
            if new_signals_to_notify:
                logger.info(f"Phát hiện {len(new_signals_to_notify)} tín hiệu mới cần thông báo.")
                for signal in new_signals_to_notify:
                    notifier.queue_signal(dict(signal))
                    notified_signal_ids.add(signal['rowid'])
        except Exception as e:
            logger.error(f"Lỗi trong signal_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def updater_loop(client: AsyncClient):
    """LOOP 3: Cập nhật trạng thái của các tín hiệu (check TP/SL)."""
    logger.info("✅ Trade Updater Loop starting...")
    while True:
        try:
            await check_signal_outcomes(client)
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng trong updater_loop: {e}", exc_info=True)
        await asyncio.sleep(config.UPDATER_INTERVAL_SECONDS)

async def outcome_check_loop(notifier: NotificationHandler):
    """LOOP 4: Kiểm tra các giao dịch đã đóng để gửi thông báo kết quả."""
    logger.info("✅ Trade Outcome Notification Loop starting...")
    notified_trade_ids = set()
    try:
        with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
            closed_trades = conn.execute("SELECT rowid FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
            notified_trade_ids.update(row[0] for row in closed_trades)
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo outcome_check_loop: {e}")

    while True:
        try:
            with sqlite3.connect(f'file:{config.SQLITE_DB_PATH}?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                all_closed_trades = conn.execute("SELECT rowid, * FROM trend_analysis WHERE status != 'ACTIVE'").fetchall()
                newly_closed_trades = [t for t in all_closed_trades if t['rowid'] not in notified_trade_ids]
            if newly_closed_trades:
                logger.info(f"Phát hiện {len(newly_closed_trades)} giao dịch vừa đóng.")
                for trade in newly_closed_trades:
                    notifier.queue_trade_outcome(dict(trade))
                    notified_trade_ids.add(trade['rowid'])
        except Exception as e:
            logger.error(f"Lỗi trong outcome_check_loop: {e}", exc_info=True)
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SECONDS)

async def notification_flush_loop(notifier: NotificationHandler):
    """LOOP 5: Gửi các thông báo trong hàng đợi một cách định kỳ."""
    logger.info("✅ Notification Queue Flush Loop starting (10 min interval)...")
    while True:
        await asyncio.sleep(10 * 60)
        logger.info("⏰ Đến giờ, gửi các thông báo đang chờ...")
        await asyncio.gather(
            notifier.flush_signal_queue(),
            notifier.flush_outcome_queue()
        )

async def summary_loop(notifier: NotificationHandler):
    """LOOP 6: Gửi tóm tắt hiệu suất hoạt động định kỳ."""
    logger.info("✅ Periodic Summary Loop starting (60 min interval)...")
    while True:
        await asyncio.sleep(60 * 60)
        logger.info("📰 Tạo và gửi tóm tắt hiệu suất định kỳ...")
        await notifier.send_periodic_summary_notification()

# Trong tệp: src/run_loops.py

async def update_loop(notifier: NotificationHandler):
    """LOOP 7: Tự động kiểm tra cập nhật từ Git và khởi động lại bot."""
    logger.info("✅ Auto-update Loop starting...")
    remote_name = "origin"
    branch_name = "ai"
    remote_branch = f"{remote_name}/{branch_name}"

    while True:
        await asyncio.sleep(10 * 60)
        try:
            logger.info("📡 Kiểm tra cập nhật mã nguồn từ Git...")

            # SỬA LỖI: Tách await và .wait()
            fetch_process = await asyncio.create_subprocess_shell(
                f'git fetch {remote_name}',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await fetch_process.wait()

            local_hash_proc = await asyncio.create_subprocess_shell('git rev-parse HEAD', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            local_hash_out, _ = await local_hash_proc.communicate()

            remote_hash_proc = await asyncio.create_subprocess_shell(f'git rev-parse {remote_branch}', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            remote_hash_out, remote_hash_err = await remote_hash_proc.communicate()

            if remote_hash_proc.returncode != 0:
                logger.error(f"Không thể lấy commit hash từ remote '{remote_branch}': {remote_hash_err.decode().strip()}")
                continue
            
            local_hash = local_hash_out.decode().strip()
            remote_hash = remote_hash_out.decode().strip()

            if local_hash != remote_hash:
                logger.info(f"💡 Phát hiện mã nguồn mới trên {remote_branch}! Đang thử cập nhật...")
                
                # SỬA LỖI: Tách await và .wait()
                stash_proc = await asyncio.create_subprocess_shell(
                    'git stash',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await stash_proc.wait()
                
                # SỬA LỖI: Tách await và .wait()
                pull_process = await asyncio.create_subprocess_shell(
                    f'git pull {remote_name} {branch_name}',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                pull_stdout, pull_stderr = await pull_process.communicate() # Dùng communicate() để lấy output

                if pull_process.returncode == 0:
                    logger.critical(f"✅ Cập nhật thành công! Chuẩn bị khởi động lại bot...\n{pull_stdout.decode()}")
                    await notifier.send_message_to_all("🚨 Bot đang khởi động lại để áp dụng phiên bản mới...")
                    await asyncio.sleep(5)
                    os.execv(sys.executable, ['python'] + sys.argv)
                else:
                    logger.error(f"❌ Cập nhật thất bại: {pull_stderr.decode()}")
                    await notifier.send_message_to_all(f"❌ Lỗi khi cập nhật từ Git:\n`{pull_stderr.decode()}`")
            else:
                logger.info(f"✅ Mã nguồn đã ở phiên bản mới nhất ({remote_branch}).")

        except Exception as e:
            logger.error(f"❌ Lỗi trong vòng lặp tự động cập nhật: {e}", exc_info=True)

def run_api_server():
    """Hàm đồng bộ để chạy Flask server trong một thread riêng."""
    logger.info("✅ Starting API server in a background thread...")
    flask_app.run(host='0.0.0.0', port=8080, debug=False)