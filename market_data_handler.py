# market_data_handler.py (Phiên bản có thêm log DEBUG chi tiết)
import pandas as pd
from binance import AsyncClient as Client
import logging

logger = logging.getLogger(__name__)

async def get_market_data(client: Client, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """
    Lấy dữ liệu nến từ Binance và chuyển thành Pandas DataFrame.
    """
    try:
        # === LOG DEBUG MỚI THÊM VÀO ===
        logger.info(f"--- [DEBUG] Sending API request for symbol='{symbol}', interval='{timeframe}', limit={limit}")
        # ================================

        klines = await client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
        
        # === LOG DEBUG MỚI THÊM VÀO ===
        logger.info(f"--- [DEBUG] Received raw API response for {symbol}. Number of klines (rows) = {len(klines)}")
        if not klines:
            logger.warning(f"--- [DEBUG] Binance API returned an EMPTY list for {symbol}. This almost always points to an API key permission issue on the Binance website.")
        # ================================

        if not klines:
            return pd.DataFrame()

        columns = [
            'kline_open_time', 'open', 'high', 'low', 'close', 'volume',
            'kline_close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
        df = pd.DataFrame(klines, columns=columns)
        
        df['kline_open_time'] = pd.to_datetime(df['kline_open_time'], unit='ms', utc=True)
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.set_index('kline_open_time', inplace=True)
        
        return df

    except Exception as e:
        logger.error(f"Error inside get_market_data for {symbol}: {e}", exc_info=True)
        return pd.DataFrame()

