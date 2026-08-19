"""Confluence scoring on top of the base EMA-cross signal.

The current live rule is binary: an EMA cross inside an RSI band fires a trade,
and nothing else is consulted. Scoring replaces that with a 0-100 confidence built
from several independent confirmations, and trades only above a threshold. The
point is not that more inputs are better - it is that a threshold gives a single
dial to trade frequency against selectivity, which a boolean does not.

Every component is optional and separately weighted so backtest.py can measure
them one at a time. Adding all of them at once and observing an improvement tells
you nothing about which one earned it, and risks carrying several useless features
that each add an overfitting degree of freedom.

Scores are computed from precomputed feature columns (see features.py), never from
future bars. generate_scored_signal takes the same 2-row slice contract as
strategy.generate_signal so the two are drop-in interchangeable in the simulator.
"""
import config

# Default component weights, summing to 100. These are a starting point chosen from
# the ordering the research suggested (HTF bias first, structure second), NOT a
# fitted result - fitting them against the same data used to evaluate them is the
# textbook route to an overfit backtest. Every weight change is a new trial and
# must be counted in --trials when reading the Deflated Sharpe Ratio.
DEFAULT_WEIGHTS = {
    "base": 30,        # the EMA cross + RSI band that fires today
    "htf": 25,         # higher-timeframe trend agreement
    "structure": 15,   # break of structure in the trade's direction
    "liquidity": 10,   # liquidity grab in the trade's direction
    "fvg": 10,         # fair value gap in the trade's direction
    "pattern": 5,      # confirming candlestick pattern
    "session": 5,      # London/NY overlap
}

DEFAULT_MIN_CONFIDENCE = 55


def _direction_of(signal):
    return 1 if signal == "BUY" else -1


def score_row(row, base_signal, weights=None, require_htf=False):
    """Score one bar's setup out of 100 for the given base signal direction.

    Returns (score, reasons) where reasons maps each contributing component to the
    points it added, so a trade can be explained after the fact rather than being
    an opaque number.

    require_htf=True hard-vetoes any setup fighting the higher-timeframe trend,
    regardless of score. That is a stricter rule than weighting alone: a setup with
    every other confirmation can still be the wrong side of a 4h downtrend.
    """
    weights = weights or DEFAULT_WEIGHTS
    want = _direction_of(base_signal)
    reasons = {}

    if require_htf and row.get("htf_bias", 0) != 0 and row.get("htf_bias", 0) != want:
        return 0, {"vetoed": "against higher-timeframe bias"}

    reasons["base"] = weights.get("base", 0)

    if row.get("htf_bias", 0) == want:
        reasons["htf"] = weights.get("htf", 0)
    if row.get("structure_break", 0) == want:
        reasons["structure"] = weights.get("structure", 0)
    if row.get("liquidity_grab", 0) == want:
        reasons["liquidity"] = weights.get("liquidity", 0)
    if row.get("fvg", 0) == want:
        reasons["fvg"] = weights.get("fvg", 0)
    if row.get("pattern", 0) == want:
        reasons["pattern"] = weights.get("pattern", 0)
    if row.get("in_overlap", 0) == 1:
        reasons["session"] = weights.get("session", 0)

    return sum(reasons.values()), reasons


def base_signal(df):
    """The existing EMA-cross + RSI rule, unchanged.

    Duplicated from strategy.generate_signal rather than imported so that scoring
    experiments cannot accidentally mutate the live signal path.
    """
    if len(df) < 2:
        return None
    prev, last = df.iloc[-2], df.iloc[-1]

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    if crossed_up and config.RSI_LONG_MIN <= last["rsi"] <= config.RSI_LONG_MAX:
        return "BUY"
    if crossed_down and config.RSI_SHORT_MIN <= last["rsi"] <= config.RSI_SHORT_MAX:
        return "SELL"
    return None


def make_signal_fn(min_confidence=DEFAULT_MIN_CONFIDENCE, weights=None, require_htf=False,
                   return_score=False):
    """Build a generate_signal-compatible callable with these scoring settings.

    The returned function has the same contract as strategy.generate_signal - it
    takes a 2-row slice and returns "BUY" / "SELL" / None - so backtest.simulate
    can use either without knowing which it holds.
    """
    def generate(df):
        sig = base_signal(df)
        if sig is None:
            return None
        row = df.iloc[-1]
        score, reasons = score_row(row, sig, weights=weights, require_htf=require_htf)
        # A veto is not a low score - it is a refusal, and must hold even at
        # min_confidence=0 where "score < threshold" would be False and would let
        # the trade through. Check it explicitly rather than relying on the number.
        if "vetoed" in reasons:
            return None
        if score < min_confidence:
            return None
        return (sig, score, reasons) if return_score else sig

    generate.min_confidence = min_confidence
    generate.weights = weights or DEFAULT_WEIGHTS
    generate.require_htf = require_htf
    return generate


def volatility_window(min_tod_ratio=None, max_tod_ratio=None, macro_hours_only=False,
                      min_vol_regime=None, max_vol_regime=None, avoid_quiet=False):
    """The existing entry rule, restricted to particular volatility conditions.

    Unlike the confluence features, this does not try to predict direction - it
    only decides WHEN the existing rule is allowed to act. That distinction matters
    given the measured evidence: hours 12-15 UTC carry >1.2x the all-day mean
    absolute return on all three metals over four years, and that effect is
    knowable from the clock in advance rather than inferred from a price
    correlation that has already been arbitraged away.

    Two opposite hypotheses are worth testing and this supports both:
      - trade only when volatility is high (moves are large enough to clear costs)
      - trade only when volatility is normal (avoid whipsaw around releases)
    """
    from features import MACRO_RELEASE_HOURS_UTC, QUIET_HOURS_UTC

    def generate(df):
        sig = base_signal(df)
        if sig is None:
            return None
        row = df.iloc[-1]

        if macro_hours_only and not row.get("is_macro_hour", 0):
            return None

        if avoid_quiet:
            ts = row.get("time")
            if ts is not None and getattr(ts, "hour", None) in QUIET_HOURS_UTC:
                return None

        tod = row.get("tod_vol_ratio", 1.0)
        if min_tod_ratio is not None and tod < min_tod_ratio:
            return None
        if max_tod_ratio is not None and tod > max_tod_ratio:
            return None

        regime = row.get("vol_regime", 1.0)
        if min_vol_regime is not None and regime < min_vol_regime:
            return None
        if max_vol_regime is not None and regime > max_vol_regime:
            return None

        return sig

    generate.min_confidence = 0
    return generate


def htf_filter_only(require_htf=True):
    """The simplest possible upgrade: the existing rule, vetoed when it fights the
    higher-timeframe trend. No scoring, no threshold - isolated so its effect can
    be measured on its own before any weighting scheme is introduced."""
    def generate(df):
        sig = base_signal(df)
        if sig is None:
            return None
        if require_htf:
            row = df.iloc[-1]
            bias = row.get("htf_bias", 0)
            if bias != 0 and bias != _direction_of(sig):
                return None
        return sig

    generate.min_confidence = 0
    generate.require_htf = require_htf
    return generate
