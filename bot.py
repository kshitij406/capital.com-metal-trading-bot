import sqlite3
from datetime import datetime, timezone

import requests

import config
import logger
import stats
import strategy
import risk
from capital_api import CapitalAPI

DIRECTION_TO_API = {"LONG": "BUY", "SHORT": "SELL"}
CLOSE_TOLERANCE = 0.5


def notify_discord(message):
    try:
        resp = requests.post(config.DISCORD_WEBHOOK_URL, json={"content": message})
        if resp.status_code >= 300:
            print(f"notify_discord error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"notify_discord error: {e}")


def format_trade_message(epic, direction, size, entry, sl, tp, risk_amount):
    return (
        f"🟢 **OPENED {direction} — {epic}**\n"
        f"Size: {size}\n"
        f"Entry: ${entry:.2f}\n"
        f"Stop Loss: ${sl:.2f}\n"
        f"Take Profit: ${tp:.2f}\n"
        f"Risk: ${risk_amount:.2f}"
    )


def format_daily_summary(data):
    now = datetime.now(timezone.utc)
    overall = data["overall"]

    def signed(v):
        return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"

    lines = [
        f"Daily Stats Summary - {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Overall:",
        f"Trades: {overall['total_trades']} ({overall['closed_trades']} closed, {overall['open_trades']} open)",
        f"Win rate: {overall['win_rate']}% ({overall['winners']}W / {overall['losers']}L)",
        f"Total PnL: {signed(overall['total_pnl'])}",
        f"Best trade: {signed(overall['best_trade'])} | Worst trade: {signed(overall['worst_trade'])}",
        f"Expectancy: {signed(overall['expectancy'])} | Max drawdown: {signed(overall['max_drawdown'])}",
        f"Current streak: {overall['current_streak']}",
        "",
        "By Epic:",
    ]
    for epic, epic_stats in data["by_epic"].items():
        lines.append(
            f"{epic}: {epic_stats['trades']} trades, {epic_stats['win_rate']}% win rate, PnL {signed(epic_stats['pnl'])}"
        )

    return "\n".join(lines)


def send_daily_summary_if_due(stats_data):
    now = datetime.now(timezone.utc)
    # ponytail: gated on "first cron slot of the hour" instead of a last-sent-date
    # file, since the schedule always lands on the same 4 minutes each hour - add
    # a state file if the schedule ever runs off that grid.
    if now.hour == config.DAILY_SUMMARY_HOUR_UTC and now.minute < 15:
        notify_discord(format_daily_summary(stats_data))


def get_total_pnl():
    with sqlite3.connect(config.DB_PATH) as conn:
        total = conn.execute("SELECT SUM(pnl) FROM trades WHERE close_price IS NOT NULL").fetchone()[0]
    return total or 0


def determine_close_reason(close_price, stop_loss, take_profit):
    if take_profit is not None and abs(close_price - take_profit) <= CLOSE_TOLERANCE:
        return "TP"
    if stop_loss is not None and abs(close_price - stop_loss) <= CLOSE_TOLERANCE:
        return "SL"
    return "MANUAL"


CLOSE_PRICE_MAX_DEVIATION = 0.10


def fetch_close_details(api, deal_id, direction, size, entry_price, fallback_price):
    close_price = None
    try:
        for activity in api.get_deal_activity(deal_id):
            level = activity.get("details", {}).get("level")
            if level is not None and level > 0:
                close_price = level
                break
    except Exception:
        pass

    if not close_price:
        close_price = fallback_price

    if not close_price:
        return None, None

    if direction == "LONG":
        pnl = (close_price - entry_price) * size
    else:
        pnl = (entry_price - close_price) * size

    return round(close_price, 2), round(pnl, 2)


def is_valid_close_price(close_price, entry_price):
    if not close_price or close_price <= 0:
        return False
    return abs(close_price - entry_price) / entry_price <= CLOSE_PRICE_MAX_DEVIATION


def check_closed_trades(api, epic, positions, current_close_price):
    live_deal_ids = {p["position"]["dealId"] for p in positions if p["market"]["epic"] == epic}

    with sqlite3.connect(config.DB_PATH) as conn:
        open_trades = conn.execute(
            "SELECT deal_id, direction, size, entry_price, stop_loss, take_profit FROM trades "
            "WHERE epic = ? AND status = 'OPENED' AND close_price IS NULL AND deal_id IS NOT NULL",
            (epic,),
        ).fetchall()

    for deal_id, direction, size, entry_price, stop_loss, take_profit in open_trades:
        if deal_id in live_deal_ids:
            continue

        close_price, pnl = fetch_close_details(api, deal_id, direction, size, entry_price, current_close_price)

        if not is_valid_close_price(close_price, entry_price):
            print(f"WARNING: skipping close for {epic} deal {deal_id}, invalid close_price={close_price} (entry={entry_price})")
            continue

        close_reason = determine_close_reason(close_price, stop_loss, take_profit)

        logger.update_trade_status(deal_id, "CLOSED", close_price=close_price, pnl=pnl, close_reason=close_reason)

        running_total = get_total_pnl()
        balance = api.get_balance()
        result_emoji = "🟢" if pnl >= 0 else "🔴"
        notify_discord(
            f"{result_emoji} **CLOSED {direction} — {epic} [{close_reason}]**\n"
            f"PnL: {'+' if pnl >= 0 else ''}${pnl:.2f}\n"
            f"Running total: {'+' if running_total >= 0 else ''}${running_total:.2f}\n"
            f"Account balance: ${balance:.2f}"
        )


def run_epic_cycle(api, epic):
    try:
        positions = api.get_open_positions()

        candles = api.get_candles(epic)
        df = strategy.candles_to_dataframe(candles)
        df = strategy.add_indicators(df)
        last = df.iloc[-1]

        check_closed_trades(api, epic, positions, last["close"])

        if any(p["market"]["epic"] == epic for p in positions):
            print(f"Position already open on {epic}, skipping cycle.")
            return

        signal = strategy.generate_signal(df)
        logger.log_signal(epic, last["ema20"], last["ema50"], last["rsi"], last["atr"], signal or "NONE")

        if signal is None:
            print(f"No signal this cycle for {epic}.")
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
            epic=epic,
        )
        confirmation = api.get_confirmation(result["dealReference"])
        deal_id = confirmation.get("dealId", result.get("dealReference"))

        logger.log_trade(
            epic, direction, trade["size"], entry_price,
            trade["stop_loss"], trade["take_profit"], "OPENED", deal_id=deal_id,
        )
        notify_discord(format_trade_message(
            epic, direction, trade["size"], entry_price, trade["stop_loss"], trade["take_profit"], trade["risk_amount"],
        ))

    except Exception as e:
        logger.log_trade(epic, "NONE", None, None, None, None, "ERROR", error=str(e))
        notify_discord(f"ERROR: {epic} - {e}\nCycle skipped.")


def run_cycle():
    api = CapitalAPI()

    try:
        api.login()
    except Exception as e:
        notify_discord(f"ERROR: login failed - {e}\nCycle skipped.")
        return

    for epic in config.EPICS:
        run_epic_cycle(api, epic)

    stats_data = stats.update_stats()
    send_daily_summary_if_due(stats_data)


if __name__ == "__main__":
    logger.init_db()
    run_cycle()
