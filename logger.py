import sqlite3
from datetime import datetime, timezone

import config


def init_db():
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    epic TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    size REAL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    status TEXT NOT NULL,
                    deal_id TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    epic TEXT NOT NULL,
                    ema20 REAL,
                    ema50 REAL,
                    rsi REAL,
                    atr REAL,
                    signal_generated TEXT NOT NULL
                )
            """)
            conn.commit()
        update_trades_table()
        return True
    except Exception as e:
        print(f"init_db error: {e}")
        return False


def update_trades_table():
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
            for column, col_type in (("close_price", "REAL"), ("pnl", "REAL"), ("close_reason", "TEXT")):
                if column not in existing:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {column} {col_type}")
            conn.commit()
        return True
    except Exception as e:
        print(f"update_trades_table error: {e}")
        return False


def log_signal(epic, ema20, ema50, rsi, atr, signal):
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO signals (timestamp, epic, ema20, ema50, rsi, atr, signal_generated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), epic, ema20, ema50, rsi, atr, signal),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"log_signal error: {e}")
        return False


def log_trade(epic, direction, size, entry_price, stop_loss, take_profit, status, deal_id=None, error=None):
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO trades (timestamp, epic, direction, size, entry_price, stop_loss, "
                "take_profit, status, deal_id, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), epic, direction, size, entry_price, stop_loss,
                 take_profit, status, deal_id, error),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"log_trade error: {e}")
        return False


def update_trade_status(deal_id, status, close_price=None, pnl=None, close_reason=None):
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute(
                "UPDATE trades SET status = ?, close_price = ?, pnl = ?, close_reason = ? WHERE deal_id = ?",
                (status, close_price, pnl, close_reason, deal_id),
            )
            conn.commit()
        return True
    except Exception as e:
        print(f"update_trade_status error: {e}")
        return False


if __name__ == "__main__":
    print("init_db:", init_db())
    print("log_signal:", log_signal("GOLD", 4130.5, 4125.1, 52.3, 16.2, "NONE"))
    print("log_trade:", log_trade("GOLD", "LONG", 1.33, 2000.0, 1992.5, 2015.0, "OPENED", deal_id="TEST123"))

    with sqlite3.connect(config.DB_PATH) as conn:
        print("\nsignals:")
        for row in conn.execute("SELECT * FROM signals"):
            print(row)
        print("\ntrades:")
        for row in conn.execute("SELECT * FROM trades"):
            print(row)
