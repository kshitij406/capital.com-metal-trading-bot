# capital.com-metal-trading-bot

Gold/Silver/Copper CFD trading bot using the Capital.com REST API. Runs every 15 min (demo testing) via GitHub Actions.

## Strategy

- Instruments: `GOLD`, `SILVER`, `COPPER` (`config.EPICS`)
- Timeframe: 15-minute candles
- EMA 9/21 crossover + RSI(14) confirmation, ATR(14) for stop sizing
- Long: EMA9 crosses above EMA21 and RSI in [40, 70]
- Short: EMA9 crosses below EMA21 and RSI in [30, 60]
- Stop loss: 1.5x ATR, take profit: 3x ATR
- Risk per trade: 1% of account balance
- One open position per epic at a time

## Files

- `config.py` - env vars and constants
- `capital_api.py` - all Capital.com API calls
- `strategy.py` - indicator calculation and signal generation
- `risk.py` - position sizing and SL/TP calculation
- `logger.py` - SQLite logging (`trades.db`)
- `stats.py` - recalculates `stats.json` from `trades.db` after every cycle
- `bot.py` - wires everything together, main entry point

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
python bot.py
```

## Environment variables

See `.env.example`:

- `CAPITAL_API_KEY`, `CAPITAL_EMAIL`, `CAPITAL_PASSWORD`
- `CAPITAL_BASE_URL`, `CAPITAL_BASE_DEMO_URL`
- `DISCORD_WEBHOOK_URL`
- `IS_DEMO` (`true` uses the demo account/URL)

## Scheduling

`.github/workflows/bot.yml` triggers on `workflow_dispatch` only (GitHub's native `schedule:` cron was dropped — it never reliably fired over a 2+ hour test window). Runs are instead triggered externally by a cron-job.org job (id `8018835`) that POSTs to the GitHub Actions dispatch endpoint every 15 minutes, offset to `:03/:18/:33/:48` UTC to avoid GitHub's documented peak-load delays at `:00/:15/:30/:45`.

The workflow persists `trades.db` and `stats.json` back to the repo at the end of each run so state survives across ephemeral runners.

## Stats

`stats.json` is regenerated at the end of every cycle from closed trades in `trades.db`: win rate, PnL, expectancy, drawdown, streak, both overall and per epic. It's runtime output, not committed (see `.gitignore`).
