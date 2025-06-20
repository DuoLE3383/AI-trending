import pandas as pd
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from typing import Set

# Import specific config variables needed by these functions
from config import TIMEFRAME, EMA_SLOW, ANALYSIS_CANDLE_BUFFER, DYN_SYMBOLS_QUOTE_ASSET, DYN_SYMBOLS_EXCLUDE

logger = logging.getLogger(__name__)

def get_market_data(binance_client: Client, symbol: str) -> pd.DataFrame:
    """Fetches and prepares market data for a single symbol."""
    if not binance_client:
        logger.error("Binance client not initialized. Cannot fetch market data.")
        return pd.DataFrame()

    required_candles = EMA_SLOW + ANALYSIS_CANDLE_BUFFER
    limit = min(required_candles, 1000)

    try:
        klines = binance_client.get_historical_klines(symbol, TIMEFRAME, limit=limit)
        if not klines:
            logger.warning(f"No klines data received for {symbol} with limit {limit}.")
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        if len(df) < EMA_SLOW:
            logger.warning(f"Not enough data for {symbol} ({len(df)} candles) to calculate all EMAs (need {EMA_SLOW}).")
            return pd.DataFrame()

        return df

    except (BinanceAPIException, BinanceRequestException) as e:
        logger.error(f"Binance error fetching data for {symbol}: {e}")
    except Exception:
        logger.error(f"An unexpected error occurred while fetching market data for {symbol}", exc_info=True)
    return pd.DataFrame()

def fetch_and_filter_binance_symbols(binance_client: Client) -> Set[str]:
    """Fetches and filters symbols from Binance based on config."""
    if not binance_client:
        logger.error("Binance client not initialized. Cannot fetch symbols.")
        return set()
    logger.info(f"Fetching symbols for quote asset: {DYN_SYMBOLS_QUOTE_ASSET}")
    try:
        exchange_info = binance_client.get_exchange_info()
        all_symbols = {s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING'}
        filtered_by_quote = {s for s in all_symbols if s.endswith(DYN_SYMBOLS_QUOTE_ASSET)}
        final_symbols = {s for s in filtered_by_quote if not any(ex in s for ex in DYN_SYMBOLS_EXCLUDE)}
        logger.info(f"Found {len(final_symbols)} symbols to monitor (after filtering).")
        return final_symbols
    except Exception:
        logger.error(f"Failed to fetch or filter symbols from Binance", exc_info=True)
        return set()