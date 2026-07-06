import math

import config

MAX_UNITS = 50
MIN_ATR = 0.01


def calculate_trade(account_balance, entry_price, atr, direction):
    if atr < MIN_ATR:
        raise ValueError(f"ATR too small for safe position sizing: {atr}")

    risk_amount = account_balance * config.RISK_PER_TRADE
    sl_distance = atr * config.SL_ATR_MULT
    size = math.floor((risk_amount / sl_distance) * 100) / 100
    size = min(size, MAX_UNITS)

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
    print("PASS")
