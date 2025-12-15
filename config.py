import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set (use environment variable BOT_TOKEN)")

DB_PATH = os.getenv("DB_PATH", "db.sqlite3")

STATIONS_API = "https://eticket.railway.uz/api/v1/handbook/stations/list"
TRAINS_API = "https://eticket.railway.uz/api/v3/handbook/trains/list"

ETICKET_XSRF = os.getenv("ETICKET_XSRF", "").strip()
ETICKET_COOKIE = os.getenv("ETICKET_COOKIE", "").strip()

BASE_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
}
if ETICKET_XSRF:
    BASE_HEADERS["X-XSRF-TOKEN"] = ETICKET_XSRF
if ETICKET_COOKIE:
    BASE_HEADERS["Cookie"] = ETICKET_COOKIE
