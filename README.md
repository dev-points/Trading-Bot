
📌 Overview
This project is an automated cryptocurrency trading bot for the **MEXC exchange**.  
It uses **RSI (Relative Strength Index)** and **Parabolic SAR** indicators to make buy and sell decisions and can be fully controlled and monitored via **Telegram commands**.

The bot supports:
- Automated trading
- Manual trade overrides
- Loss streak protection with cooldown
- Live performance tracking
- Telegram-based control panel

 Features
- RSI + Parabolic SAR strategy
- Fully automated market orders
- Telegram bot integration
- Dynamic loss control & cooldown system
- Profit & loss tracking
- Runtime configuration via Telegram
- Trade history logging
- 1-minute candle analysis
  

# Trading Strategy
# Buy Conditions
- RSI is within a defined range (default: 47–52)
- Price is above Parabolic SAR
- OR manual `/buy` command via Telegram

# Sell Conditions
- Profit target reached
- Stop-loss reached
- RSI falls below sell threshold
- OR manual `/sell` command



# Requirements
- Python **3.9+**
- MEXC account with API access
- Telegram bot token





# Environment Variables

Create a `.env` file in the project root:

env
API_KEY=your_mexc_api_key
SECRET_KEY=your_mexc_secret_key
TELEGRAM_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id


Once started, the bot will:

* Connect to MEXC
* Fetch market data
* Start monitoring trades
* Send updates to Telegram


# Telegram Commands

| Command                   | Description                             |
| ------------------------- | --------------------------------------- |
| `/cmd`                    | Show all available commands             |
| `/start`                  | Start or resume trading                 |
| `/stop`                   | Pause the bot                           |
| `/status`                 | View indicators, balances, and position |
| `/buy`                    | Force buy                               |
| `/sell`                   | Force sell                              |
| `/setpair SYMBOL`         | Change trading pair                     |
| `/setcapital AMOUNT`      | Change trade capital                    |
| `/setlosscount COUNT MIN` | Set loss streak & cooldown              |
| `/resetlosscount`         | Reset loss counter                      |
| `/pnl`                    | Show profit & loss summary              |
| `/trades`                 | View recent trades                      |







# Risk Management

* Configurable stop-loss and profit target
* Automatic pause after consecutive losses
* Cooldown timer before trading resumes

 **Trading cryptocurrencies involves risk. Use at your own discretion.**


# Performance Tracking

The bot tracks:

* Total trades
* Total profit
* Total loss
* Net PnL
* Loss streak count

All stats are accessible via Telegram.


# Disclaimer

This project is for **educational purposes only**.
The author is not responsible for any financial losses incurred from using this software.



