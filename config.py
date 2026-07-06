import os
from dotenv import load_dotenv

load_dotenv()

CAPITAL_API_KEY = os.environ["CAPITAL_API_KEY"]
CAPITAL_EMAIL = os.environ["CAPITAL_EMAIL"]
CAPITAL_PASSWORD = os.environ["CAPITAL_PASSWORD"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
IS_DEMO = os.environ["IS_DEMO"].lower() == "true"

CAPITAL_BASE_URL = os.environ["CAPITAL_BASE_DEMO_URL"] if IS_DEMO else os.environ["CAPITAL_BASE_URL"]

EPIC = "GOLD"
RESOLUTION = "HOUR"
CANDLE_COUNT = 100

EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

RISK_PER_TRADE = 0.01
SL_ATR_MULT = 1.5
TP_ATR_MULT = 3.0

DB_PATH = "trades.db"
