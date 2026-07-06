I am building a Python trading bot for metals CFDs using the Capital.com REST API.
Do not use any external data sources. All market data comes from Capital.com only.
Build this in stages and confirm each stage works before moving to the next.

---

ENVIRONMENT
- Python version: [paste your python --version output here]
- Runs on: GitHub Actions on a cron schedule every 1 hour
- OS for local testing: Fedora Linux
- Notifications: Discord webhook

---

ACCOUNT DETAILS (load all from .env, never hardcode)
- CAPITAL_API_KEY=[your key from Settings > API integrations]
- CAPITAL_EMAIL=[your Capital.com login email]
- CAPITAL_PASSWORD=[your Capital.com password]
- CAPITAL_BASE_URL=https://api-capital.backend.capital
- DISCORD_WEBHOOK_URL=[your Discord webhook URL]
- IS_DEMO=true

NOTE: Capital.com uses your email address as the identifier in API login, not a numeric ID.
The active account ID must be fetched dynamically by calling GET /api/v1/accounts after
authenticating and selecting the first account returned. Do not hardcode any account ID.

---

PROJECT STRUCTURE
Build exactly this structure, no files outside it:

metals-bot/
├── bot.py              # main entry point, runs the full cycle
├── strategy.py         # indicator logic and signal generation only
├── capital_api.py      # all Capital.com API calls, nothing else
├── risk.py             # position sizing and stop loss calculation
├── logger.py           # trade and error logging to SQLite
├── config.py           # loads all env vars and constants
├── requirements.txt
└── .env.example        # template with empty values, no real credentials

---

STRATEGY
- Instrument: Gold CFD (epic: GOLD)
- Timeframe: 1 hour candles
- Indicators:
  - 20 EMA and 50 EMA for crossover signal
  - RSI(14) as confirmation filter
  - ATR(14) for stop loss sizing
- Entry long: 20 EMA crosses above 50 EMA AND RSI is between 45 and 65
- Entry short: 20 EMA crosses below 50 EMA AND RSI is between 35 and 55
- Stop loss: 1.5 x ATR from entry price
- Take profit: 3 x ATR from entry price (giving 1:2 risk/reward minimum)
- Max one open position at a time
- Both long and short directions enabled

---

RISK MANAGEMENT
- Risk per trade: 1% of current account balance
- Position size calculated as: (account_balance * 0.01) / (ATR * 1.5)
- Every order must include stop loss. Refuse to place order if stop loss calculation fails.
- Never open a new position if one is already open on GOLD

---

CAPITAL.COM API DETAILS
Base URL: https://api-capital.backend.capital
CAPITAL_BASE_DEMO_URL : https://demo-api-capital.backend-capital.com/

Authentication flow:
1. POST /api/v1/sessions
   Headers: X-CAP-API-KEY: {api_key}, Content-Type: application/json
   Body: {"identifier": CAPITAL_EMAIL, "password": CAPITAL_PASSWORD, "encryptedPassword": false}
2. Store CST and X-SECURITY-TOKEN from response headers
3. Include both CST and X-SECURITY-TOKEN in all subsequent request headers
4. After auth, call GET /api/v1/accounts and store the first account's ID for balance queries

Key endpoints:
- GET /api/v1/prices/{epic}?resolution=HOUR&max=100 — fetch candles
- GET /api/v1/positions — get open positions
- POST /api/v1/positions — place order
- DELETE /api/v1/positions/{dealId} — close position
- GET /api/v1/accounts — get account balance

Order body for POST /api/v1/positions:
{
  "epic": "GOLD",
  "direction": "BUY" or "SELL",
  "size": [calculated from risk.py],
  "guaranteedStop": false,
  "stopLevel": [calculated stop loss price],
  "profitLevel": [calculated take profit price]
}

Reference Capital_API_Docs.md for the API documentation

---

NOTIFICATIONS
Use Discord webhook for all notifications. No Telegram.
Send via: requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

Format all messages clearly:
Trade opened:
  LONG GOLD
  Size: 1.23
  Entry: $2345.60
  Stop Loss: $2334.50
  Take Profit: $2367.80
  Risk: $10.00

Error:
  ERROR: [description]
  Cycle skipped.

---

LOGGING
- Log to SQLite file trades.db
- Log table: trades (id, timestamp, epic, direction, size, entry_price, stop_loss, take_profit, status, error)
- Log table: signals (id, timestamp, epic, ema20, ema50, rsi, atr, signal_generated)
- Every API error must be caught, logged to SQLite, and sent to Discord. Do not crash.
- Every trade placed must send a Discord notification with: direction, size, entry, SL, TP

---

GITHUB ACTIONS
Create .github/workflows/bot.yml that:
- Runs on schedule: every hour (cron: "0 * * * *")
- Uses Python [your version]
- Installs requirements.txt
- Runs bot.py
- Loads secrets: CAPITAL_API_KEY, CAPITAL_EMAIL, CAPITAL_PASSWORD, DISCORD_WEBHOOK_URL, CAPITAL_BASE_URL, IS_DEMO

---

LIBRARIES
Use only these, no others unless essential:
- requests
- pandas
- pandas-ta
- python-dotenv
- sqlite3 (stdlib)

Do not use TA-Lib. Do not use any paid data sources.

---

CONSTRAINTS
- All credentials from environment variables only
- Every order must have a stop loss, no exceptions
- If IS_DEMO=true the account type is demo (already selected on Capital.com dashboard)
- If API returns any error, log it, notify Discord, skip the cycle, do not crash
- At the start of each cycle, check for open positions first. Only proceed to signal
  generation if no position is open.
- Session tokens expire after some time. If a 401 is returned on any call,
  re-authenticate once and retry. If it fails again, log and skip the cycle.

---

BUILD ORDER
Stage 1: Build config.py and capital_api.py only. Test that session auth works,
  GET /api/v1/accounts returns balance, and candle data returns correctly.
  Print raw API responses before proceeding.
Stage 2: Build strategy.py. Test that indicators calculate correctly on the
  candle data from stage 1. Print last 3 rows of indicator values.
Stage 3: Build risk.py. Test position size calculation with balance=1000,
  entry=2000, atr=5.0. Expected: size=1.33, SL=1992.5, TP=2015.0.
Stage 4: Build logger.py and confirm SQLite tables create correctly.
Stage 5: Build bot.py to wire everything together.
Stage 6: Build the GitHub Actions workflow.

Do not skip stages. After each stage show me the output and wait for me to
confirm before continuing.