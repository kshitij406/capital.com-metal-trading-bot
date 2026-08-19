"""Optional confluence features layered on top of the base EMA-cross signal.

Kept separate from strategy.py so the live signal path stays exactly as small as
it is today until a feature has actually earned its way in. Everything here is
computed as extra DataFrame columns, which matters for two reasons:

1. strategy.generate_signal only ever sees a 2-row slice, so any higher-timeframe
   or multi-bar context has to be precomputed per bar rather than looked up at
   decision time.
2. Every column is built with backward-looking windows only. A feature that peeks
   at bar i+1 would inflate the backtest exactly the way same-bar fills did, and
   that class of bug is invisible in the output - so the rule here is that no
   column may be assigned from an unshifted rolling/resample result.

Feature set, in the order the research suggested trying them:

  htf_bias          higher-timeframe trend direction (+1/-1/0)
  swing structure   BOS / CHoCH derived from confirmed swing highs and lows
  liquidity_grab    wick beyond a prior swing that closes back inside it
  fvg               3-bar fair value gap (imbalance) direction
  patterns          engulfing / hammer / shooting star, hand-rolled because
                    pandas_ta's candle patterns route through TA-Lib, which
                    CLAUDE.md forbids installing
  session           London / NY overlap flags
"""
import numpy as np
import pandas as pd

import config


# --------------------------------------------------------------------------
# Higher-timeframe bias
# --------------------------------------------------------------------------

def add_htf_bias(df, rule="4h", fast=None, slow=None):
    """Resample to a higher timeframe, compute the EMA relationship there, and
    map it back onto every lower-timeframe bar.

    The mapped value is SHIFTED by one HTF bar before the merge. Without that
    shift, every 15m bar inside a 4h candle would see that candle's final EMA -
    a value not knowable until the 4h candle closes. That is look-ahead bias, and
    on a trend filter it is particularly damaging because it effectively tells the
    strategy which way the next four hours resolved.
    """
    fast = fast or config.EMA_FAST
    slow = slow or config.EMA_SLOW

    htf = (
        df.set_index("time")
          .resample(rule)
          .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
          .dropna()
    )
    if len(htf) < slow + 2:
        out = df.copy()
        out["htf_bias"] = 0
        out["htf_slope"] = 0.0
        return out

    ema_fast = htf["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = htf["close"].ewm(span=slow, adjust=False).mean()

    bias = pd.Series(0, index=htf.index, dtype=int)
    bias[ema_fast > ema_slow] = 1
    bias[ema_fast < ema_slow] = -1

    slope = ema_slow.diff()

    # Shift by one HTF bar: a 15m bar may only use HTF information that was already
    # complete when that 15m bar opened.
    htf_frame = pd.DataFrame({
        "htf_bias": bias.shift(1).fillna(0).astype(int),
        "htf_slope": slope.shift(1).fillna(0.0),
    })

    out = df.copy()
    merged = pd.merge_asof(
        out.sort_values("time"),
        htf_frame.reset_index().rename(columns={"time": "htf_time"}).sort_values("htf_time"),
        left_on="time", right_on="htf_time", direction="backward",
    )
    out["htf_bias"] = merged["htf_bias"].fillna(0).astype(int).values
    out["htf_slope"] = merged["htf_slope"].fillna(0.0).values
    return out


# --------------------------------------------------------------------------
# Swing structure: BOS / CHoCH
# --------------------------------------------------------------------------

def add_swing_structure(df, lookback=5):
    """Confirmed swing highs/lows and the resulting break-of-structure signal.

    A swing high at bar i needs `lookback` bars on BOTH sides to confirm it, so it
    is only knowable at bar i+lookback. The confirmed levels are therefore shifted
    forward by that amount before being carried, which is the difference between a
    usable structure signal and one that silently reads the future.

    structure_break: +1 when price closes above the last confirmed swing high
    (bullish BOS), -1 when it closes below the last confirmed swing low.
    """
    out = df.copy()
    high, low = out["high"], out["low"]

    is_swing_high = (
        (high == high.rolling(lookback * 2 + 1, center=True).max())
        & high.rolling(lookback * 2 + 1, center=True).count().eq(lookback * 2 + 1)
    )
    is_swing_low = (
        (low == low.rolling(lookback * 2 + 1, center=True).min())
        & low.rolling(lookback * 2 + 1, center=True).count().eq(lookback * 2 + 1)
    )

    # Confirmation lag: a centered window at bar i is only complete at i+lookback.
    swing_high_level = high.where(is_swing_high).shift(lookback).ffill()
    swing_low_level = low.where(is_swing_low).shift(lookback).ffill()

    out["swing_high"] = swing_high_level
    out["swing_low"] = swing_low_level

    broke_up = out["close"] > swing_high_level
    broke_down = out["close"] < swing_low_level

    structure = pd.Series(0, index=out.index, dtype=int)
    structure[broke_up] = 1
    structure[broke_down] = -1
    out["structure_break"] = structure

    # CHoCH: a structure break in the opposite direction to the previous one.
    prev = structure.replace(0, np.nan).ffill()
    out["choch"] = ((structure != 0) & (structure != prev.shift(1))).astype(int)
    return out


# --------------------------------------------------------------------------
# Liquidity grabs
# --------------------------------------------------------------------------

def add_liquidity_grab(df, lookback=20, wick_ratio=0.5):
    """A bar that pierces a recent extreme but closes back inside it.

    The classic stop-run: price reaches beyond the prior `lookback` bars' high or
    low, then rejects. Requires the rejecting wick to be at least `wick_ratio` of
    the bar's total range so a marginal poke does not count.

    +1 = downside liquidity taken then rejected (bullish), -1 = the reverse.
    """
    out = df.copy()
    # shift(1) so the reference extreme excludes the current bar.
    prior_high = out["high"].rolling(lookback).max().shift(1)
    prior_low = out["low"].rolling(lookback).min().shift(1)

    rng = (out["high"] - out["low"]).replace(0, np.nan)
    upper_wick = out["high"] - out[["open", "close"]].max(axis=1)
    lower_wick = out[["open", "close"]].min(axis=1) - out["low"]

    bullish = (out["low"] < prior_low) & (out["close"] > prior_low) & (lower_wick / rng >= wick_ratio)
    bearish = (out["high"] > prior_high) & (out["close"] < prior_high) & (upper_wick / rng >= wick_ratio)

    grab = pd.Series(0, index=out.index, dtype=int)
    grab[bullish.fillna(False)] = 1
    grab[bearish.fillna(False)] = -1
    out["liquidity_grab"] = grab
    return out


# --------------------------------------------------------------------------
# Fair value gaps
# --------------------------------------------------------------------------

def add_fvg(df, min_gap_atr=0.1):
    """Three-bar imbalance: bar i-2's high below bar i's low leaves an unfilled gap.

    Only gaps wider than `min_gap_atr` * ATR count, so ordinary bar-to-bar noise
    is not read as an institutional imbalance. The signal is attributed to the bar
    that completes the pattern, which is the earliest bar at which it is knowable.
    """
    out = df.copy()
    high2 = out["high"].shift(2)
    low2 = out["low"].shift(2)
    atr = out["atr"] if "atr" in out.columns else (out["high"] - out["low"]).rolling(14).mean()
    threshold = atr * min_gap_atr

    bull_gap = out["low"] - high2
    bear_gap = low2 - out["high"]

    fvg = pd.Series(0, index=out.index, dtype=int)
    fvg[(bull_gap > threshold).fillna(False)] = 1
    fvg[(bear_gap > threshold).fillna(False)] = -1
    out["fvg"] = fvg
    out["fvg_size"] = np.where(fvg == 1, bull_gap, np.where(fvg == -1, bear_gap, 0.0))
    return out


# --------------------------------------------------------------------------
# Candlestick patterns
# --------------------------------------------------------------------------

def add_patterns(df, body_ratio=0.6, wick_mult=2.0):
    """Engulfing, hammer and shooting star, computed directly.

    pandas_ta exposes these only via TA-Lib, which CLAUDE.md forbids installing,
    and each is a few comparisons anyway.
    """
    out = df.copy()
    o, h, l, c = out["open"], out["high"], out["low"], out["close"]
    prev_o, prev_c = o.shift(1), c.shift(1)

    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    bull_engulf = (c > o) & (prev_c < prev_o) & (c >= prev_o) & (o <= prev_c)
    bear_engulf = (c < o) & (prev_c > prev_o) & (c <= prev_o) & (o >= prev_c)

    hammer = (lower_wick >= body * wick_mult) & (upper_wick <= body) & (body / rng <= body_ratio)
    shooting_star = (upper_wick >= body * wick_mult) & (lower_wick <= body) & (body / rng <= body_ratio)

    pattern = pd.Series(0, index=out.index, dtype=int)
    pattern[(bull_engulf | hammer).fillna(False)] = 1
    pattern[(bear_engulf | shooting_star).fillna(False)] = -1
    out["pattern"] = pattern
    return out


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

LONDON = (7, 16)
NEW_YORK = (12, 21)


def add_session(df):
    """Flag the London/NY overlap, when metals volume and range are highest."""
    out = df.copy()
    hour = pd.to_datetime(out["time"]).dt.hour
    out["in_london"] = ((hour >= LONDON[0]) & (hour < LONDON[1])).astype(int)
    out["in_newyork"] = ((hour >= NEW_YORK[0]) & (hour < NEW_YORK[1])).astype(int)
    out["in_overlap"] = (out["in_london"] & out["in_newyork"]).astype(int)
    return out


# --------------------------------------------------------------------------
# Volatility regime and time-of-day
# --------------------------------------------------------------------------

# US macro releases (CPI, NFP, PPI, retail sales, jobless claims) land at 08:30
# New York, which is 12:30 or 13:30 UTC depending on daylight saving, and the US
# cash session opens shortly after. Measured over 4 years of 15m data, hours 12-15
# UTC exceed 1.2x the all-day mean absolute return on ALL THREE metals - the
# largest and most stable time-of-day effect in the data, and unlike a price
# correlation it is knowable in advance from the clock alone. The 13:30 bucket
# alone runs 1.83x on gold. Quiet hours (3-4 and 20-23 UTC) run below 0.8x.
MACRO_RELEASE_HOURS_UTC = (12, 13, 14, 15)
QUIET_HOURS_UTC = (3, 4, 20, 21, 22, 23)


def add_time_of_day_volatility(df, min_history_days=30):
    """Expected volatility for this bar's time-of-day, learned from history only.

    The profile at bar i is built from an EXPANDING window over all bars strictly
    before i, so the value never reflects the period being tested. Computing a
    single profile over the whole series and applying it everywhere would leak the
    test period's own volatility into the decision that trades it - the same class
    of error as a same-bar fill, and just as invisible in the PnL.

    tod_vol_ratio: this slot's historical mean |return| divided by the all-day
    historical mean. 1.0 = an average-volatility slot, >1 = a busy one.
    """
    out = df.copy()
    t = pd.to_datetime(out["time"])
    out["slot"] = t.dt.hour * 4 + t.dt.minute // 15
    ret = np.log(out["close"]).diff().abs()

    # Expanding per-slot mean, shifted so bar i sees only bars < i.
    slot_mean = ret.groupby(out["slot"]).transform(
        lambda s: s.shift(1).expanding(min_periods=8).mean()
    )
    all_mean = ret.shift(1).expanding(min_periods=200).mean()

    ratio = (slot_mean / all_mean).replace([np.inf, -np.inf], np.nan)

    # Before enough history accumulates, claim no knowledge (1.0 = neutral) rather
    # than guessing - a warm-up NaN silently dropped would bias which bars trade.
    warmup = pd.to_datetime(out["time"]) < (t.iloc[0] + pd.Timedelta(days=min_history_days))
    ratio = ratio.mask(warmup, 1.0).fillna(1.0)

    out["tod_vol_ratio"] = ratio
    out["is_macro_hour"] = t.dt.hour.isin(MACRO_RELEASE_HOURS_UTC).astype(int)
    out = out.drop(columns=["slot"])
    return out


def add_volatility_regime(df, fast=20, slow=200):
    """Current ATR relative to its own longer-run level.

    vol_regime > 1 means the market is currently more volatile than its recent
    norm. This is distinct from tod_vol_ratio, which is a clock effect: this one
    is a market-state effect, and the two can disagree (a quiet 13:30, a wild
    03:00). Both are computed from completed bars only.
    """
    out = df.copy()
    if "atr" not in out.columns:
        tr = (out["high"] - out["low"]).abs()
        out["atr"] = tr.rolling(14).mean()

    atr_fast = out["atr"].rolling(fast, min_periods=fast // 2).mean()
    atr_slow = out["atr"].rolling(slow, min_periods=slow // 2).mean()

    # shift(1): the regime that informs bar i must be complete before bar i opens.
    regime = (atr_fast / atr_slow).shift(1).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    out["vol_regime"] = regime
    return out


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

ALL_FEATURES = ("htf", "structure", "liquidity", "fvg", "patterns", "session")
VOL_FEATURES = ("session", "tod_vol", "vol_regime")


def add_all(df, features=ALL_FEATURES, htf_rule="4h"):
    """Attach the requested feature columns. Order matters only for fvg, which
    reads the atr column that strategy.add_indicators supplies."""
    out = df
    if "htf" in features:
        out = add_htf_bias(out, rule=htf_rule)
    if "structure" in features:
        out = add_swing_structure(out)
    if "liquidity" in features:
        out = add_liquidity_grab(out)
    if "fvg" in features:
        out = add_fvg(out)
    if "patterns" in features:
        out = add_patterns(out)
    if "session" in features:
        out = add_session(out)
    if "tod_vol" in features:
        out = add_time_of_day_volatility(out)
    if "vol_regime" in features:
        out = add_volatility_regime(out)
    return out


FEATURE_COLUMNS = {
    "htf": ["htf_bias", "htf_slope"],
    "structure": ["swing_high", "swing_low", "structure_break", "choch"],
    "liquidity": ["liquidity_grab"],
    "fvg": ["fvg", "fvg_size"],
    "patterns": ["pattern"],
    "session": ["in_london", "in_newyork", "in_overlap"],
    "tod_vol": ["tod_vol_ratio", "is_macro_hour"],
    "vol_regime": ["vol_regime"],
}
