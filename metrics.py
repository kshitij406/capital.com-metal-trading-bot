"""Performance and statistical-significance metrics for backtests. Never imported by bot.py.

Beyond the descriptive stats (win rate, profit factor, drawdown) this module
answers the question those stats cannot: is this edge real, or is it the luckiest
of however many variants were tried?

That question matters more than it sounds. Bailey & Lopez de Prado (2014) show
that across 1,000 independent backtests of a strategy whose TRUE Sharpe is
exactly zero, the expected maximum observed Sharpe is 3.26. Picking the best of N
variants by raw Sharpe therefore selects for luck almost as strongly as for skill,
and the more variants tried the worse it gets. The Deflated Sharpe Ratio corrects
the observed Sharpe for the number of trials, the sample length, and the skew and
kurtosis of the return distribution, returning a probability rather than a score.

References:
    Bailey & Lopez de Prado, "The Deflated Sharpe Ratio: Correcting for Selection
    Bias, Backtest Overfitting and Non-Normality" (2014).
    Bailey, Borwein, Lopez de Prado & Zhu, "The Probability of Backtest
    Overfitting" (2015).
"""
import math

import numpy as np
from scipy import stats as sps

BARS_PER_YEAR = {
    "MINUTE": 525600, "MINUTE_5": 105120, "MINUTE_15": 35040, "MINUTE_30": 17520,
    "HOUR": 8760, "HOUR_4": 2190, "DAY": 365, "WEEK": 52,
}

EULER_MASCHERONI = 0.5772156649015329


# --------------------------------------------------------------------------
# Return series
# --------------------------------------------------------------------------

def equity_curve(trades, starting_balance):
    """Balance after each closed trade, starting from the opening balance."""
    equity = [starting_balance]
    for t in trades:
        equity.append(equity[-1] + t["pnl"])
    return equity


def trade_returns(trades, starting_balance):
    """Per-trade fractional returns on the running balance.

    Returns are computed against the balance at the time of the trade rather than
    against the starting balance, because position size is a function of the live
    balance in risk.calculate_trade - so a fixed denominator would misstate the
    compounding the bot actually does.
    """
    out = []
    balance = starting_balance
    for t in trades:
        if balance <= 0:
            break
        out.append(t["pnl"] / balance)
        balance += t["pnl"]
    return np.array(out, dtype=float)


# --------------------------------------------------------------------------
# Risk-adjusted return
# --------------------------------------------------------------------------

def sharpe_ratio(returns, periods_per_year=None):
    """Sharpe on the per-trade return series. Not annualized unless
    periods_per_year is given, since trade counts vary between runs."""
    if len(returns) < 2:
        return 0.0
    sd = returns.std(ddof=1)
    if sd == 0:
        return 0.0
    sr = returns.mean() / sd
    if periods_per_year:
        sr *= math.sqrt(periods_per_year)
    return float(sr)


def sortino_ratio(returns, periods_per_year=None):
    """Like Sharpe but penalizes only downside deviation - upside volatility is
    not a risk the trader wants to be charged for."""
    if len(returns) < 2:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) == 0:
        return float("inf")
    dd = math.sqrt((downside ** 2).mean())
    if dd == 0:
        return 0.0
    sr = returns.mean() / dd
    if periods_per_year:
        sr *= math.sqrt(periods_per_year)
    return float(sr)


def probabilistic_sharpe_ratio(returns, benchmark_sr=0.0):
    """P(true Sharpe > benchmark), correcting for skew, kurtosis and sample length.

    A fat-tailed or negatively skewed return stream needs a higher observed Sharpe
    than a Gaussian one to justify the same confidence, which the plain Sharpe
    ignores entirely.
    """
    n = len(returns)
    if n < 3:
        return 0.0
    sr = sharpe_ratio(returns)
    skew = float(sps.skew(returns, bias=False))
    kurt = float(sps.kurtosis(returns, fisher=False, bias=False))

    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr ** 2
    if denom <= 0:
        return 0.0
    z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(sps.norm.cdf(z))


def deflated_sharpe_ratio(returns, n_trials, variance_of_trial_sharpes=None):
    """Probability the observed Sharpe reflects genuine skill after correcting for
    having selected the best of `n_trials` variants.

    The benchmark is not zero - it is the Sharpe you would EXPECT to see from the
    best of n_trials strategies that all have zero true edge. Only a result
    exceeding that null is evidence of anything. DSR > 0.95 is the conventional
    bar for calling a backtest significant.

    n_trials must be an honest count of every variant evaluated, including the ones
    discarded along the way; undercounting it inflates the result, which is exactly
    the bias this statistic exists to remove.
    """
    n = len(returns)
    if n < 3 or n_trials < 1:
        return 0.0

    if variance_of_trial_sharpes is None:
        # Without an observed spread across trials, use the sample's own Sharpe
        # variance as a proxy for how much trial-to-trial dispersion to expect.
        variance_of_trial_sharpes = max(returns.std(ddof=1) ** 2, 1e-12)
    sd = math.sqrt(variance_of_trial_sharpes)

    if n_trials == 1:
        expected_max_sr = 0.0
    else:
        # Expected maximum of n_trials draws from a standard normal (Bailey &
        # Lopez de Prado eq. for E[max SR] under the null of zero true Sharpe).
        e = EULER_MASCHERONI
        q1 = sps.norm.ppf(1.0 - 1.0 / n_trials)
        q2 = sps.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        expected_max_sr = sd * ((1.0 - e) * q1 + e * q2)

    return probabilistic_sharpe_ratio(returns, benchmark_sr=expected_max_sr)


def expected_max_sharpe(n_trials, variance_of_trial_sharpes=1.0):
    """The Sharpe a zero-edge strategy is expected to reach as the best of
    n_trials. Reported alongside DSR to make the selection-bias hurdle visible."""
    if n_trials < 2:
        return 0.0
    sd = math.sqrt(variance_of_trial_sharpes)
    e = EULER_MASCHERONI
    q1 = sps.norm.ppf(1.0 - 1.0 / n_trials)
    q2 = sps.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sd * ((1.0 - e) * q1 + e * q2))


# --------------------------------------------------------------------------
# Drawdown
# --------------------------------------------------------------------------

def drawdown_stats(equity):
    """Peak-to-trough decline in both absolute and percentage terms.

    Percentage matters more than dollars for a compounding account: a $500
    drawdown means something different at a $1,000 balance than at $10,000.
    """
    if len(equity) < 2:
        return {"max_drawdown": 0.0, "max_drawdown_pct": 0.0, "longest_drawdown_trades": 0}

    peak = equity[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    longest = 0
    current = 0

    for value in equity:
        if value >= peak:
            peak = value
            longest = max(longest, current)
            current = 0
        else:
            current += 1
            dd = value - peak
            max_dd = min(max_dd, dd)
            if peak > 0:
                max_dd_pct = min(max_dd_pct, dd / peak * 100)

    longest = max(longest, current)
    return {
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "longest_drawdown_trades": longest,
    }


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------

def compute(trades, resolution, starting_balance, n_trials=1, bars_elapsed=None):
    """Full metric set for one list of closed trades."""
    total = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = sum(t["pnl"] for t in losses)
    from data import RESOLUTION_MINUTES
    minutes_per_bar = RESOLUTION_MINUTES[resolution]

    def avg_hold(rows):
        if not rows:
            return 0.0
        return round(sum(t["holding_bars"] for t in rows) / len(rows) * minutes_per_bar, 1)

    equity = equity_curve(trades, starting_balance)
    returns = trade_returns(trades, starting_balance)
    dd = drawdown_stats(equity)

    # Annualization factor: trades per year implied by how many bars the test
    # covered, so Sharpe is comparable across runs of different lengths.
    periods_per_year = None
    if bars_elapsed and total > 1:
        bars_per_year = BARS_PER_YEAR[resolution]
        trades_per_year = total * (bars_per_year / bars_elapsed)
        periods_per_year = max(trades_per_year, 1.0)

    total_pnl = sum(t["pnl"] for t in trades)

    result = {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / total * 100, 1) if total else 0.0,
        "total_pnl": round(total_pnl, 2),
        "return_pct": round(total_pnl / starting_balance * 100, 2) if starting_balance else 0.0,
        "profit_factor": round(gross_profit / abs(gross_loss), 2) if gross_loss else float("inf"),
        "expectancy": round(total_pnl / total, 2) if total else 0.0,
        "avg_win": round(gross_profit / len(wins), 2) if wins else 0.0,
        "avg_loss": round(gross_loss / len(losses), 2) if losses else 0.0,
        "avg_holding_minutes_wins": avg_hold(wins),
        "avg_holding_minutes_losses": avg_hold(losses),
        "sharpe": round(sharpe_ratio(returns, periods_per_year), 3),
        "sortino": round(sortino_ratio(returns, periods_per_year), 3),
        "psr": round(probabilistic_sharpe_ratio(returns), 4),
        "dsr": round(deflated_sharpe_ratio(returns, n_trials), 4),
        "n_trials": n_trials,
        **dd,
    }
    result["final_balance"] = round(starting_balance + total_pnl, 2)
    return result


# --------------------------------------------------------------------------
# Probability of Backtest Overfitting
# --------------------------------------------------------------------------

def probability_of_backtest_overfitting(perf_matrix, n_splits=8):
    """PBO via combinatorially symmetric cross-validation (Bailey et al. 2015).

    perf_matrix: 2-D array, rows = time slices, cols = strategy variants, values =
    a performance measure (e.g. per-slice Sharpe).

    Splits the timeline into n_splits chunks, forms every balanced train/test
    partition of those chunks, picks the variant that ranks best in-sample, and
    records where that variant lands out-of-sample. PBO is the fraction of
    partitions where the in-sample winner falls into the bottom half out-of-sample
    - i.e. how often "best on the training data" predicts nothing at all.

    PBO below ~0.5 is the minimum bar; a selection process that lands above 0.5 is
    doing worse than choosing at random.
    """
    from itertools import combinations

    perf = np.asarray(perf_matrix, dtype=float)
    if perf.ndim != 2 or perf.shape[1] < 2:
        return None

    n_rows = perf.shape[0]
    if n_rows < n_splits or n_splits % 2 != 0:
        n_splits = max(2, (min(n_rows, n_splits) // 2) * 2)
    if n_rows < n_splits or n_splits < 2:
        return None

    chunks = np.array_split(np.arange(n_rows), n_splits)
    half = n_splits // 2
    logits = []

    for train_ids in combinations(range(n_splits), half):
        test_ids = [i for i in range(n_splits) if i not in train_ids]
        train_rows = np.concatenate([chunks[i] for i in train_ids])
        test_rows = np.concatenate([chunks[i] for i in test_ids])

        train_perf = np.nanmean(perf[train_rows], axis=0)
        test_perf = np.nanmean(perf[test_rows], axis=0)
        if np.all(np.isnan(train_perf)) or np.all(np.isnan(test_perf)):
            continue

        best = int(np.nanargmax(train_perf))
        # Relative rank of the in-sample winner among out-of-sample results.
        ranks = sps.rankdata(test_perf)
        omega = ranks[best] / (len(test_perf) + 1)
        omega = min(max(omega, 1e-6), 1 - 1e-6)
        logits.append(math.log(omega / (1 - omega)))

    if not logits:
        return None
    return float(np.mean(np.array(logits) <= 0))


if __name__ == "__main__":
    rng = np.random.default_rng(42)

    # A zero-edge return stream should not clear the significance bar, and the
    # deflated statistic should be strictly harsher than the undeflated one.
    noise = rng.normal(0, 0.01, 200)
    psr_noise = probabilistic_sharpe_ratio(noise)
    dsr_noise = deflated_sharpe_ratio(noise, n_trials=50)
    print(f"zero-edge:  sharpe={sharpe_ratio(noise):+.3f}  psr={psr_noise:.3f}  dsr(50 trials)={dsr_noise:.3f}")
    assert dsr_noise <= psr_noise, "deflation must never increase confidence"
    assert dsr_noise < 0.95, "zero-edge stream must not clear the DSR bar"

    # A genuinely profitable stream should clear it.
    edge = rng.normal(0.004, 0.01, 200)
    psr_edge = probabilistic_sharpe_ratio(edge)
    dsr_edge = deflated_sharpe_ratio(edge, n_trials=5)
    print(f"real edge:  sharpe={sharpe_ratio(edge):+.3f}  psr={psr_edge:.3f}  dsr(5 trials)={dsr_edge:.3f}")
    assert psr_edge > 0.95, "clear edge should be significant before deflation"

    # More trials must make the hurdle harder, never easier.
    d5 = deflated_sharpe_ratio(edge, n_trials=5)
    d1000 = deflated_sharpe_ratio(edge, n_trials=1000)
    print(f"trial cost: dsr(5)={d5:.3f} -> dsr(1000)={d1000:.3f}")
    assert d1000 <= d5, "more trials must not raise confidence"

    print(f"E[max Sharpe | zero edge]: 100 trials={expected_max_sharpe(100):.3f}, "
          f"1000 trials={expected_max_sharpe(1000):.3f}")

    # Drawdown on a known path.
    dd = drawdown_stats([1000, 1100, 900, 950, 1200])
    assert dd["max_drawdown"] == -200.0, dd
    print("drawdown:", dd)

    # PBO on pure noise should be high - no variant has a real edge, so the
    # in-sample winner is arbitrary and predicts nothing out-of-sample.
    pbo_noise = probability_of_backtest_overfitting(rng.normal(0, 1, (64, 10)))
    print(f"PBO on pure noise (want ~0.5, i.e. selection is worthless): {pbo_noise:.3f}")
    assert pbo_noise is not None and pbo_noise > 0.25

    print("\nPASS: all metric self-checks")
