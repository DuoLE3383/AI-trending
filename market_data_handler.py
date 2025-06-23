# market_data_handler.py
import pandas as pd
from binance.client import Client
import logging
import config

logger = logging.getLogger(__name__)

def get_market_data(client: Client, symbol: str, kline_limit: int = 200) -> pd.DataFrame:
    try:
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=kline_limit)
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Chuyển đổi kiểu dữ liệu
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logger.error(f"Failed to fetch market data for {symbol}: {e}")
        return pd.DataFrame()

def fetch_and_filter_binance_symbols(client: Client) -> set:
    try:
        exchange_info = client.get_exchange_info()
        symbols = {
            s['symbol'] for s in exchange_info['symbols']
            if s['status'] == 'TRADING' and s['symbol'].endswith('USDT') and 'UP' not in s['symbol'] and 'DOWN' not in s['symbol']
        }
        return symbols
    except Exception as e:
        logger.error(f"Failed to fetch and filter Binance symbols: {e}")
        return set()
