"""Forward-test progress and backtest reconciliation. Never imported by bot.py.

Run: .venv/bin/python forward_test.py

A forward test answers a question a backtest cannot: do live fills, live spreads and
live timing match what was simulated? This module compares the two directly rather
than just reporting live PnL, because live PnL on its own cannot distinguish "the
edge is not real" from "the edge is real but execution is worse than modelled".

Three sections:

  PROGRESS      how far through the test we are, against the sample size actually
                needed for the result to mean anything
  DECISIONS     what the gates did - how often each one blocked a trade. If the
                distribution here does not resemble the backtest's, live and
                simulated logic have diverged and the PnL comparison is meaningless
  RECONCILIATION live outcomes vs the backtested expectation for the same rule
"""
import argparse
import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np

import config

# Backtested expectation for STRATEGY="vol_regime" on GOLD, measured 2026-08-18 over
# 4 years of 15m Dukascopy data with walk-forward validation, spread + slippage + swap,
# and volatility-managed sizing, at VOL_REGIME_MIN=1.05. These are the numbers the
# forward test is checking. Percentage metrics (win rate, profit factor, Sharpe) are
# risk-level independent, so they hold at 3% risk even though the backtest that
# produced them ran at 1%.
BACKTEST_EXPECTATION = {
    "trades_per_year": 39.5,
    "win_rate_pct": 40.5,
    "profit_factor": 1.36,
    "max_drawdown_pct": -3.7,
    "sharpe": 1.239,
}

# A forward test needs enough trades for its win rate to be distinguishable from the
# baseline's. At ~40 trades/year that is ~9 months for a first read - stating it
# plainly is the point, because the most likely way this test fails is being called
# early on a sample far too small to say anything.
MIN_TRADES_FOR_SIGNAL = 30
MIN_TRADES_FOR_CONFIDENCE = 100


def _connect():
    return sqlite3.connect(config.DB_PATH)


def load_forward_trades(since=None):
    """Closed trades logged under the forward-test strategy.

    Filtered by the trades table's own strategy column, not by date. Date alone is
    not enough: baseline trades opened on the same day the forward test starts would
    otherwise be counted as forward-test results and flatter (or damn) it unfairly.
    Rows written before this column existed are NULL and correctly excluded.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, epic, direction, size, entry_price, close_price, pnl, "
            "close_reason, status FROM trades "
            "WHERE close_price IS NOT NULL AND strategy = 'vol_regime' "
            "AND timestamp >= ? ORDER BY timestamp",
            (since or "2026-08-18",),
        ).fetchall()
    return rows


def load_decisions(since=None):
    with _connect() as conn:
        return conn.execute(
            "SELECT timestamp, epic, gate, vol_regime, hour_utc, base_signal, "
            "signal_generated, size_multiplier FROM signals "
            "WHERE strategy = 'vol_regime' AND timestamp >= ? ORDER BY timestamp",
            (since or "2026-08-18",),
        ).fetchall()


def summarize(trades):
    if not trades:
        return None
    pnls = np.array([t[6] for t in trades if t[6] is not None], dtype=float)
    if len(pnls) == 0:
        return None
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    gross_win, gross_loss = wins.sum(), abs(losses.sum())

    equity = np.concatenate([[0.0], np.cumsum(pnls)])
    peak = np.maximum.accumulate(equity)
    dd = equity - peak

    first = datetime.fromisoformat(trades[0][0])
    last = datetime.fromisoformat(trades[-1][0])
    days = max((last - first).days, 1)

    return {
        "trades": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(pnls) * 100, 1),
        "total_pnl": round(float(pnls.sum()), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        "expectancy": round(float(pnls.mean()), 2),
        "max_drawdown": round(float(dd.min()), 2),
        "days_running": days,
        "trades_per_year": round(len(pnls) / days * 365, 1),
        "sharpe": round(float(pnls.mean() / pnls.std() * np.sqrt(252)), 3) if len(pnls) > 1 and pnls.std() else 0.0,
    }


def print_progress(live):
    print("\nPROGRESS")
    if not live:
        print("  No closed forward-test trades yet.")
        per_month = BACKTEST_EXPECTATION["trades_per_year"] / 12
        print(f"  Expect roughly {BACKTEST_EXPECTATION['trades_per_year']:.0f} trades/year "
              f"(~{per_month:.1f}/month) on GOLD alone.")
        return

    n = live["trades"]
    print(f"  {n} closed trades over {live['days_running']} days "
          f"({live['trades_per_year']:.1f}/year pace)")

    for label, target in (("first read", MIN_TRADES_FOR_SIGNAL),
                          ("confidence", MIN_TRADES_FOR_CONFIDENCE)):
        if n >= target:
            print(f"  [reached] {target} trades for a {label}")
        else:
            need = target - n
            eta_days = need / max(live["trades_per_year"] / 365, 1e-9)
            print(f"  [pending] {need} more trades for a {label} "
                  f"(~{eta_days / 30:.1f} months at current pace)")


def print_decisions(decisions):
    print("\nDECISIONS")
    if not decisions:
        print("  No forward-test decisions logged yet.")
        return

    gates = {}
    for row in decisions:
        gates[row[2] or "unknown"] = gates.get(row[2] or "unknown", 0) + 1
    total = len(decisions)

    print(f"  {total} decision points logged")
    for gate, count in sorted(gates.items(), key=lambda kv: -kv[1]):
        print(f"    {gate:26} {count:>6}  ({count / total * 100:5.1f}%)")

    passed = gates.get("passed", 0)
    if passed:
        regimes = [r[3] for r in decisions if r[2] == "passed" and r[3] is not None]
        mults = [r[7] for r in decisions if r[2] == "passed" and r[7] is not None]
        if regimes:
            print(f"  vol_regime when passed: min {min(regimes):.2f} / "
                  f"mean {np.mean(regimes):.2f} / max {max(regimes):.2f}")
        if mults:
            print(f"  size multiplier:        min {min(mults):.2f} / "
                  f"mean {np.mean(mults):.2f} / max {max(mults):.2f}")

    # A gate that never fires means the live rule is not the rule that was tested.
    for expected in ("outside_macro_hours", "vol_regime_too_low", "no_base_signal"):
        if expected not in gates:
            print(f"  NOTE: gate '{expected}' has never fired - verify the live rule "
                  f"matches the backtested one.")


def print_reconciliation(live):
    print("\nRECONCILIATION vs BACKTEST")
    exp = BACKTEST_EXPECTATION

    if not live or live["trades"] < 5:
        print("  Too few closed trades to compare. The backtested expectation is:")
        for k, v in exp.items():
            print(f"    {k:36} {v}")
        return

    rows = [
        ("win rate %", live["win_rate_pct"], exp["win_rate_pct"]),
        ("profit factor", live["profit_factor"], exp["profit_factor"]),
        ("trades/year", live["trades_per_year"], exp["trades_per_year"]),
        ("sharpe", live["sharpe"], exp["sharpe"]),
    ]
    print(f"  {'metric':<20}{'live':>10}{'backtest':>11}{'delta':>10}")
    for name, l, b in rows:
        if l == float("inf"):
            print(f"  {name:<20}{'inf':>10}{b:>11}{'—':>10}")
        else:
            print(f"  {name:<20}{l:>10.2f}{b:>11.2f}{l - b:>+10.2f}")

    if live["trades"] < MIN_TRADES_FOR_SIGNAL:
        print(f"\n  WARNING: {live['trades']} trades is below the {MIN_TRADES_FOR_SIGNAL} "
              f"needed for even a first read.")
        print("  Differences at this sample size are noise. Do not act on them.")
    elif live["profit_factor"] < 1.0:
        print("\n  Live profit factor is below 1.0 — the strategy is losing money live.")
        print("  Check the DECISIONS section first: if the gate distribution differs from")
        print("  the backtest, the live rule diverged rather than the edge failing.")
    else:
        print("\n  Live profit factor is above 1.0 and the sample is large enough for a")
        print("  first read. Continue to 100 trades before drawing a conclusion.")


def main():
    parser = argparse.ArgumentParser(description="Forward-test progress and reconciliation.")
    parser.add_argument("--since", default="2026-08-18",
                        help="ISO date the forward test started.")
    args = parser.parse_args()

    print("=" * 70)
    print(f"FORWARD TEST — strategy={config.STRATEGY}, epics={config.EPICS}")
    print(f"vol_regime >= {config.VOL_REGIME_MIN}, macro hours {config.MACRO_HOURS_UTC} UTC, "
          f"vol-managed sizing={config.VOL_MANAGED_SIZING}")
    print("=" * 70)

    trades = load_forward_trades(args.since)
    decisions = load_decisions(args.since)
    live = summarize(trades)

    print_progress(live)
    print_decisions(decisions)
    print_reconciliation(live)
    print()


if __name__ == "__main__":
    main()
