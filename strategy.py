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
    df["ema20"] = ta.ema(df["close"], length=config.EMA_FAST)
    df["ema50"] = ta.ema(df["close"], length=config.EMA_SLOW)
    df["rsi"] = ta.rsi(df["close"], length=config.RSI_PERIOD)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=config.ATR_PERIOD)
    return df


def generate_signal(df):
    if len(df) < 2:
        return None

    prev, last = df.iloc[-2], df.iloc[-1]

    crossed_up = prev["ema20"] <= prev["ema50"] and last["ema20"] > last["ema50"]
    crossed_down = prev["ema20"] >= prev["ema50"] and last["ema20"] < last["ema50"]

    if crossed_up and config.RSI_LONG_MIN <= last["rsi"] <= config.RSI_LONG_MAX:
        return "BUY"
    if crossed_down and config.RSI_SHORT_MIN <= last["rsi"] <= config.RSI_SHORT_MAX:
        return "SELL"
    return None


if __name__ == "__main__":
    from capital_api import CapitalAPI

    api = CapitalAPI()
    api.login()
    candles = api.get_candles(config.EPICS[0])
    df = candles_to_dataframe(candles)
    df = add_indicators(df)
    print(df[["time", "open", "high", "low", "close", "ema20", "ema50", "rsi", "atr"]].tail(3))
    print("Signal:", generate_signal(df))
