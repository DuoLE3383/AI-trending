# notifications.py (Phiên bản cuối cùng, đầy đủ tất cả các hàm thông báo)
import logging
from typing import List, Dict, Any
import asyncio
from telegram_handler import TelegramHandler
import httpx # Import httpx to catch its specific exceptions
import json # Import json for parsing Telegram API error responses
import config
import re
import pandas as pd

logger = logging.getLogger(__name__)

class NotificationHandler:
    # ... (rest of the class)
    def __init__(self, telegram_handler: TelegramHandler):
        self.telegram_handler = telegram_handler
        self.logger = logger
        self.esc = self.telegram_handler.escape_markdownv2
        self.signal_notification_queue: List[Dict[str, Any]] = []
        self.BATCH_THRESHOLD = 10

    def format_and_escape(self, value: Any, precision: int = 5) -> str:
        """Định dạng một giá trị số và escape nó an toàn cho MarkdownV2."""
        if value is None: return '`—`'
        try:
            return f"`{self.esc(f'{float(value):.{precision}f}')}`"
        except (ValueError, TypeError):
            return '`—`'

    async def _send_with_retry(self, send_func, **kwargs):
        """
        Hàm helper để gửi tin nhắn/ảnh với cơ chế thử lại,
        đặc biệt xử lý lỗi 429 Too Many Requests từ Telegram API.
        """
        max_retries = 3
        initial_delay = 2 # Initial delay for non-429 errors

        for attempt in range(max_retries):
            try:
                await send_func(**kwargs)
                self.logger.debug(f"Successfully sent Telegram message/photo (attempt {attempt + 1}).")
                return True
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    try:
                        error_json = e.response.json()
                        retry_after = error_json.get('parameters', {}).get('retry_after')
                        if retry_after:
                            self.logger.warning(f"Telegram API hit rate limit (429). Retrying after {retry_after} seconds (attempt {attempt + 1}/{max_retries}).")
                            await asyncio.sleep(retry_after)
                            continue # Continue to the next attempt immediately after sleeping
                    except (json.JSONDecodeError, AttributeError): # Need to import json
                        self.logger.warning(f"Telegram API hit rate limit (429) but could not parse 'retry_after'. Using exponential backoff (attempt {attempt + 1}/{max_retries}).")
                
                # For other HTTP errors or if 429 without retry_after
                self.logger.error(f"HTTP error occurred while sending (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1: await asyncio.sleep(initial_delay * (2 ** attempt))
                else: self.logger.critical(f"❌ Failed after {max_retries} attempts due to HTTP error.")
                raise # Re-raise the last HTTP error if all retries fail
            except Exception as e: # Catch any other unexpected errors
                self.logger.error(f"An unexpected error occurred while sending (attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                if attempt < max_retries - 1: await asyncio.sleep(initial_delay * (2 ** attempt))
                else: self.logger.critical(f"❌ Failed after {max_retries} attempts due to unexpected error.")
                raise # Re-raise the last unexpected error if all retries fail
        return False

    async def _send_to_both(self, message: str, thread_id: int = None, disable_web_page_preview: bool = False):
        """Gửi tin nhắn văn bản đến cả group và channel."""
        self.logger.debug(f"Preparing to send text message to Telegram (both group and channel): {message[:100]}...")
        common_kwargs = {'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_web_page_preview}
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'text': message, 'message_thread_id': thread_id, **common_kwargs}
        await self._send_with_retry(self.telegram_handler.send_message, **group_kwargs)
        # Gửi đến channel nếu TELEGRAM_CHANNEL_ID được cấu hình và khác với group ID
        if hasattr(config, 'TELEGRAM_CHANNEL_ID') and config.TELEGRAM_CHANNEL_ID and config.TELEGRAM_CHANNEL_ID != config.TELEGRAM_CHAT_ID:
            channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'text': message, **common_kwargs} # Channel thường không có thread_id
            await self._send_with_retry(self.telegram_handler.send_message, **channel_kwargs)

    async def _send_photo_to_both(self, photo: str, caption: str, thread_id: int = None):
        """Gửi ảnh có chú thích đến cả group và channel."""
        self.logger.debug(f"Preparing to send photo to Telegram with caption: {caption[:100]}...")
        group_kwargs = {'chat_id': config.TELEGRAM_CHAT_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2', 'message_thread_id': thread_id}
        await self._send_with_retry(self.telegram_handler.send_photo, **group_kwargs)
        # Gửi ảnh đến channel nếu TELEGRAM_CHANNEL_ID được cấu hình và khác với group ID
        if hasattr(config, 'TELEGRAM_CHANNEL_ID') and config.TELEGRAM_CHANNEL_ID and config.TELEGRAM_CHANNEL_ID != config.TELEGRAM_CHAT_ID:
            channel_kwargs = {'chat_id': config.TELEGRAM_CHANNEL_ID, 'photo': photo, 'caption': caption, 'parse_mode': 'MarkdownV2'}
            await self._send_with_retry(self.telegram_handler.send_photo, **channel_kwargs)

    # === CÁC HÀM GỬI THÔNG BÁO ===

    def queue_signal(self, signal: Dict[str, Any]):
        """Adds a single signal to the notification queue."""
        self.signal_notification_queue.append(signal)
        self.logger.info(f"Queued signal for {signal.get('symbol')}. Queue size: {len(self.signal_notification_queue)}")

    async def flush_signal_queue(self):
        """
        Checks the queue and sends notifications.
        Groups them if the queue size is over the threshold.
        """
        if not self.signal_notification_queue:
            return

        signals_to_send = self.signal_notification_queue.copy()
        self.signal_notification_queue.clear()
        self.logger.info(f"Flushing signal queue with {len(signals_to_send)} signals.")

        if len(signals_to_send) > self.BATCH_THRESHOLD:
            # Group messages into one
            header = self.esc(f"🆘 {len(signals_to_send)} New Signals Found! 🆘")
            message_parts = [header, self.esc("\n\n----------------------------------------\n\n")]
            
            for i, result in enumerate(signals_to_send):
                trend_raw = result.get('trend', '').replace("_", " ").title()
                trend_emoji = "🔼 LONG" if "Bullish" in trend_raw else "🔽 SHORT"
                
                signal_summary = (
                    f"*{i+1}\\. {self.esc(result.get('symbol', 'N/A'))}* \\| {trend_emoji}\n"
                    f"  Entry: {self.format_and_escape(result.get('entry_price'))} \\| SL: {self.format_and_escape(result.get('stop_loss'))} \\| TP1: {self.format_and_escape(result.get('take_profit_1'))}"
                    f" \\| TP2: {self.format_and_escape(result.get('take_profit_2'))} \\| TP3: {self.format_and_escape(result.get('take_profit_3'))}"
                )

                message_parts.append(signal_summary)
                
                # Add a separator between signals, but not after the last one
                if i < len(signals_to_send) - 1:
                    message_parts.append(self.esc("---")) 
            
            full_message = "\n".join(message_parts)
            
            # Telegram message limit is 4096 characters. Truncate if necessary.
            if len(full_message) > 4096:
                self.logger.warning(f"Grouped message for {len(signals_to_send)} signals exceeds Telegram limit. Truncating.")
                full_message = full_message[:4090] + self.esc("...") # Add ellipsis and ensure it's escaped
            
            await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

        else:
            # Send individually if not over threshold
            header = self.esc("🆘 New Signal Found! 🆘") # Changed header for individual messages
            separator = self.esc("\n\n----------------------------------------\n\n")
            for result in signals_to_send:
                trend_raw = result.get('trend', '').replace("_", " ").title()
                trend_emoji = "🔼 LONG" if "Bullish" in trend_raw else "🔽 SHORT"
                signal_detail = (
                    f"\\#{self.esc(trend_raw)} // {trend_emoji} // {self.esc(result.get('symbol', 'N/A'))}\n"
                    f"📌Entry: {self.format_and_escape(result.get('entry_price'))}\n"
                    f"❌SL: {self.format_and_escape(result.get('stop_loss'))}\n"
                    f"🎯TP1: {self.format_and_escape(result.get('take_profit_1'))}\n"
                    f"🎯TP2: {self.format_and_escape(result.get('take_profit_2'))}\n"
                    f"🎯TP3: {self.format_and_escape(result.get('take_profit_3'))}"
                )
                full_message = header + separator + signal_detail
                await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
                await asyncio.sleep(0.5) # Small delay between individual messages

    async def send_periodic_summary_notification(self):
        """Fetches performance stats and sends a summary notification."""
        self.logger.info("Preparing periodic performance summary notification...")
        
        try:
            # Local import to avoid potential circular dependency issues at startup
            from performance_analyzer import get_performance_stats 
            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(None, get_performance_stats)
            
            if not stats or stats.get('total_completed_trades', 0) == 0:
                self.logger.info("No completed trades to summarize. Skipping summary notification.")
                return

            header = self.esc("📊 Hourly Performance Summary")
            
            total_trades = stats.get('total_completed_trades', 0)
            wins = stats.get('wins', 0)
            losses = stats.get('losses', 0)
            win_rate = stats.get('win_rate', 0.0)

            summary_msg = (
                f"Total Trades: `{total_trades}`\n"
                f"Wins: `{wins}`\n"
                f"Losses: `{losses}`\n"
                f"Win Rate: `{win_rate:.2f}%`"
            )
            
            full_message = "\n\n".join([header, self.esc("---"), summary_msg])
            await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

        except Exception as e:
            self.logger.error(f"Failed to send periodic summary notification: {e}", exc_info=True)

    async def send_simulation_summary_notification(self, stats_by_symbol: Dict[str, Any]):
        """Sends a per-symbol summary of the data simulation results."""
        self.logger.info("Preparing data simulation summary notification...")
        
        if not stats_by_symbol:
            message = self.esc("Data simulation complete, but no trades were generated to analyze.")
            await self._send_to_both(message)
            return

        header = self.esc("📊 Data Simulation Complete - Per-Symbol Summary 📊")
        
        message_parts = [header]
        
        # Sort symbols by the number of trades, descending
        sorted_symbols = sorted(stats_by_symbol.items(), key=lambda item: item[1].get('total_trades', 0), reverse=True)

        for symbol, stats in sorted_symbols:
            total_trades = stats.get('total_trades', 0)
            wins = stats.get('wins', 0)
            losses = stats.get('losses', 0)
            win_rate = stats.get('win_rate', 0.0)
            net_pnl = stats.get('net_pnl_percentage', 0.0)

            symbol_header = f"*{self.esc(symbol)} Summary*"
            symbol_details = (
                f"Total Trades: `{total_trades}`\n"
                f"Wins: `{wins}` \\| Losses: `{losses}`\n"
                f"Win Rate: `{win_rate:.2f}%`\n"
                f"Net PnL: `{net_pnl:+.2f}%`"
            )
            message_parts.append("\n\n".join([self.esc("---"), symbol_header, symbol_details]))
        
        footer = self.esc("The bot will now start with this historical data for training.")
        message_parts.append("\n\n" + footer)
        
        full_message = "\n".join(message_parts)

        # Truncate if message is too long for Telegram
        if len(full_message) > 4096:
            self.logger.warning("Per-symbol summary message exceeds Telegram limit. Truncating.")
            full_message = full_message[:4090] + self.esc("\n... (message truncated)")

        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_trade_outcome_notification(self, trade_details: Dict[str, Any]):
        self.logger.info(f"Preparing to send trade outcome notification for {trade_details.get('symbol')}.")
        try:
            status_raw = trade_details.get('status', 'N/A')
            trend_raw = trade_details.get('trend', '')
            pnl_percentage_from_db = trade_details.get('pnl_percentage') # Lấy PnL từ DB

            is_win = ("TP" in status_raw) or (pnl_percentage_from_db is not None and pnl_percentage_from_db > 0)
            outcome_emoji, outcome_text = ("✅", "WIN") if is_win else ("❌", "LOSS")
            header = f"{outcome_emoji} *Trade Closed: {self.esc(outcome_text)}* {outcome_emoji}"
            symbol = self.esc(trade_details.get('symbol', 'N/A'))
            direction = f"LONG 🔼" if 'BULLISH' in trend_raw else f"SHORT 🔽"
            pnl_without_leverage_str, pnl_with_leverage_str = "`—`", "`—`"
            entry_p, closing_p = trade_details.get('entry_price'), trade_details.get('exit_price')
            if entry_p and closing_p:
                try:
                    pnl = ((float(closing_p) - float(entry_p)) / float(entry_p)) * 100
                    if 'BEARISH' in trend_raw: pnl *= -1
                    pnl_without_leverage_str = f"`{self.esc(f'{pnl:+.2f}%')}`"
                    pnl_with_leverage_str = f"`{self.esc(f'{pnl * config.LEVERAGE:+.2f}%')}`"
                except (ValueError, TypeError): pass
            message = (
                f"{header}\n\n"
                f"Symbol: `{symbol}`\n"
                f"Direction: `{self.esc(direction)}`\n"
                f"Outcome: `{self.esc(status_raw)}`\n\n"
                f"Entry Price: {self.format_and_escape(trade_details.get('entry_price'))}\n"
                f"Closing Price: {self.format_and_escape(closing_p)}\n"
                # f"PNL \\(1x\\): {pnl_without_leverage_str}\n"
                f"PNL \\(x{config.LEVERAGE}\\): {pnl_with_leverage_str}"
            )
            await self._send_to_both(message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)
        except Exception as e:
            self.logger.error(f"Failed to send trade outcome notification: {e}", exc_info=True)

    async def send_startup_notification(self, symbols_count: int, accuracy: float | None):
        self.logger.info(f"Preparing to send startup notification (symbols: {symbols_count}, accuracy: {accuracy}).")
        safe_accuracy_msg = ""
        if accuracy is not None:
            safe_accuracy_msg = f"✅ *Initial Model Trained* \\| *Accuracy:* `{self.esc(f'{accuracy:.2%}')}`"
        else:
            safe_accuracy_msg = "⚠️ *Initial Model Training Failed/Skipped*"
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        separator = self.esc("-----------------------------------------")
        caption = "\n\n".join(["🚀 *AI Trading Bot Activated*", safe_accuracy_msg, monitoring_msg, separator, promo_msg])
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_training_complete_notification(self, accuracy: float | None, symbols_count: int):
        self.logger.info("Preparing periodic training complete notification...")
        """Hàm thông báo kết quả training định kỳ."""
        self.logger.info("Preparing periodic training complete notification...")
        header = self.esc("🤖 AI Model Update")
        
        status_message = ""
        if accuracy is not None:
            status_message = f"✅ *Periodic Training Complete*\\.\n*New Accuracy:* `{self.esc(f'{accuracy:.2%}')}`"
        else:
            status_message = "❌ *Periodic Training Failed*\\."

        monitoring_msg = f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        
        full_message = "\n\n".join([header, status_message, monitoring_msg])
        await self._send_to_both(full_message, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)

    async def send_fallback_mode_startup_notification(self, symbols_count: int):
        self.logger.info(f"Preparing to send fallback mode startup notification (symbols: {symbols_count}).")
        binance_link = 'https://www.binance.com/activity/referral-entry/CPA?ref=CPA_006MBW985P'
        main_msg = (
            f"⚠️ *AI Model not available* \\- not enough training data\\.\n"
            f"✅ Bot is running in *Rule\\-Based Mode* and collecting data\\.\n\n"
            f"📡 Monitoring `{symbols_count}` pairs on the `{self.esc(config.TIMEFRAME)}` timeframe\\."
        )
        promo_msg = f"💰 *New \\#Binance\\?* [Get a \\$100 Bonus]({binance_link})\\!"
        separator = self.esc("-----------------------------------------")
        caption = "\n\n".join(["🚀 *AI Trading Bot Activated \\(Fallback Mode\\)*", main_msg, separator, promo_msg])
        photo_url = "https://github.com/DuoLE3383/AI-trending/blob/main/100usd.png?raw=true"
        await self._send_photo_to_both(photo=photo_url, caption=caption, thread_id=config.TELEGRAM_MESSAGE_THREAD_ID)