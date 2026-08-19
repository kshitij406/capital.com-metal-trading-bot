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
        update_signals_table()
        return True
    except Exception as e:
        print(f"init_db error: {e}")
        return False


def update_trades_table():
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
            for column, col_type in (("close_price", "REAL"), ("pnl", "REAL"),
                                     ("close_reason", "TEXT"), ("strategy", "TEXT")):
                if column not in existing:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {column} {col_type}")
            conn.commit()
        return True
    except Exception as e:
        print(f"update_trades_table error: {e}")
        return False


def update_signals_table():
    """Add the forward-test decision columns to the signals table.

    Additive migration, matching update_trades_table: existing rows keep NULL in the
    new columns rather than being rewritten, so the pre-forward-test history stays
    intact and distinguishable.
    """
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(signals)")}
            for column, col_type in (
                ("strategy", "TEXT"),
                ("vol_regime", "REAL"),
                ("hour_utc", "INTEGER"),
                ("gate", "TEXT"),
                ("base_signal", "TEXT"),
                ("size_multiplier", "REAL"),
            ):
                if column not in existing:
                    conn.execute(f"ALTER TABLE signals ADD COLUMN {column} {col_type}")
            conn.commit()
        return True
    except Exception as e:
        print(f"update_signals_table error: {e}")
        return False


def log_signal(epic, ema_fast, ema_slow, rsi, atr, signal, context=None, size_multiplier=None):
    """The ema20/ema50 DB columns are legacy names retained for schema compatibility
    with existing rows - they hold config.EMA_FAST (9) and config.EMA_SLOW (21)."""
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            ctx = context or {}
            conn.execute(
                "INSERT INTO signals (timestamp, epic, ema20, ema50, rsi, atr, signal_generated, "
                "strategy, vol_regime, hour_utc, gate, base_signal, size_multiplier) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), epic, ema_fast, ema_slow, rsi, atr, signal,
                 config.STRATEGY, ctx.get("vol_regime"), ctx.get("hour_utc"), ctx.get("gate"),
                 ctx.get("base_signal"), size_multiplier),
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
                "take_profit, status, deal_id, error, strategy) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), epic, direction, size, entry_price, stop_loss,
                 take_profit, status, deal_id, error, config.STRATEGY),
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
