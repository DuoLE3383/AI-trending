# notifications.py

import logging
import pandas as pd
import asyncio
import configparser
from typing import List, Dict, Any, Optional, Tuple
from typing_extensions import TypedDict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from datetime import datetime, timedelta

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
    if not price or price == 0:
        return f"`${low:,.4f} - ${high:,.4f}`"
    low_pct = f"({((low - price) / price) * 100:+.2f}%)"
    high_pct = f"({((high - price) / price) * 100:+.2f}%)"
    return f"`${low:,.4f}` {low_pct} - `${high:,.4f}` {high_pct}"


class TrendNotifier:
    """
    Handles trend analysis notifications, state management, and message formatting.
    NOTE: Your realtime-trend.py imports 'NotificationHandler'. You may need to rename this class.
    """
    ## REFACTORED: Class constants for trade directions and levels
    _LONG_TRADE = "Long"
    _SHORT_TRADE = "Short"
    _STOP_LOSS = "SL"

    def __init__(self, config_path: str, telegram_handler: Any):
        """
        Initializes the TrendNotifier.

        Args:
            config_path (str): Path to the configuration file.
            telegram_handler (Any): An initialized instance of the telegram handler module.
        """
        self.config = self._load_config(config_path)
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(__name__)

        # --- Settings ---
        self.notification_threshold = self.config.getfloat('settings', 'notification_threshold_percent', fallback=0.05)
        self.status_interval = timedelta(minutes=self.config.getint('settings', 'status_update_interval_minutes', fallback=10))
        self.leverage = self.config.getint('settings', 'leverage_multiplier', fallback=5)

        # --- Emojis and Messages ---
        self.emojis = self.config['emojis']

        # --- In-memory State Stores ---
        ## REFACTORED: State is now managed as instance attributes
        self.last_notified_ranges: Dict[str, Dict[str, Optional[float]]] = {}
        self.last_notification_timestamp: Dict[str, pd.Timestamp] = {}

    def _load_config(self, config_path: str) -> configparser.ConfigParser:
        """Loads configuration from an INI file with error handling."""
        config = configparser.ConfigParser()
        try:
            if not config.read(config_path):
                raise FileNotFoundError(f"Configuration file not found at {config_path}")
        except (configparser.Error, FileNotFoundError) as e:
            logging.critical(f"Failed to load configuration: {e}")
            raise
        return config

    # <<< --- EDITED METHOD --- >>>
    async def send_startup_notification(self, chat_id: str, message_thread_id: Optional[int], symbols_str: str, symbols_full_list: List[str]):
        """Sends a notification when the bot starts up, using the pre-formatted symbol string."""
        if not self.telegram_handler.is_configured():
            return
        
        # NOTE: The 'timeframe' setting is not available in this class.
        # It would need to be passed from realtime-trend.py if you want to include it here.
        # The message format is now updated to match your request.
        msg = (
            f"📈 *Trend Analysis Bot Started*\n\n"
            f"📊 Monitoring: *{symbols_str}* 🎯Most #Binance Pair List\n"
            f"⚙️ Settings: Timeframe=15m\n" # Assuming 15m, as it's not passed directly
            f"🕒 Time: `{pd.to_datetime('now', utc=True).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n\n"
            f"🔔 This will be updated every 10 minutes with the latest analysis results.🚨🚨 Keep Calm and follow @aisignalvip for more updates.\n\n"
            f"💡 Tip: If you want to receive notifications in a specific topic, please set the topic ID in the config file."
        )
        
        self.logger.info("Attempting to send startup notification...")
        try:
            await self.telegram_handler.send_telegram_notification(
                chat_id, msg, message_thread_id=message_thread_id, suppress_print=True
            )
            self.logger.info(f"Startup notification sent successfully. Monitoring {len(symbols_full_list)} symbols.")
        except Exception as e:
            self.logger.critical(f"Could not send startup message to Telegram: {e}")


    async def send_shutdown_notification(self, chat_id: str, message_thread_id: Optional[int], symbols: List[str]):
        """Sends a notification when the bot is shut down."""
        if not self.telegram_handler.is_configured():
            return
        msg = (f"🛑 Trend Analysis Bot for *{len(symbols)} symbols* stopped by user at "
               f"`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}`.")
        await self.telegram_handler.send_telegram_notification(chat_id, msg, message_thread_id=message_thread_id)

    def _should_send_alert(self, symbol_key: str, new_ranges: Dict[str, Optional[float]]) -> bool:
        """Determines if a notification should be sent based on range changes."""
        previous_ranges = self.last_notified_ranges.get(symbol_key)
        if not previous_ranges:
            return True

        for key, prev_val in previous_ranges.items():
            curr_val = new_ranges.get(key)
            if prev_val and curr_val and prev_val != 0:
                if abs(curr_val - prev_val) / abs(prev_val) > self.notification_threshold:
                    self.logger.info(f"Threshold exceeded for {symbol_key} on '{key}'. Sending alert.")
                    return True
        return False

    def _determine_trade_info(self, entry: Optional[float], tp1: Optional[float], original_trend: str) -> Tuple[Optional[str], str, str]:
        """Determines trade direction and corrects the trend label if necessary."""
        if not all([entry, tp1]):
            return None, original_trend, ""

        if tp1 > entry:
            direction = self._LONG_TRADE
            corrected_label = f"{self.emojis.get('bullish')} Bullish"
        else:
            direction = self._SHORT_TRADE
            corrected_label = f"{self.emojis.get('bearish')} Bearish"

        if original_trend not in corrected_label:
            self.logger.warning(f"Correcting trend! Original='{original_trend}', but levels indicate a '{direction}' trade.")
        return direction, corrected_label, f"({direction})"

    def _format_level(self, level_name: str, level_val: Optional[float], entry_val: float, emoji: str, direction: str) -> str:
        """Formats a single SL or TP level with its percentage change."""
        if not all([level_val, entry_val, direction]):
            return ""
        percentage = ((level_val - entry_val) / entry_val) * 100
        leveraged_percentage = -abs(percentage * self.leverage) if level_name == self._STOP_LOSS else abs(percentage * self.leverage)
        return f"{emoji} {level_name}: `${level_val:,.4f}` ({leveraged_percentage:+.2f}%)\n"

    def _create_alert_keyboard(self, symbol: str) -> Optional[InlineKeyboardMarkup]:
        """Creates the inline keyboard with buttons for an alert."""
        buttons = []
        links = self.config['links']
        
        if tv_url_template := links.get('tradingview_url'):
            buttons.append(InlineKeyboardButton("📈 View on TradingView", url=tv_url_template.format(symbol=symbol)))
        if info_url := links.get('signal_info_url'):
            buttons.append(InlineKeyboardButton("ℹ️ Signal Info", url=info_url))
            
        return InlineKeyboardMarkup([buttons]) if buttons else None

    def _format_header(self, r: AnalysisResult) -> str:
        return f"*{r.get('symbol')} Trend Alert* ({r.get('timeframe')})\n"

    def _format_analytics(self, r: AnalysisResult) -> str:
        consts = self.config['constants']
        return (
            f"🕒 Time: `{r.get('analysis_timestamp_utc', datetime.now().astimezone()).strftime('%Y-%m-%d %H:%M:%S %Z')}`\n"
            f"💲 Price: `${r.get('price', 0):,.4f}`\n"
            f"📊 RSI ({consts.get('rsi_period')}): `{r.get('rsi_val', 0):.2f}` ({r.get('rsi_interpretation', 'N/A')})\n"
            f"📉 ATR ({consts.get('atr_period')}): `{r.get('atr_value', 0):.4f}`\n"
            f"📉 EMAs:\n"
            f"  • Fast ({consts.get('ema_fast')}): `${r.get('ema_fast_val', 0):,.2f}`\n"
            f"  • Medium ({consts.get('ema_medium')}): `${r.get('ema_medium_val', 0):,.2f}`\n"
            f"  • Slow ({consts.get('ema_slow')}): `${r.get('ema_slow_val', 0):,.2f}`\n"
        )

    def _format_trade_levels(self, r: AnalysisResult, direction: str) -> str:
        entry_price = r.get('entry_price')
        if not entry_price or not direction:
            return ""
        trade_type_str = f"({direction})"
        levels = [
            f"{self.emojis.get('entry')} Entry Price: `${entry_price:,.4f}` {trade_type_str}",
            self._format_level("SL", r.get('stop_loss'), entry_price, self.emojis.get('sl'), direction),
            self._format_level("TP1", r.get('take_profit_1'), entry_price, self.emojis.get('tp'), direction),
            self._format_level("TP2", r.get('take_profit_2'), entry_price, self.emojis.get('tp'), direction),
            self._format_level("TP3", r.get('take_profit_3'), entry_price, self.emojis.get('tp'), direction),
            f"Leverage: x{self.leverage} (Margin)\n"
        ]
        return "\n".join(part for part in levels if part)

    def _format_projected_ranges(self, r: AnalysisResult, corrected_trend: str) -> str:
        price = r.get('price', 0)
        short_range = _get_range_str(r.get('proj_range_short_low', 0), r.get('proj_range_short_high', 0), price)
        long_range = _get_range_str(r.get('proj_range_long_low', 0), r.get('proj_range_long_high', 0), price)
        return (
            f"💡 Trend (4h): *{corrected_trend}* (Range: {short_range})\n"
            f"💡 Trend (8h): *{corrected_trend}* (Range: {long_range})"
        )

    def _format_alert_message(self, result: AnalysisResult) -> str:
        """Constructs the full alert message from smaller pieces."""
        direction, corrected_trend, _ = self._determine_trade_info(
            result.get('entry_price'), result.get('take_profit_1'), result.get('trend', 'N/A')
        )
        parts = [
            self._format_header(result),
            self._format_analytics(result),
            self._format_trade_levels(result, direction),
            self._format_projected_ranges(result, corrected_trend)
        ]
        return "\n".join(filter(None, parts))

    async def _send_no_signal_status_update(self, chat_id: str, thread_id: Optional[int], result: AnalysisResult):
        """Sends a simplified status update when no major signal is found."""
        symbol, timeframe = result.get('symbol', 'N/A'), result.get('timeframe', 'N/A')
        message = (
            f"⏳ *{symbol} Status Update* ({timeframe})\n\n"
            f"No significant signal change detected recently.\n\n"
            f"*Current Analytics:*\n"
            f"  • Price: `${result.get('price', 0):,.4f}`\n"
            f"  • RSI: `{result.get('rsi_val', 0):.2f}` ({result.get('rsi_interpretation', 'N/A')})\n\n"
            f"🕒 Time: `{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}`"
        )
        self.logger.info(f"Sending status update for {symbol}_{timeframe}.")
        await self.telegram_handler.send_telegram_notification(chat_id, message, message_thread_id=thread_id)
        self.last_notification_timestamp[f"{symbol}_{timeframe}"] = pd.Timestamp.now(tz='UTC')

    async def process_analysis_and_notify(self, chat_id: str, thread_id: Optional[int], result: AnalysisResult):
        """
        Main entry point to process an analysis result and send a Telegram alert if necessary.
        """
        if not self.telegram_handler.is_configured():
            self.logger.warning("Telegram handler not configured. Skipping notification.")
            return

        symbol, timeframe = result.get('symbol', 'N/A'), result.get('timeframe', 'N/A')
        symbol_key = f"{symbol}_{timeframe}"

        new_ranges = {
            "short_low": result.get("proj_range_short_low"),
            "short_high": result.get("proj_range_short_high"),
            "long_low": result.get("proj_range_long_low"),
            "long_high": result.get("proj_range_long_high")
        }

        if not self._should_send_alert(symbol_key, new_ranges):
            last_ts = self.last_notification_timestamp.get(symbol_key)
            if not last_ts or (pd.Timestamp.now(tz='UTC') - last_ts > self.status_interval):
                await self._send_no_signal_status_update(chat_id, thread_id, result)
            return

        message = self._format_alert_message(result)
        keyboard = self._create_alert_keyboard(symbol)

        await self.telegram_handler.send_telegram_notification(
            chat_id, message, message_thread_id=thread_id, reply_markup=keyboard
        )

        self.last_notified_ranges[symbol_key] = new_ranges
        self.last_notification_timestamp[symbol_key] = pd.Timestamp.now(tz='UTC')
        await asyncio.sleep(0.5)

