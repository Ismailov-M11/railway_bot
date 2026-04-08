"""
REST API server for the Telegram Mini App (Web App).
Runs alongside the bot using aiohttp.

Auth: every request must include header  X-Telegram-Init-Data: <initData>
      obtained from window.Telegram.WebApp.initData on the client side.
"""
import json
import hmac
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, parse_qsl

from aiohttp import web

from config import BOT_TOKEN
from db import (
    get_user, ensure_user, list_routes, add_route,
    update_route_field, delete_route,
    set_language, set_notify_mode, count_routes,
)
from api import fetch_trains, search_stations
from scheduler import parse_ticket_info

logger = logging.getLogger("railway_bot.api")

WEBAPP_ORIGIN = os.getenv("WEBAPP_ORIGIN", "https://railway-bot.netlify.app")
MAX_ROUTES = 5


# ─── CORS ────────────────────────────────────────────────────────────────────

def _cors(origin: str | None = None) -> dict:
    return {
        "Access-Control-Allow-Origin":  origin or WEBAPP_ORIGIN,
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
        "Access-Control-Max-Age":       "86400",
    }


async def handle_options(request: web.Request) -> web.Response:
    return web.Response(headers=_cors())


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _verify_init_data(init_data: str) -> dict:
    """Verify Telegram initData HMAC and return the user dict."""
    parsed = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
    received_hash = parsed.pop("hash", "")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData hash")

    return json.loads(parsed.get("user", "{}"))


async def _auth(request: web.Request) -> dict:
    """Return {'telegram_id': int, 'tg_user': dict} or raise HTTP 401."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise web.HTTPUnauthorized(reason="Missing X-Telegram-Init-Data")
    try:
        tg_user = _verify_init_data(init_data)
        telegram_id = int(tg_user.get("id", 0))
        if not telegram_id:
            raise ValueError("No user id")
        await ensure_user(telegram_id)
        return {"telegram_id": telegram_id, "tg_user": tg_user}
    except web.HTTPUnauthorized:
        raise
    except Exception as exc:
        logger.warning("Auth failed: %s", exc)
        raise web.HTTPUnauthorized(reason="Invalid initData")


# ─── Response helper ──────────────────────────────────────────────────────────

def ok(data: dict, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False),
        content_type="application/json",
        status=status,
        headers=_cors(),
    )


def err(message: str, status: int = 400) -> web.Response:
    return web.Response(
        text=json.dumps({"error": message}, ensure_ascii=False),
        content_type="application/json",
        status=status,
        headers=_cors(),
    )


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def api_user(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    user = await get_user(ctx["telegram_id"])
    return ok({"user": user})


async def api_get_routes(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    routes = await list_routes(ctx["telegram_id"])
    return ok({"routes": routes})


async def api_create_route(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    tid = ctx["telegram_id"]

    cnt = await count_routes(tid)
    if cnt >= MAX_ROUTES:
        return err("Max routes reached (5)", 400)

    try:
        body = await request.json()
        required = ("from_code", "from_name", "to_code", "to_name", "travel_date")
        for field in required:
            if not body.get(field):
                return err(f"Missing field: {field}", 400)

        # Validate date not in past (Tashkent UTC+5)
        tz_uz = timezone(timedelta(hours=5))
        today = datetime.now(tz_uz).date()
        travel = datetime.strptime(body["travel_date"], "%Y-%m-%d").date()
        if travel < today:
            return err("Travel date has already passed", 400)

        route_id = await add_route(
            tid,
            body["from_code"], body["from_name"],
            body["to_code"],   body["to_name"],
            body["travel_date"],
        )
        routes = await list_routes(tid)
        route = next((r for r in routes if r["id"] == route_id), None)
        return ok({"route": route}, 201)
    except Exception as exc:
        logger.error("create_route error: %s", exc)
        return err(str(exc), 500)


async def api_update_route(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    route_id = int(request.match_info["id"])

    routes = await list_routes(ctx["telegram_id"])
    if not any(r["id"] == route_id for r in routes):
        return err("Route not found", 404)

    try:
        body = await request.json()
        allowed = {"from_code", "from_name", "to_code", "to_name", "travel_date"}

        if "travel_date" in body:
            tz_uz = timezone(timedelta(hours=5))
            today = datetime.now(tz_uz).date()
            travel = datetime.strptime(body["travel_date"], "%Y-%m-%d").date()
            if travel < today:
                return err("Travel date has already passed", 400)

        for field, value in body.items():
            if field in allowed:
                await update_route_field(route_id, field, str(value))

        routes = await list_routes(ctx["telegram_id"])
        route = next((r for r in routes if r["id"] == route_id), None)
        return ok({"route": route})
    except Exception as exc:
        logger.error("update_route error: %s", exc)
        return err(str(exc), 500)


async def api_delete_route(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    route_id = int(request.match_info["id"])

    routes = await list_routes(ctx["telegram_id"])
    if not any(r["id"] == route_id for r in routes):
        return err("Route not found", 404)

    await delete_route(route_id)
    return ok({"ok": True})


async def api_check_route(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    route_id = int(request.match_info["id"])

    routes = await list_routes(ctx["telegram_id"])
    route = next((r for r in routes if r["id"] == route_id), None)
    if not route:
        return err("Route not found", 404)

    user = await get_user(ctx["telegram_id"])
    lang = user.get("language", "ru")

    try:
        api_json = await fetch_trains(
            route["from_code"], route["to_code"], route["travel_date"], lang
        )
        available, trains_data, _ = parse_ticket_info(api_json)
        tz_uz = timezone(timedelta(hours=5))
        checked_at = datetime.now(tz_uz).isoformat(timespec="seconds")
        return ok({
            "available": available,
            "trains": trains_data,
            "checked_at": checked_at,
        })
    except Exception as exc:
        logger.error("check_route error: %s", exc)
        return err(str(exc), 500)


async def api_check_all(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    tid = ctx["telegram_id"]
    user = await get_user(tid)
    lang = user.get("language", "ru")
    routes = await list_routes(tid)

    results = []
    tz_uz = timezone(timedelta(hours=5))
    checked_at = datetime.now(tz_uz).isoformat(timespec="seconds")

    for route in routes:
        try:
            api_json = await fetch_trains(
                route["from_code"], route["to_code"], route["travel_date"], lang
            )
            available, trains_data, _ = parse_ticket_info(api_json)
            results.append({
                "route_id": route["id"],
                "available": available,
                "trains": trains_data,
                "checked_at": checked_at,
            })
        except Exception as exc:
            results.append({"route_id": route["id"], "error": str(exc)})

    return ok({"results": results})


async def api_update_settings(request: web.Request) -> web.Response:
    ctx = await _auth(request)
    tid = ctx["telegram_id"]
    try:
        body = await request.json()
        if body.get("language") in ("ru", "uz", "en"):
            await set_language(tid, body["language"])
        if body.get("notify_mode") in ("always", "on_available"):
            await set_notify_mode(tid, body["notify_mode"])
        user = await get_user(tid)
        return ok({"user": user})
    except Exception as exc:
        logger.error("update_settings error: %s", exc)
        return err(str(exc), 500)


async def api_stations(request: web.Request) -> web.Response:
    await _auth(request)
    query = request.rel_url.query.get("q", "").strip()
    lang  = request.rel_url.query.get("lang", "ru")
    if len(query) < 2:
        return ok({"stations": []})
    try:
        stations = await search_stations(query, lang)
        return ok({"stations": stations})
    except Exception as exc:
        logger.warning("stations search error: %s", exc)
        return ok({"stations": []})


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get   ("/api/user",               api_user)
    app.router.add_get   ("/api/routes",              api_get_routes)
    app.router.add_post  ("/api/routes",              api_create_route)
    app.router.add_patch ("/api/routes/{id}",         api_update_route)
    app.router.add_delete("/api/routes/{id}",         api_delete_route)
    app.router.add_post  ("/api/routes/{id}/check",   api_check_route)
    app.router.add_post  ("/api/check-all",           api_check_all)
    app.router.add_patch ("/api/settings",            api_update_settings)
    app.router.add_get   ("/api/stations",            api_stations)
    return app
