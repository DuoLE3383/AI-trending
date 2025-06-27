# data_simulator.py
import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
import logging
import os 
import json # Import json to read config.json directly

from pairlistupdater import perform_single_pairlist_update, CONFIG_FILE_PATH as PAIRLIST_CONFIG_PATH

# Assume config.py exists in the same directory or is importable
import config
from binance import AsyncClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

async def fetch_klines(client, symbol, interval, start_str, end_str=None):
    """Fetches historical klines from Binance."""
    try:
        klines = await client.get_historical_klines(symbol, interval, start_str, end_str)
        # Convert klines to a more usable format (list of dicts)
        parsed_klines = []
        for kline in klines:
            parsed_klines.append({
                'open_time': datetime.fromtimestamp(kline[0] / 1000),
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5]),
                'close_time': datetime.fromtimestamp(kline[6] / 1000)
            })
        return parsed_klines
    except Exception as e:
        logger.error(f"Error fetching klines for {symbol}: {e}")
        return []

async def simulate_trade_data(client: AsyncClient, db_path: str, all_symbols: list, num_trades_per_symbol: int = 3, lookback_days: int = 90):
    """
    Simulates historical trade data and inserts it into the trend_analysis table.
    This function will clear existing data in trend_analysis before inserting new.
    """
    logger.info(f"Starting trade data simulation for {num_trades_per_symbol} trades per symbol over {lookback_days} days.")
    
    # all_symbols is now passed as an argument, reflecting the latest from config.json
    num_symbols_to_simulate = 100  # Default to 100 symbols if available  

    if len(all_symbols) > num_symbols_to_simulate:
        symbols_to_simulate = random.sample(all_symbols, num_symbols_to_simulate)
    else:
        symbols_to_simulate = all_symbols
        
    logger.info(f"Will simulate data for {len(symbols_to_simulate)} symbols: {symbols_to_simulate}")

    # Clear existing data to ensure a fresh start for simulation
    try:
        with get_db_connection(db_path) as conn:
            conn.execute("DELETE FROM trend_analysis")
            conn.commit()
        logger.info("Cleared existing data from 'trend_analysis' table.")
    except Exception as e:
        logger.error(f"Error clearing 'trend_analysis' table: {e}")
        return

    for symbol in symbols_to_simulate:
        logger.info(f"Simulating trades for {symbol}...")
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        klines = await fetch_klines(client, symbol, config.TIMEFRAME, 
                                    start_date.strftime('%d %b %Y %H:%M:%S'), 
                                    end_date.strftime('%d %b %Y %H:%M:%S'))
        
        if not klines:
            logger.warning(f"No klines fetched for {symbol}. Skipping simulation for this symbol.")
            continue

        # Simple strategy: simulate a trade every N candles
        candles_per_trade = len(klines) // num_trades_per_symbol
        if candles_per_trade < 1:
            candles_per_trade = 1 # Ensure at least one trade if not enough klines

        trade_counter = 0
        for i in range(0, len(klines) - 5, candles_per_trade): # Ensure enough candles for outcome
            if trade_counter >= num_trades_per_symbol:
                break

            entry_kline = klines[i]
            entry_price = entry_kline['close']
            
            # Randomly choose trend
            trend = random.choice(['BULLISH', 'BEARISH'])
            
            # Định nghĩa SL/TP dựa trên các phần trăm yêu cầu
            sl_factor = 0.025 # 2.5%
            tp1_factor = 0.028 # 2.8%
            tp2_factor = 0.036 # 3.6%
            tp3_factor = 0.049 # 4.9%
            
            if trend == 'BULLISH':
                stop_loss = entry_price * (1 - sl_factor)
                take_profit_1 = entry_price * (1 + tp1_factor)
                take_profit_2 = entry_price * (1 + tp2_factor)
                take_profit_3 = entry_price * (1 + tp3_factor)
            else: # BEARISH
                stop_loss = entry_price * (1 + sl_factor)
                take_profit_1 = entry_price * (1 - tp1_factor)
                take_profit_2 = entry_price * (1 - tp2_factor)
                take_profit_3 = entry_price * (1 - tp3_factor)

            # Mô phỏng kết quả trong vài nến tiếp theo, kiểm tra tất cả các TP
            exit_price = None
            status = 'ACTIVE'
            
            for j in range(i + 1, min(i + 6, len(klines))): # Check next 5 candles
                outcome_kline = klines[j]
                sl_hit = False
                tp_hit = False
                exit_price_candidate = None
                status_candidate = None
                
                if trend == 'BULLISH':
                    # Luôn kiểm tra SL trước (giả định thận trọng)
                    if outcome_kline['low'] <= stop_loss:
                        sl_hit = True
                    
                    # Sau đó kiểm tra các mức TP
                    if outcome_kline['high'] >= take_profit_3:
                        tp_hit = True
                        exit_price_candidate = take_profit_3
                        status_candidate = 'TP3'
                    elif outcome_kline['high'] >= take_profit_2:
                        tp_hit = True
                        exit_price_candidate = take_profit_2
                        status_candidate = 'TP2'
                    elif outcome_kline['high'] >= take_profit_1:
                        tp_hit = True
                        exit_price_candidate = take_profit_1
                        status_candidate = 'TP1'
                else: # BEARISH
                    if outcome_kline['high'] >= stop_loss:
                        sl_hit = True

                    if outcome_kline['low'] <= take_profit_3:
                        tp_hit = True
                        exit_price_candidate = take_profit_3
                        status_candidate = 'TP3'
                    elif outcome_kline['low'] <= take_profit_2:
                        tp_hit = True
                        exit_price_candidate = take_profit_2
                        status_candidate = 'TP2'
                    elif outcome_kline['low'] <= take_profit_1:
                        tp_hit = True
                        exit_price_candidate = take_profit_1
                        status_candidate = 'TP1'
                
                # Ưu tiên SL nếu cả hai cùng bị chạm trong một nến
                if sl_hit:
                    exit_price = stop_loss
                    status = 'SL'
                    break
                elif tp_hit:
                    exit_price = exit_price_candidate
                    status = status_candidate
                    break
            
            # If no SL/TP hit within 5 candles, close manually at last candle's close
            if status == 'ACTIVE':
                exit_price = klines[min(i + 360, len(klines) - 60)]['close']
                status = 'CLOSED_MANUALLY (OUT OF TIME)' # Standardize status for clarity
            pnl_percentage = None
            pnl_with_leverage = None
            if exit_price is not None:
                try:
                    pnl = ((exit_price - entry_price) / entry_price) * 100
                    if trend == 'BEARISH': # Đảo ngược PnL cho lệnh short (nhân với -1)
                        pnl *= -1 # Đã sửa: Chỉ nên nhân với -1 để đảo dấu
                    # For BULLISH trades, the initial 'pnl' calculation is already correct.
                    pnl_percentage = pnl
                    pnl_with_leverage = pnl * config.LEVERAGE # Assuming LEVERAGE is in config
                except (TypeError, ZeroDivisionError):
                    logger.warning(f"Could not calculate PnL for {symbol} trade at {entry_kline['open_time']}.")
            # Insert into DB
            try:
                with get_db_connection(db_path) as conn:
                    conn.execute("""
                        INSERT INTO trend_analysis (
                            symbol, analysis_timestamp_utc, trend, entry_price,
                            stop_loss, take_profit_1, take_profit_2, take_profit_3, exit_price, status,
                            pnl_percentage, pnl_with_leverage
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, 
                        entry_kline['open_time'].isoformat(), 
                        trend, 
                        entry_price, 
                        stop_loss, 
                        take_profit_1,
                        take_profit_2,
                        take_profit_3,
                        exit_price, 
                        status, 
                        pnl_percentage, 
                        pnl_with_leverage
                    ))
                    conn.commit()
                trade_counter += 1
            except Exception as e:
                logger.error(f"Error inserting simulated trade for {symbol}: {e}")
        logger.info(f"Finished simulating {trade_counter} trades for {symbol}.")

async def main():
    logger.info("Initializing data simulation...")
    client = None
    try:
        client = await AsyncClient.create(config.API_KEY, config.API_SECRET)
        
        # Step 1: Run pairlist updater to ensure config.json is up-to-date
        logger.info("Running pairlist updater to get the latest symbols...")
        updated_symbols = await perform_single_pairlist_update()
        
        # Step 2: Load the updated config.json to get the latest symbols and other settings
        # This is crucial because `import config` at the top only loads it once.
        try:
            with open(PAIRLIST_CONFIG_PATH, 'r') as f:
                current_config_data = json.load(f)
            # Ensure config.trading.symbols is updated for simulate_trade_data
            # and other config values are accessible if needed.
            # For this specific case, we only need the symbols list.
            # If config.py is designed to be reloaded, that would be another approach.
            # For now, we pass the symbols directly.
            latest_all_symbols = current_config_data.get('trading', {}).get('symbols', [])
            if not latest_all_symbols:
                logger.warning("No symbols found in updated config.json. Using default or empty list.")
                # Fallback to config.py's symbols if config.json is empty or malformed
                latest_all_symbols = config.trading.symbols if hasattr(config, 'trading') and hasattr(config.trading, 'symbols') else []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config.json after pairlist update: {e}. Using symbols from initial config import.")
            latest_all_symbols = config.trading.symbols if hasattr(config, 'trading') and hasattr(config.trading, 'symbols') else []

        await simulate_trade_data(client, config.SQLITE_DB_PATH, latest_all_symbols) # Pass the updated symbols
        logger.info("Data simulation complete. You can now run the bot.")
    except Exception as e:
        logger.critical(f"A critical error occurred during data simulation: {e}", exc_info=True)
    finally:
        if client:
            await client.close_connection()
            logger.info("Binance client connection closed.")

if __name__ == "__main__":
    # Ensure the database file exists and table is created if not
    try:
        with get_db_connection(config.SQLITE_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trend_analysis (
                    symbol TEXT NOT NULL,
                    analysis_timestamp_utc TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    take_profit_3 REAL,
                    exit_price REAL,
                    status TEXT NOT NULL,
                    pnl_percentage REAL,
                    pnl_with_leverage REAL
                );
            """)
            conn.commit()
        logger.info(f"Database '{config.SQLITE_DB_PATH}' and 'trend_analysis' table ensured.")
    except Exception as e:
        logger.critical(f"Error ensuring database/table existence: {e}")
        exit(1) # Exit if DB cannot be prepared

    asyncio.run(main())