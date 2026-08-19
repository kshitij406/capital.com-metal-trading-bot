import pandas as pd
import pandas_ta as ta

import config


def candles_to_dataframe(candles):
    prices = candles["prices"]
    rows = []
    for p in prices:
        rows.append({
            "time": p["snapshotTimeUTC"],
            "open": (p["openPrice"]["bid"] + p["openPrice"]["ask"]) / 2,
            "high": (p["highPrice"]["bid"] + p["highPrice"]["ask"]) / 2,
            "low": (p["lowPrice"]["bid"] + p["lowPrice"]["ask"]) / 2,
            "close": (p["closePrice"]["bid"] + p["closePrice"]["ask"]) / 2,
            "volume": p["lastTradedVolume"],
        })
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    return df


def add_indicators(df):
    df["ema_fast"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema_slow"] = ta.ema(df["close"], length=config.EMA_SLOW)
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_PERIOD)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=config.ATR_PERIOD)
    return df


def add_volatility_regime(df, fast=None, slow=None):
    """ATR(fast)/ATR(slow), shifted so the value is complete before the bar it gates.

    Mirrors features.add_volatility_regime, which is what the backtest measured. The
    shift matters as much live as it does historically: without it the bot would
    gate on a ratio that includes the still-forming bar.
    """
    fast = fast or config.VOL_REGIME_FAST
    slow = slow or config.VOL_REGIME_SLOW

    atr_fast = df["atr"].rolling(fast, min_periods=fast // 2).mean()
    atr_slow = df["atr"].rolling(slow, min_periods=slow // 2).mean()
    df["vol_regime"] = (atr_fast / atr_slow).shift(1)
    df["baseline_atr"] = df["atr"].rolling(slow, min_periods=slow // 2).mean().shift(1)
    return df


def generate_signal(df):
    """The original EMA-cross + RSI rule. Unchanged.

    Kept as the exact function the backtest replays, so live and simulated decisions
    cannot drift apart.
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


def generate_vol_regime_signal(df, now=None):
    """The forward-test rule: the base signal, gated on macro hours and volatility.

    Returns (signal, context) where context records every gate's input and outcome.
    The context is logged whether or not a trade results, because the point of a
    forward test is to verify that live decisions match backtested ones - and a
    decision to SKIP is as much a decision as a decision to trade.
    """
    ctx = {"gate": None, "vol_regime": None, "hour_utc": None, "base_signal": None}

    if len(df) < 2:
        ctx["gate"] = "insufficient_data"
        return None, ctx

    last = df.iloc[-1]
    ts = now or last.get("time")
    hour = getattr(ts, "hour", None)
    ctx["hour_utc"] = hour

    regime = last.get("vol_regime")
    ctx["vol_regime"] = None if regime is None or pd.isna(regime) else round(float(regime), 4)

    sig = generate_signal(df)
    ctx["base_signal"] = sig or "NONE"

    if sig is None:
        ctx["gate"] = "no_base_signal"
        return None, ctx

    if hour is not None and hour not in config.MACRO_HOURS_UTC:
        ctx["gate"] = "outside_macro_hours"
        return None, ctx

    if ctx["vol_regime"] is None:
        # Not enough history to know the regime. Refuse rather than assume: assuming
        # 1.0 would let the bot trade during exactly the warm-up period the backtest
        # never traded.
        ctx["gate"] = "vol_regime_unavailable"
        return None, ctx

    if ctx["vol_regime"] < config.VOL_REGIME_MIN:
        ctx["gate"] = "vol_regime_too_low"
        return None, ctx

    ctx["gate"] = "passed"
    return sig, ctx


if __name__ == "__main__":
    from oanda_api import OandaAPI

    api = OandaAPI()
    api.login()
    candles = api.get_candles(config.EPICS[0])
    df = candles_to_dataframe(candles)
    df = add_indicators(df)
    print(df[["time", "open", "high", "low", "close", "ema_fast", "ema_slow", "rsi", "atr"]].tail(3))
    print("Signal:", generate_signal(df))
