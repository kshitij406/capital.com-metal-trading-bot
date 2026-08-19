"""Candidate replacements for the EMA-cross base entry. Never imported by bot.py.

The volatility gates (macro hours + high regime) are a filter, not an entry - they
decide WHEN to act, and something else has to decide WHAT. Today that something is
an EMA cross, which fires ~1052 times/year on 15m gold and, unfiltered, loses money
at profit factor 0.95.

That makes the base rule the binding constraint on both frequency and edge: the
gates can only ever pass through a fraction of whatever the base rule produces, and
they cannot turn a bad signal into a good one.

Each candidate here has the same contract as strategy.generate_signal - takes a
2-row slice, returns "BUY"/"SELL"/None - so they drop into the same simulator and
the same gates, and the comparison isolates the entry rule.

Hypotheses, and why each is worth a trial:

  ema_cross     the incumbent, for reference
  rsi_reversion buy oversold / sell overbought. The opposite bet to the incumbent:
                if a 32%-win-rate trend rule is losing, the move it predicts may be
                reverting rather than continuing
  bb_reversion  the same reversion bet expressed against volatility bands, which
                adapt to regime rather than using fixed RSI thresholds
  breakout      trade the break of a recent range - a trend bet, but on price
                structure rather than on a lagging moving-average crossover
  momentum      simple n-bar return continuation, the academic time-series momentum
                formulation rather than a crossover proxy for it
  macd_cross    a slower, smoothed crossover; tests whether the incumbent's problem
                is the crossover idea itself or just its speed
"""
import numpy as np
import pandas as pd

import config


def _safe(row, key, default=np.nan):
    v = row.get(key, default)
    return default if v is None else v


# --------------------------------------------------------------------------
# Indicator columns these rules need
# --------------------------------------------------------------------------

def add_base_indicators(df, bb_period=20, bb_std=2.0, breakout_lookback=20,
                        momentum_lookback=12):
    """Attach every column the candidate rules read.

    All windows are backward-looking and the breakout bands are shifted by one bar
    so a bar cannot break a range that includes itself - the same causality rule as
    features.py, and just as easy to get wrong.
    """
    out = df.copy()
    close = out["close"]

    mid = close.rolling(bb_period).mean()
    sd = close.rolling(bb_period).std()
    out["bb_mid"] = mid
    out["bb_upper"] = mid + bb_std * sd
    out["bb_lower"] = mid - bb_std * sd

    out["range_high"] = out["high"].rolling(breakout_lookback).max().shift(1)
    out["range_low"] = out["low"].rolling(breakout_lookback).min().shift(1)

    out["momentum"] = close.pct_change(momentum_lookback)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    return out


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------

def ema_cross(df):
    """The incumbent rule, duplicated so experiments cannot mutate the live path."""
    if len(df) < 2:
        return None
    prev, last = df.iloc[-2], df.iloc[-1]
    up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    dn = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]
    if up and config.RSI_LONG_MIN <= last["rsi"] <= config.RSI_LONG_MAX:
        return "BUY"
    if dn and config.RSI_SHORT_MIN <= last["rsi"] <= config.RSI_SHORT_MAX:
        return "SELL"
    return None


def make_rsi_reversion(oversold=30, overbought=70):
    """Buy when RSI crosses UP out of oversold, sell when it crosses DOWN out of
    overbought. Crossing out rather than merely being extreme, so the rule waits for
    the turn instead of catching a falling knife."""
    def fn(df):
        if len(df) < 2:
            return None
        prev, last = df.iloc[-2], df.iloc[-1]
        if pd.isna(prev["rsi"]) or pd.isna(last["rsi"]):
            return None
        if prev["rsi"] <= oversold < last["rsi"]:
            return "BUY"
        if prev["rsi"] >= overbought > last["rsi"]:
            return "SELL"
        return None
    fn.__name__ = f"rsi_reversion_{oversold}_{overbought}"
    return fn


def bb_reversion(df):
    """Buy when price closes back inside the lower band, sell inside the upper.
    Volatility-adaptive by construction, unlike fixed RSI thresholds."""
    if len(df) < 2:
        return None
    prev, last = df.iloc[-2], df.iloc[-1]
    lo, up = _safe(last, "bb_lower"), _safe(last, "bb_upper")
    if pd.isna(lo) or pd.isna(up):
        return None
    if prev["close"] < _safe(prev, "bb_lower") and last["close"] > lo:
        return "BUY"
    if prev["close"] > _safe(prev, "bb_upper") and last["close"] < up:
        return "SELL"
    return None


def breakout(df):
    """Trade the break of the prior N-bar range. The range excludes the current bar
    (shifted in add_base_indicators), so a bar cannot break its own high."""
    if len(df) < 2:
        return None
    last = df.iloc[-1]
    hi, lo = _safe(last, "range_high"), _safe(last, "range_low")
    if pd.isna(hi) or pd.isna(lo):
        return None
    if last["close"] > hi:
        return "BUY"
    if last["close"] < lo:
        return "SELL"
    return None


def make_momentum(threshold=0.002):
    """Time-series momentum: trade in the direction of the last n-bar return once it
    exceeds a threshold. The threshold exists so the rule does not fire on noise."""
    def fn(df):
        if len(df) < 2:
            return None
        m = _safe(df.iloc[-1], "momentum")
        if pd.isna(m):
            return None
        if m > threshold:
            return "BUY"
        if m < -threshold:
            return "SELL"
        return None
    fn.__name__ = f"momentum_{threshold}"
    return fn


def macd_cross(df):
    """MACD line crossing its signal line - a slower, smoothed crossover. Tests
    whether the incumbent's weakness is crossovers per se or just its speed."""
    if len(df) < 2:
        return None
    prev, last = df.iloc[-2], df.iloc[-1]
    for k in ("macd", "macd_signal"):
        if pd.isna(_safe(prev, k)) or pd.isna(_safe(last, k)):
            return None
    if prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]:
        return "BUY"
    if prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]:
        return "SELL"
    return None


CANDIDATES = {
    "ema_cross (incumbent)": ema_cross,
    "rsi_reversion 30/70": make_rsi_reversion(30, 70),
    "rsi_reversion 25/75": make_rsi_reversion(25, 75),
    "bb_reversion": bb_reversion,
    "breakout 20": breakout,
    "momentum 0.2%": make_momentum(0.002),
    "momentum 0.5%": make_momentum(0.005),
    "macd_cross": macd_cross,
}


def gated(base_fn, macro_hours_only=True, min_vol_regime=1.05):
    """Wrap a base rule in the volatility gates, so every candidate is measured
    under the same conditions the current strategy trades in."""
    def fn(df):
        sig = base_fn(df)
        if sig is None:
            return None
        row = df.iloc[-1]
        if macro_hours_only and not row.get("is_macro_hour", 0):
            return None
        regime = row.get("vol_regime", np.nan)
        if pd.isna(regime) or regime < min_vol_regime:
            return None
        return sig
    fn.__name__ = f"gated_{getattr(base_fn, '__name__', 'fn')}"
    return fn
