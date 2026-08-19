"""Checks for the confluence scoring in signals.py.
Run: .venv/bin/python test_signals.py
"""
import numpy as np
import pandas as pd

import config
import signals


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise AssertionError(f"{name}: {detail}")


ALL_BULLISH = {
    "htf_bias": 1, "structure_break": 1, "liquidity_grab": 1,
    "fvg": 1, "pattern": 1, "in_overlap": 1,
}


def test_scoring():
    print("\nScoring")
    check("weights sum to 100", sum(signals.DEFAULT_WEIGHTS.values()) == 100,
          str(sum(signals.DEFAULT_WEIGHTS.values())))

    score, why = signals.score_row(ALL_BULLISH, "BUY")
    check("every confluence aligned scores 100", score == 100, f"{score} {why}")

    # Session is deliberately DIRECTIONLESS: the London/NY overlap is a
    # volatility/liquidity condition, not a directional one, so it scores for both
    # sides. Every other component must only pay when it agrees with the trade.
    score, why = signals.score_row(ALL_BULLISH, "SELL")
    check("bullish confluence pays a SELL only base + session", score == 35, f"{score} {why}")
    check("no directional component credited a SELL",
          set(why) == {"base", "session"}, str(why))

    no_overlap = dict(ALL_BULLISH, in_overlap=0)
    score, why = signals.score_row(no_overlap, "SELL")
    check("outside the overlap a contradicted setup scores base only", score == 30, f"{score} {why}")

    score, _ = signals.score_row({}, "BUY")
    check("missing feature columns degrade to the base score", score == 30, str(score))


def test_htf_veto():
    print("\nHigher-timeframe veto")
    score, why = signals.score_row({"htf_bias": -1}, "BUY", require_htf=True)
    check("a setup fighting HTF bias is vetoed to 0", score == 0 and "vetoed" in why, str(why))

    score, _ = signals.score_row({"htf_bias": 0}, "BUY", require_htf=True)
    check("a neutral HTF bias does not veto", score == 30, str(score))

    score, _ = signals.score_row({"htf_bias": 1}, "BUY", require_htf=True)
    check("an aligned HTF bias scores base + htf", score == 55, str(score))

    # The veto must beat any amount of other confluence: being on the wrong side of
    # the higher timeframe is a structural objection, not one more vote.
    score, _ = signals.score_row(dict(ALL_BULLISH, htf_bias=-1), "BUY", require_htf=True)
    check("veto overrides every other confirmation", score == 0, str(score))


def _slice(**cols):
    """A 2-row frame shaped like what generate_signal receives, rigged so the base
    EMA rule fires a BUY on the last row."""
    base = {
        "ema_fast": [1.0, 2.0], "ema_slow": [1.5, 1.5],
        "rsi": [50.0, 50.0], "close": [100.0, 101.0],
    }
    for k, v in cols.items():
        base[k] = [v, v]
    return pd.DataFrame(base)


def test_signal_fn_contract():
    print("\ngenerate_signal contract")
    fn = signals.make_signal_fn(min_confidence=0)
    check("a crossing bar fires BUY at threshold 0", fn(_slice()) == "BUY")

    fn_high = signals.make_signal_fn(min_confidence=90)
    check("the same bar is filtered out at threshold 90", fn_high(_slice()) is None)

    fn_htf = signals.make_signal_fn(min_confidence=0, require_htf=True)
    check("aligned HTF passes the veto", fn_htf(_slice(htf_bias=1)) == "BUY")
    check("opposed HTF is vetoed", fn_htf(_slice(htf_bias=-1)) is None)

    veto_only = signals.htf_filter_only()
    check("htf_filter_only passes when aligned", veto_only(_slice(htf_bias=1)) == "BUY")
    check("htf_filter_only blocks when opposed", veto_only(_slice(htf_bias=-1)) is None)
    check("htf_filter_only passes when HTF is neutral", veto_only(_slice(htf_bias=0)) == "BUY")

    scored = signals.make_signal_fn(min_confidence=0, return_score=True)
    out = scored(_slice(htf_bias=1))
    check("return_score exposes the score and its reasons",
          isinstance(out, tuple) and out[0] == "BUY" and out[1] == 55, str(out))

    check("a non-crossing bar returns None",
          fn(pd.DataFrame({"ema_fast": [1.0, 1.0], "ema_slow": [1.5, 1.5],
                           "rsi": [50.0, 50.0], "close": [100.0, 100.0]})) is None)


def test_base_matches_live():
    """signals.base_signal duplicates the live rule; the duplicate must not drift."""
    print("\nBase rule parity")
    import strategy

    rng = np.random.default_rng(5)
    mismatches = 0
    for _ in range(400):
        df = pd.DataFrame({
            "ema_fast": rng.normal(100, 2, 2),
            "ema_slow": rng.normal(100, 2, 2),
            "rsi": rng.uniform(20, 80, 2),
            "close": rng.normal(100, 2, 2),
        })
        if strategy.generate_signal(df) != signals.base_signal(df):
            mismatches += 1
    check("signals.base_signal matches strategy.generate_signal on random inputs",
          mismatches == 0, f"{mismatches}/400 disagreed")


if __name__ == "__main__":
    print("=" * 70)
    print("SIGNAL SCORING CHECKS")
    print("=" * 70)
    test_scoring()
    test_htf_veto()
    test_signal_fn_contract()
    test_base_matches_live()
    print("\n" + "=" * 70)
    print("ALL CHECKS PASSED")
    print("=" * 70)
