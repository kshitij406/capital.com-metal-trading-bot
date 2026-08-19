import requests

import config

# Map the bot's internal epic names onto OANDA v20 instrument names. The rest of the
# codebase (strategy, risk, logger, trades.db) keeps using the short names, so this
# mapping is the only place the broker's vocabulary appears.
EPIC_TO_INSTRUMENT = {
    "GOLD": "XAU_USD",
    "SILVER": "XAG_USD",
    "COPPER": "XCU_USD",
}
INSTRUMENT_TO_EPIC = {v: k for k, v in EPIC_TO_INSTRUMENT.items()}

# config.RESOLUTION uses Capital.com's vocabulary; translate to v20 granularity.
RESOLUTION_TO_GRANULARITY = {
    "MINUTE": "M1",
    "MINUTE_5": "M5",
    "MINUTE_15": "M15",
    "MINUTE_30": "M30",
    "HOUR": "H1",
    "HOUR_4": "H4",
    "DAY": "D",
}


class OandaAPI:
    """Adapter over OANDA's v20 REST API that presents the same surface bot.py already
    calls against Capital.com. Response shapes are translated to the Capital.com shapes
    the rest of the bot parses (notably the market/position nesting used by
    resolve_opened_position and check_closed_trades), so no call site had to change."""

    def __init__(self):
        self.base_url = config.OANDA_BASE_URL.rstrip("/")
        self.account_id = None

    def _headers(self):
        return {
            "Authorization": f"Bearer {config.OANDA_API_TOKEN}",
            "Content-Type": "application/json",
            # v20 returns RFC3339 timestamps under this format; the default (UNIX
            # epoch floats) would break strategy.candles_to_dataframe's time parsing.
            "Accept-Datetime-Format": "RFC3339",
        }

    def login(self):
        """No session handshake exists on v20 - the API token is a long-lived bearer.
        This resolves the account id (per the project constraint that it is fetched
        dynamically rather than hardcoded) and doubles as a credential check."""
        accounts = self.get_accounts()
        if not accounts:
            raise RuntimeError("OANDA returned no accounts for this API token.")
        self.account_id = accounts[0]["id"]
        return {"accountId": self.account_id}

    def _request(self, method, path, **kwargs):
        resp = requests.request(method, f"{self.base_url}{path}", headers=self._headers(), timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _account_request(self, method, path, **kwargs):
        if not self.account_id:
            self.login()
        return self._request(method, f"/v3/accounts/{self.account_id}{path}", **kwargs)

    def get_accounts(self):
        return self._request("GET", "/v3/accounts")["accounts"]

    def get_balance(self):
        return float(self._account_request("GET", "/summary")["account"]["balance"])

    def get_account_currency(self):
        return self._account_request("GET", "/summary")["account"]["currency"]

    def get_conversion_rate(self, from_currency, to_currency):
        """Mid-rate for converting from_currency into to_currency. Needed because the
        account is denominated in CAD while every metal instrument is USD-quoted, so a
        CAD risk budget cannot be divided by a USD stop distance directly."""
        if from_currency == to_currency:
            return 1.0
        pair = f"{from_currency}_{to_currency}"
        inverted = False
        prices = self._account_request("GET", "/pricing", params={"instruments": pair}).get("prices", [])
        if not prices:
            pair = f"{to_currency}_{from_currency}"
            inverted = True
            prices = self._account_request("GET", "/pricing", params={"instruments": pair}).get("prices", [])
        if not prices:
            raise RuntimeError(f"No conversion rate available for {from_currency}->{to_currency}")
        p = prices[0]
        rate = (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2
        return 1.0 / rate if inverted else rate

    def get_candles(self, epic, resolution=None, max_candles=None, from_date=None, to_date=None):
        instrument = EPIC_TO_INSTRUMENT.get(epic, epic)
        granularity = RESOLUTION_TO_GRANULARITY.get(resolution or config.RESOLUTION, "M15")
        params = {"granularity": granularity, "price": "BA"}
        if from_date or to_date:
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
        else:
            params["count"] = max_candles or config.CANDLE_COUNT
        data = self._request("GET", f"/v3/instruments/{instrument}/candles", params=params)
        return self._candles_to_capital_shape(data)

    @staticmethod
    def _candles_to_capital_shape(data):
        """Reshape v20 candles into the {"prices": [...]} structure that
        strategy.candles_to_dataframe already parses, so the strategy layer is
        untouched by the broker swap. Incomplete candles are dropped: the final v20
        candle is the in-progress bar, and feeding a partial bar into the EMA cross
        would produce signals that vanish when the bar closes."""
        prices = []
        for c in data.get("candles", []):
            if not c.get("complete"):
                continue
            bid, ask = c["bid"], c["ask"]
            prices.append({
                "snapshotTimeUTC": c["time"],
                "openPrice": {"bid": float(bid["o"]), "ask": float(ask["o"])},
                "highPrice": {"bid": float(bid["h"]), "ask": float(ask["h"])},
                "lowPrice": {"bid": float(bid["l"]), "ask": float(ask["l"])},
                "closePrice": {"bid": float(bid["c"]), "ask": float(ask["c"])},
                "lastTradedVolume": c.get("volume", 0),
            })
        return {"prices": prices}

    def get_open_positions(self):
        """Returns open *trades* (v20's per-fill records), not v20 "positions" which
        aggregate every fill on an instrument. bot.py tracks individual deals by id and
        reconciles them against trades.db, so the per-trade granularity is required."""
        trades = self._account_request("GET", "/openTrades")["trades"]
        out = []
        for t in trades:
            instrument = t["instrument"]
            units = float(t["currentUnits"])
            out.append({
                "market": {"epic": INSTRUMENT_TO_EPIC.get(instrument, instrument)},
                "position": {
                    "dealId": t["id"],
                    "level": float(t["price"]),
                    "size": abs(units),
                    "direction": "BUY" if units > 0 else "SELL",
                    "stopLevel": self._nested_price(t, "stopLossOrder"),
                    "profitLevel": self._nested_price(t, "takeProfitOrder"),
                },
            })
        return out

    @staticmethod
    def _nested_price(trade, key):
        order = trade.get(key)
        return float(order["price"]) if order and "price" in order else None

    def place_order(self, direction, size, stop_level, profit_level, epic):
        """Market order with attached SL and TP. The stop loss is non-optional per the
        project constraint - a missing or non-positive stop is refused here rather than
        being silently sent as a naked order."""
        if stop_level is None or stop_level <= 0:
            raise ValueError(f"Refusing to place {epic} order without a valid stop loss (got {stop_level}).")

        instrument = EPIC_TO_INSTRUMENT.get(epic, epic)
        units = size if direction == "BUY" else -size
        precision = config.INSTRUMENT_PRECISION.get(epic, 0)

        body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": f"{units:.{precision}f}",
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": self._fmt_price(stop_level, epic)},
            }
        }
        if profit_level is not None:
            body["order"]["takeProfitOnFill"] = {"price": self._fmt_price(profit_level, epic)}

        resp = self._account_request("POST", "/orders", json=body)

        # Prefer the fill, then the cancel, then the create transaction. Order matters:
        # on a rejected order the create transaction only ever reports reason
        # "CLIENT_ORDER" (i.e. "a client sent this"), while the cancel transaction
        # carries the actual cause - MARKET_HALTED, INSUFFICIENT_MARGIN, FIFO_VIOLATION.
        # Falling back to create first made every rejection look identical.
        for key in ("orderFillTransaction", "orderCancelTransaction", "orderCreateTransaction"):
            tx = resp.get(key)
            if tx and tx.get("id"):
                resp["dealReference"] = tx["id"]
                break
        else:
            resp["dealReference"] = None

        # Surface the rejection cause directly rather than making callers re-fetch it.
        cancel = resp.get("orderCancelTransaction")
        if cancel:
            resp["rejectReason"] = cancel.get("reason")
        return resp

    @staticmethod
    def _fmt_price(price, epic):
        return f"{price:.{config.PRICE_PRECISION.get(epic, 3)}f}"

    def get_confirmation(self, deal_reference):
        """v20 fills synchronously, so the order response already carries the outcome.
        Re-read the transaction by id and translate it into the dealStatus/dealId shape
        bot.py checks."""
        try:
            tx = self._account_request("GET", f"/transactions/{deal_reference}")["transaction"]
        except requests.HTTPError:
            return {"dealStatus": "REJECTED", "reason": f"transaction {deal_reference} not found"}

        if tx.get("type") == "ORDER_FILL":
            return {
                "dealStatus": "ACCEPTED",
                "dealId": tx.get("tradeOpened", {}).get("tradeID", deal_reference),
                "level": float(tx["price"]) if "price" in tx else None,
            }

        # MARKET_HALTED is expected outside trading hours (metals break ~21:00-22:00 UTC
        # daily and over the weekend) and is not a misconfiguration, so it is reported
        # distinctly - bot.py should skip the cycle quietly rather than alerting.
        reason = tx.get("reason", tx.get("type", "UNKNOWN"))
        return {
            "dealStatus": "REJECTED",
            "reason": reason,
            "marketClosed": reason == "MARKET_HALTED",
        }

    def close_position(self, deal_id):
        return self._account_request("PUT", f"/trades/{deal_id}/close", json={"units": "ALL"})

    def get_deal_activity(self, deal_id):
        """bot.py uses this to recover the close price of a trade that is no longer
        open, reading activity[]["details"]["level"]. The v20 equivalent is the closed
        trade's averageClosePrice."""
        try:
            trade = self._account_request("GET", f"/trades/{deal_id}")["trade"]
        except requests.HTTPError:
            return []
        price = trade.get("averageClosePrice")
        if price is None:
            return []
        return [{"details": {"level": float(price)}}]

    def get_transactions(self, from_date, to_date, tx_type=None):
        """Realized PnL cross-check source. bot.py's fetch_reported_pnl reads each
        entry's "size" field as the realized amount and matches on dealId + a
        "Trade closed" note, so closed-trade transactions are translated into that
        shape rather than v20's native field names."""
        params = {"from": from_date, "to": to_date}
        if tx_type:
            params["type"] = "ORDER_FILL"
        try:
            data = self._account_request("GET", "/transactions/idrange", params=params)
        except requests.HTTPError:
            try:
                data = self._account_request("GET", "/transactions", params=params)
            except requests.HTTPError:
                return []

        out = []
        for tx in data.get("transactions", []):
            closed = tx.get("tradesClosed") or []
            for tc in closed:
                out.append({
                    "dealId": tc.get("tradeID"),
                    "note": "Trade closed",
                    "size": float(tc.get("realizedPL", 0.0)),
                })
        return out


if __name__ == "__main__":
    api = OandaAPI()
    print("Resolving account...")
    print(api.login())
    print("Currency:", api.get_account_currency())
    print("Balance:", api.get_balance())
    candles = api.get_candles(config.EPICS[0])
    print(f"Candles: {len(candles['prices'])} complete bars, last =", candles["prices"][-1]["snapshotTimeUTC"])
