"""Standalone backtesting harness. Never imported by bot.py.

Replays the exact strategy.generate_signal / risk.calculate_trade functions the
live bot uses against historical OHLC pulled from Capital.com's historical
prices endpoint, so results reflect the live decision logic rather than a
reimplementation of it that could quietly drift from what actually trades.

Historical prices are only available up to 1000 candles per request, so
fetch_historical_candles pages through date-bounded chunks to cover a wider
range.

Usage:
    python backtest.py --epic GOLD --resolution MINUTE_15 --days 180
"""
import argparse
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

import config
import risk
import strategy
from capital_api import CapitalAPI

RESOLUTION_MINUTES = {
    "MINUTE": 1, "MINUTE_5": 5, "MINUTE_15": 15, "MINUTE_30": 30,
    "HOUR": 60, "HOUR_4": 240, "DAY": 1440, "WEEK": 10080,
}

IN_SAMPLE_FRACTION = 0.7  # chronological split point — tune only against the first slice
REQUEST_PAUSE_SECONDS = 0.15  # keep well under the documented 10 req/sec account-wide limit


def fetch_historical_candles(api, epic, resolution, start, end, pause=REQUEST_PAUSE_SECONDS):
    """Page through /api/v1/prices/{epic} in <=1000-candle chunks to cover [start, end].

    The endpoint's actual limit is a calendar-time span (1000 bars' worth of
    wall-clock time at the given resolution), not a returned-row count, so it
    rejects requests with error.invalid.max.daterange even when far fewer than
    1000 rows would come back (e.g. over a weekend with no trading). Chunking
    at 900 bars instead of 1000 keeps a safety margin under that cap."""
    step = timedelta(minutes=RESOLUTION_MINUTES[resolution] * 900)
    all_prices = []
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
        all_prices.extend(candles.get("prices", []))
        chunk_start = chunk_end
        time.sleep(pause)
    return {"prices": all_prices}


def candles_to_backtest_df(candles):
    """Like strategy.candles_to_dataframe, but keeps close bid/ask separately so
    the backtest can charge the real historical spread instead of trading on
    the midprice the live indicator logic uses. Deduplicates/sorts because
    chunked requests can overlap at their boundaries."""
    rows = []
    for p in candles["prices"]:
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
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    return df


def _fill_price(row, direction, side, spread_mode, slippage_points):
    """side is 'entry' or 'exit'. With spread_mode='historical', buys fill at the
    bar's recorded ask and sells at its recorded bid — the actual spread that
    existed at that moment, not an assumed constant. spread_mode='none' trades
    at the midprice (matches what the live bot currently assumes, for
    before/after comparison)."""
    is_buy = (direction == "LONG") == (side == "entry")
    if spread_mode == "historical":
        price = row["close_ask"] if is_buy else row["close_bid"]
    else:
        price = row["close"]
    return price + slippage_points if is_buy else price - slippage_points


def simulate(df, start_idx, end_idx, starting_balance, conservative_fill=True,
             spread_mode="historical", slippage_points=0.0):
    """Walk bar-by-bar over df[start_idx:end_idx]. One open position at a time,
    matching the live bot's "skip cycle if a position is already open" rule.

    SL/TP fills use each bar's high/low, not the entry-only close price, since
    a stop can be hit intrabar on data the live bot never gets to react to
    until its next scheduled cycle. When both SL and TP fall inside the same
    bar's range, conservative_fill=True (default) assumes the stop loss was
    hit first — a pessimistic assumption, deliberately, since tick data isn't
    available to know the true intrabar order and defaulting optimistic would
    inflate the backtest relative to what live trading could realistically
    achieve.
    """
    balance = starting_balance
    trades = []
    position = None

    for i in range(start_idx, end_idx):
        row = df.iloc[i]

        if position is not None:
            direction = position["direction"]
            sl, tp = position["stop_loss"], position["take_profit"]
            hit_tp = row["high"] >= tp if direction == "LONG" else row["low"] <= tp
            hit_sl = row["low"] <= sl if direction == "LONG" else row["high"] >= sl

            close_reason = None
            if hit_tp and hit_sl:
                close_reason = "SL" if conservative_fill else ("TP" if row["close"] >= row["open"] else "SL")
            elif hit_tp:
                close_reason = "TP"
            elif hit_sl:
                close_reason = "SL"

            if close_reason:
                close_price = sl if close_reason == "SL" else tp
                pnl = (close_price - position["entry_price"]) * position["size"] if direction == "LONG" \
                    else (position["entry_price"] - close_price) * position["size"]
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["time"],
                    "direction": direction,
                    "size": position["size"],
                    "entry_price": round(position["entry_price"], 2),
                    "exit_price": round(close_price, 2),
                    "close_reason": close_reason,
                    "pnl": round(pnl, 2),
                    "holding_bars": i - position["entry_index"],
                })
                balance += pnl
                position = None

        if position is None and i >= 1:
            signal = strategy.generate_signal(df.iloc[i - 1:i + 1])
            if signal:
                direction = "LONG" if signal == "BUY" else "SHORT"
                atr = row["atr"]
                entry_price = _fill_price(row, direction, "entry", spread_mode, slippage_points)
                try:
                    trade = risk.calculate_trade(balance, entry_price, atr, direction)
                except ValueError:
                    continue
                position = {
                    "direction": direction,
                    "size": trade["size"],
                    "entry_price": entry_price,
                    "stop_loss": trade["stop_loss"],
                    "take_profit": trade["take_profit"],
                    "entry_time": row["time"],
                    "entry_index": i,
                }

    return trades, balance, position


def compute_metrics(trades, resolution):
    minutes_per_bar = RESOLUTION_MINUTES[resolution]
    total = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = sum(t["pnl"] for t in losses)

    def avg_holding_minutes(rows):
        if not rows:
            return 0
        return round(sum(t["holding_bars"] for t in rows) / len(rows) * minutes_per_bar, 1)

    equity, peak, max_dd = 0.0, 0.0, 0.0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / total * 100, 1) if total else 0,
        "total_pnl": round(sum(t["pnl"] for t in trades), 2),
        "profit_factor": round(gross_profit / abs(gross_loss), 2) if gross_loss else float("inf"),
        "avg_holding_minutes_wins": avg_holding_minutes(wins),
        "avg_holding_minutes_losses": avg_holding_minutes(losses),
        "max_drawdown": round(max_dd, 2),
    }


def run_backtest(epic, resolution, start, end, starting_balance, split=IN_SAMPLE_FRACTION,
                  conservative_fill=True, spread_mode="historical", slippage_points=0.0):
    api = CapitalAPI()
    api.login()

    raw = fetch_historical_candles(api, epic, resolution, start, end)
    df = candles_to_backtest_df(raw)
    df = strategy.add_indicators(df)

    if len(df) < 10:
        raise ValueError(f"Only {len(df)} candles returned for {epic}/{resolution} in that range — too few to backtest.")

    split_idx = int(len(df) * split)

    in_trades, _, in_open = simulate(
        df, 1, split_idx, starting_balance, conservative_fill, spread_mode, slippage_points)
    out_trades, _, out_open = simulate(
        df, split_idx, len(df), starting_balance, conservative_fill, spread_mode, slippage_points)

    return {
        "epic": epic,
        "resolution": resolution,
        "candle_count": len(df),
        "date_range": (df["time"].iloc[0], df["time"].iloc[-1]),
        "split_date": df["time"].iloc[split_idx],
        "in_sample": {
            "metrics": compute_metrics(in_trades, resolution),
            "trades": in_trades,
            "position_open_at_end": in_open is not None,
        },
        "out_of_sample": {
            "metrics": compute_metrics(out_trades, resolution),
            "trades": out_trades,
            "position_open_at_end": out_open is not None,
        },
    }


def _print_metrics(label, metrics):
    print(f"  {label}")
    print(f"    Total trades:  {metrics['total_trades']}")
    print(f"    Win rate:      {metrics['win_rate_pct']}% ({metrics['wins']}W / {metrics['losses']}L)")
    print(f"    Total PnL:     ${metrics['total_pnl']:.2f}")
    print(f"    Profit factor: {metrics['profit_factor']}")
    print(f"    Avg hold (W):  {metrics['avg_holding_minutes_wins']} min")
    print(f"    Avg hold (L):  {metrics['avg_holding_minutes_losses']} min")
    print(f"    Max drawdown:  ${metrics['max_drawdown']:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest the live strategy against historical OHLC.")
    parser.add_argument("--epic", default=config.EPICS[0])
    parser.add_argument("--resolution", default=config.RESOLUTION)
    parser.add_argument("--days", type=int, default=180, help="Lookback window in days from now.")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting account balance for the simulation.")
    parser.add_argument("--split", type=float, default=IN_SAMPLE_FRACTION, help="In-sample fraction (chronological).")
    parser.add_argument("--spread", choices=["historical", "none"], default="historical",
                         help="'historical' charges the real recorded bid/ask spread; 'none' trades at midprice like the live bot's current entry_price does.")
    parser.add_argument("--slippage", type=float, default=0.0, help="Extra points added against you on every fill.")
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=args.days)

    result = run_backtest(
        args.epic, args.resolution, start, end, args.balance,
        split=args.split, spread_mode=args.spread, slippage_points=args.slippage,
    )

    print(f"\n{result['epic']} / {result['resolution']} — {result['candle_count']} candles "
          f"({result['date_range'][0]} to {result['date_range'][1]})")
    print(f"Chronological split at {result['split_date']} ({args.split:.0%} in-sample)\n")
    _print_metrics("IN-SAMPLE (tuning)", result["in_sample"]["metrics"])
    print()
    _print_metrics("OUT-OF-SAMPLE (validation only)", result["out_of_sample"]["metrics"])
    if result["in_sample"]["position_open_at_end"] or result["out_of_sample"]["position_open_at_end"]:
        print("\nNote: a position was still open at the end of one of the periods and is excluded from its metrics.")
