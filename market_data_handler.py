# market_data_handler.py - PHIÊN BẢN ĐÃ SỬA
import pandas as pd
from binance.client import Client
import logging

logger = logging.getLogger(__name__)

# 1. THÊM `limit: int` vào danh sách tham số của hàm
async def get_market_data(client: Client, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """
    Lấy dữ liệu nến từ Binance và chuyển thành Pandas DataFrame.
    """
    try:
        # 2. SỬ DỤNG tham số 'limit' được truyền vào thay vì một số cố định
        klines = await client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
        
        # Định nghĩa các cột cho DataFrame
        columns = [
            'kline_open_time', 'open', 'high', 'low', 'close', 'volume',
            'kline_close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
        
        df = pd.DataFrame(klines, columns=columns)
        
        # Chuyển đổi kiểu dữ liệu cho các cột cần thiết
        df['kline_open_time'] = pd.to_datetime(df['kline_open_time'], unit='ms', utc=True)
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Đặt kline_open_time làm index
        df.set_index('kline_open_time', inplace=True)
        
        return df

    except Exception as e:
        logger.error(f"Error fetching market data for {symbol}: {e}")
        # Trả về một DataFrame rỗng nếu có lỗi
        return pd.DataFrame()
