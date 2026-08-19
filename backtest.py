"""Standalone backtesting harness. Never imported by bot.py.

Replays the exact strategy.generate_signal / risk.calculate_trade functions the
live bot uses against historical OHLC, so results reflect the live decision logic
rather than a reimplementation of it that could quietly drift from what actually
trades. This is why the harness is hand-rolled rather than built on vectorbt or
backtesting.py: those frameworks require the strategy to be expressed in their
own API, which reintroduces exactly that drift.

Validation design
-----------------
Two modes, and the difference matters:

  --mode split    One chronological in-sample/out-of-sample cut. Fast, and useful
                  as a smoke test, but it reports ONE number from ONE regime. A
                  split that happens to land on a trending market flatters a
                  trend-following strategy and says nothing about the rest.

  --mode wf       Walk-forward (default). Rolls a train/test window through the
                  whole history and reports the DISTRIBUTION of out-of-sample
                  results - how many windows were profitable, the worst one, the
                  spread. A strategy that only works in two of nine windows is
                  visible here and invisible under --mode split.

Significance
------------
Descriptive metrics cannot distinguish edge from luck. Pass --trials N with an
honest count of every strategy variant evaluated so far, and the Deflated Sharpe
Ratio corrects for having picked the best of N. See metrics.py for why this is
not optional: the expected best-of-1000 Sharpe under a true zero edge is 3.26.

Usage:
    python backtest.py --epic GOLD --resolution MINUTE_15 --days 730
    python backtest.py --source capital --days 180 --mode split
    python backtest.py --trials 12 --swap-rate -0.0075
"""
import argparse
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import config
import data
import metrics
import risk
import strategy

IN_SAMPLE_FRACTION = 0.7  # chronological split point - tune only against the first slice

# Overnight financing on a leveraged metals CFD, charged per calendar day a
# position is held past the broker's rollover. Expressed as a daily fraction of
# notional. Capital.com's actual gold rate sits near -0.0075%/day on the long
# side; it is configurable because it moves with rates and differs per epic.
DEFAULT_SWAP_RATE_DAILY_PCT = -0.0075
ROLLOVER_HOUR_UTC = 21  # ~5pm New York, the conventional FX/metals rollover


def _fill_price(row, direction, side, spread_mode, slippage_points):
    """side is 'entry' or 'exit'. With spread_mode='historical', buys fill at the
    bar's recorded ask and sells at its recorded bid - the actual spread that
    existed at that moment, not an assumed constant. spread_mode='none' trades at
    the midprice (matches what the live bot's entry_price currently assumes, kept
    for before/after comparison)."""
    is_buy = (direction == "LONG") == (side == "entry")
    if spread_mode == "historical":
        price = row["close_ask"] if is_buy else row["close_bid"]
    else:
        price = row["close"]
    return price + slippage_points if is_buy else price - slippage_points


def _rollovers_crossed(entry_time, exit_time):
    """Number of daily rollover points a position was held through.

    Financing is charged per rollover crossed, not per 24h elapsed, so a position
    opened at 20:00 UTC and closed at 22:00 UTC pays one full day's swap despite
    being open for two hours. Modelling it as elapsed/24 would understate the cost
    of exactly the short-hold trades this strategy produces most of.
    """
    if exit_time <= entry_time:
        return 0
    count = 0
    cursor = entry_time.replace(hour=ROLLOVER_HOUR_UTC, minute=0, second=0, microsecond=0)
    if cursor <= entry_time:
        cursor += timedelta(days=1)
    while cursor <= exit_time:
        count += 1
        cursor += timedelta(days=1)
    return count


def _swap_cost(entry_time, exit_time, size, price, swap_rate_daily_pct):
    """Financing charged against notional for each rollover crossed. Returned as a
    negative number when it is a cost."""
    if not swap_rate_daily_pct:
        return 0.0
    nights = _rollovers_crossed(entry_time, exit_time)
    if not nights:
        return 0.0
    notional = size * price
    return notional * (swap_rate_daily_pct / 100.0) * nights


def simulate(df, start_idx, end_idx, starting_balance, conservative_fill=True,
             spread_mode="historical", slippage_points=0.0, entry_delay_bars=1,
             swap_rate_daily_pct=DEFAULT_SWAP_RATE_DAILY_PCT,
             epic=None, quote_to_account_rate=1.0, signal_fn=None,
             vol_managed=False, baseline_atr_window=200):
    """Walk bar-by-bar over df[start_idx:end_idx]. One open position at a time,
    matching the live bot's "skip cycle if a position is already open" rule.

    SL/TP fills use each bar's high/low, not the entry-only close price, since a
    stop can be hit intrabar on data the live bot never gets to react to until its
    next scheduled cycle. When both SL and TP fall inside the same bar's range,
    conservative_fill=True (default) assumes the stop loss was hit first - a
    pessimistic assumption, deliberately, since tick data isn't available to know
    the true intrabar order and defaulting optimistic would inflate the backtest
    relative to what live trading could realistically achieve.

    entry_delay_bars controls when a signal is actually filled. The signal on bar
    i is derived from bar i's close, which is not knowable until bar i has ended,
    so entry_delay_bars=1 (the default) fills on bar i+1 - the earliest bar a live
    cron-triggered bot could realistically transact on. entry_delay_bars=0
    reproduces the older same-bar fill, which is look-ahead biased and will
    overstate results; it is kept only for before/after comparison.

    Balance compounds across trades so position sizing reflects what
    risk.calculate_trade would size on the live account at that moment.
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
                gross = (close_price - position["entry_price"]) * position["size"] if direction == "LONG" \
                    else (position["entry_price"] - close_price) * position["size"]
                swap = _swap_cost(
                    position["entry_time"], row["time"], position["size"],
                    position["entry_price"], swap_rate_daily_pct,
                )
                # Round once, here, and use the same rounded figure for both the
                # trade record and the running balance. Letting the balance
                # accumulate unrounded while reporting rounded per-trade PnL makes
                # the two disagree by a growing amount over a long run, so the
                # reported trades no longer reconcile against the final balance.
                pnl = round(gross + swap, 2)
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["time"],
                    "direction": direction,
                    "size": position["size"],
                    "entry_price": round(position["entry_price"], 2),
                    "exit_price": round(close_price, 2),
                    "close_reason": close_reason,
                    "gross_pnl": round(gross, 2),
                    "swap_cost": round(swap, 2),
                    "pnl": pnl,
                    "holding_bars": i - position["entry_index"],
                })
                balance += pnl
                position = None

        if position is None and i >= 1 + entry_delay_bars:
            # Signal is evaluated on the bar that closed entry_delay_bars ago, then
            # filled at the current bar - never on the same bar whose close produced
            # the signal, which the live bot cannot see until that bar has ended.
            sig_i = i - entry_delay_bars
            # signal_fn defaults to the live strategy. Variants (see signals.py) are
            # injected here so every comparison runs on identical bars, fills and
            # costs - the only difference being the decision rule itself.
            fn = signal_fn or strategy.generate_signal
            signal = fn(df.iloc[sig_i - 1:sig_i + 1])
            if signal:
                direction = "LONG" if signal == "BUY" else "SHORT"
                atr = row["atr"]
                entry_price = _fill_price(row, direction, "entry", spread_mode, slippage_points)
                try:
                    # epic and quote_to_account_rate must be passed through: the live
                    # bot sizes in CAD against USD-quoted metals and rounds to each
                    # instrument's unit precision, and calculate_trade refuses sizes
                    # under the broker minimum. Backtesting on the defaults (rate 1.0,
                    # no epic) would oversize by the full FX rate and would silently
                    # take trades the broker would have rejected outright.
                    # baseline_atr is the instrument's longer-run ATR as of the
                    # PREVIOUS bar, so the volatility-managed multiplier never reads
                    # the bar it is sizing.
                    baseline = None
                    if vol_managed and i > baseline_atr_window:
                        baseline = df["atr"].iloc[i - baseline_atr_window:i].mean()
                    trade = risk.calculate_trade(
                        balance, entry_price, atr, direction,
                        epic=epic, quote_to_account_rate=quote_to_account_rate,
                        baseline_atr=baseline,
                    )
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


# --------------------------------------------------------------------------
# Validation modes
# --------------------------------------------------------------------------

def _sim_kwargs(args_like):
    return {
        "conservative_fill": args_like.get("conservative_fill", True),
        "spread_mode": args_like.get("spread_mode", "historical"),
        "slippage_points": args_like.get("slippage_points", 0.0),
        "entry_delay_bars": args_like.get("entry_delay_bars", 1),
        "swap_rate_daily_pct": args_like.get("swap_rate_daily_pct", DEFAULT_SWAP_RATE_DAILY_PCT),
        "epic": args_like.get("epic"),
        "quote_to_account_rate": args_like.get("quote_to_account_rate", 1.0),
        "signal_fn": args_like.get("signal_fn"),
        "vol_managed": args_like.get("vol_managed", False),
        "baseline_atr_window": args_like.get("baseline_atr_window", 200),
    }


def run_split(df, resolution, starting_balance, split=IN_SAMPLE_FRACTION, n_trials=1, **sim):
    """Single chronological in-sample/out-of-sample cut."""
    split_idx = int(len(df) * split)
    kw = _sim_kwargs(sim)

    in_trades, _, in_open = simulate(df, 1, split_idx, starting_balance, **kw)
    out_trades, _, out_open = simulate(df, split_idx, len(df), starting_balance, **kw)

    return {
        "mode": "split",
        "split_date": df["time"].iloc[split_idx],
        "in_sample": {
            "metrics": metrics.compute(in_trades, resolution, starting_balance,
                                       n_trials=n_trials, bars_elapsed=split_idx),
            "trades": in_trades,
            "position_open_at_end": in_open is not None,
        },
        "out_of_sample": {
            "metrics": metrics.compute(out_trades, resolution, starting_balance,
                                       n_trials=n_trials, bars_elapsed=len(df) - split_idx),
            "trades": out_trades,
            "position_open_at_end": out_open is not None,
        },
    }


def run_walk_forward(df, resolution, starting_balance, n_windows=8, train_frac=0.7,
                     n_trials=1, **sim):
    """Roll a train/test window through the history and report every OOS slice.

    Windows are anchored so each test slice immediately follows its own train
    slice and no test slice overlaps another, which makes the concatenated OOS
    trades a legitimate contiguous out-of-sample record rather than a resampling
    of the same period.

    The train slice is simulated but its trades are deliberately NOT counted
    toward the headline result - the current strategy has no fitted parameters, so
    the train slice exists to keep the window geometry honest and to expose
    train-vs-test degradation if parameter fitting is added later.
    """
    kw = _sim_kwargs(sim)
    n = len(df)

    # Geometry: windows advance by test_len (non-overlapping test slices), and the
    # first window additionally needs train_len bars of history ahead of it. So
    # total bars consumed = train_len + n_windows * test_len. Solving for test_len
    # with train_len = test_len * train_frac/(1-train_frac) gives the divisor
    # below. Sizing off n_windows alone would silently produce far fewer windows
    # than requested, understating how many regimes the strategy was tested across.
    ratio = train_frac / (1.0 - train_frac)
    test_len = int(n / (n_windows + ratio))
    train_len = int(test_len * ratio)

    if test_len < 10 or train_len < 10:
        raise ValueError(
            f"Not enough bars ({n}) for {n_windows} walk-forward windows "
            f"(need ~{int((n_windows + ratio) * 10)} minimum). "
            f"Use a longer --days range or fewer --wf-windows."
        )

    windows = []
    all_oos_trades = []
    start = 0
    while start + train_len + test_len <= n:
        train_end = start + train_len
        test_end = train_end + test_len

        tr_trades, _, _ = simulate(df, max(start, 1), train_end, starting_balance, **kw)
        te_trades, _, te_open = simulate(df, train_end, test_end, starting_balance, **kw)

        windows.append({
            "window": len(windows) + 1,
            "train_start": df["time"].iloc[start],
            "test_start": df["time"].iloc[train_end],
            "test_end": df["time"].iloc[test_end - 1],
            "train_metrics": metrics.compute(tr_trades, resolution, starting_balance,
                                             bars_elapsed=train_len),
            "test_metrics": metrics.compute(te_trades, resolution, starting_balance,
                                            bars_elapsed=test_len),
            "position_open_at_end": te_open is not None,
        })
        all_oos_trades.extend(te_trades)
        # Advance by test_len, not by train_len+test_len: the train window slides
        # forward to sit immediately before the next test slice. Test slices remain
        # contiguous and non-overlapping (so the concatenated OOS record is a real
        # continuous out-of-sample history), while train windows overlap each other,
        # which is the standard rolling walk-forward geometry. Advancing by the full
        # window instead would discard train_len bars of testable history per step.
        start += test_len

    if not windows:
        raise ValueError("Walk-forward produced no complete windows; widen the date range.")

    oos_pnls = [w["test_metrics"]["total_pnl"] for w in windows]
    oos_sharpes = [w["test_metrics"]["sharpe"] for w in windows]
    profitable = sum(1 for p in oos_pnls if p > 0)

    # Aggregate OOS record: every test slice stitched together chronologically.
    #
    # Each window is simulated from the same starting_balance so windows stay
    # independent and comparable, which means summing their PnL can imply a
    # balance below zero - an artifact of the summation, not a real ruin event.
    # Reporting the aggregate as a compounded RETURN instead keeps it honest:
    # each window's return is applied in sequence to a single running balance.
    compounded = starting_balance
    for w in windows:
        compounded *= (1.0 + w["test_metrics"]["return_pct"] / 100.0)

    aggregate = metrics.compute(
        all_oos_trades, resolution, starting_balance,
        n_trials=n_trials, bars_elapsed=len(windows) * test_len,
    )
    aggregate["compounded_balance"] = round(compounded, 2)
    aggregate["compounded_return_pct"] = round((compounded / starting_balance - 1) * 100, 2)
    aggregate["windows_summed_note"] = (
        "total_pnl sums independent windows that each start at the opening balance; "
        "compounded_balance chains their returns instead and is the realistic figure."
    )

    return {
        "mode": "walk_forward",
        "n_windows": len(windows),
        "train_bars": train_len,
        "test_bars": test_len,
        "windows": windows,
        "aggregate_oos": aggregate,
        "consistency": {
            "profitable_windows": profitable,
            "total_windows": len(windows),
            "profitable_pct": round(profitable / len(windows) * 100, 1),
            "best_window_pnl": round(max(oos_pnls), 2),
            "worst_window_pnl": round(min(oos_pnls), 2),
            "median_window_pnl": round(float(np.median(oos_pnls)), 2),
            "mean_window_sharpe": round(float(np.mean(oos_sharpes)), 3),
            "sharpe_std_across_windows": round(float(np.std(oos_sharpes, ddof=1)), 3) if len(windows) > 1 else 0.0,
        },
        "trades": all_oos_trades,
    }


def run_backtest(epic, resolution, start, end, starting_balance, source="dukascopy",
                 mode="wf", split=IN_SAMPLE_FRACTION, n_windows=8, n_trials=1, **sim):
    df = data.fetch(source, epic, resolution, start, end)

    if len(df) < 60:
        raise ValueError(
            f"Only {len(df)} candles returned for {epic}/{resolution} from {source} "
            f"in that range - too few to backtest."
        )

    df = strategy.add_indicators(df)
    spread = data.spread_summary(df)

    sim.setdefault("epic", epic)

    if mode == "split":
        result = run_split(df, resolution, starting_balance, split=split, n_trials=n_trials, **sim)
    else:
        result = run_walk_forward(df, resolution, starting_balance, n_windows=n_windows,
                                  n_trials=n_trials, **sim)

    result.update({
        "epic": epic,
        "resolution": resolution,
        "source": source,
        "candle_count": len(df),
        "date_range": (df["time"].iloc[0], df["time"].iloc[-1]),
        "spread": spread,
        "starting_balance": starting_balance,
    })
    return result


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _print_metrics(label, m, indent="  "):
    inf = float("inf")
    pf = "inf" if m["profit_factor"] == inf else f"{m['profit_factor']}"
    print(f"{indent}{label}")
    print(f"{indent}  Trades:        {m['total_trades']}  ({m['wins']}W / {m['losses']}L, {m['win_rate_pct']}% win)")
    print(f"{indent}  Net PnL:       ${m['total_pnl']:,.2f}  ({m['return_pct']:+.2f}%)  -> ${m['final_balance']:,.2f}")
    print(f"{indent}  Profit factor: {pf}   Expectancy: ${m['expectancy']:.2f}/trade")
    print(f"{indent}  Avg win/loss:  ${m['avg_win']:.2f} / ${m['avg_loss']:.2f}")
    print(f"{indent}  Sharpe:        {m['sharpe']}   Sortino: {m['sortino']}")
    print(f"{indent}  PSR:           {m['psr']:.3f}   DSR({m['n_trials']} trials): {m['dsr']:.3f}")
    print(f"{indent}  Max drawdown:  ${m['max_drawdown']:,.2f} ({m['max_drawdown_pct']:.2f}%), "
          f"longest {m['longest_drawdown_trades']} trades")
    print(f"{indent}  Avg hold:      {m['avg_holding_minutes_wins']}min W / {m['avg_holding_minutes_losses']}min L")


def print_report(result):
    print(f"\n{'=' * 78}")
    print(f"{result['epic']} / {result['resolution']} via {result['source']} — "
          f"{result['candle_count']:,} candles")
    print(f"{result['date_range'][0]} to {result['date_range'][1]}")
    if result.get("spread"):
        s = result["spread"]
        print(f"Spread: mean ${s['mean']} / median ${s['median']} / p95 ${s['p95']} "
              f"({s['mean_pct_of_price']}% of price)")
    print("=" * 78)

    if result["mode"] == "split":
        print(f"\nChronological split at {result['split_date']}\n")
        _print_metrics("IN-SAMPLE (tuning)", result["in_sample"]["metrics"])
        print()
        _print_metrics("OUT-OF-SAMPLE (validation only)", result["out_of_sample"]["metrics"])
        if result["in_sample"]["position_open_at_end"] or result["out_of_sample"]["position_open_at_end"]:
            print("\nNote: a position was still open at the end of a period and is excluded from its metrics.")
        return

    c = result["consistency"]
    print(f"\nWALK-FORWARD: {result['n_windows']} windows "
          f"({result['train_bars']} train / {result['test_bars']} test bars each)\n")

    print(f"  {'Win':>3}  {'Test period':<26} {'Trades':>6} {'PnL':>11} {'Sharpe':>7}  {'Win%':>5}")
    print(f"  {'-' * 68}")
    for w in result["windows"]:
        m = w["test_metrics"]
        period = f"{w['test_start']:%Y-%m-%d} to {w['test_end']:%Y-%m-%d}"
        flag = " " if m["total_pnl"] > 0 else "*"
        print(f"  {w['window']:>3}{flag} {period:<26} {m['total_trades']:>6} "
              f"${m['total_pnl']:>10,.2f} {m['sharpe']:>7.3f}  {m['win_rate_pct']:>4.1f}%")
    print(f"  {'-' * 68}")
    print(f"  (* = losing window)\n")

    print(f"  CONSISTENCY")
    print(f"    Profitable windows:  {c['profitable_windows']}/{c['total_windows']} ({c['profitable_pct']}%)")
    print(f"    Best / worst window: ${c['best_window_pnl']:,.2f} / ${c['worst_window_pnl']:,.2f}")
    print(f"    Median window:       ${c['median_window_pnl']:,.2f}")
    print(f"    Sharpe across windows: mean {c['mean_window_sharpe']}, std {c['sharpe_std_across_windows']}")
    print()
    _print_metrics("AGGREGATE OUT-OF-SAMPLE (all test slices combined)", result["aggregate_oos"])
    agg = result["aggregate_oos"]
    if "compounded_balance" in agg:
        print(f"    Compounded:    ${agg['compounded_balance']:,.2f} "
              f"({agg['compounded_return_pct']:+.2f}%) — windows chained rather than summed")

    n_trials = result["aggregate_oos"]["n_trials"]
    dsr = result["aggregate_oos"]["dsr"]
    print(f"\n  VERDICT")
    if n_trials > 1:
        hurdle = metrics.expected_max_sharpe(n_trials)
        print(f"    Selection-bias hurdle: a zero-edge strategy would be expected to show")
        print(f"    Sharpe ~{hurdle:.2f} as the best of {n_trials} trials.")
    if dsr >= 0.95:
        print(f"    DSR {dsr:.3f} >= 0.95 — result is statistically significant.")
    elif dsr >= 0.80:
        print(f"    DSR {dsr:.3f} — suggestive but below the 0.95 bar. Not yet evidence of an edge.")
    else:
        print(f"    DSR {dsr:.3f} < 0.80 — NOT significant. Consistent with no real edge.")
    if c["profitable_pct"] < 60:
        print(f"    Only {c['profitable_pct']}% of windows profitable — inconsistent across regimes.")


def _json_default(o):
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    if isinstance(o, (np.integer, np.floating)):
        return o.item()
    raise TypeError(f"Not JSON serializable: {type(o)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest the live strategy against historical OHLC.")
    parser.add_argument("--epic", default=config.EPICS[0])
    parser.add_argument("--resolution", default=config.RESOLUTION)
    parser.add_argument("--source", choices=sorted(data.SOURCES), default="dukascopy",
                        help="dukascopy = deep history, ECN spreads. capital = the live broker's own feed.")
    parser.add_argument("--days", type=int, default=730, help="Lookback window in days from now.")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting account balance.")
    parser.add_argument("--mode", choices=["wf", "split"], default="wf",
                        help="wf = walk-forward across many windows (default). split = single IS/OOS cut.")
    parser.add_argument("--wf-windows", type=int, default=8, help="Number of walk-forward windows.")
    parser.add_argument("--split", type=float, default=IN_SAMPLE_FRACTION,
                        help="In-sample fraction for --mode split.")
    parser.add_argument("--trials", type=int, default=1,
                        help="Honest count of strategy variants evaluated so far, for the Deflated Sharpe Ratio.")
    parser.add_argument("--spread", choices=["historical", "none"], default="historical",
                        help="'historical' charges the real recorded bid/ask; 'none' trades at midprice.")
    parser.add_argument("--slippage", type=float, default=0.0,
                        help="Extra points added against you on every fill.")
    parser.add_argument("--swap-rate", type=float, default=DEFAULT_SWAP_RATE_DAILY_PCT,
                        help="Daily overnight financing as %% of notional (negative = cost). 0 disables.")
    parser.add_argument("--entry-delay", type=int, default=1,
                        help="Bars between signal and fill. 1 (default) is realistic; 0 is look-ahead biased.")
    parser.add_argument("--optimistic-fill", action="store_true",
                        help="When SL and TP are both inside one bar, assume TP. Default assumes SL.")
    parser.add_argument("--fx-rate", type=float, default=1.0,
                        help="Quote-currency to account-currency rate (e.g. 1.39 for USD-quoted "
                             "metals on a CAD account). Must match what the live bot uses or "
                             "position sizes will not reflect live behaviour.")
    parser.add_argument("--json", metavar="PATH", help="Write the full result (including trades) to a JSON file.")
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    start = end - timedelta(days=args.days)

    result = run_backtest(
        args.epic, args.resolution, start, end, args.balance,
        source=args.source, mode=args.mode, split=args.split,
        n_windows=args.wf_windows, n_trials=args.trials,
        spread_mode=args.spread, slippage_points=args.slippage,
        entry_delay_bars=args.entry_delay,
        conservative_fill=not args.optimistic_fill,
        swap_rate_daily_pct=args.swap_rate,
        quote_to_account_rate=args.fx_rate,
    )

    print_report(result)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2, default=_json_default)
        print(f"\nFull result written to {args.json}")
