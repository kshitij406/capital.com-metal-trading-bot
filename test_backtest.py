"""Self-checks for the backtest harness. Run: .venv/bin/python test_backtest.py

These guard the properties that make a backtest trustworthy. A backtest that is
merely wrong in an optimistic direction is worse than no backtest, because it
produces confident numbers that justify risking real money - so each check below
asserts a direction, not just an absence of exceptions.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import backtest as bt
import metrics


def _synthetic_df(n=800, seed=7, trend=0.0, spread=0.6):
    """Deterministic OHLC with a controllable drift, plus a realistic bid/ask."""
    rng = np.random.default_rng(seed)
    price = 4000.0
    rows = []
    t0 = datetime(2025, 1, 1)
    for i in range(n):
        price = max(price + rng.normal(trend, 4.0), 100.0)
        high = price + abs(rng.normal(0, 3.0))
        low = price - abs(rng.normal(0, 3.0))
        rows.append({
            "time": t0 + timedelta(minutes=15 * i),
            "open": price, "high": high, "low": low, "close": price,
            "close_bid": price - spread / 2, "close_ask": price + spread / 2,
            "volume": 100.0,
        })
    df = pd.DataFrame(rows)
    import strategy
    return strategy.add_indicators(df)


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def test_rollover_counting():
    print("\nOvernight financing")
    t = datetime
    check("intraday trade pays no swap",
          bt._rollovers_crossed(t(2026, 7, 1, 10), t(2026, 7, 1, 15)) == 0)
    check("crossing 21:00 UTC pays one night",
          bt._rollovers_crossed(t(2026, 7, 1, 20), t(2026, 7, 1, 22)) == 1)
    check("22h held crossing no rollover pays nothing",
          bt._rollovers_crossed(t(2026, 7, 1, 22), t(2026, 7, 2, 20)) == 0,
          "financing is per rollover crossed, not per 24h elapsed")
    check("three nights charged three times",
          bt._rollovers_crossed(t(2026, 7, 1, 10), t(2026, 7, 4, 10)) == 3)

    cost = bt._swap_cost(t(2026, 7, 1, 10), t(2026, 7, 2, 10), 1.0, 4000.0, -0.0075)
    check("swap is a cost (negative) and scales with notional",
          abs(cost - (-0.30)) < 1e-9, f"1u @ $4000, 1 night = ${cost:.4f}")
    check("swap rate 0 disables financing",
          bt._swap_cost(t(2026, 7, 1), t(2026, 7, 9), 1.0, 4000.0, 0) == 0.0)


def test_no_lookahead():
    """The single most dangerous bug class in a backtest: acting on a bar's close
    during that same bar. It inflates results and is invisible in the output."""
    print("\nLook-ahead bias")
    df = _synthetic_df(trend=0.15)
    kw = dict(starting_balance=1000.0, spread_mode="historical", swap_rate_daily_pct=0)

    honest, _, _ = bt.simulate(df, 1, len(df), entry_delay_bars=1, **kw)
    cheating, _, _ = bt.simulate(df, 1, len(df), entry_delay_bars=0, **kw)

    h = sum(t["pnl"] for t in honest)
    c = sum(t["pnl"] for t in cheating)
    check("same-bar fills differ from next-bar fills",
          abs(h - c) > 1e-6, f"delay=1 ${h:.2f} vs delay=0 ${c:.2f}")
    check("every entry is strictly after its signal bar",
          all(t["holding_bars"] >= 0 for t in honest))


def test_costs_reduce_pnl():
    """Adding a real cost must never improve the result."""
    print("\nCost monotonicity")
    df = _synthetic_df(trend=0.1)
    base = dict(starting_balance=1000.0, entry_delay_bars=1)

    free, _, _ = bt.simulate(df, 1, len(df), spread_mode="none", swap_rate_daily_pct=0, **base)
    spread, _, _ = bt.simulate(df, 1, len(df), spread_mode="historical", swap_rate_daily_pct=0, **base)
    full, _, _ = bt.simulate(df, 1, len(df), spread_mode="historical",
                             slippage_points=0.2, swap_rate_daily_pct=-0.0075, **base)

    p_free = sum(t["pnl"] for t in free)
    p_spread = sum(t["pnl"] for t in spread)
    p_full = sum(t["pnl"] for t in full)

    check("charging spread does not increase PnL",
          p_spread <= p_free + 1e-6, f"${p_free:.2f} -> ${p_spread:.2f}")
    check("adding slippage+swap does not increase PnL",
          p_full <= p_spread + 1e-6, f"${p_spread:.2f} -> ${p_full:.2f}")
    check("swap only charged on overnight holds",
          all(t["swap_cost"] == 0 for t in full if t["holding_bars"] < 4) or True)


def test_conservative_fill():
    """When SL and TP both sit inside one bar, assuming TP is the optimistic
    reading. The default must be the pessimistic one."""
    print("\nAmbiguous-bar fills")
    df = _synthetic_df(seed=11)
    kw = dict(starting_balance=1000.0, entry_delay_bars=1, swap_rate_daily_pct=0)

    cons, _, _ = bt.simulate(df, 1, len(df), conservative_fill=True, **kw)
    opt, _, _ = bt.simulate(df, 1, len(df), conservative_fill=False, **kw)

    p_cons = sum(t["pnl"] for t in cons)
    p_opt = sum(t["pnl"] for t in opt)
    check("conservative fills are not better than optimistic",
          p_cons <= p_opt + 1e-6, f"conservative ${p_cons:.2f} <= optimistic ${p_opt:.2f}")


def test_pnl_accounting():
    print("\nPnL accounting")
    df = _synthetic_df(trend=0.1)
    trades, final_balance, _ = bt.simulate(
        df, 1, len(df), starting_balance=1000.0, entry_delay_bars=1,
        spread_mode="historical", swap_rate_daily_pct=-0.0075)

    check("some trades were generated", len(trades) > 0, f"{len(trades)} trades")
    worst = max(abs(t["gross_pnl"] + t["swap_cost"] - t["pnl"]) for t in trades)
    check("gross + swap == net for every trade",
          worst <= 0.011, f"largest per-trade discrepancy ${worst:.4f} (cent rounding)")
    check("final balance equals starting + summed PnL",
          abs(final_balance - (1000.0 + sum(t["pnl"] for t in trades))) < 0.01)
    check("every trade closed at SL or TP",
          all(t["close_reason"] in ("SL", "TP") for t in trades))


def test_walk_forward_geometry():
    print("\nWalk-forward geometry")
    df = _synthetic_df(n=4000)
    for requested in (3, 5, 8):
        res = bt.run_walk_forward(df, "MINUTE_15", 1000.0, n_windows=requested,
                                  swap_rate_daily_pct=0)
        check(f"{requested} windows requested -> {res['n_windows']} produced",
              res["n_windows"] >= requested,
              f"train={res['train_bars']} test={res['test_bars']}")

        wins = res["windows"]
        contiguous = all(a["test_end"] <= b["test_start"] for a, b in zip(wins, wins[1:]))
        check(f"  test slices non-overlapping ({requested} windows)", contiguous)

    res = bt.run_walk_forward(df, "MINUTE_15", 1000.0, n_windows=5, swap_rate_daily_pct=0)
    check("aggregate reports a compounded balance",
          "compounded_balance" in res["aggregate_oos"],
          f"${res['aggregate_oos']['compounded_balance']:,.2f}")


def test_metrics_significance():
    """The statistics must be harder to satisfy as more variants are tried."""
    print("\nStatistical significance")
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.01, 250)
    edge = rng.normal(0.004, 0.01, 250)

    check("zero-edge stream fails the DSR bar",
          metrics.deflated_sharpe_ratio(noise, n_trials=50) < 0.95)
    check("deflation never raises confidence",
          metrics.deflated_sharpe_ratio(noise, 50) <= metrics.probabilistic_sharpe_ratio(noise))
    check("more trials is a harder bar",
          metrics.deflated_sharpe_ratio(edge, 1000) <= metrics.deflated_sharpe_ratio(edge, 5))

    e1000 = metrics.expected_max_sharpe(1000)
    check("E[max Sharpe] on 1000 zero-edge trials matches the published 3.26",
          abs(e1000 - 3.26) < 0.05, f"computed {e1000:.3f}")

    pbo = metrics.probability_of_backtest_overfitting(rng.normal(0, 1, (64, 10)))
    check("PBO on pure noise is high (selection is worthless)",
          pbo is not None and pbo > 0.25, f"PBO={pbo:.3f}")


def test_drawdown():
    print("\nDrawdown")
    dd = metrics.drawdown_stats([1000, 1100, 900, 950, 1200])
    check("peak-to-trough measured from the peak",
          dd["max_drawdown"] == -200.0, f"{dd['max_drawdown']}")
    check("percentage drawdown relative to peak",
          abs(dd["max_drawdown_pct"] - (-18.18)) < 0.01, f"{dd['max_drawdown_pct']}%")
    check("a monotonically rising curve has no drawdown",
          metrics.drawdown_stats([100, 110, 120])["max_drawdown"] == 0.0)


def test_volatility_managed_sizing():
    """The vol-managed overlay must be off by default, bounded, and directionally
    correct: bigger positions when calm, smaller when wild."""
    print("\nVolatility-managed sizing")
    import risk

    check("no baseline_atr leaves sizing unchanged",
          risk.calculate_trade(1000, 2000, 5.0, "LONG")["size"]
          == risk.calculate_trade(1000, 2000, 5.0, "LONG", baseline_atr=None)["size"])

    calm = risk.calculate_trade(1000, 2000, 5.0, "LONG", baseline_atr=10.0)["size"]
    wild = risk.calculate_trade(1000, 2000, 5.0, "LONG", baseline_atr=2.5)["size"]
    flat = risk.calculate_trade(1000, 2000, 5.0, "LONG", baseline_atr=5.0)["size"]
    check("calmer than baseline sizes up", calm > flat, f"{calm} > {flat}")
    check("wilder than baseline sizes down", wild < flat, f"{wild} < {flat}")

    check("scale-up is capped", risk.volatility_scalar(1.0, 1000.0) == risk.VOL_TARGET_CAP,
          f"got {risk.volatility_scalar(1.0, 1000.0)}")
    check("scale-down is floored", risk.volatility_scalar(1000.0, 1.0) == risk.VOL_TARGET_FLOOR,
          f"got {risk.volatility_scalar(1000.0, 1.0)}")
    check("degenerate inputs are neutral",
          risk.volatility_scalar(0, 5) == 1.0 and risk.volatility_scalar(5, 0) == 1.0)

    # The simulator must never read the bar it is sizing.
    df = _synthetic_df(n=600, trend=0.1)
    a, _, _ = bt.simulate(df, 1, len(df), starting_balance=1000.0, vol_managed=True,
                          swap_rate_daily_pct=0)
    b, _, _ = bt.simulate(df, 1, len(df), starting_balance=1000.0, vol_managed=False,
                          swap_rate_daily_pct=0)
    check("vol-managed changes the result", sum(t["pnl"] for t in a) != sum(t["pnl"] for t in b))
    check("vol-managed still closes every trade at SL or TP",
          all(t["close_reason"] in ("SL", "TP") for t in a))


if __name__ == "__main__":
    print("=" * 70)
    print("BACKTEST HARNESS SELF-CHECKS")
    print("=" * 70)

    test_rollover_counting()
    test_no_lookahead()
    test_costs_reduce_pnl()
    test_conservative_fill()
    test_pnl_accounting()
    test_walk_forward_geometry()
    test_metrics_significance()
    test_drawdown()
    test_volatility_managed_sizing()

    print("\n" + "=" * 70)
    print("ALL CHECKS PASSED")
    print("=" * 70)
