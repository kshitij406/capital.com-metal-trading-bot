import requests

import config
import logger
import risk
import strategy
from capital_api import CapitalAPI

DIRECTION_TO_API = {"LONG": "BUY", "SHORT": "SELL"}


def notify_discord(message):
    try:
        requests.post(config.DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"notify_discord error: {e}")


def format_trade_message(direction, size, entry, sl, tp, risk_amount):
    return (
        f"{direction} {config.EPIC}\n"
        f"Size: {size}\n"
        f"Entry: ${entry:.2f}\n"
        f"Stop Loss: ${sl:.2f}\n"
        f"Take Profit: ${tp:.2f}\n"
        f"Risk: ${risk_amount:.2f}"
    )


def run_cycle():
    api = CapitalAPI()

    try:
        api.login()
    except Exception as e:
        notify_discord(f"ERROR: login failed - {e}\nCycle skipped.")
        return

    try:
        positions = api.get_open_positions()
        if any(p["market"]["epic"] == config.EPIC for p in positions):
            print("Position already open on GOLD, skipping cycle.")
            return

        candles = api.get_candles()
        df = strategy.candles_to_dataframe(candles)
        df = strategy.add_indicators(df)
        last = df.iloc[-1]

        signal = strategy.generate_signal(df)
        logger.log_signal(config.EPIC, last["ema20"], last["ema50"], last["rsi"], last["atr"], signal or "NONE")

        if signal is None:
            print("No signal this cycle.")
            return

        direction = "LONG" if signal == "BUY" else "SHORT"
        balance = api.get_balance()
        entry_price = last["close"]
        atr = last["atr"]

        trade = risk.calculate_trade(balance, entry_price, atr, direction)

        result = api.place_order(
            direction=DIRECTION_TO_API[direction],
            size=trade["size"],
            stop_level=trade["stop_loss"],
            profit_level=trade["take_profit"],
        )
        deal_id = result.get("dealReference")

        logger.log_trade(
            config.EPIC, direction, trade["size"], entry_price,
            trade["stop_loss"], trade["take_profit"], "OPENED", deal_id=deal_id,
        )
        notify_discord(format_trade_message(
            direction, trade["size"], entry_price, trade["stop_loss"], trade["take_profit"], trade["risk_amount"],
        ))

    except Exception as e:
        logger.log_trade(config.EPIC, "NONE", None, None, None, None, "ERROR", error=str(e))
        notify_discord(f"ERROR: {e}\nCycle skipped.")


if __name__ == "__main__":
    logger.init_db()
    run_cycle()
