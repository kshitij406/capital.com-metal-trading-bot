"""Look-ahead checks for features.py. Run: .venv/bin/python test_features.py

The single property that matters for every feature column: the value at bar i must
depend only on bars <= i. A feature that reads bar i+1 makes a backtest look
brilliant and a live bot lose money, and nothing in the PnL output reveals it.

The test is causality by truncation: compute a feature on the full series, then
recompute it on a prefix, and require the overlapping values to be identical. If
a column peeks ahead, appending future bars changes its historical values and the
comparison fails.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import features
import strategy


def _df(n=1200, seed=3):
    rng = np.random.default_rng(seed)
    price = 4000.0
    rows = []
    t0 = datetime(2025, 1, 1)
    for i in range(n):
        price = max(price + rng.normal(0, 4.0), 100.0)
        rows.append({
            "time": t0 + timedelta(minutes=15 * i),
            "open": price + rng.normal(0, 1),
            "high": price + abs(rng.normal(0, 3)),
            "low": price - abs(rng.normal(0, 3)),
            "close": price,
            "close_bid": price - 0.3, "close_ask": price + 0.3,
            "volume": 100.0,
        })
    df = pd.DataFrame(rows)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return strategy.add_indicators(df)


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise AssertionError(f"{name}: {detail}")


def test_no_lookahead_per_feature():
    """Truncation test: values computed on a prefix must match those computed on
    the full series, for every bar the prefix contains."""
    print("\nCausality (no feature may read a future bar)")
    full = _df()
    cut = 900

    for feat in tuple(features.ALL_FEATURES) + ("tod_vol", "vol_regime"):
        whole = features.add_all(full.copy(), features=(feat,))
        prefix = features.add_all(full.iloc[:cut].copy(), features=(feat,))

        for col in features.FEATURE_COLUMNS[feat]:
            a = whole[col].iloc[:cut].reset_index(drop=True)
            b = prefix[col].reset_index(drop=True)

            # Compare only where the prefix produced a value; warm-up NaNs differ
            # legitimately at the very start of a rolling window.
            both = a.notna() & b.notna()
            if not both.any():
                check(f"{feat}.{col} produced values", False, "all NaN")
                continue

            if np.issubdtype(a.dtype, np.number):
                same = np.allclose(a[both].astype(float), b[both].astype(float), atol=1e-9)
            else:
                same = a[both].equals(b[both])

            n_diff = int((~np.isclose(a[both].astype(float), b[both].astype(float), atol=1e-9)).sum()) \
                if np.issubdtype(a.dtype, np.number) else -1
            check(f"{feat}.{col} is causal", same,
                  "" if same else f"{n_diff} of {int(both.sum())} overlapping values changed when future bars were appended")


def test_htf_shift():
    """The HTF bias must lag: a 15m bar may not see the 4h candle it sits inside."""
    print("\nHigher-timeframe bias")
    df = _df()
    out = features.add_htf_bias(df, rule="4h")
    check("htf_bias only takes values in {-1,0,1}",
          set(out["htf_bias"].unique()) <= {-1, 0, 1}, f"{sorted(set(out['htf_bias'].unique()))}")
    check("htf_bias is not constant", out["htf_bias"].nunique() > 1,
          f"{out['htf_bias'].value_counts().to_dict()}")

    # The bias attached to a bar must equal the bias of a COMPLETED earlier 4h bar,
    # never the one still forming.
    htf = (df.set_index("time").resample("4h")
             .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna())
    ef = htf["close"].ewm(span=9, adjust=False).mean()
    es = htf["close"].ewm(span=21, adjust=False).mean()
    current = np.sign(ef - es).astype(int)

    merged = out.set_index("time")
    mismatches = 0
    for ts in htf.index[30:60]:
        window = merged.loc[(merged.index >= ts) & (merged.index < ts + pd.Timedelta("4h"))]
        if window.empty:
            continue
        # Bars inside this 4h candle must NOT carry this candle's own bias value
        # unless the previous candle happened to share it.
        if len(set(window["htf_bias"])) == 1 and window["htf_bias"].iloc[0] == current.loc[ts]:
            prev_ts = ts - pd.Timedelta("4h")
            if prev_ts in current.index and current.loc[prev_ts] != current.loc[ts]:
                mismatches += 1
    check("htf_bias lags by one HTF bar", mismatches == 0,
          f"{mismatches} windows carried the in-progress candle's own bias")


def test_feature_semantics():
    print("\nFeature semantics")
    df = _df()
    out = features.add_all(df.copy())

    for col, allowed in (("structure_break", {-1, 0, 1}), ("liquidity_grab", {-1, 0, 1}),
                         ("fvg", {-1, 0, 1}), ("pattern", {-1, 0, 1}), ("choch", {0, 1})):
        check(f"{col} takes only {sorted(allowed)}", set(out[col].unique()) <= allowed,
              f"got {sorted(set(out[col].unique()))}")

    check("some structure breaks detected", (out["structure_break"] != 0).sum() > 0,
          f"{(out['structure_break'] != 0).sum()} bars")
    check("some patterns detected", (out["pattern"] != 0).sum() > 0,
          f"{(out['pattern'] != 0).sum()} bars")
    check("session overlap is a subset of both sessions",
          bool((out["in_overlap"] <= (out["in_london"] & out["in_newyork"])).all()))

    # A swing high, once confirmed, must never exceed the running max of the bars
    # that produced it - a cheap sanity check that levels are real prices.
    sh = out["swing_high"].dropna()
    check("swing highs are real prices from the series",
          bool(sh.isin(out["high"]).all()), f"{(~sh.isin(out['high'])).sum()} synthetic values")


def test_features_are_optional():
    print("\nComposition")
    df = _df()
    only_htf = features.add_all(df.copy(), features=("htf",))
    check("requesting one feature adds only its columns",
          "htf_bias" in only_htf.columns and "fvg" not in only_htf.columns)
    check("base columns survive feature attachment",
          all(c in only_htf.columns for c in ("open", "high", "low", "close", "atr")))
    # add_all defaults to ALL_FEATURES; the volatility features are opt-in, so ask
    # for every declared feature explicitly rather than assuming the default set.
    all_feats = tuple(features.FEATURE_COLUMNS)
    everything = features.add_all(df.copy(), features=all_feats)
    expected = [c for cols in features.FEATURE_COLUMNS.values() for c in cols]
    check("add_all attaches every declared column",
          all(c in everything.columns for c in expected),
          f"missing {[c for c in expected if c not in everything.columns]}")


if __name__ == "__main__":
    print("=" * 70)
    print("FEATURE CAUSALITY CHECKS")
    print("=" * 70)
    test_no_lookahead_per_feature()
    test_htf_shift()
    test_feature_semantics()
    test_features_are_optional()
    print("\n" + "=" * 70)
    print("ALL CHECKS PASSED")
    print("=" * 70)
