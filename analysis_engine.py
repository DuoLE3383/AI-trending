# # analysis_engine.py
# import pandas as pd
# import pandas_ta as ta 
# import sqlite3
# import logging
# from typing import Dict, Any

# # Import a_variables from config.py
# from config import *
# # Import data retrieval function
# from market_data_handler import get_market_data
# # Import AsyncClient for correct type hinting
# from binance import AsyncClient

# logger = logging.getLogger(__name__)

# def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
#     """
#     Private function to save a signal to the SQLite database.
#     Separating this logic keeps the main function cleaner.
#     """
#     sql_insert = """
#     INSERT INTO trend_analysis (
#         analysis_timestamp_utc, symbol, timeframe, last_price,timestamp_utc
#         ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val,
#         rsi_len, rsi_val, trend, kline_open_time,
#         bbands_lower, bbands_middle, bbands_upper, atr_val,
#         entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status
#     ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
#     """
    
#     db_values = (
#         signal_data['analysis_time'], signal_data['symbol'], signal_data['timeframe'], signal_data['price'],
#         signal_data['ema_fast_len'], signal_data['ema_fast_val'], signal_data['ema_medium_len'], signal_data['ema_medium_val'], signal_data['ema_slow_len'], signal_data['ema_slow_val'],
#         signal_data['rsi_len'], signal_data['rsi_val'], signal_data['trend'], signal_data['kline_time'],
#         signal_data['bb_lower'], signal_data['bb_middle'], signal_data['bb_upper'], signal_data['atr'],
#         signal_data['entry'], signal_data['sl'], signal_data['tp1'], signal_data['tp2'], signal_data['tp3'], 'ACTIVE'
#     )

#     try:
#         with sqlite3.connect(SQLITE_DB_PATH) as conn:
#             conn.execute(sql_insert, db_values)
#         logger.info(f"✅ Strong Signal Saved for {signal_data['symbol']}: Trend={signal_data['trend']}")
#     except sqlite3.Error as e:
#         logger.error(f"❌ Error saving analysis for {signal_data['symbol']} to DB: {e}", exc_info=True)

# def _perform_analysis(df: pd.DataFrame, symbol: str) -> None:
#     """
#     Performs technical analysis on a given DataFrame.
#     This is the core processing logic, with no network or I/O operations.
#     """
#     # if df.empty or len(df) < EMA_SLOW:
#     #     logger.warning(f"Skipping analysis for {symbol}: not enough data points ({len(df)} rows).")
#     #     return

#     # --- 1. Calculate technical indicators ---
#     df.ta.ema(length=EMA_FAST, append=True)
#     df.ta.ema(length=EMA_MEDIUM, append=True)
#     df.ta.ema(length=EMA_SLOW, append=True)
#     df.ta.rsi(length=RSI_PERIOD, append=True)
#     df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
#     df.ta.atr(length=ATR_PERIOD, append=True)
#     df.ta.sma(length=VOLUME_SMA_PERIOD, close='volume', prefix='VOLUME', append=True)

#     last = df.iloc[-1]
#     price = last.get('close')
#     if price is None:
#         logger.error(f"Could not get 'close' price for {symbol}.")
#         return

#     # --- 2. Apply strategy filters ---
#     atr_value = last.get(f'ATRr_{ATR_PERIOD}')
#     # ROBUSTNESS: Ensure atr_value is not None before using it
#     if atr_value is None:
#         logger.warning(f"Skipping analysis for {symbol}: ATR value is None.")
#         return
        
#     atr_percent = (atr_value / price) * 100 if price > 0 else 0
#     # if atr_percent < MIN_ATR_PERCENT:
#     #     # logger.info(f"{symbol}: Skipping. Low volatility (ATR: {atr_percent:.2f}%).")
#     #     return

#     current_volume = last.get('volume')
#     volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
#     # if current_volume is None or volume_sma is None or current_volume < (volume_sma * MIN_VOLUME_RATIO):
#     #     logger.info(f"{symbol}: Skipping. Low volume (Current: {current_volume} < SMA: {volume_sma}).")
#     #     return

#     # --- 3. Trend determination logic ---
#     ema_f = last.get(f'EMA_{EMA_FAST}')
#     ema_m = last.get(f'EMA_{EMA_MEDIUM}')
#     ema_s = last.get(f'EMA_{EMA_SLOW}')
#     trend = TREND_SIDEWAYS
    
#     # ROBUSTNESS: Ensure EMA values exist before comparing them to prevent TypeError
#     if any(v is None for v in [price, ema_f, ema_m, ema_s]):
#         logger.warning(f"Skipping trend analysis for {symbol}: One or more EMA values are None.")
#         return

#     # Trend conditions
#     if price > ema_f > ema_m > ema_s:
#         trend = TREND_STRONG_BULLISH
#     elif price < ema_f < ema_m < ema_s:
#         trend = TREND_STRONG_BEARISH
#     elif price > ema_s and ema_f > ema_m:
#         trend = TREND_BULLISH
#     elif price < ema_s and ema_f < ema_m:
#         trend = TREND_BEARISH
    
#     # --- 4. Calculate Entry/SL/TP and Save if a strong signal is found ---
#     if trend.startswith("STRONG"):
#         entry = price
#         if trend == TREND_STRONG_BULLISH:
#             sl = entry - (atr_value * ATR_MULTIPLIER_SL)
#             tp1 = entry + (atr_value * ATR_MULTIPLIER_TP1)
#             tp2 = entry + (atr_value * ATR_MULTIPLIER_TP2)
#             tp3 = entry + (atr_value * ATR_MULTIPLIER_TP3)
#         else:  # TREND_STRONG_BEARISH
#             sl = entry + (atr_value * ATR_MULTIPLIER_SL)
#             tp1 = entry - (atr_value * ATR_MULTIPLIER_TP1)
#             tp2 = entry - (atr_value * ATR_MULTIPLIER_TP2)
#             tp3 = entry - (atr_value * ATR_MULTIPLIER_TP3)

#         signal_data = {
#             "analysis_time": pd.to_datetime('now', utc=True).isoformat(),
#             "symbol": symbol, "timeframe": TIMEFRAME, "price": price,
#             "ema_fast_len": EMA_FAST, "ema_fast_val": ema_f,
#             "ema_medium_len": EMA_MEDIUM, "ema_medium_val": ema_m,
#             "ema_slow_len": EMA_SLOW, "ema_slow_val": ema_s,
#             "rsi_len": RSI_PERIOD, "rsi_val": last.get(f'RSI_{RSI_PERIOD}'),
#             "trend": trend, "kline_time": last.name.isoformat(),
#             "bb_lower": last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
#             "bb_middle": last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
#             "bb_upper": last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
#             "atr": atr_value, "entry": entry, "sl": sl,
#             "tp1": tp1, "tp2": tp2, "tp3": tp3
#         }
#         _save_signal_to_db(signal_data)
#     else:
#         logger.info(f"{symbol}: Analysis complete. Trend is '{trend}', no strong signal generated.")
# # Hypothetical /Users/duongle/aitrending/AI-trending/analysis_engine.py (or similar)
# import config

# def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
#     # Existing indicators
#     df['EMA_FAST'] = ta.trend.ema_indicator(df['close'], window=config.EMA_FAST)
#     df['EMA_MEDIUM'] = ta.trend.ema_indicator(df['close'], window=config.EMA_MEDIUM)
#     df['EMA_SLOW'] = ta.trend.ema_indicator(df['close'], window=config.EMA_SLOW)
#     df['RSI'] = ta.momentum.rsi(df['close'], window=config.RSI_PERIOD)
#     df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = ta.volatility.bollinger_bands(
#         df['close'], window=config.BBANDS_PERIOD, window_dev=config.BBANDS_STD_DEV
#     )
#     df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=config.ATR_PERIOD)
#     df['VOLUME_SMA'] = ta.volume.volume_sma(df['volume'], window=config.VOLUME_SMA_PERIOD)

#     # --- Add new indicators ---
#     # MACD
#     df['MACD'] = ta.trend.macd(df['close'], window_fast=config.MACD_FAST_PERIOD,
#                                window_slow=config.MACD_SLOW_PERIOD,
#                                fillna=True)
#     df['MACD_Signal'] = ta.trend.macd_signal(df['close'], window_fast=config.MACD_FAST_PERIOD,
#                                             window_slow=config.MACD_SLOW_PERIOD,
#                                             window_sign=config.MACD_SIGNAL_PERIOD,
#                                             fillna=True)
#     df['MACD_Hist'] = ta.trend.macd_diff(df['close'], window_fast=config.MACD_FAST_PERIOD,
#                                          window_slow=config.MACD_SLOW_PERIOD,
#                                          window_sign=config.MACD_SIGNAL_PERIOD,
#                                          fillna=True)

#     # ADX
#     df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=config.ADX_PERIOD, fillna=True)
#     df['ADX_POS'] = ta.trend.adx_pos(df['high'], df['low'], df['close'], window=config.ADX_PERIOD, fillna=True)
#     df['ADX_NEG'] = ta.trend.adx_neg(df['high'], df['low'], df['close'], window=config.ADX_PERIOD, fillna=True)

#     return df

# # Ví dụ về cách sử dụng chỉ báo mới trong logic tạo tín hiệu
# # (Đây chỉ là một đoạn mã minh họa, bạn cần tích hợp vào logic hiện có của mình)
# def generate_signal_with_new_indicators(df: pd.DataFrame, current_trend: str) -> Dict[str, Any]:
#     # Đảm bảo các chỉ báo đã được tính toán trong df
#     if df.empty or 'MACD' not in df.columns or 'ADX' not in df.columns:
#         return {} # Hoặc xử lý lỗi

#     # Lấy giá trị chỉ báo mới nhất
#     last_macd = df['MACD'].iloc[-1]
#     last_macd_signal = df['MACD_Signal'].iloc[-1]
#     last_adx = df['ADX'].iloc[-1]

#     # Logic tạo tín hiệu được cải thiện
#     signal_details = {}

#     if current_trend == config.TREND_STRONG_BULLISH:
#         # Thêm điều kiện MACD cắt lên đường tín hiệu và ADX xác nhận xu hướng mạnh
#         if (last_macd > last_macd_signal and df['MACD'].iloc[-2] <= df['MACD_Signal'].iloc[-2]) and \
#            (last_adx > config.ADX_MIN_TREND_STRENGTH):
#             # Đây là điểm vào lệnh tiềm năng
#             # ... tính toán entry_price, stop_loss, take_profits dựa trên các chỉ báo khác
#             # Ví dụ:
#             # signal_details = {
#             #     'symbol': df['symbol'].iloc[-1],
#             #     'trend': current_trend,
#             #     'entry_price': df['close'].iloc[-1],
#             #     'stop_loss': df['close'].iloc[-1] - config.ATR_MULTIPLIER_SL * df['ATR'].iloc[-1],
#             #     'take_profit_1': df['close'].iloc[-1] + config.ATR_MULTIPLIER_TP1 * df['ATR'].iloc[-1],
#             #     # ...
#             # }
#             pass
#     elif current_trend == config.TREND_STRONG_BEARISH:
#         # Thêm điều kiện MACD cắt xuống đường tín hiệu và ADX xác nhận xu hướng mạnh
#         if (last_macd < last_macd_signal and df['MACD'].iloc[-2] >= df['MACD_Signal'].iloc[-2]) and \
#            (last_adx > config.ADX_MIN_TREND_STRENGTH):
#             # Đây là điểm vào lệnh tiềm năng
#             # ... tính toán entry_price, stop_loss, take_profits
#             pass

#     return signal_details


# async def process_symbol(client: AsyncClient, symbol: str) -> None:
#     """
#     Entry-point function: Fetches market data for a symbol and then performs analysis.
#     This function will be called from run.py.
#     """
#     try:
#         # Step 1: Get data and create DataFrame
#         df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        
#         # Step 2: Call the core analysis function with the DataFrame
#         if df is not None:
#              _perform_analysis(df, symbol)
#         else:
#             logger.warning(f"Did not perform analysis for {symbol} because no data was returned.")

#     except Exception as e:
#         logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {e}", exc_info=True)
# analysis_engine.py (Phiên bản cuối cùng, tích hợp AI, MACD, ADX)
import pandas as pd
import pandas_ta as ta 
import sqlite3
import logging
from typing import Dict, Any, List

# Import các type hint cho model
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# Import các biến từ config.py
from config import *
# Import hàm lấy dữ liệu
from market_data_handler import get_market_data
# Import AsyncClient để gợi ý type hint
from binance import AsyncClient

logger = logging.getLogger(__name__)

def _save_signal_to_db(signal_data: Dict[str, Any]) -> None:
    """
    Lưu tín hiệu vào database SQLite.
    Đã được cập nhật để lưu tất cả các cột cần thiết, bao gồm cả chỉ báo mới.
    """
    # SỬA LỖI & CẢI THIỆN: Câu lệnh SQL đã được sửa cú pháp và thêm các cột mới
    sql_insert = """
    INSERT INTO trend_analysis (
        analysis_timestamp_utc, symbol, timeframe, last_price, timestamp_utc,
        ema_fast_len, ema_fast_val, ema_medium_len, ema_medium_val, ema_slow_len, ema_slow_val,
        rsi_len, rsi_val, trend, kline_open_time,
        bbands_lower, bbands_middle, bbands_upper, atr_val,
        macd, macd_signal, macd_hist, adx,
        entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3, status
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    
    # SỬA LỖI & CẢI THIỆN: Cung cấp đầy đủ giá trị cho tất cả các cột
    db_values = (
        signal_data.get('analysis_time'), signal_data.get('symbol'), signal_data.get('timeframe'), signal_data.get('price'),
        signal_data.get('kline_timestamp'),
        signal_data.get('ema_fast_len'), signal_data.get('ema_fast_val'), signal_data.get('ema_medium_len'), signal_data.get('ema_medium_val'), signal_data.get('ema_slow_len'), signal_data.get('ema_slow_val'),
        signal_data.get('rsi_len'), signal_data.get('rsi_val'), signal_data.get('trend'), signal_data.get('kline_time'),
        signal_data.get('bb_lower'), signal_data.get('bb_middle'), signal_data.get('bb_upper'), signal_data.get('atr'),
        signal_data.get('macd'), signal_data.get('macd_signal'), signal_data.get('macd_hist'), signal_data.get('adx'),
        signal_data.get('entry'), signal_data.get('sl'), signal_data.get('tp1'), signal_data.get('tp2'), signal_data.get('tp3'), 'ACTIVE'
    )

    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            conn.execute(sql_insert, db_values)
        logger.info(f"✅ High-Quality AI Signal Saved for {signal_data['symbol']}: Trend={signal_data['trend']}")
    except sqlite3.Error as e:
        logger.error(f"❌ Error saving analysis for {signal_data['symbol']} to DB: {e}", exc_info=True)


def _perform_analysis(
    df: pd.DataFrame, 
    symbol: str, 
    model: RandomForestClassifier, 
    label_encoder: LabelEncoder,
    model_features: List[str]
) -> None:
    """
    Thực hiện phân tích kỹ thuật, dùng model ML dự đoán và bộ lọc xác nhận.
    """
    if df.empty or len(df) < MACD_SLOW_PERIOD: # Cần đủ dữ liệu để tính các chỉ báo
        return

    # --- 1. Tính toán tất cả các chỉ báo kỹ thuật bằng pandas-ta ---
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_MEDIUM, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)
    df.ta.rsi(length=RSI_PERIOD, append=True)
    df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STD_DEV, append=True)
    df.ta.atr(length=ATR_PERIOD, append=True)
    df.ta.sma(length=VOLUME_SMA_PERIOD, close='volume', prefix='VOLUME', append=True)
    df.ta.macd(fast=MACD_FAST_PERIOD, slow=MACD_SLOW_PERIOD, signal=MACD_SIGNAL_PERIOD, append=True)
    df.ta.adx(length=ADX_PERIOD, append=True)
    
    last = df.iloc[-1]
    last_but_one = df.iloc[-2]
    price = last.get('close')
    if price is None: return

    # --- 2. Áp dụng các bộ lọc cơ bản (ATR, Volume) ---
    atr_value = last.get(f'ATRr_{ATR_PERIOD}')
    if atr_value is None or atr_value == 0: return
    if (atr_value / price) * 100 < MIN_ATR_PERCENT: return
    current_volume = last.get('volume')
    volume_sma = last.get(f'VOLUME_SMA_{VOLUME_SMA_PERIOD}')
    if current_volume is None or volume_sma is None or current_volume < (volume_sma * MIN_VOLUME_RATIO): return

    # --- 3. DÙNG MODEL AI ĐỂ DỰ ĐOÁN TREND ---
    features_for_prediction = [last.get(feature_name) for feature_name in model_features]
    if any(v is None for v in features_for_prediction): return

    prediction_encoded = model.predict([features_for_prediction])
    predicted_trend = label_encoder.inverse_transform(prediction_encoded)[0]
    
    # --- 4. KIỂM TRA XÁC NHẬN VỚI MACD & ADX ---
    if predicted_trend in [TREND_STRONG_BULLISH, TREND_STRONG_BEARISH]:
        macd = last.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}')
        macd_signal = last.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}')
        adx = last.get(f'ADX_{ADX_PERIOD}')
        
        is_confirmed = False
        if predicted_trend == TREND_STRONG_BULLISH and adx is not None and adx > ADX_MIN_TREND_STRENGTH:
            # Check MACD vừa cắt lên trên đường signal
            if macd > macd_signal and last_but_one.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}') <= last_but_one.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'):
                is_confirmed = True
        elif predicted_trend == TREND_STRONG_BEARISH and adx is not None and adx > ADX_MIN_TREND_STRENGTH:
            # Check MACD vừa cắt xuống dưới đường signal
            if macd < macd_signal and last_but_one.get(f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}') >= last_but_one.get(f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'):
                is_confirmed = True

        if not is_confirmed:
            logger.info(f"{symbol}: AI predicted '{predicted_trend}', but confirmation (MACD/ADX) failed.")
            return

        # --- 5. TÍNH TOÁN ENTRY/SL/TP VÀ LƯU TÍN HIỆU CHẤT LƯỢNG CAO ---
        entry = price
        if predicted_trend == TREND_STRONG_BULLISH:
            sl = entry - (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry + (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry + (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry + (atr_value * ATR_MULTIPLIER_TP3)
        else: # TREND_STRONG_BEARISH
            sl = entry + (atr_value * ATR_MULTIPLIER_SL)
            tp1 = entry - (atr_value * ATR_MULTIPLIER_TP1)
            tp2 = entry - (atr_value * ATR_MULTIPLIER_TP2)
            tp3 = entry - (atr_value * ATR_MULTIPLIER_TP3)

        signal_data = {
            "analysis_time": pd.to_datetime('now', utc=True).isoformat(), "symbol": symbol, "timeframe": TIMEFRAME, "price": price,
            "kline_time": last.name.isoformat(), "kline_timestamp": last.name.timestamp(),
            "ema_fast_len": EMA_FAST, "ema_fast_val": last.get(f'EMA_{EMA_FAST}'),
            "ema_medium_len": MEDIUM, "ema_medium_val": last.get(f'EMA_{MEDIUM}'),
            "ema_slow_len": EMA_SLOW, "ema_slow_val": last.get(f'EMA_{EMA_SLOW}'),
            "rsi_len": RSI_PERIOD, "rsi_val": last.get(f'RSI_{RSI_PERIOD}'),
            "trend": predicted_trend,
            "bb_lower": last.get(f'BBL_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_middle": last.get(f'BBM_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'), "bb_upper": last.get(f'BBU_{BBANDS_PERIOD}_{BBANDS_STD_DEV}'),
            "atr": atr_value, "macd": macd, "macd_signal": macd_signal, "macd_hist": last.get(f'MACDh_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}'), "adx": adx,
            "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3
        }
        _save_signal_to_db(signal_data)
    else:
        logger.info(f"{symbol}: AI analysis complete. Predicted trend is '{predicted_trend}', no strong signal generated.")

async def process_symbol(
    client: AsyncClient, 
    symbol: str, 
    model: RandomForestClassifier, 
    label_encoder: LabelEncoder,
    model_features: List[str]
) -> None:
    """Hàm đầu vào: Lấy dữ liệu và thực hiện phân tích bằng AI."""
    try:
        df = await get_market_data(client, symbol, TIMEFRAME, limit=500)
        
        if df is not None and not df.empty:
             _perform_analysis(df, symbol, model, label_encoder, model_features)
    except Exception as e:
        logger.error(f"❌ FAILED TO PROCESS SYMBOL: {symbol}. Error: {e}", exc_info=True)
