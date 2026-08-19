"""Compare strategy variants on identical data, fills and costs.

Run: .venv/bin/python compare.py --epic GOLD --days 730

Why a dedicated harness rather than running backtest.py repeatedly: every variant
must see the same bars, the same spread, the same slippage and the same swap, or
the comparison measures the settings instead of the strategy. This module fetches
once and reuses the frame for all variants.

It also counts trials honestly. Each variant evaluated here is one more draw in a
selection process, and the Deflated Sharpe Ratio for the winner is computed
against the total number tried - not against 1. Reporting the best variant's raw
Sharpe is how a backtest talks you into a strategy that has no edge.
"""
import argparse
from datetime import datetime, timedelta, timezone

import numpy as np

import backtest
import config
import data
import features
import metrics
import signals
import strategy


def build_variants():
    """The variants to evaluate, in the order the research suggested trying them.

    Deliberately incremental: each adds ONE idea to the one before it, so an
    improvement can be attributed. A single 'everything on' variant would show a
    number without revealing which component produced it.
    """
    return [
        ("baseline (live rule)", strategy.generate_signal, ()),
        ("+ HTF veto (4h)", signals.htf_filter_only(), ("htf",)),
        ("+ scoring >=45", signals.make_signal_fn(45), features.ALL_FEATURES),
        ("+ scoring >=55", signals.make_signal_fn(55), features.ALL_FEATURES),
        ("+ scoring >=65", signals.make_signal_fn(65), features.ALL_FEATURES),
        ("+ scoring >=55 + HTF veto", signals.make_signal_fn(55, require_htf=True),
         features.ALL_FEATURES),
        ("+ scoring >=65 + HTF veto", signals.make_signal_fn(65, require_htf=True),
         features.ALL_FEATURES),
    ]


def build_volatility_variants():
    """Volatility-timing variants: same entry rule, different permission to act.

    These test WHEN to trade rather than WHAT to trade, which is a different
    hypothesis from the confluence work and is measured separately so the two
    experiments' trial counts do not contaminate each other.

    Both directions of the hypothesis are included deliberately - "only trade the
    busy hours" and "only trade the calm ones" cannot both be right, and running
    only the one that matches a prior belief is how a backtest gets talked into
    an answer.
    """
    return [
        ("baseline (live rule)", strategy.generate_signal),
        ("macro hours only (12-15 UTC)", signals.volatility_window(macro_hours_only=True)),
        ("avoid quiet hours", signals.volatility_window(avoid_quiet=True)),
        ("busy slots (tod >= 1.2)", signals.volatility_window(min_tod_ratio=1.2)),
        ("quiet-hours only (inverse)", signals.volatility_window(max_tod_ratio=0.9)),
        ("high vol regime (>= 1.2)", signals.volatility_window(min_vol_regime=1.2)),
        ("normal vol regime (0.8-1.2)", signals.volatility_window(min_vol_regime=0.8,
                                                                 max_vol_regime=1.2)),
        ("macro hours + high regime", signals.volatility_window(macro_hours_only=True,
                                                                min_vol_regime=1.1)),
    ]


def run_comparison(epic, resolution, days, balance, source="dukascopy", n_windows=8,
                   fx_rate=1.0, swap_rate=backtest.DEFAULT_SWAP_RATE_DAILY_PCT,
                   slippage=0.0, htf_rule="4h", mode="smc"):
    end = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    start = end - timedelta(days=days)

    df = data.fetch(source, epic, resolution, start, end)
    if len(df) < 60:
        raise ValueError(f"Only {len(df)} candles for {epic} - too few to compare.")

    df = strategy.add_indicators(df)
    if mode == "vol":
        df = features.add_all(df, features=features.VOL_FEATURES, htf_rule=htf_rule)
        variants = [(n, f, ()) for n, f in build_volatility_variants()]
    else:
        df = features.add_all(df, htf_rule=htf_rule)
        variants = build_variants()
    n_trials = len(variants)
    results = []

    for name, fn, _needs in variants:
        res = backtest.run_walk_forward(
            df, resolution, balance, n_windows=n_windows,
            n_trials=n_trials,
            signal_fn=fn, epic=epic, quote_to_account_rate=fx_rate,
            swap_rate_daily_pct=swap_rate, slippage_points=slippage,
            spread_mode="historical", entry_delay_bars=1, conservative_fill=True,
        )
        agg = res["aggregate_oos"]
        cons = res["consistency"]
        results.append({
            "name": name,
            "trades": agg["total_trades"],
            "win_rate": agg["win_rate_pct"],
            "pnl": agg["total_pnl"],
            "compounded_pct": agg.get("compounded_return_pct", 0.0),
            "profit_factor": agg["profit_factor"],
            "sharpe": agg["sharpe"],
            "psr": agg["psr"],
            "dsr": agg["dsr"],
            "max_dd_pct": agg["max_drawdown_pct"],
            "profitable_windows": f"{cons['profitable_windows']}/{cons['total_windows']}",
            "profitable_pct": cons["profitable_pct"],
            "window_pnls": [w["test_metrics"]["total_pnl"] for w in res["windows"]],
        })

    return {
        "epic": epic,
        "resolution": resolution,
        "source": source,
        "candles": len(df),
        "date_range": (df["time"].iloc[0], df["time"].iloc[-1]),
        "n_trials": n_trials,
        "mode": mode,
        "results": results,
    }


def print_comparison(cmp_result):
    print(f"\n{'=' * 100}")
    print(f"{cmp_result['epic']} / {cmp_result['resolution']} via {cmp_result['source']} — "
          f"{cmp_result['candles']:,} candles "
          f"({cmp_result['date_range'][0]:%Y-%m-%d} to {cmp_result['date_range'][1]:%Y-%m-%d})")
    print(f"Walk-forward out-of-sample. {cmp_result['n_trials']} variants evaluated — "
          f"DSR is deflated for all {cmp_result['n_trials']}.")
    print("=" * 100)

    header = (f"  {'Variant':<28} {'Trades':>6} {'Win%':>6} {'PnL':>10} {'PF':>6} "
              f"{'Sharpe':>7} {'DSR':>6} {'MaxDD%':>8} {'Win wins':>9}")
    print(header)
    print("  " + "-" * 98)

    baseline = cmp_result["results"][0]
    for r in cmp_result["results"]:
        pf = "inf" if r["profit_factor"] == float("inf") else f"{r['profit_factor']:.2f}"
        better = "" if r is baseline else (" +" if r["pnl"] > baseline["pnl"] else " -")
        print(f"  {r['name']:<28} {r['trades']:>6} {r['win_rate']:>5.1f}% "
              f"${r['pnl']:>9,.2f} {pf:>6} {r['sharpe']:>7.3f} {r['dsr']:>6.3f} "
              f"{r['max_dd_pct']:>7.1f}% {r['profitable_windows']:>9}{better}")

    print("  " + "-" * 98)

    best = max(cmp_result["results"], key=lambda r: r["pnl"])
    hurdle = metrics.expected_max_sharpe(cmp_result["n_trials"])
    print(f"\n  Best by PnL: {best['name']} (${best['pnl']:,.2f}, DSR {best['dsr']:.3f})")
    print(f"  Selection-bias hurdle: a zero-edge strategy would be expected to reach")
    print(f"  Sharpe ~{hurdle:.2f} as the best of {cmp_result['n_trials']} trials.")

    if best["dsr"] >= 0.95:
        print(f"  DSR {best['dsr']:.3f} >= 0.95 — significant after correcting for selection.")
    else:
        print(f"  DSR {best['dsr']:.3f} < 0.95 — NOT significant. Beating the baseline here is")
        print(f"  not yet evidence of an edge; it is what the best of {cmp_result['n_trials']} tries looks like.")

    if best["pnl"] <= baseline["pnl"]:
        print(f"  No variant beat the baseline (${baseline['pnl']:,.2f}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare strategy variants on identical data.")
    parser.add_argument("--epic", default=config.EPICS[0])
    parser.add_argument("--resolution", default=config.RESOLUTION)
    parser.add_argument("--source", choices=sorted(data.SOURCES), default="dukascopy")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--balance", type=float, default=1000.0)
    parser.add_argument("--wf-windows", type=int, default=8)
    parser.add_argument("--fx-rate", type=float, default=1.0)
    parser.add_argument("--swap-rate", type=float, default=backtest.DEFAULT_SWAP_RATE_DAILY_PCT)
    parser.add_argument("--slippage", type=float, default=0.0)
    parser.add_argument("--htf-rule", default="4h", help="Higher timeframe for the bias filter.")
    parser.add_argument("--mode", choices=["smc", "vol"], default="smc",
                        help="smc = confluence/SMC variants; vol = volatility-timing variants.")
    parser.add_argument("--all-epics", action="store_true",
                        help="Run the comparison for every epic in config.EPICS.")
    args = parser.parse_args()

    epics = config.EPICS if args.all_epics else [args.epic]
    for epic in epics:
        result = run_comparison(
            epic, args.resolution, args.days, args.balance,
            source=args.source, n_windows=args.wf_windows, fx_rate=args.fx_rate,
            swap_rate=args.swap_rate, slippage=args.slippage, htf_rule=args.htf_rule,
            mode=args.mode,
        )
        print_comparison(result)
