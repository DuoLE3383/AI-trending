import logging
import pandas as pd
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from typing_extensions import TypedDict
from datetime import datetime, timedelta

# Import the main config module
import config

# --- Type Definitions ---
class AnalysisResult(TypedDict, total=False):
    symbol: str
    timeframe: str
    price: float
    rsi_val: float
    rsi_interpretation: str
    atr_value: float
    ema_fast_val: float
    ema_medium_val: float
    ema_slow_val: float
    trend: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    proj_range_short_low: float
    proj_range_short_high: float
    proj_range_long_low: float
    proj_range_long_high: float
    analysis_timestamp_utc: pd.Timestamp

# --- Module-level Helper Functions ---
def _get_range_str(low: float, high: float, price: float) -> str:
    """Formats a projected range string with percentage changes from the current price."""
    if not all(isinstance(i, (int, float)) for i in [low, high, price]) or price == 0:
        return "`$N/A - $N/A`"
    low_pct = f"({((low - price) / price) * 100:+.2f}%)"
    high_pct = f"({((high - price) / price) * 100:+.2f}%)"
    return f"`${low:,.4f}` {low_pct} - `${high:,.4f}` {high_pct}"


# Ensure the class name here matches your import in run.py
class NotificationHandler:
    """
    Handles trend analysis notifications, now integrated with the main config.
    """
    _LONG_TRADE = "Long"
    _SHORT_TRADE = "Short"
    
    def __init__(self, telegram_handler: Any):
        """
        Initializes the NotificationHandler.
        Args:
            telegram_handler (Any): An initialized instance of the telegram handler.
        """
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

        # Settings loaded from main config
        self.status_interval = timedelta(minutes=config.config_data["notifications"]["status_update_interval_minutes"])
        self.leverage = config.config_data["notifications"]["leverage_multiplier"]
        
        # In-memory State Stores
        self.last_notified_signal: Dict[str, str] = {}
        self.last_status_update: Dict[str, pd.Timestamp] = {}

    async def send_startup_notification(self, chat_id: str, message_thread_id: Optional[int], symbols_str: str, symbols_full_list: List[str]):
        """Sends a notification when the bot starts up."""
        msg = (
            f"📈 *Trend Analysis Bot Started*\n\n"
            f"📊 Monitoring: *{symbols_str}* 🎯Most #Binance Pair List\n"
            f"⚙️ Settings: Timeframe={config.TIMEFRAME}\n"
            f"🕒 Time: `{pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        
        self.logger.info("Attempting to send startup notification...")
        try:
            # CORRECTED function name
            await self.telegram_handler.send_telegram_notification(
                chat_id, msg, message_thread_id=message_thread_id
            )
            self.logger.info(f"Startup notification sent successfully. Monitoring {len(symbols_full_list)} symbols.")
        except Exception as e:
            self.logger.critical(f"Could not send startup message to Telegram: {e}")

    async def send_individual_trend_alert_notification(self, chat_id: str, message_thread_id: Optional[int], analysis_result: AnalysisResult):
        """Formats and sends a detailed alert for a strong signal."""
        symbol = analysis_result.get('symbol', 'N/A')
        trend = analysis_result.get('trend', 'N/A')
        price = analysis_result.get('price', 0)
        entry = analysis_result.get('entry_price')
        sl = analysis_result.get('stop_loss')
        tp1 = analysis_result.get('take_profit_1')
        tp2 = analysis_result.get('take_profit_2')
        tp3 = analysis_result.get('take_profit_3')

        message = (
            f"{trend}\n\n"
            f"Symbol: *{symbol}*\n"
            f"Entry: `${entry:,.4f}`\n"
            f"StopLoss: `${sl:,.4f}`\n"
            f"TakeProfit 1: `${tp1:,.4f}`\n"
            f"TakeProfit 2: `${tp2:,.4f}`\n"
            f"TakeProfit 3: `${tp3:,.4f}`\n\n"
            f"Leverage: x{self.leverage}\n"
            f"Current Price: `${price:,.4f}`\n"
            f"🕒 Time: `{pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        
        try:
            # CORRECTED function name
            await self.telegram_handler.send_telegram_notification(
                chat_id, message, message_thread_id=message_thread_id
            )
            self.logger.info(f"Signal alert for {symbol} sent successfully.")
        except Exception as e:
            self.logger.error(f"Failed to send signal alert for {symbol}: {e}")
