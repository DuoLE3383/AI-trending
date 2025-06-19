AI-Trending: Real-Time Crypto Market Analysis Bot
AI-Trending is an automated Python bot designed for real-time cryptocurrency market analysis using the Binance API. It continuously monitors specified trading pairs, calculates key technical indicators, identifies market trends, and delivers timely notifications directly to your Telegram.
The bot operates on a dual-loop system:
 * A high-frequency notification loop provides periodic market summaries.
 * A lower-frequency analysis loop performs deep analysis and sends immediate alerts when strong, actionable trends are detected.
Key Features
 * Real-Time Market Analysis: Connects directly to the Binance API to fetch the latest candle data.
 * Configurable Technical Indicators: Utilizes the pandas-ta library to calculate:
   * Exponential Moving Averages (EMA)
   * Relative Strength Index (RSI)
   * Bollinger Bands (BBands)
   * Average True Range (ATR) for volatility and projected price ranges.
 * Dual Notification System:
   * Strong Trend Alerts: Sends an immediate, detailed alert when a strong bullish or bearish trend is identified, including contrarian trade suggestions with Take Profit (TP) and Stop Loss (SL) levels.
   * Periodic Summaries: Delivers a concise summary of all monitored assets at a regular interval (e.g., every 10 minutes) to keep you informed of the general market state.
 * SQLite Database Logging: All analysis results are saved to a local SQLite database for persistence, review, and potential future backtesting.
 * Easy Configuration: All settings—including API keys, trading symbols, indicator parameters, and loop timings—are managed in a simple config.json file.
 * Built with asyncio: Leverages Python's asyncio for efficient, concurrent handling of the analysis and notification loops.
How It Works
The bot's architecture is designed for efficiency and responsiveness. It runs two main loops concurrently:
 * The Analysis Loop (Long Interval)
   * Runs on a longer, user-defined interval (e.g., every 1 hour).
   * Fetches a full set of historical data for each symbol from Binance.
   * Performs a comprehensive technical analysis.
   * Saves the detailed results to the trend_analysis.db database.
   * If a StrongBullish or StrongBearish trend is detected, it immediately triggers the send_individual_trend_alert_notification function.
 * The Notification Loop (Short Interval)
   * Runs on a shorter, user-defined interval (e.g., every 10 minutes).
   * Does not connect to the Binance API.
   * Queries the local trend_analysis.db to get the most recent analysis data saved by the other loop.
   * Formats this data into a quick summary and sends it using the send_periodic_summary_notification function.
This separation ensures that frequent updates can be sent without constantly hitting the Binance API, making the bot efficient and less prone to rate-limiting.
Sample Notifications
Strong Trend Alert
> This is sent immediately when the analysis loop detects a strong trend.
> 
✅ #StrongBullish Signal for BTCUSDT (Contrarian SHORT)
-----------------------------
Analysis (15m Timeframe)
  Price: $68,500.50
  EMA (34): $68,100.10
  EMA (89): $67,950.25
  EMA (200): $67,500.90
  RSI (14): 75.20 (Overbought)

Volatility (ATR 14)
  ATR: 150.45
  Proj. Range: $68,274.32 - $68,726.68

Contrarian SHORT Signal
  Entry: $68,500.50
  SL: $75,599.35 (10% above proj. high)
  TP1: $67,130.49 (-2%)
  TP2: $65,760.48 (-4%)
  TP3: $64,390.47 (-6%)

Periodic Market Summary
> This is sent every 10 minutes (or as configured) with the latest data from the database.
> 
📊 *Market Summary* (15m)
_________________________

*BTCUSDT*:
  `Price: $68,500.50    `
  `RSI:   75.2          `
  `Trend: ✅ #StrongBullish`

*ETHUSDT*:
  `Price: $3,805.15     `
  `RSI:   55.8          `
  `Trend: 📈 #Bullish`

<sub>Last Updated: 2025-06-19 08:42:00 UTC</sub>

Getting Started
Follow these steps to set up and run the bot.
1. Prerequisites
 * Python 3.10 or newer.
 * Git for cloning the repository.
2. Clone the Repository
git clone https://github.com/DuoLE3383/AI-trending.git
cd AI-trending

3. Create requirements.txt and Install Dependencies
Create a file named requirements.txt in the project directory and add the following content:
python-dotenv
pandas
pandas-ta
python-binance
aiohttp

Now, install these packages using pip:
pip install -r requirements.txt

4. Configure the Bot
All configuration is done in the config.json file. Rename the example file and edit it with your details.
a. Rename the config file:
# On Windows
rename config.json.example config.json

# On macOS/Linux
mv config.json.example config.json

b. Get Your API Keys and IDs:
 * Binance API Keys:
   * Log in to your Binance account.
   * Go to API Management and create a new API key.
   * Important: Ensure the key has permissions for "Enable Reading" and "Enable Futures" or "Enable Spot & Margin Trading" depending on your needs. For security, do not enable withdrawals.
 * Telegram Bot Token & Chat ID:
   * Talk to @BotFather on Telegram.
   * Create a new bot to get your Bot Token.
   * Talk to @userinfobot to get your personal Chat ID.
   * If sending to a group chat, add your bot to the group. Get the group ID by sending a message in the group and forwarding it to a bot like @RawDataBot. The group ID will start with a -.
c. Edit config.json:
Open config.json and fill in the placeholder values with your actual keys and preferences. See the Configuration Details section below for more information.
5. Run the Bot
Once configured, you can start the bot with the following command:
python realtime-trend.py

The bot will initialize, pre-load historical data, and start its concurrent analysis and notification loops. Press CTRL+C to stop the bot gracefully.
Configuration Details (config.json)
| Section | Key | Description |
|---|---|---|
| binance | api_key_placeholder | Your Binance API Key. |
|  | api_secret_placeholder | Your Binance API Secret. |
| trading | symbols | A list of crypto pairs to monitor (e.g., ["BTCUSDT", "ETHUSDT"]). |
|  | timeframe | The candle chart timeframe to analyze (e.g., 15m, 1h, 4h). |
|  | ema_fast, ema_medium, ema_slow | The periods for the three Exponential Moving Averages. |
|  | loop_sleep_interval_seconds | Analysis Loop: Interval in seconds between each full analysis (e.g., 3600 for 1 hour). |
|  | periodic_notification_interval_seconds | Notification Loop: Interval in seconds for sending the periodic summary (e.g., 600 for 10 mins). |
| sqlite | db_path | The file path for the SQLite database (e.g., "trend_analysis.db"). |
| telegram | bot_token_placeholder | Your Telegram Bot Token from BotFather. |
|  | chat_id_placeholder | The Telegram Chat ID where notifications will be sent. |
|  | message_thread_id_placeholder | (Optional) The Topic ID if you are sending to a group with topics enabled. Leave as placeholder otherwise. |
File Structure
.
├── config.json                 # Main configuration file for all settings.
├── config.json.example         # Example configuration file.
├── realtime-trend.py           # The main entry point and orchestrator for the bot.
├── notifications.py            # Contains functions for formatting and sending Telegram messages.
├── telegram_handler.py         # Handles the low-level communication with the Telegram API.
├── trend_evaluator.py          # A separate utility for evaluating past trends from the DB.
├── .env                        # (Optional) For storing environment variables like API keys.
└── README.md                   # This file.

Disclaimer
This project is for educational and informational purposes only. It is not financial advice. Cryptocurrency trading is inherently risky, and you should never trade with money you cannot afford to lose. The author is not responsible for any financial losses you may incur. Use this bot at your own risk.
License
This project is licensed under the MIT License. See the LICENSE file for details.
Made By Gemini Pro