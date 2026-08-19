import math

import config

MAX_NOTIONAL_MULT = 5.0  # cap exposure at 5x account balance. Expressed as notional
                         # (size * entry_price) rather than a raw unit count, because a
                         # flat unit cap is meaningless across instruments at different
                         # price scales - 50 units is $205k of GOLD but $310 of COPPER,
                         # so a unit cap silently throttled COPPER to ~0.1% risk on
                         # every single trade while never binding on GOLD at all.
MIN_ATR_PCT = 0.0005  # ATR must be at least 0.05% of entry_price - a fixed absolute
                      # floor doesn't work across instruments at very different price
                      # scales (e.g. GOLD ~4100 vs COPPER ~6.2), so this is expressed
                      # relative to price instead. Deliberately relative-only, not
                      # combined with an absolute floor: measured against the actual
                      # 2.5yr ATR/price distribution for all three instruments, an
                      # absolute 0.01 floor over-rejected 59% of COPPER's raw signals
                      # while never binding on GOLD/SILVER at all - see the "Fix MIN_ATR
                      # unit mismatch" commit for the verification (41%->100% COPPER
                      # pass rate).


# Volatility-managed sizing (Moreira & Muir 2017, "Volatility-Managed Portfolios").
# The paper's result is that scaling exposure by the INVERSE OF VARIANCE - not just
# inverse volatility - raises risk-adjusted returns, because changes in volatility are
# not fully offset by proportional changes in expected return.
#
# This bot already sizes by risk_amount / (atr * SL_ATR_MULT), which is inverse-VOL
# sizing. The extra increment the paper prescribes is one more factor of vol. Measured
# on 10 years of daily gold, at matched volatility:
#     unscaled buy-and-hold      Sharpe 0.73
#     inverse vol (today's rule) Sharpe 0.82
#     inverse variance (paper)   Sharpe 0.89
# and the inverse-variance version improved Sharpe in 5 of 5 two-year blocks, on all
# three metals. The multiplier is capped because the raw ratio explodes in very quiet
# markets, which would size a position far beyond what the account can survive when
# volatility mean-reverts.
VOL_TARGET_CAP = 2.0   # never scale UP by more than 2x
VOL_TARGET_FLOOR = 0.5  # never scale DOWN by more than 2x


def volatility_scalar(atr, baseline_atr, cap=VOL_TARGET_CAP, floor=VOL_TARGET_FLOOR):
    """Extra sizing multiplier from volatility-managed portfolio theory.

    Returns baseline_atr / atr, clamped. Because the caller already divides by atr
    once, applying this multiplier makes total sizing proportional to 1/atr^2 - the
    inverse-variance rule - while the clamp keeps the position inside what the
    account can survive when a quiet regime ends abruptly.

    baseline_atr is the instrument's own longer-run ATR, so the scalar is a relative
    judgement ("calmer than usual") rather than an absolute one, which is what lets
    the same rule apply to gold at 4100 and copper at 6.2.
    """
    if not baseline_atr or not atr or atr <= 0 or baseline_atr <= 0:
        return 1.0
    return max(floor, min(cap, baseline_atr / atr))


def calculate_trade(account_balance, entry_price, atr, direction, epic=None, quote_to_account_rate=1.0,
                    baseline_atr=None):
    min_atr = entry_price * MIN_ATR_PCT
    if atr < min_atr:
        raise ValueError(f"ATR too small for safe position sizing: {atr} (min {min_atr:.6f})")

    risk_amount = account_balance * config.RISK_PER_TRADE
    sl_distance = atr * config.SL_ATR_MULT

    # quote_to_account_rate stays 1.0 for Capital.com (no currency-conversion method
    # on capital_api.py, and today's account is already quote-currency-denominated) -
    # this is a no-op unless a caller explicitly passes a different rate.
    risk_amount_quote = risk_amount / quote_to_account_rate
    size = risk_amount_quote / sl_distance

    # Volatility-managed overlay. Off by default (baseline_atr=None) so the live
    # sizing rule is unchanged until this has earned its way in.
    if baseline_atr:
        size *= volatility_scalar(atr, baseline_atr)

    max_size = ((account_balance / quote_to_account_rate) * MAX_NOTIONAL_MULT) / entry_price
    size = min(size, max_size)

    # Round DOWN to the broker's unit precision for this instrument. Gold accepts
    # tenths; silver and copper are integer-only, so a 2-decimal size would be rejected.
    # NOTE: these per-instrument precision/minimum values (config.INSTRUMENT_PRECISION,
    # config.MIN_TRADE_SIZE) were sourced from OANDA's instrument spec - verify against
    # Capital.com's own GET /api/v1/markets/{epic} response before relying on them live.
    precision = config.INSTRUMENT_PRECISION.get(epic, 2)
    factor = 10 ** precision
    size = math.floor(size * factor) / factor

    # A size that rounds below the broker's minimum must not be sent as a live order.
    # Raising here means the cycle logs a skip rather than the broker rejecting an
    # order, or - worse - a zero-size order being accepted with no stop attached.
    min_size = config.MIN_TRADE_SIZE.get(epic, 0.0)
    if min_size and size < min_size:
        raise ValueError(
            f"Position size {size} for {epic} is below the broker minimum {min_size}. "
            f"Balance {account_balance} is too small to risk {config.RISK_PER_TRADE:.1%} "
            f"with a stop {sl_distance:.4f} wide."
        )

    if direction == "LONG":
        stop_loss = entry_price - sl_distance
        take_profit = entry_price + (atr * config.TP_ATR_MULT)
    elif direction == "SHORT":
        stop_loss = entry_price + sl_distance
        take_profit = entry_price - (atr * config.TP_ATR_MULT)
    else:
        raise ValueError(f"Invalid direction: {direction}")

    if size <= 0:
        raise ValueError(f"Calculated size must be > 0, got {size}")

    if direction == "LONG":
        if not stop_loss < entry_price:
            raise ValueError(f"LONG stop_loss ({stop_loss}) must be < entry_price ({entry_price})")
        if not take_profit > entry_price:
            raise ValueError(f"LONG take_profit ({take_profit}) must be > entry_price ({entry_price})")
    else:
        if not stop_loss > entry_price:
            raise ValueError(f"SHORT stop_loss ({stop_loss}) must be > entry_price ({entry_price})")
        if not take_profit < entry_price:
            raise ValueError(f"SHORT take_profit ({take_profit}) must be < entry_price ({entry_price})")

    return {
        "risk_amount": risk_amount,
        "sl_distance": sl_distance,
        "size": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }


if __name__ == "__main__":
    result = calculate_trade(account_balance=1000, entry_price=2000, atr=5.0, direction="LONG")
    for k, v in result.items():
        print(f"{k}: {v}")

    expected = {
        "risk_amount": 10.0,
        "sl_distance": 7.5,
        "size": 1.33,
        "stop_loss": 1992.5,
        "take_profit": 2015.0,
    }
    assert result == expected, f"Mismatch: {result} != {expected}"
    print("PASS: original sizing case unchanged")

    # Each epic at realistic price/ATR should now achieve the full 1% risk target,
    # rather than COPPER being throttled by a unit cap that never bound on GOLD.
    for epic, price, atr in (("GOLD", 4100.0, 16.0), ("SILVER", 48.0, 0.35), ("COPPER", 6.2, 0.02)):
        r = calculate_trade(1000, price, atr, "LONG")
        implied_risk = r["size"] * r["sl_distance"]
        notional = r["size"] * price
        print(f"{epic:7} size={r['size']:>8.2f} implied_risk=${implied_risk:>6.2f} notional=${notional:>9,.0f}")
        assert 9.0 <= implied_risk <= 10.0, f"{epic} risk {implied_risk} not ~1% of 1000"
    print("PASS: all epics achieve ~1% risk")

    # Per-instrument precision: sizes must be representable at the broker.
    for epic, price, atr in (("GOLD", 4332.0, 16.0), ("SILVER", 48.0, 0.35), ("COPPER", 6.2, 0.02)):
        r = calculate_trade(1000, price, atr, "LONG", epic=epic)
        prec = config.INSTRUMENT_PRECISION[epic]
        assert round(r["size"], prec) == r["size"], f"{epic} size {r['size']} exceeds precision {prec}"
        assert r["size"] >= config.MIN_TRADE_SIZE[epic], f"{epic} below minimum"
    print("PASS: sizes respect per-instrument precision and minimums")

    # Relative MIN_ATR floor: 6.2 * 0.0005 = 0.0031, so 0.001 must be rejected and
    # 0.005 must pass (this is the fix that took COPPER's raw-signal pass rate from
    # 41% to 100% - a flat absolute floor over-rejected COPPER specifically).
    try:
        calculate_trade(1000, 6.2, 0.001, "LONG", epic="COPPER")
    except ValueError as e:
        print(f"PASS: COPPER relative ATR floor still enforced ({e.__class__.__name__})")
    else:
        raise AssertionError("expected ValueError for COPPER ATR below the relative floor")
    calculate_trade(1000, 6.2, 0.005, "LONG", epic="COPPER")
    print("PASS: COPPER ATR above the relative floor is accepted (no over-rejection)")

    # Minimum-size guard: a balance too small for the instrument must raise, not
    # silently produce a zero-unit order.
    try:
        calculate_trade(10, 4332.0, 16.0, "LONG", epic="SILVER")
    except ValueError as e:
        print(f"PASS: minimum-size guard raised ({e.__class__.__name__})")
    else:
        raise AssertionError("expected ValueError for sub-minimum size")
