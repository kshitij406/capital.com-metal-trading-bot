"""Historical OHLC data sources for backtesting. Never imported by bot.py.

Provides a single normalized DataFrame shape regardless of which vendor the
candles came from, so backtest.py can compare a strategy across two independent
feeds. A result that only appears on one feed is usually an artifact of that
feed rather than a real edge.

Normalized schema (one row per bar, chronological, deduplicated):
    time       tz-naive UTC datetime
    open/high/low/close   midprice, matching what strategy.py computes on live
    close_bid  bid at bar close - what a SELL actually fills at
    close_ask  ask at bar close - what a BUY actually fills at
    volume

Both sources return midprice OHLC for indicators and separate bid/ask closes for
fills, because charging the real historical spread is the single largest
correction between a naive backtest and live results.

Capital.com is the live broker, so its spreads are the ones that will actually
be paid; Dukascopy is an ECN feed with materially tighter spreads but far deeper
history (2015+ vs Capital's ~180 days) and no rate limit. Use Capital to
calibrate absolute cost, Dukascopy to compare strategy A against strategy B over
enough market regimes for the comparison to mean anything.
"""
import os
import time
from datetime import datetime, timedelta

import pandas as pd

RESOLUTION_MINUTES = {
    "MINUTE": 1, "MINUTE_5": 5, "MINUTE_15": 15, "MINUTE_30": 30,
    "HOUR": 60, "HOUR_4": 240, "DAY": 1440, "WEEK": 10080,
}

COLUMNS = ["time", "open", "high", "low", "close", "close_bid", "close_ask", "volume"]

# Capital.com epic -> Dukascopy instrument. Capital's "GOLD"/"SILVER" are spot
# metal CFDs, matching Dukascopy's XAU/XAG spot pairs. COPPER maps to Dukascopy's
# copper CFD rather than an FX-style pair, hence the different constant shape.
EPIC_TO_DUKASCOPY = {
    "GOLD": "XAU/USD",
    "SILVER": "XAG/USD",
    "COPPER": "COPPER.CMD/USD",
}

REQUEST_PAUSE_SECONDS = 0.15  # keep well under Capital's documented 10 req/sec account-wide limit


def _normalize(df):
    """Sort, deduplicate and enforce column order/dtypes on a built frame.

    Chunked requests can overlap at their boundaries, and a duplicated bar would
    let the simulator act on the same signal twice.
    """
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    return df[COLUMNS]


# --------------------------------------------------------------------------
# Capital.com
# --------------------------------------------------------------------------

def fetch_capital(epic, resolution, start, end, api=None, pause=REQUEST_PAUSE_SECONDS):
    """Page through /api/v1/prices/{epic} in <=900-bar chunks to cover [start, end].

    The endpoint's limit is a calendar-time span (1000 bars' worth of wall-clock
    time at the given resolution), not a returned-row count, so it rejects
    requests with error.invalid.max.daterange even when far fewer than 1000 rows
    would come back (e.g. over a weekend with no trading). Chunking at 900 bars
    keeps a safety margin under that cap.
    """
    if api is None:
        from capital_api import CapitalAPI
        api = CapitalAPI()
        api.login()

    step = timedelta(minutes=RESOLUTION_MINUTES[resolution] * 900)
    prices = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + step, end)
        candles = api.get_candles(
            epic,
            resolution=resolution,
            max_candles=1000,
            from_date=chunk_start.strftime("%Y-%m-%dT%H:%M:%S"),
            to_date=chunk_end.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        prices.extend(candles.get("prices", []))
        chunk_start = chunk_end
        time.sleep(pause)

    rows = []
    for p in prices:
        rows.append({
            "time": p["snapshotTimeUTC"],
            "open": (p["openPrice"]["bid"] + p["openPrice"]["ask"]) / 2,
            "high": (p["highPrice"]["bid"] + p["highPrice"]["ask"]) / 2,
            "low": (p["lowPrice"]["bid"] + p["lowPrice"]["ask"]) / 2,
            "close": (p["closePrice"]["bid"] + p["closePrice"]["ask"]) / 2,
            "close_bid": p["closePrice"]["bid"],
            "close_ask": p["closePrice"]["ask"],
            "volume": p["lastTradedVolume"],
        })

    if not rows:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    return _normalize(df)


# --------------------------------------------------------------------------
# Dukascopy
# --------------------------------------------------------------------------

DUKASCOPY_INTERVALS = {
    "MINUTE": "INTERVAL_MIN_1", "MINUTE_5": "INTERVAL_MIN_5",
    "MINUTE_15": "INTERVAL_MIN_15", "MINUTE_30": "INTERVAL_MIN_30",
    "HOUR": "INTERVAL_HOUR_1", "HOUR_4": "INTERVAL_HOUR_4",
    "DAY": "INTERVAL_DAY_1", "WEEK": "INTERVAL_WEEK_1",
}


def fetch_dukascopy(epic, resolution, start, end):
    """Fetch bid and ask series separately and join them into the normalized shape.

    Dukascopy serves one offer side per request, so a true spread requires two
    calls. They are joined on timestamp with an inner join: a bar present on only
    one side has no measurable spread, and inventing one by forward-filling would
    fabricate the exact number the backtest is trying to measure honestly.
    """
    import logging

    import dukascopy_python
    from dukascopy_python import instruments

    # The vendor library logs a progress line per download chunk at INFO, which
    # buries the actual report under hundreds of lines on a multi-year fetch.
    logging.getLogger("DUKASCRIPT").setLevel(logging.WARNING)

    if epic not in EPIC_TO_DUKASCOPY:
        raise ValueError(
            f"No Dukascopy instrument mapped for epic {epic!r}. Known: {sorted(EPIC_TO_DUKASCOPY)}"
        )
    if resolution not in DUKASCOPY_INTERVALS:
        raise ValueError(f"Resolution {resolution!r} not supported by the Dukascopy source.")

    symbol = EPIC_TO_DUKASCOPY[epic]
    instrument = next(
        getattr(instruments, n) for n in dir(instruments)
        if n.startswith("INSTRUMENT_") and getattr(instruments, n) == symbol
    )
    interval = getattr(dukascopy_python, DUKASCOPY_INTERVALS[resolution])

    def _side(offer_side):
        df = dukascopy_python.fetch(instrument, interval, offer_side, start, end)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df.index = pd.to_datetime(df.index).tz_convert("UTC").tz_localize(None)
        return df

    bid = _side(dukascopy_python.OFFER_SIDE_BID)
    ask = _side(dukascopy_python.OFFER_SIDE_ASK)

    if bid.empty or ask.empty:
        return pd.DataFrame(columns=COLUMNS)

    joined = bid.join(ask, how="inner", lsuffix="_bid", rsuffix="_ask")

    df = pd.DataFrame({
        "time": joined.index,
        # Midprice OHLC so indicators see the same thing strategy.py computes live,
        # where candles_to_dataframe averages Capital's bid/ask.
        "open": (joined["open_bid"] + joined["open_ask"]) / 2,
        "high": (joined["high_bid"] + joined["high_ask"]) / 2,
        "low": (joined["low_bid"] + joined["low_ask"]) / 2,
        "close": (joined["close_bid"] + joined["close_ask"]) / 2,
        "close_bid": joined["close_bid"],
        "close_ask": joined["close_ask"],
        "volume": joined["volume_bid"] + joined["volume_ask"],
    }).reset_index(drop=True)

    return _normalize(df)


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# OANDA v20
# --------------------------------------------------------------------------

def fetch_oanda(epic, resolution, start, end, api=None, pause=REQUEST_PAUSE_SECONDS):
    """Page through v20 /instruments/{instrument}/candles to cover [start, end].

    v20 caps a single response at 5000 candles and rejects a from/to span implying
    more, so chunk well under that. Unlike Capital.com the limit is a row count
    rather than a calendar span, so a quiet weekend does not cause a rejection.
    """
    if api is None:
        from oanda_api import OandaAPI
        api = OandaAPI()
        api.login()

    step = timedelta(minutes=RESOLUTION_MINUTES[resolution] * 4000)
    prices = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + step, end)
        candles = api.get_candles(
            epic,
            resolution=resolution,
            from_date=chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            to_date=chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        prices.extend(candles.get("prices", []))
        chunk_start = chunk_end
        time.sleep(pause)

    rows = []
    for p in prices:
        rows.append({
            "time": p["snapshotTimeUTC"],
            "open": (p["openPrice"]["bid"] + p["openPrice"]["ask"]) / 2,
            "high": (p["highPrice"]["bid"] + p["highPrice"]["ask"]) / 2,
            "low": (p["lowPrice"]["bid"] + p["lowPrice"]["ask"]) / 2,
            "close": (p["closePrice"]["bid"] + p["closePrice"]["ask"]) / 2,
            "volume": p["lastTradedVolume"],
            "spread": p["closePrice"]["ask"] - p["closePrice"]["bid"],
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"])
    return df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)


SOURCES = {"capital": fetch_capital, "dukascopy": fetch_dukascopy, "oanda": fetch_oanda}

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".data_cache")


def _cache_path(source, epic, resolution, start, end):
    key = f"{source}_{epic}_{resolution}_{start:%Y%m%d}_{end:%Y%m%d}"
    return os.path.join(CACHE_DIR, f"{key}.parquet")


def fetch(source, epic, resolution, start, end, use_cache=True, **kwargs):
    """Fetch normalized candles, caching to disk by (source, epic, resolution, range).

    Dukascopy reconstructs bars from tick archives, so a two-year 15-minute pull
    takes minutes. Iterating on a strategy means running the same fetch repeatedly
    against unchanging history, which makes caching the difference between a
    multi-minute loop and a sub-second one. Capital results are cached too, which also
    keeps repeated runs off its rate limit.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown source {source!r}. Known: {sorted(SOURCES)}")

    path = _cache_path(source, epic, resolution, start, end)
    if use_cache and os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            pass  # corrupt or unreadable cache entry: fall through and refetch

    if source in ("capital", "oanda"):
        df = fetch_capital(epic, resolution, start, end, **kwargs)
    else:
        df = fetch_dukascopy(epic, resolution, start, end)

    if use_cache and not df.empty:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            df.to_parquet(path, index=False)
        except Exception as e:
            print(f"WARNING: could not write data cache {path}: {e}")

    return df


def spread_summary(df):
    """Descriptive spread stats, used to compare what two feeds charge for the
    same instrument over the same window."""
    if df.empty:
        return {}
    spread = df["close_ask"] - df["close_bid"]
    pct = (spread / df["close"] * 100).replace([float("inf"), float("-inf")], pd.NA).dropna()
    return {
        "bars": len(df),
        "mean": round(float(spread.mean()), 4),
        "median": round(float(spread.median()), 4),
        "p95": round(float(spread.quantile(0.95)), 4),
        "max": round(float(spread.max()), 4),
        "mean_pct_of_price": round(float(pct.mean()), 5) if len(pct) else None,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare spreads between data sources.")
    parser.add_argument("--epic", default="GOLD")
    parser.add_argument("--resolution", default="MINUTE_15")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    end = datetime.utcnow().replace(microsecond=0)
    start = end - timedelta(days=args.days)

    for source in ("dukascopy", "capital"):
        try:
            df = fetch(source, args.epic, args.resolution, start, end)
            print(f"{source:10} {spread_summary(df)}")
        except Exception as e:
            print(f"{source:10} FAILED: {type(e).__name__}: {e}")
