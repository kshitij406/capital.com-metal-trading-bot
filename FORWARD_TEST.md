# Forward Test — Setup and Operation

**Strategy under test:** `vol_regime` — the existing EMA-cross entry, gated on US macro hours (12–15 UTC) and volatility regime (ATR20/ATR200 ≥ 1.05), with volatility-managed position sizing, at 3% risk per trade.

**Backtested result (gold, 4 years, walk-forward, all costs):** profit factor 1.36, DSR 0.961, 9/10 windows profitable, ~40 trades/year. At 3% risk: +29.7% over 4 years, worst historical losing streak −8.6%.

**Why forward-test rather than deploy:** DSR 0.961 clears the 0.95 bar on the 4-year window but scores 0.888 on 2 years, and the whole result comes from a search over one instrument's history. Forward testing generates genuinely out-of-sample data at zero risk, which no amount of additional backtesting can substitute for — more backtesting on the same history actively *degrades* the result by raising the trial count.

---

## What you need to do

Everything in the code is done. Three steps remain, all in GitHub.

### 1. Set the repository variables

**Settings → Secrets and variables → Actions → Variables tab**

| Variable | Value | Effect |
|---|---|---|
| `STRATEGY` | `vol_regime` | Switches to the forward-test rule and restricts to gold |
| `VOL_MANAGED_SIZING` | `true` | Enables inverse-variance position sizing |
| `RISK_PER_TRADE` | `0.03` | 3% per trade — shortens time-to-decision. Leave unset for the 1% default |
| `VOL_REGIME_MIN` | `1.05` | Optional; 1.05 is already the code default |
| `BALANCE_CAP` | `1000` | Already set — caps the sizing balance so demo sizing resembles a real account |

Unset variables fall back to code defaults — an empty GitHub variable is handled, not a crash.

Leaving `STRATEGY` unset keeps the old baseline behaviour on all three metals. That is the revert path: delete the variable, and the next run is back to the previous bot.

### 2. Confirm `IS_DEMO=true`

**Settings → Secrets and variables → Actions → Secrets**

This must be `true`. The whole point is running against the practice account.

### 3. Enable the schedule

The cron is already in [.github/workflows/bot.yml](.github/workflows/bot.yml):

```yaml
- cron: "0,15,30,45 12-15 * * 1-5"
```

Every 15 minutes, 12:00–15:59 UTC, weekdays — about 16 runs per weekday. GitHub disables scheduled workflows on repositories with no activity for 60 days; the bot commits `trades.db` on every run, so that will not trigger.

**Note:** scheduled workflows only run from the default branch. Merge to `main` before expecting the cron to fire.

---

## Checking progress

```bash
STRATEGY=vol_regime .venv/bin/python forward_test.py
```

Three sections:

**PROGRESS** — trades closed, pace, and how far from a meaningful sample.

**DECISIONS** — what each gate did. This is the section to read first if something looks wrong. The expected distribution is dominated by `no_base_signal` (the EMA cross rarely fires), then `outside_macro_hours`, then `vol_regime_too_low`. If a gate never fires, live and backtested logic have diverged and the PnL comparison is meaningless.

**RECONCILIATION** — live metrics against the backtested expectation.

---

## How long this takes

The strategy fires roughly **40 trades per year on gold** — about 3.3 per month. That is the single most important fact about this test. Raising risk to 3% does not create more trades; it makes each one more informative, which is why the milestone table below is in trades, not dollars.

| Milestone | Trades | Time at expected pace |
|---|---:|---|
| First read | 30 | ~9 months |
| Real confidence | 100 | ~2.5 years |

**Three months is about 10 trades.** That is not enough to distinguish this strategy from the baseline, or from chance. Anyone reading a 10-trade sample as evidence is reading noise.

If that timeline is unacceptable, the honest options are: accept a longer test, trade a higher-frequency variant (which backtested worse), or accept the backtest evidence as-is and decide on that. Shortening the test does not produce a faster answer — it produces a wrong one.

---

## What would make this fail — and what each failure means

**Live profit factor < 1.0 with a gate distribution matching the backtest.** The edge is not real. This is the outcome the test exists to detect. Revert by deleting the `STRATEGY` variable.

**Gate distribution differs from the backtest.** Live logic diverged from simulated logic. Check `CANDLE_COUNT` is high enough for ATR(200), and that the cron actually ran during macro hours. The PnL is uninterpretable until this is fixed.

**Trades fire far more often than ~3/month.** Something is wrong with the gating — most likely `vol_regime` is coming back NULL and a gate is being skipped. `vol_regime_unavailable` in the DECISIONS output confirms this.

**Live PnL is worse but the win rate matches.** Execution cost, not signal quality. The backtest used Dukascopy ECN spreads, which are tighter than a retail CFD broker's. This is the *expected* discrepancy and is exactly what a forward test is for — compare `entry_price` in `trades.db` against the signal bar's close to quantify it.

---

## What NOT to do during the test

**Do not tune the parameters.** `VOL_REGIME_MIN = 1.05` and the macro-hour window were set from measurement, not fitted. 1.05 sits on a measured plateau (PF 1.36-1.42 across 1.05/1.10/1.15), chosen at the frequency end of it. Adjusting them mid-test against live results converts a forward test into an in-sample optimisation, which destroys the only thing this exercise produces.

**Do not stop early on a losing streak.** At a 41.8% expected win rate, a run of 5 consecutive losses has probability ≈ 0.07 — it will happen, and it means nothing.

**Do not add instruments.** Silver backtests negative and copper break-even. Adding them adds cost and noise without adding information.

**Do not judge on PnL alone.** At $30 risk per trade, expected profit is roughly $6/month. The test measures whether the edge is real, not whether it is lucrative at this size.

---

## Reverting

Delete the `STRATEGY` repository variable. The next scheduled run returns to the baseline rule on all three metals. No code change, no redeploy.

To stop trading entirely, create a file named `PAUSED` in the repository root — [bot.py](bot.py) checks for it and skips the cycle.

---

## What was changed for this test

| File | Change |
|---|---|
| [config.py](config.py) | `STRATEGY` switch, forward-test constants, `CANDLE_COUNT` 100 → 300 for ATR(200) |
| [strategy.py](strategy.py) | `add_volatility_regime`, `generate_vol_regime_signal`. `generate_signal` unchanged |
| [risk.py](risk.py) | `volatility_scalar`, opt-in via `baseline_atr`. Default sizing unchanged |
| [bot.py](bot.py) | Routes to the selected strategy, logs decision context |
| [logger.py](logger.py) | `strategy` column on trades; `vol_regime`/`hour_utc`/`gate`/`base_signal`/`size_multiplier` on signals |
| [forward_test.py](forward_test.py) | Progress and reconciliation reporting |
| [.github/workflows/bot.yml](.github/workflows/bot.yml) | 15-minute cron during macro hours |

Both schema migrations are additive — the 221 existing trades and 7,218 existing signals are preserved, with NULL in the new columns so pre-test history stays distinguishable.
