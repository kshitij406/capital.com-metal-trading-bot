# metals-bot

Gold CFD trading bot using the Capital.com REST API. Runs on GitHub Actions hourly.

## Stack
- Python, requests, pandas, pandas-ta, python-dotenv, sqlite3
- Capital.com REST API (CFD account)
- Discord webhook for notifications
- GitHub Actions for scheduling

## File responsibilities
- capital_api.py: all Capital.com API calls only
- strategy.py: indicator calculations and signal logic only
- risk.py: position sizing, SL and TP calculation only
- logger.py: SQLite logging only
- bot.py: wires everything together, main entry point
- config.py: loads all env vars and constants
- backtest.py: standalone backtest script, never imported by bot.py

## Agent routing
Use the capital-api-agent for any API work.
Use the strategy-agent for any indicator or signal work.
Use the risk-agent for any position sizing or SL/TP calculation work.
Use the debug-agent when diagnosing errors or reading logs.
Use the backtest-agent when testing strategy changes before deploying.

## Constraints
- All credentials from environment variables only, never hardcoded
- Every order must include a stop loss, no exceptions
- IS_DEMO=true means run against the demo account
- Never install TA-Lib (requires C compiler)
- Never use paid external data sources
- The API identifier is the account email address, not a numeric ID
- Account ID is fetched dynamically from GET /api/v1/accounts on session start

## Environment variables required
CAPITAL_API_KEY
CAPITAL_EMAIL
CAPITAL_PASSWORD
CAPITAL_BASE_URL
CAPITAL_BASE_DEMO_URL
DISCORD_WEBHOOK_URL
IS_DEMO