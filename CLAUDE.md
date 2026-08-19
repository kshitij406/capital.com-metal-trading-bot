# metals-bot

Metals CFD trading bot (gold, silver, copper) using the OANDA v20 REST API. Runs on GitHub Actions hourly.

## Stack
- Python, requests, pandas, pandas-ta, python-dotenv, sqlite3
- Capital.com REST API (CFD account)
- Discord webhook for notifications
- GitHub Actions for scheduling

## File responsibilities
- oanda_api.py: all OANDA v20 API calls only, and the translation of v20 response
  shapes into the shapes the rest of the bot parses
- capital_api.py: legacy Capital.com client, no longer wired into bot.py
- strategy.py: indicator calculations and signal logic only
- risk.py: position sizing, SL and TP calculation only
- logger.py: SQLite logging only
- bot.py: wires everything together, main entry point
- config.py: loads all env vars and constants
- backtest.py: standalone backtest script, never imported by bot.py
- data.py: historical OHLC sources for backtesting only (Capital + Dukascopy), never imported by bot.py
- metrics.py: performance and significance statistics for backtests only, never imported by bot.py
- test_backtest.py: self-checks for the backtest harness

## Agent routing
Use the capital-api-agent for any API work.
Use the strategy-agent for any indicator or signal work.
Use the risk-agent for any position sizing or SL/TP calculation work.
Use the debug-agent when diagnosing errors or reading logs.
Use the backtest-agent when testing strategy changes before deploying.

## Backtesting
- Run with `.venv/bin/python`, not `python3`. The system Python is 3.14 and numba
  (via pandas-ta) requires <3.14, so the venv is built from `/usr/local/bin/python3.12`.
- Default mode is walk-forward (`--mode wf`), not a single train/test split. One split
  reports one number from one market regime and hides regime dependence.
- Always report the Deflated Sharpe Ratio with an honest `--trials N` count of every
  strategy variant tried. Raw Sharpe selects for luck: the expected best-of-1000 Sharpe
  under a true zero edge is 3.26.
- Never compare a new strategy against a baseline run with different cost settings.
  Look-ahead (`--entry-delay 0`) and zero costs each swing gold's 2-year result by
  roughly $380 on a $1000 account.
- Dukascopy is an ECN feed with tighter spreads than Capital's CFD markup. Use it to
  compare strategy A vs B; use `--source capital` to calibrate absolute cost.
- Run `.venv/bin/python test_backtest.py` after changing the harness.

## Baseline (measured 2026-08-18, 2y 15m walk-forward, 8 windows, spread+slippage+swap)
The CURRENT EMA-cross + RSI strategy is unprofitable on all three epics out-of-sample:
- GOLD:   -30.3% aggregate, 2/8 windows profitable, PF 0.96, DSR 0.428
- SILVER: -82.8% aggregate, 2/8 windows profitable, PF 0.88, DSR 0.530
- COPPER: -114.7% aggregate, 3/8 windows profitable, PF 0.84, DSR 0.002
Any strategy change must beat these numbers on the same harness and cost settings.

## SMC/confluence results (measured 2026-08-18) — NOT adopted
HTF bias filter, BOS/CHoCH, liquidity grabs, FVG, candle patterns and session filters
are implemented in features.py + signals.py and compared via compare.py. Every variant
improves on the baseline, but none is significant:
- GOLD 2y: best was scoring>=55 at +$55.51 (DSR 0.487)
- GOLD 4y: the SAME variant is -$103.44 — the 2y profit did not survive out-of-period
- SILVER 2y: best was scoring>=65 (+$38.98, DSR 0.532); GOLD's best was >=55
- COPPER 2y: every variant still negative
Different winning thresholds per epic, and a winner that reverses on a longer window,
is the signature of noise. Do NOT deploy these to live on this evidence. The live
strategy.generate_signal is deliberately unchanged.

## Volatility timing (measured 2026-08-18) — best result so far, not yet proven
Restricting the SAME entry rule to high volatility regime (ATR20/ATR200 >= 1.2) during
US macro hours (12-15 UTC) is the only tested idea that SURVIVED the 4-year test:
- GOLD 4y: +$145.18, PF 1.37, 7/10 windows, max DD -5.8%, DSR 0.913
- Best variant on all three metals with the SAME threshold (silver -$50, copper +$15)
- 2y result (+$94.60) IMPROVED on 4y, unlike the SMC winner which reversed
Mechanism is structural, not predictive: hours 12-15 UTC carry >1.2x the all-day mean
absolute return on all three metals, knowable from the clock in advance. Macro price
data (FRED real yields, DXY) correlates contemporaneously (-0.24 to -0.35) but has
ZERO predictive power next-bar (+0.02) - already arbitraged away.
Caveats: DSR 0.913 < 0.95 bar; only ~25 trades/year; do NOT tune the 1.2 threshold on
this data. Demo forward-test candidate, gold only.

## Volatility-managed sizing (measured 2026-08-18) — replicated from literature
Moreira & Muir (2017): scale exposure by inverse VARIANCE, not inverse volatility.
risk.py already divided by ATR (inverse vol); risk.volatility_scalar adds the extra
factor, opt-in via the baseline_atr argument (off by default).
10y daily gold at matched vol: unscaled 0.73 -> inverse-vol 0.82 -> inverse-var 0.89,
better in 5/5 two-year blocks and on all three metals.
Applied to the macro+regime variant it improves PF 1.37->1.42, Sharpe 0.995->1.070,
DSR 0.919->0.941, maxDD -5.8%->-3.9%. It AMPLIFIES a losing strategy (baseline goes
-$484 -> -$566), so never apply it to an unprofitable base.

## Tested and REJECTED: overnight/session anomaly
Published finding (overnight gold returns positive, session negative) reproduces on
4 years but is a bull-market artifact. Over 10 years: beta 0.683 to the daily return,
R2 0.698, alpha -0.26bps/day. Overnight-only underperforms buy-and-hold on both return
and Sharpe. Do not revisit without a genuinely new mechanism.
ALWAYS test new ideas on 10 years, not 4 - this one flipped sign between the two.

## Constraints
- All credentials from environment variables only, never hardcoded
- Every order must include a stop loss, no exceptions
- IS_DEMO=true means run against the demo account
- Never install TA-Lib (requires C compiler)
- Never use paid external data sources
- Auth is a long-lived bearer token, not a session handshake; there is no login call
- Account ID is fetched dynamically from GET /v3/accounts on startup
- The account is CAD-denominated while all metals are USD-quoted, so position sizing
  must convert the risk budget through USD_CAD - see risk.calculate_trade
- Gold accepts 0.1-unit sizes; silver and copper are integer-unit only
- Practice balance is 100,000; BALANCE_CAP limits what the risk layer sees

## Environment variables required
OANDA_API_TOKEN
DISCORD_WEBHOOK_URL
IS_DEMO
BALANCE_CAP (optional, defaults to 1000)

# Pushing to GitHub
Dont add yourself as the collaborator each push should only be under my name