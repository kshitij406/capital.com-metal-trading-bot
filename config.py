import os
from dotenv import load_dotenv

load_dotenv()

# Credentials are read lazily rather than at import. bot.py must fail loudly and
# immediately if any is missing, but backtest.py against a non-Capital data source
# needs none of them - and requiring them at import time made the whole backtest
# harness unrunnable locally, where credentials live only in GitHub Actions secrets.
# require_live_credentials() restores the fail-fast behaviour for the live path.


def _float_env(name, default):
    """Parse a float env var, tolerating the empty string.

    GitHub Actions substitutes an UNSET repository variable as an empty string
    rather than omitting it, so os.environ.get(name, default) returns "" and
    float("") raises - which would crash every scheduled run the moment one of
    these optional variables was left unset.
    """
    raw = os.environ.get(name, "")
    if raw is None or str(raw).strip() == "":
        return float(default)
    try:
        return float(raw)
    except ValueError:
        print(f"WARNING: {name}={raw!r} is not a number; using default {default}.")
        return float(default)


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Set it in .env (see .env.example) or in the GitHub Actions secrets."
        )
    return value


OANDA_API_TOKEN = os.environ.get("OANDA_API_TOKEN", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
IS_DEMO = os.environ.get("IS_DEMO", "true").lower() == "true"

# v20 splits practice and live onto separate hosts rather than separate credentials,
# so IS_DEMO selects the host exactly as it did for Capital.com. Defaults are the
# documented OANDA endpoints; override in .env only if OANDA changes them.
OANDA_PRACTICE_URL = os.environ.get("OANDA_PRACTICE_URL", "https://api-fxpractice.oanda.com")
OANDA_LIVE_URL = os.environ.get("OANDA_LIVE_URL", "https://api-fxtrade.oanda.com")
OANDA_BASE_URL = OANDA_PRACTICE_URL if IS_DEMO else OANDA_LIVE_URL


def require_live_credentials():
    """Assert every credential the live bot needs is present. Called by bot.py at
    startup so a misconfigured deployment fails before it can place an order."""
    for name in ("OANDA_API_TOKEN", "DISCORD_WEBHOOK_URL"):
        _required(name)
    if not OANDA_BASE_URL:
        raise RuntimeError(
            "Missing required environment variable "
            f"{'OANDA_PRACTICE_URL' if IS_DEMO else 'OANDA_LIVE_URL'} (IS_DEMO={IS_DEMO})."
        )


# --------------------------------------------------------------------------
# Forward test (started 2026-08-18)
# --------------------------------------------------------------------------
# STRATEGY selects which decision rule the live bot runs:
#
#   "baseline"  the original EMA-cross + RSI rule. Backtests at profit factor
#               0.95/0.88/0.84 on gold/silver/copper - it loses money.
#   "vol_regime" the forward-test candidate: the SAME entry rule, but only during
#               US macro hours (12-15 UTC) and only when the volatility regime
#               (ATR20/ATR200) is at least VOL_REGIME_MIN, with volatility-managed
#               position sizing. Backtests at PF 1.42, DSR 0.941 on gold over 4y.
#
# This is a switch rather than a rewrite so the previous behaviour is one env var
# away, and so the forward test is reverting-safe if it goes wrong.
STRATEGY = os.environ.get("STRATEGY", "baseline")

FORWARD_TEST_EPICS = ["GOLD"]  # silver backtests negative, copper break-even
# ATR(20)/ATR(200) floor. Measured as a PLATEAU rather than a peak: profit factor is
# 1.36-1.42 across 1.05/1.10/1.15, so the exact value is not knife-edge. 1.05 sits at
# the frequency end of that plateau (~40 trades/yr vs ~24 at 1.10), which shortens the
# forward test. Do NOT tune this further on historical data - 1.05 and 1.10 swap ranks
# depending on whether you look at 2 or 4 years, so choosing between them on backtest
# numbers is threshold-shopping, not measurement.
VOL_REGIME_MIN = _float_env("VOL_REGIME_MIN", 1.05)
VOL_REGIME_FAST = 20
VOL_REGIME_SLOW = 200
MACRO_HOURS_UTC = (12, 13, 14, 15)  # measured >1.2x mean volatility on all 3 metals
VOL_MANAGED_SIZING = os.environ.get("VOL_MANAGED_SIZING", "true").lower() == "true"

_ALL_EPICS = ["GOLD", "SILVER", "COPPER"]
EPICS = FORWARD_TEST_EPICS if STRATEGY == "vol_regime" else _ALL_EPICS

RESOLUTION = "MINUTE_15"
# The volatility regime needs ATR(200) plus the ATR period itself, so the candle
# request must comfortably exceed VOL_REGIME_SLOW or vol_regime is always NaN and
# the bot silently never trades.
CANDLE_COUNT = 300

EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
ATR_PERIOD = 14

RSI_LONG_MIN = 40
RSI_LONG_MAX = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 60

# Risk per trade. The baseline strategy uses 1%; the forward test uses a larger size
# so a decision arrives sooner at the same (low) trade count - the constraint on this
# test is calendar time, not trade count, and risking more per trade buys information
# faster without needing more trades.
#
# Measured on GOLD 4y at regime>=1.05, the worst historical losing streak was:
#     1% risk -> -4.2% of a $1000 account
#     2% risk -> -7.8%
#     3% risk -> -8.6%
# and returns scale sublinearly (16.2% -> 29.7%) because MAX_NOTIONAL_MULT binds, so
# past ~3% the extra risk buys progressively less. 3% is the point where the tail is
# still recoverable and the signal-to-noise is meaningfully better than 1%.
#
# This is a DEMO account. Do not carry 3% to a live account without re-reading the
# streak numbers above: 8 consecutive losses has a 1.3% probability at this win rate.
RISK_PER_TRADE = _float_env("RISK_PER_TRADE", 0.01)
SL_ATR_MULT = 1.5
TP_ATR_MULT = 3.0

DB_PATH = "trades.db"

DAILY_SUMMARY_HOUR_UTC = 21

# OANDA minimum trade sizes and unit precision, read from GET /v3/accounts/{id}/instruments
# on 2026-08-18. Gold trades in tenths; silver and copper are integer-unit only, so a
# blanket 2-decimal round would be rejected by the broker.
INSTRUMENT_PRECISION = {"GOLD": 1, "SILVER": 0, "COPPER": 0}
MIN_TRADE_SIZE = {"GOLD": 0.1, "SILVER": 1.0, "COPPER": 1.0}
PRICE_PRECISION = {"GOLD": 3, "SILVER": 5, "COPPER": 5}

# The practice account is funded at 100,000 CAD, which is not a balance worth sizing
# against - trades validated at that scale tell you nothing about live behaviour. Cap
# the balance the risk layer sees so demo sizing matches what a real account would do.
BALANCE_CAP = _float_env("BALANCE_CAP", 1000)
