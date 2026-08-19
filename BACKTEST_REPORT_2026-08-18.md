# Backtest Findings — Metals Bot

**Date:** 2026-08-18
**Scope:** Control baseline for the live EMA-cross strategy, plus seven SMC/confluence variants
**Data:** Dukascopy XAU/XAG/COPPER, 15-minute bars, bid/ask separately sourced
**Verdict:** No variant is statistically significant. Nothing was deployed to live.

---

## 1. Summary

The live EMA-cross + RSI strategy is **unprofitable on all three metals** out-of-sample, and the six SMC features built to improve it (higher-timeframe bias, BOS/CHoCH, liquidity grabs, fair value gaps, candle patterns, session filters) **did not produce a significant edge**.

One variant looked promising on 2 years of gold (+$55.51). Re-run on 4 years, the same variant lost $103.44. That reversal is the central finding of this report.

Three things were established:

1. A rebuilt backtest harness with walk-forward validation and significance testing
2. A measured baseline showing the current live strategy has no edge
3. Evidence that the proposed SMC additions do not fix it

---

## 2. Why the old backtest could not have shown this

The previous harness was sound in its mechanics — it already had entry delay, intrabar SL/TP fills, and real historical spread. Its weakness was **validation method**: a single 70/30 chronological split reports one number from one market regime.

Run today on the same data, that single-split method still reports **+10.32% out-of-sample for gold**. The walk-forward method on the same bars reports **−20.81%**. The split happened to land on a favourable regime.

Two sensitivity runs quantify how much the cost and timing assumptions matter (gold, 2 years, $1,000 account):

| Configuration | Result | Delta vs realistic |
|---|---:|---:|
| Same-bar fills (look-ahead) | +$76.55 | +$379 |
| No spread, no swap | +$58.33 | +$361 |
| **Realistic (next-bar fills, spread + slippage + swap)** | **−$302.65** | — |

Both corrections were already present in the old harness. The point is the magnitude: a ~$380 swing on a $1,000 account from assumptions that are easy to get wrong and invisible in the output.

---

## 3. Baseline — current live strategy

Walk-forward, 8 windows, 2 years, spread + slippage + overnight swap, sized as the live bot sizes (CAD account, USD-quoted metals at 1.39).

| Epic | Trades | Win rate | Net PnL | Profit factor | Windows profitable | DSR |
|---|---:|---:|---:|---:|---:|---:|
| GOLD | 1,112 | 32.5% | −$208.11 | 0.96 | 2/8 | 0.171 |
| SILVER | 1,050 | 30.5% | −$609.21 | 0.88 | 2/8 | 0.023 |
| COPPER | 1,118 | 29.3% | −$859.36 | 0.84 | 3/8 | 0.251 |

**Profit factor below 1.0 on all three.** This is not a near miss — the strategy loses money gross of any judgment call about costs.

Note on sizing: correcting the FX rate from 1.0 to 1.39 shrank the losses (smaller positions) but left profit factors **identical** at 0.96 / 0.88 / 0.84. Sizing scales magnitude, not edge.

---

## 4. Variant comparison — GOLD, 2 years

All seven variants run on identical bars, fills, and costs. DSR deflated for all 7 trials.

| Variant | Trades | Win% | PnL | PF | Sharpe | DSR | Max DD | Windows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (live rule) | 1,112 | 32.5% | −$208.11 | 0.96 | −0.422 | 0.171 | −41.4% | 2/8 |
| + HTF veto (4h) | 681 | 32.6% | −$88.43 | 0.97 | −0.196 | 0.281 | −34.4% | 3/8 |
| + scoring ≥45 | 859 | 32.9% | −$97.13 | 0.97 | −0.191 | 0.272 | −29.1% | 4/8 |
| **+ scoring ≥55** | 756 | 33.9% | **+$55.51** | 1.02 | 0.328 | 0.487 | −25.8% | 4/8 |
| + scoring ≥65 | 307 | 32.9% | −$21.76 | 0.98 | −0.044 | 0.390 | −22.1% | 3/8 |
| + scoring ≥55 + HTF veto | 681 | 32.6% | −$88.43 | 0.97 | −0.196 | 0.281 | −34.4% | 3/8 |
| + scoring ≥65 + HTF veto | 307 | 32.9% | −$21.76 | 0.98 | −0.044 | 0.390 | −22.1% | 3/8 |

Every variant beats the baseline. One turns positive. Taken alone, this table would look like a successful result.

> **Why the duplicate rows are not a bug.** The HTF veto is strict enough that everything surviving it already scores ≥55 — the HTF component alone contributes 25 of the 30 points needed above base. Verified directly: `scoring ≥55 + HTF veto` and `HTF veto` alone emit an identical 602 BUY / 405 SELL signals. The variants genuinely collapse to the same rule.

---

## 5. The reversal — same variants, 4 years

| Variant | 2-year PnL | 4-year PnL | Outcome |
|---|---:|---:|---|
| baseline | −$208.11 | −$484.10 | consistently negative |
| + HTF veto | −$88.43 | −$226.65 | consistently negative |
| **+ scoring ≥55** | **+$55.51** | **−$103.44** | **reversed** |
| + scoring ≥65 | −$21.76 | −$63.89 | consistently negative |

Full 4-year table (10 windows, 94,369 candles, 2022-08-21 → 2026-08-18):

| Variant | Trades | Win% | PnL | PF | Sharpe | DSR | Windows |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline (live rule) | 2,279 | 32.2% | −$484.10 | 0.95 | −0.448 | 0.058 | 3/10 |
| + HTF veto (4h) | 1,385 | 32.5% | −$226.65 | 0.96 | −0.318 | 0.158 | 3/10 |
| + scoring ≥45 | 1,751 | 31.7% | −$485.08 | 0.93 | −0.519 | 0.054 | 4/10 |
| + scoring ≥55 | 1,546 | 32.9% | −$103.44 | 0.98 | −0.052 | 0.265 | 6/10 |
| + scoring ≥65 | 677 | 33.1% | −$63.89 | 0.98 | −0.116 | 0.312 | 4/10 |

### Where the 2-year profit came from

Per-window PnL for the ≥55 variant on gold, 2 years:

| Window | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **+ scoring ≥55** | −33.73 | −51.01 | −108.24 | +50.24 | **+137.30** | −60.70 | **+114.41** | +7.24 |
| baseline | −103.78 | −1.39 | −92.11 | −110.31 | −28.29 | +21.91 | +143.65 | −37.79 |

Two windows (5 and 7) contribute +$251.71. The other six sum to −$196.20. The aggregate profit is **two good quarters, not an edge**.

---

## 6. Cross-epic evidence

If the confluence scoring captured something real about metals microstructure, the same threshold should work across instruments. It does not.

| Epic | Best variant | Best PnL | DSR |
|---|---|---:|---:|
| GOLD (2y) | scoring ≥55 | +$55.51 | 0.487 |
| SILVER (2y) | scoring ≥65 | +$38.98 | 0.532 |
| COPPER (2y) | scoring ≥65 + HTF veto | −$192.75 | 0.134 |

Gold's winner is silver's loser. Copper never turns positive under any of the seven variants. **Different optimal thresholds per instrument, and a winner that reverses out-of-period, is the signature of fitting noise.**

---

## 7. Statistical verdict

The Deflated Sharpe Ratio corrects an observed Sharpe for the number of variants tried, the sample length, and the return distribution's skew and kurtosis. It answers: *is this the best of N tries, or a real edge?*

- **Highest DSR observed across all runs: 0.532** (silver, ≥65)
- **Significance bar: 0.95**
- **Selection-bias hurdle for 7 trials: Sharpe ≈ 1.39**

No variant came close. For context on why this matters — across 1,000 backtests of a strategy whose *true* Sharpe is exactly zero, the expected maximum observed Sharpe is **3.26** (Bailey & López de Prado, 2014). Picking the best of N by raw PnL selects for luck. The harness reproduces that published constant at **3.255**, which validates the implementation against its source.

The DSR flagged the ≥55 variant as insignificant (0.487) **before** the 4-year run confirmed it was noise.

---

## 8. The structural problem

Across all seven variants, win rate moved within a narrow band: **28.2% – 34.1%**.

Filtering a losing rule more selectively produces **fewer trades, not better ones**. The ≥65 threshold cuts gold from 1,112 trades to 307 — a 72% reduction — and the win rate moves from 32.5% to 32.9%. That is the whole story of this experiment: confluence filters change *how many* setups pass, not *which kind* of setup wins.

The EMA cross itself is what loses money. Adding confirmation layers on top of a broken entry does not repair it.

---

## 9. What was built

| File | Purpose |
|---|---|
| `data.py` | Pluggable feeds (Dukascopy + Capital), bid/ask normalized, parquet-cached |
| `metrics.py` | Sharpe, Sortino, PSR, Deflated Sharpe, PBO |
| `backtest.py` | Walk-forward mode, overnight swap costs, compounded aggregate |
| `features.py` | Six SMC features, every column causality-tested |
| `signals.py` | 0–100 confluence scoring with HTF veto |
| `compare.py` | Runs all variants on identical data, deflates for trial count |
| `test_backtest.py` / `test_features.py` / `test_signals.py` | 79 checks, all passing (31 / 28 / 20) |

**Data upgrade:** Dukascopy provides history back past 2015 versus Capital's ~180 days, with bid and ask fetched separately. Mean gold spread measured at $0.63 (0.0175% of price).

### Bugs found and fixed

| Bug | Impact |
|---|---|
| Walk-forward produced 3 windows instead of 8 | Skipped two-thirds of the timeline, including most losing periods |
| Aggregate reported a negative account balance | Summed independent windows that each restart at opening balance |
| PnL rounding drifted from running balance | Reported trades did not reconcile with final balance |
| HTF veto bypassed at `min_confidence=0` | `0 < 0` is false, so vetoed trades passed the threshold |
| Backtest sized at FX rate 1.0 | Live bot uses ~1.39 for the CAD account — a 39% sizing error |
| `config.py` required credentials at import | Backtests could not run locally at all |

### Look-ahead prevention

Every feature column is verified causal by **truncation test**: compute on the full series, recompute on a prefix, require the overlapping values to be identical. A column that peeks ahead changes its historical values when future bars are appended, and the test fails.

This matters most for the HTF bias, which is shifted by one 4-hour bar. Without that shift, every 15-minute bar inside a 4h candle would see that candle's final EMA — effectively telling the strategy how the next four hours resolved.

---

## 10. Recommendations

**Do not deploy the SMC features.** They are implemented, tested, and ready — but on this evidence, deploying would be trading a fitted result. `strategy.generate_signal` is deliberately unchanged and byte-identical to what was there before.

**The live bot is currently trading a strategy measured at profit factor 0.96 / 0.88 / 0.84.** That is worth a decision, independent of anything else in this report.

**Next step: replace the entry rule, don't filter it.** The evidence points at the EMA cross as the source of the loss. Options worth testing on this harness:

- Mean-reversion entries rather than trend-following (32% win rate with a 2:1 reward:risk suggests the current TP/SL geometry may be inverted relative to what the signal actually predicts)
- Volatility-regime gating — the ATR floor in `risk.py` already hints the strategy behaves differently across volatility states
- Longer base timeframe — 15-minute bars on metals may simply be below the noise floor

**Methodology to keep.** Any future change gets measured on `compare.py` with an honest `--trials` count. Two numbers decide adoption: profitable windows out of N, and DSR ≥ 0.95. Never compare against a baseline run with different cost or sizing flags.

---

## Appendix — Reproducing these results

```bash
# Baseline, all three epics
.venv/bin/python backtest.py --epic GOLD --days 730 --wf-windows 8 --fx-rate 1.39

# Variant comparison
.venv/bin/python compare.py --epic GOLD --days 730 --wf-windows 8 --fx-rate 1.39
.venv/bin/python compare.py --all-epics --days 730 --fx-rate 1.39

# The reversal test
.venv/bin/python compare.py --epic GOLD --days 1460 --wf-windows 10 --fx-rate 1.39

# Sensitivity controls
.venv/bin/python backtest.py --days 730 --entry-delay 0        # look-ahead
.venv/bin/python backtest.py --days 730 --spread none --swap-rate 0   # no costs

# Test suites
.venv/bin/python test_backtest.py && .venv/bin/python test_features.py && .venv/bin/python test_signals.py
```

**Environment:** Requires the Python 3.12 venv (`numba` does not support the system Python 3.14).
Rebuild with `/usr/local/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-backtest.txt`.

**Test configuration:** 15-minute bars · next-bar fills · historical bid/ask spread · overnight swap at −0.0075%/day charged per rollover crossed · conservative intrabar fills (SL assumed first when SL and TP fall in the same bar) · $1,000 starting balance · 1% risk per trade.

---

## Follow-up

A second experiment tested volatility *timing* rather than directional confluence — restricting the same entry rule to high-volatility conditions instead of trying to predict direction. It produced the first result in this work that survived the 4-year test.

See **[VOLATILITY_REPORT_2026-08-18.md](VOLATILITY_REPORT_2026-08-18.md)**.
