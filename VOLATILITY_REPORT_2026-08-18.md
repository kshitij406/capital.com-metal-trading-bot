# Volatility Timing — Backtest Findings

**Date:** 2026-08-18
**Question:** Can free public data provide an edge, and if not, what can?
**Scope:** Macro data survey (FRED, currency APIs) plus eight volatility-timing variants
**Data:** Dukascopy XAU/XAG/COPPER, 15-minute bars, 2 and 4 year windows
**Verdict:** Macro price data has no predictive value. Volatility *timing* produced the first result in this project to survive out-of-period testing.

> Companion document: [BACKTEST_REPORT_2026-08-18.md](BACKTEST_REPORT_2026-08-18.md) covers the baseline and the SMC/confluence experiment that preceded this one.

---

## 1. Summary

Two findings, one negative and one positive.

**Negative:** Free public macro data — Federal Reserve real yields, dollar index, currency rates — correlates strongly with gold *on the same bar* and predicts *nothing* about the next one. This is not a data-quality problem; it is what an efficiently priced market looks like.

**Positive:** Volatility is structurally predictable in a way price is not. Restricting the existing entry rule to high-volatility conditions during US macro hours produced **+$145.18 on gold over 4 years, profit factor 1.37, 7 of 10 windows profitable, maximum drawdown −5.8%.**

Critically, this result **improved** when the test window was extended from 2 years to 4. The SMC confluence winner from the previous experiment reversed under the same test.

This is the strongest result produced so far. It is still below the significance bar, and the recommendation is demo forward-testing, not live deployment.

---

## 2. The macro data question

The starting point was a survey of free public APIs for anything that might predict metals: commodity prices, interest rates, economic indicators, central bank data.

Two candidates were worth testing. FRED (Federal Reserve Economic Data) serves the 10-year TIPS real yield — widely cited as the single most important macro driver of gold — with no API key and history back to 2003. Currency APIs serve the dollar index, gold's other well-documented driver.

Both were measured against 4 years of gold on your own data.

### Results

| Signal | Same-bar correlation | Predicts next bar |
|---|---:|---:|
| 10Y real yield (FRED `DFII10`) | −0.242 | **+0.019** |
| Dollar index (FRED `DTWEXBGS`) | −0.349 | **+0.028** |
| Inflation breakeven (FRED `T10YIE`) | −0.049 | **+0.031** |
| VIX (FRED `VIXCLS`) | −0.126 | **−0.056** |
| EUR/USD at 15-minute resolution | +0.310 | **+0.011** |

A direct test at trading horizon: after a 2-sigma EUR/USD move, gold moves the same direction on the next bar **50.9% of the time** across 2,038 occurrences. A coin flip.

### Why this is the expected result

The literature is correct that real yields drive gold — the published rolling correlation is around −0.73, and real-rate moves explain up to 25% of quarterly gold variation. The measured contemporaneous correlations here (−0.24 to −0.35 on daily changes) are consistent with that.

But contemporaneous is not tradeable. Gold reprices within seconds of a yield move. FRED publishes daily, next-day. By the time the data is available, the information is hours to days stale and thousands of faster participants have already acted on it.

**Free, public, low-frequency data cannot provide directional edge in a liquid market.** Gold futures are among the most efficiently priced instruments in the world. If a no-auth API predicted them, the edge would be arbitraged away before the documentation finished loading.

### What the APIs are still worth

Not alpha, but infrastructure:

- **FRED** — usable as a slow regime filter ("is the real-yield trend up or down this quarter") rather than an entry timer. No key required, works today.
- **Frankfurter / exchangerate.host** — free, no auth, and the bot currently hardcodes USD→CAD at 1.39 for position sizing. That number should come from an API.

---

## 3. The structural alternative

Price direction is arbitraged. **Volatility is not** — it is driven by when information is scheduled to arrive, which is public knowledge in advance.

US macro releases (CPI, non-farm payrolls, PPI, retail sales, jobless claims) land at 08:30 New York, which is 12:30 or 13:30 UTC depending on daylight saving. The US cash session opens shortly after.

Measured over 4 years of 15-minute bars, average absolute return by UTC hour:

| Epic | All-day mean | Hours above 1.2× | Hours below 0.8× |
|---|---:|---|---|
| GOLD | 7.43 bps | 1, **12, 13, 14, 15** | 3, 4, 20, 21, 23 |
| SILVER | 15.25 bps | 1, **12, 13, 14, 15** | 3, 4, 20, 21, 22, 23 |
| COPPER | 10.81 bps | 1, 7, 8, **12, 13, 14, 15** | 0, 4, 18, 19, 20, 21, 22, 23 |

**Hours 12–15 UTC exceed 1.2× the all-day mean on all three metals.** The 13:30 bucket alone runs 1.83× on gold. Quiet hours run below 0.8× — a roughly 3× spread between busiest and quietest slots.

This effect is stable across instruments and across four years, and unlike a price correlation it is knowable from the clock before the bar opens.

---

## 4. What was tested

Eight variants, all using the **unchanged** entry rule. These do not attempt to predict direction — they only decide *when* the existing rule is permitted to act.

Two measures of volatility, deliberately distinct:

- **`tod_vol_ratio`** — a clock effect. This time-slot's historical mean absolute return divided by the all-day mean, learned from an expanding window over past bars only.
- **`vol_regime`** — a market-state effect. Current ATR(20) divided by ATR(200), shifted so the value is complete before the bar opens.

The two can disagree: a quiet 13:30, a wild 03:00.

Both directions of the hypothesis were included. "Only trade the busy hours" and "only trade the calm ones" cannot both be right, and testing only the one matching a prior belief is how a backtest gets talked into an answer.

---

## 5. Results — GOLD

Walk-forward, out-of-sample, spread + slippage + overnight swap, live-accurate sizing.

### 4 years (94,369 candles, 10 windows)

| Variant | Trades | Win% | PnL | PF | Sharpe | DSR | Max DD | Windows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (live rule) | 2,279 | 32.2% | −$484.10 | 0.95 | −0.448 | 0.052 | −67.5% | 3/10 |
| macro hours only (12–15 UTC) | 649 | 32.5% | −$135.38 | 0.95 | −0.336 | 0.202 | −26.4% | 4/10 |
| avoid quiet hours | 2,014 | 31.0% | −$824.24 | 0.90 | −0.673 | 0.005 | −90.0% | 2/10 |
| busy slots (tod ≥ 1.2) | 746 | 31.8% | −$234.71 | 0.93 | −0.529 | 0.117 | −37.9% | 4/10 |
| quiet-hours only (inverse) | 1,078 | 32.6% | −$117.30 | 0.97 | −0.208 | 0.238 | −25.9% | 2/10 |
| high vol regime (≥ 1.2) | 358 | 35.2% | **+$100.07** | 1.07 | 0.425 | 0.645 | −21.8% | 4/10 |
| normal vol regime (0.8–1.2) | 1,589 | 31.1% | −$656.17 | 0.89 | −1.144 | 0.008 | −76.6% | 2/10 |
| **macro hours + high regime** | **98** | **41.8%** | **+$145.18** | **1.37** | **0.995** | **0.913** | **−5.8%** | **7/10** |

### The out-of-period test

This is the test the SMC confluence features failed:

| Variant | 2-year PnL | 4-year PnL | Outcome |
|---|---:|---:|---|
| SMC scoring ≥55 *(previous experiment)* | +$55.51 | −$103.44 | **reversed** |
| high vol regime | +$199.86 | +$100.07 | held |
| **macro hours + high regime** | **+$94.60** | **+$145.18** | **improved** |

Extending the window from 2 years to 4 years made the winning variant *better*, not worse. That is the opposite of what a fitted result does.

### Consistency

Per-window PnL across the 4-year walk-forward:

| Variant | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 | Median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | −76.2 | +60.4 | −27.3 | −160.2 | −131.7 | −39.9 | −110.9 | −138.4 | +80.5 | +59.7 | −58.08 |
| high vol regime | −4.6 | +19.1 | −44.1 | −57.3 | −47.1 | +71.2 | +93.8 | −10.6 | +113.1 | −33.4 | −7.60 |
| **macro + high regime** | +4.0 | −13.9 | +18.3 | −20.9 | +51.1 | −23.2 | +25.8 | +65.3 | +34.5 | +4.2 | **+11.21** |

The winning variant's **worst window is −$23.20** and its median window is **positive**. Compare the baseline, which has four windows worse than −$100.

This matters more than the aggregate. The SMC winner's 2-year profit came from two windows out of eight contributing +$251 while the other six lost $196 — an aggregate built on two good quarters. Here the profit is distributed.

### Trade concentration

For `high vol regime` on 2 years: 165 trades, largest single trade **$15.10**, top three trades sum to $44.71 (22% of total). Removing them entirely still leaves **+$155 of the +$200**. Median trade is −$5.82 — the strategy wins by asymmetric payoff, not by winning often.

The filter is genuinely selective: only **18% of bars** qualify as high-regime.

---

## 6. Cross-metal check (4 years)

The same threshold, applied unchanged to all three instruments:

| Epic | Baseline | macro + high regime | Improvement | PF | Windows |
|---|---:|---:|---:|---:|---:|
| GOLD | −$484.10 | **+$145.18** | +$629 | 1.37 | 7/10 |
| SILVER | −$2,439.47 | −$49.78 | +$2,390 | 0.91 | 6/10 |
| COPPER | −$2,706.17 | **+$15.15** | +$2,721 | 1.01 | 4/10 |

`macro hours + high regime` is the **best variant on all three metals**, using the **same threshold** on each.

This is the key contrast with the SMC experiment, where gold's optimal threshold was ≥55 and silver's was ≥65 — different winners on different data, the signature of fitting noise. Here one rule works everywhere in the same direction.

Only gold becomes clearly profitable. Silver and copper move from catastrophic to approximately break-even.

---

## 7. Statistical assessment

| Measure | Value | Bar |
|---|---:|---:|
| Deflated Sharpe Ratio (gold, 4y) | **0.913** | 0.95 |
| Selection-bias hurdle (8 trials) | Sharpe ≈ 1.46 | — |
| Observed Sharpe | 0.995 | — |
| Win rate vs baseline (binomial, one-sided) | 40.8% vs 32.2%, **p = 0.045** | 0.05 |
| Win rate, `high vol regime` | 35.2% vs 32.2%, **p = 0.124** | 0.05 |

DSR 0.913 is the highest figure produced in this project — the SMC experiment peaked at 0.532 — but it remains below the 0.95 threshold.

The win-rate improvement alone is marginal (p=0.045 for the winner, not significant for the runner-up). **The edge is not primarily in hit rate.** It is in payoff geometry: profit factor 1.37 against a baseline 0.95, and maximum drawdown of −5.8% against −67.5%.

---

## 8. Why this result is more credible than the last one

Four independent properties, none of which the SMC result had:

| Property | SMC confluence | Volatility timing |
|---|---|---|
| Survived 4-year test | No — reversed | **Yes — improved** |
| Same rule works across metals | No — different thresholds | **Yes — one threshold** |
| Profit distributed across windows | No — 2 of 8 carried it | **Yes — median positive** |
| Mechanism | Inferred from price patterns | **Structural, clock-based** |

The mechanism point is the substantive one. SMC features attempt to detect institutional intent from price patterns — a claim about what other participants are doing, inferred from data those participants have already acted on. Volatility timing makes a much weaker claim: information arrives on a published schedule, and markets move more when it does. That claim is verifiable independently of any trading result, and it was verified here across three instruments and four years before any strategy was built on it.

---

## 9. Limitations

Stated plainly, because the result is encouraging enough to be dangerous.

**DSR 0.913 < 0.95.** Better than anything else tested, still short of significance. This is not proof.

**Low trade frequency.** 98 trades over 4 years is roughly 25 per year, about 2 per month. The equity curve will be lumpy and an 8-trade losing streak is unremarkable at that rate. Judging this strategy over one quarter would be meaningless.

**Small sample in the winning variant.** 98 trades is a thin base for a 41.8% win-rate claim, which is why the binomial p-value sits right at 0.045.

**Eight more trials were spent.** The selection hurdle for this experiment is Sharpe ≈1.46, and the observed Sharpe is 0.995.

**The 1.2 threshold must not be tuned on this data.** Searching for a better cutoff on the same four years would convert a survived out-of-period result back into a fitted one — the exact failure mode documented in the companion report.

**Backtest spreads are ECN, not CFD.** Dukascopy's mean gold spread is $0.63. Your broker's is wider. Absolute PnL here is optimistic; the A-vs-B comparison is not.

---

## 10. Recommendation

**Forward-test on demo. Gold only. Do not deploy to live.**

The reasoning: this is the only idea tested in this project that behaved the way a genuine effect behaves — survived out-of-period, generalized across instruments with an unchanged threshold, distributed its profit across windows, and rests on a mechanism verifiable independently of the trading result.

It is also still below the significance bar, on a thin sample, after eight trials.

Demo forward-testing resolves that tension at zero cost. It generates genuinely out-of-sample data that no backtest can manufacture, at roughly 2 trades per month, against real fills and real broker spreads. Three to six months of that would be far more informative than any further work on historical data — and further backtesting on these same four years actively degrades the result by raising the trial count.

Silver and copper are break-even at best and should stay out.

**What not to do next:** tune the threshold, add more variants on this data, or deploy live on a DSR of 0.913.

---

## Appendix — Reproducing these results

```bash
# The volatility comparison (8 variants)
.venv/bin/python compare.py --epic GOLD --days 1460 --wf-windows 10 --fx-rate 1.39 --mode vol

# 2-year version, for the out-of-period comparison
.venv/bin/python compare.py --epic GOLD --days 730 --wf-windows 8 --fx-rate 1.39 --mode vol

# Cross-metal check
.venv/bin/python compare.py --epic SILVER --days 1460 --wf-windows 10 --fx-rate 1.39 --mode vol
.venv/bin/python compare.py --epic COPPER --days 1460 --wf-windows 10 --fx-rate 1.39 --mode vol

# Causality checks on the new volatility features
.venv/bin/python test_features.py
```

**Implementation:** `features.add_time_of_day_volatility` and `features.add_volatility_regime` build the columns; `signals.volatility_window` applies them as an entry gate; `compare.build_volatility_variants` defines the eight variants.

**Causality:** Both new features pass the truncation test — computed on a prefix, their historical values are identical to those computed on the full series. The time-of-day profile uses an expanding window shifted by one bar, so the volatility profile at bar *i* is learned only from bars before *i*. Computing a single profile over the whole series would leak the test period's own volatility into the decision that trades it.

**Test configuration:** 15-minute bars · next-bar fills · historical bid/ask spread · overnight swap at −0.0075%/day per rollover crossed · conservative intrabar fills · $1,000 starting balance · 1% risk per trade · FX rate 1.39 (CAD account, USD-quoted metals).

**Live code unchanged.** `strategy.generate_signal` is byte-identical to what it was before this work began, verified by test.
