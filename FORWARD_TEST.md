# Forward Test — Setup and Operation

**Strategy under test:** `vol_regime` — the existing EMA-cross entry, gated on US macro hours (12–15 UTC) and volatility regime (ATR20/ATR200 ≥ 1.05), with optional volatility-managed position sizing.

**Backtested result (gold, 4 years, walk-forward, all costs):** profit factor 1.36, DSR 0.961, 9/10 windows profitable, ~40 trades/year. See CLAUDE.md for the full set of research findings this is based on.

**Why forward-test rather than deploy at full size:** DSR 0.961 clears the 0.95 bar on the 4-year window but scores 0.888 on 2 years, and the whole result comes from a search over one instrument's history. Forward testing generates genuinely out-of-sample data at zero risk, which no amount of additional backtesting can substitute for — more backtesting on the same history actively *degrades* the result by raising the trial count.

---

## What you need to do

### 1. Set the repository variables

**Settings → Secrets and variables → Actions → Variables tab**

| Variable | Value | Effect |
|---|---|---|
| `STRATEGY` | `vol_regime` | Switches to the forward-test rule and restricts live trading to gold |
| `VOL_MANAGED_SIZING` | `true` | Enables inverse-variance position sizing (optional) |
| `RISK_PER_TRADE` | `0.01` or higher | Leave unset for the 1% default; raising it shortens time-to-decision at higher risk |
| `VOL_REGIME_MIN` | `1.05` | Optional; 1.05 is already the code default |
| `BALANCE_CAP` | `1000` | Caps the sizing balance so demo sizing resembles a real account |

Unset variables fall back to code defaults — an empty GitHub variable is handled, not a crash.

Leaving `STRATEGY` unset keeps the baseline behaviour on all three metals. That is the revert path: delete the variable, and the next run is back to the previous bot.

### 2. Confirm `IS_DEMO=true`

**Settings → Secrets and variables → Actions → Secrets**

This must be `true`. The whole point is running against the practice account.

### 3. Trigger runs

`.github/workflows/bot.yml` currently triggers on `workflow_dispatch` only (no cron). Trigger cycles manually, via an external scheduler, or via Discord's `/forcecycle` command. `strategy.generate_vol_regime_signal`'s own macro-hours gate means a cycle outside 12–15 UTC simply logs a `outside_macro_hours` skip rather than trading — running more often than necessary just produces more skip rows, not more risk.

---

## Checking progress

```bash
STRATEGY=vol_regime python forward_test.py
```

Three sections:

**PROGRESS** — trades closed, pace, and how far from a meaningful sample.

**DECISIONS** — what each gate did. This is the section to read first if something looks wrong. The expected distribution is dominated by `no_base_signal` (the EMA cross rarely fires), then `outside_macro_hours`, then `vol_regime_too_low`. If a gate never fires, live and backtested logic have diverged and the PnL comparison is meaningless.

**RECONCILIATION** — live metrics against the backtested expectation.

---

## How long this takes

The strategy fires roughly **40 trades per year on gold** — about 3.3 per month. That is the single most important fact about this test.

| Milestone | Trades | Time at expected pace |
|---|---:|---|
| First read | 30 | ~9 months |
| Real confidence | 100 | ~2.5 years |

**Three months is about 10 trades.** That is not enough to distinguish this strategy from the baseline, or from chance.

---

## What would make this fail — and what each failure means

**Live profit factor < 1.0 with a gate distribution matching the backtest.** The edge is not real. Revert by deleting the `STRATEGY` variable.

**Gate distribution differs from the backtest.** Live logic diverged from simulated logic. Check `CANDLE_COUNT` is high enough for ATR(200), and that cycles actually ran during macro hours. The PnL is uninterpretable until this is fixed.

**Trades fire far more often than ~3/month.** Something is wrong with the gating — most likely `vol_regime` is coming back NULL and a gate is being skipped. `vol_regime_unavailable` in the DECISIONS output confirms this.

**Live PnL is worse but the win rate matches.** Execution cost, not signal quality. The backtest used Dukascopy ECN spreads, which are tighter than a retail CFD broker's. Compare `entry_price` in `trades.db` against the signal bar's close to quantify it.

---

## What NOT to do during the test

**Do not tune the parameters.** `VOL_REGIME_MIN = 1.05` and the macro-hour window were set from measurement, not fitted. Adjusting them mid-test against live results converts a forward test into an in-sample optimisation.

**Do not stop early on a losing streak.** A run of several consecutive losses at the strategy's expected win rate is not evidence the edge is gone.

**Do not add instruments.** Silver backtests negative and copper break-even under `vol_regime`. Adding them adds cost and noise without adding information.

**Do not judge on PnL alone.** The test measures whether the edge is real, not whether it is lucrative at demo size.

---

## Reverting

Delete the `STRATEGY` repository variable. The next run returns to the baseline rule on all three metals. No code change, no redeploy.

To stop trading entirely, create a file named `PAUSED` in the repository root — `bot.py` checks for it and skips the cycle.

---

## What was changed for this

| File | Change |
|---|---|
| `config.py` | `STRATEGY` switch, forward-test constants, `CANDLE_COUNT` 100 → 300 for ATR(200) |
| `strategy.py` | `add_volatility_regime`, `generate_vol_regime_signal`. `generate_signal` unchanged |
| `risk.py` | `volatility_scalar`, opt-in via `baseline_atr`. Default sizing unchanged |
| `bot.py` | Routes to the selected strategy, logs decision context |
| `logger.py` | `strategy` column on trades; `vol_regime`/`hour_utc`/`gate`/`base_signal`/`size_multiplier` on signals |
| `forward_test.py` | Progress and reconciliation reporting |

Both schema migrations are additive — existing trades and signals are preserved, with NULL in the new columns so pre-test history stays distinguishable.
