import aiosqlite
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from config import DB_PATH

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ru',
                notify_mode TEXT NOT NULL DEFAULT 'always',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                from_code TEXT NOT NULL,
                from_name TEXT NOT NULL,
                to_code TEXT NOT NULL,
                to_name TEXT NOT NULL,
                travel_date TEXT NOT NULL,   -- YYYY-MM-DD
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS route_state (
                route_id INTEGER PRIMARY KEY,
                last_available INTEGER NOT NULL DEFAULT 0,
                last_checked_at TEXT,
                notifications_sent INTEGER NOT NULL DEFAULT 0,
                last_notified_at TEXT,
                FOREIGN KEY(route_id) REFERENCES routes(id)
            )
        """)
        # Migration for existing table
        try:
            await db.execute("ALTER TABLE route_state ADD COLUMN notifications_sent INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass 
        try:
            await db.execute("ALTER TABLE route_state ADD COLUMN last_notified_at TEXT")
        except Exception:
            pass
        await db.commit()

async def ensure_user(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        if not row:
            ts = now_iso()
            await db.execute(
                "INSERT INTO users (telegram_id, language, notify_mode, created_at, updated_at) VALUES (?,?,?,?,?)",
                (telegram_id, "ru", "always", ts, ts)
            )
            await db.commit()

async def get_user(telegram_id: int) -> Dict[str, Any]:
    await ensure_user(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT telegram_id, language, notify_mode FROM users WHERE telegram_id=?",
            (telegram_id,)
        )
        row = await cur.fetchone()
        return {"telegram_id": row[0], "language": row[1], "notify_mode": row[2]}

async def set_language(telegram_id: int, lang: str) -> None:
    await ensure_user(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language=?, updated_at=? WHERE telegram_id=?",
            (lang, now_iso(), telegram_id)
        )
        await db.commit()

async def set_notify_mode(telegram_id: int, mode: str) -> None:
    await ensure_user(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET notify_mode=?, updated_at=? WHERE telegram_id=?",
            (mode, now_iso(), telegram_id)
        )
        await db.commit()

async def count_routes(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM routes WHERE telegram_id=?", (telegram_id,))
        (cnt,) = await cur.fetchone()
        return int(cnt)

async def list_routes(telegram_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, from_code, from_name, to_code, to_name, travel_date FROM routes WHERE telegram_id=? ORDER BY id ASC",
            (telegram_id,)
        )
        rows = await cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "from_code": r[1],
            "from_name": r[2],
            "to_code": r[3],
            "to_name": r[4],
            "travel_date": r[5],
        })
    return out

async def add_route(telegram_id: int, from_code: str, from_name: str, to_code: str, to_name: str, travel_date: str) -> int:
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO routes (telegram_id, from_code, from_name, to_code, to_name, travel_date, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (telegram_id, from_code, from_name, to_code, to_name, travel_date, ts, ts)
        )
        await db.commit()
        route_id = cur.lastrowid
        # Initialize route_state with current time for last_notified_at to prevent immediate notification
        await db.execute(
            "INSERT OR IGNORE INTO route_state (route_id, last_available, last_notified_at) VALUES (?,0,?)", 
            (route_id, ts)
        )
        await db.commit()
        return int(route_id)

async def update_route_field(route_id: int, field: str, value: str) -> None:
    if field not in {"from_code", "from_name", "to_code", "to_name", "travel_date"}:
        raise ValueError("Bad field")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE routes SET {field}=?, updated_at=? WHERE id=?",
            (value, now_iso(), route_id)
        )
        await db.commit()

async def delete_route(route_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM route_state WHERE route_id=?", (route_id,))
        await db.execute("DELETE FROM routes WHERE id=?", (route_id,))
        await db.commit()

async def update_last_notified(route_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE route_state SET last_notified_at=? WHERE route_id=?", (now_iso(), route_id))
        await db.commit()

async def get_route_state(route_id: int) -> Tuple[int, str, int, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT last_available, last_checked_at, notifications_sent, last_notified_at FROM route_state WHERE route_id=?", (route_id,))
        row = await cur.fetchone()
        if not row: return (0, None, 0, None)
        return (row[0], row[1], row[2], row[3])

async def set_route_state(route_id: int, available: bool):
    # This keeps existing values for others
    # Actually we should use UPSERT logic properly or read-modify-write if UPSERT is complex for partial.
    # But here we just want to update last_available and last_checked_at.
    now = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        # Check existence
        cur = await db.execute("SELECT 1 FROM route_state WHERE route_id=?", (route_id,))
        exists = await cur.fetchone()
        if exists:
            await db.execute("UPDATE route_state SET last_available=?, last_checked_at=? WHERE route_id=?", (1 if available else 0, now, route_id))
        else:
            await db.execute("INSERT INTO route_state(route_id, last_available, last_checked_at) VALUES (?,?,?)", (route_id, 1 if available else 0, now))
        await db.commit()

async def get_notification_count(route_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT notifications_sent FROM route_state WHERE route_id=?", (route_id,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def increment_notification_count(route_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE route_state SET notifications_sent = notifications_sent + 1 WHERE route_id=?", (route_id,))
        await db.commit()
        cur = await db.execute("SELECT notifications_sent FROM route_state WHERE route_id=?", (route_id,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def reset_notification_count(route_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE route_state SET notifications_sent=0 WHERE route_id=?", (route_id,))
        await db.commit()

async def list_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT telegram_id FROM users")
        rows = await cur.fetchall()
    return [int(r[0]) for r in rows]
