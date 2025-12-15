import asyncio
import logging
import re
from typing import Dict, Any, List

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import local simplified modules
from config import BOT_TOKEN
from db import (
    init_db, ensure_user, get_user, set_language, count_routes, 
    list_routes, add_route, update_route_field, delete_route, 
    set_notify_mode
)
from api import search_stations
from scheduler import scheduler_tick, check_and_notify_for_user, update_route_names_for_language
from texts import t, TEXT

# --- LOGGING ---
from logging.handlers import RotatingFileHandler
import sys

# Configure logging with rotation (max 5MB per file, keep 2 backups)
logger = logging.getLogger("railway_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)

# File handler with rotation
file_handler = RotatingFileHandler(
    "railway_bot.log",
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=2  # Keep 2 backup files
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(console_formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# --- STATES ---
class InitFSM(StatesGroup):
    lang = State()

class AddRouteFSM(StatesGroup):
    from_city_query = State()
    to_city_query = State()
    date = State()

class RoutesFSM(StatesGroup):
    list = State()
    view = State()
    edit_menu = State()
    edit_from_query = State()
    edit_to_query = State()
    edit_date = State()
    delete_confirm = State()

class SettingsFSM(StatesGroup):
    menu = State()
    changing_lang = State()

# --- KEYBOARDS ---
def kb_lang_reply(lang_ui: str, show_back: bool = True) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=TEXT["ru"]["lang_ru"])],
        [KeyboardButton(text=TEXT["ru"]["lang_uz"])],
        [KeyboardButton(text=TEXT["ru"]["lang_en"])],
    ]
    if show_back:
        rows.append([KeyboardButton(text=t(lang_ui, "back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_main(lang: str, has_routes: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "add"))],
        [KeyboardButton(text=t(lang, "my"))],
        [KeyboardButton(text=t(lang, "settings"))],
    ]
    if has_routes:
        rows.append([KeyboardButton(text=t(lang, "check"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_cancel(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "cancel"))]], resize_keyboard=True)

def kb_back(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "back"))]], resize_keyboard=True)

def kb_yes_no(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "yes")), KeyboardButton(text=t(lang, "no"))]],
        resize_keyboard=True
    )

def kb_routes_list(lang: str, routes: List[Dict[str, Any]]) -> ReplyKeyboardMarkup:
    rows = []
    for idx, r in enumerate(routes, start=1):
        rows.append([KeyboardButton(text=f"{idx}. {r['from_name']} → {r['to_name']}")])
    rows.append([KeyboardButton(text=t(lang, "back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_routes_inline(routes: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, r in enumerate(routes, start=1):
        # Callback data: "route_view:ID"
        date_str = fmt_date_for_ui(r['travel_date'])
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. {r['from_name']} → {r['to_name']} ({date_str})",
            callback_data=f"route_view:{r['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def kb_route_actions(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "back"))],
            [KeyboardButton(text=t(lang, "edit"))],
            [KeyboardButton(text=t(lang, "delete"))],
        ],
        resize_keyboard=True
    )

def kb_route_edit_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "back"))],
            [KeyboardButton(text=t(lang, "edit_from"))],
            [KeyboardButton(text=t(lang, "edit_to"))],
            [KeyboardButton(text=t(lang, "edit_date"))],
        ],
        resize_keyboard=True
    )

def kb_settings_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "settings_lang"))],
            [KeyboardButton(text=t(lang, "settings_notify"))],
            [KeyboardButton(text=t(lang, "back"))],
        ],
        resize_keyboard=True
    )

def kb_notify_mode(lang: str, current_mode: str = "always") -> ReplyKeyboardMarkup:
    # Add checkmark to the currently selected mode
    always_text = t(lang, "notify_always")
    on_available_text = t(lang, "notify_on_available")
    
    if current_mode == "always":
        always_text += " ✅"
    else:
        on_available_text += " ✅"
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=always_text)],
            [KeyboardButton(text=on_available_text)],
            [KeyboardButton(text=t(lang, "back"))],
        ],
        resize_keyboard=True
    )

def kb_stations_inline(stations: List[Dict[str, str]], prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    for s in stations[:10]:
        code = s.get("code", "")
        name = s.get("name", "")
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"pick:{prefix}:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- HELPERS ---
def parse_date_ddmmyyyy(text: str) -> str:
    # returns YYYY-MM-DD or None
    text = text.strip()
    # simple regex for dd.mm.yyyy or d.m.yyyy
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", text)
    if not m:
        return None
    d, m, y = m.groups()
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

def fmt_date_for_ui(date_str: str) -> str:
    # YYYY-MM-DD -> DD.MM.YYYY
    try:
        parts = date_str.split("-")
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    except:
        return date_str

# --- HANDLERS: COMMON ---
async def on_start(msg: Message, state: FSMContext):
    await state.clear()
    await ensure_user(msg.from_user.id)
    await state.set_state(InitFSM.lang)
    await msg.answer(TEXT["ru"]["hello_3"], reply_markup=kb_lang_reply("ru", show_back=False))

async def on_lang_chosen(msg: Message, state: FSMContext):
    txt = (msg.text or "").strip()
    new_lang = None
    if txt == TEXT["ru"]["lang_ru"]: new_lang = "ru"
    elif txt == TEXT["ru"]["lang_uz"]: new_lang = "uz"
    elif txt == TEXT["ru"]["lang_en"]: new_lang = "en"
    
    if not new_lang: return

    await set_language(msg.from_user.id, new_lang)
    
    # Update route names synchronously to new language
    await update_route_names_for_language(msg.from_user.id, new_lang)

    await state.clear()
    has_routes = (await count_routes(msg.from_user.id)) > 0
    await msg.answer(t(new_lang, "menu_main"), reply_markup=kb_main(new_lang, has_routes))

# --- HANDLERS: MENU FILTERS ---
async def filter_add_route(msg: Message) -> bool:
    user = await get_user(msg.from_user.id)
    return msg.text == t(user["language"], "add")

async def filter_my_routes(msg: Message) -> bool:
    user = await get_user(msg.from_user.id)
    return msg.text == t(user["language"], "my")

async def filter_check_routes(msg: Message) -> bool:
    user = await get_user(msg.from_user.id)
    return msg.text == t(user["language"], "check")

async def filter_settings_cmd(msg: Message) -> bool:
    user = await get_user(msg.from_user.id)
    return msg.text == t(user["language"], "settings")

async def filter_cancel(msg: Message) -> bool:
    user = await get_user(msg.from_user.id)
    return msg.text == t(user["language"], "cancel")

# --- HANDLERS: MAIN FLOW ---
async def on_cancel(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    await state.clear()
    has = (await count_routes(msg.from_user.id)) > 0
    await msg.answer("❌", reply_markup=kb_main(lang, has))

async def on_add_route_start(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    if await count_routes(msg.from_user.id) >= 5:
        await msg.answer(t(lang, "max_routes"), reply_markup=kb_main(lang, has_routes=True))
        await state.clear()
        return
    await state.clear()
    await state.set_state(AddRouteFSM.from_city_query)
    await msg.answer(t(lang, "enter_from"), reply_markup=kb_cancel(lang))

async def on_my_routes(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    routes = await list_routes(msg.from_user.id)
    await state.clear()
    await state.set_state(RoutesFSM.list)
    
    # 1. Update Reply Keyboard to show only "Back" -- REMOVED per user request
    # await msg.answer(t(lang, "my"), reply_markup=kb_back(lang))
    
    if not routes:
        await msg.answer(t(lang, "no_routes"))
    else:
        # 2. Send Inline Keyboard with routes
        await msg.answer(t(lang, "select_route"), reply_markup=kb_routes_inline(routes))

async def on_check_routes(msg: Message):
    user = await get_user(msg.from_user.id)
    # await msg.answer(t(lang, "checking")) # User requested removal
    await check_and_notify_for_user(msg.bot, msg.from_user.id, force_send=True)

# --- ADD ROUTE ---
async def add_route_from_query(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    q = (msg.text or "").strip()
    try:
        stations = await search_stations(q, lang)
    except Exception:
        await msg.answer(t(lang, "unknown_error"))
        return
    if not stations:
        await msg.answer(t(lang, "city_not_found"))
        return
    await state.update_data(last_station_results=stations)
    await msg.answer(t(lang, "enter_from"), reply_markup=kb_stations_inline(stations, "from"))

async def pick_from_station(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = user["language"]
    code = cb.data.split(":")[-1]
    data = await state.get_data()
    stations = data.get("last_station_results", []) or []
    station = next((s for s in stations if s.get("code") == code), None)
    if not station:
        await cb.answer()
        return
    await state.update_data(from_code=station["code"], from_name=station["name"])
    await state.set_state(AddRouteFSM.to_city_query)
    await cb.message.edit_text(f"✅ {station['name']}")
    await cb.message.answer(t(lang, "enter_to"), reply_markup=kb_cancel(lang))
    await cb.answer()

async def add_route_to_query(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    q = (msg.text or "").strip()
    try:
        stations = await search_stations(q, lang)
    except Exception:
        await msg.answer(t(lang, "unknown_error"))
        return
    if not stations:
        await msg.answer(t(lang, "city_not_found"))
        return
    await state.update_data(last_station_results=stations)
    await msg.answer(t(lang, "enter_to"), reply_markup=kb_stations_inline(stations, "to"))

async def pick_to_station(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = user["language"]
    code = cb.data.split(":")[-1]
    data = await state.get_data()
    stations = data.get("last_station_results", []) or []
    station = next((s for s in stations if s.get("code") == code), None)
    if not station:
        await cb.answer()
        return
    await state.update_data(to_code=station["code"], to_name=station["name"])
    await state.set_state(AddRouteFSM.date)
    await cb.message.edit_text(f"✅ {station['name']}")
    await cb.message.answer(t(lang, "enter_date"), reply_markup=kb_cancel(lang))
    await cb.answer()

async def add_route_date(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    date_api = parse_date_ddmmyyyy(msg.text or "")
    if not date_api:
        await msg.answer(t(lang, "bad_date"))
        return
    if await count_routes(msg.from_user.id) >= 5:
        await msg.answer(t(lang, "max_routes"))
        await state.clear()
        has = (await count_routes(msg.from_user.id)) > 0
        await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))
        return
    data = await state.get_data()
    from_code, from_name = data.get("from_code"), data.get("from_name")
    to_code, to_name = data.get("to_code"), data.get("to_name")
    if not all([from_code, from_name, to_code, to_name]):
        await msg.answer(t(lang, "unknown_error"))
        await state.clear()
        has = (await count_routes(msg.from_user.id)) > 0
        await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))
        return
    new_route_id = await add_route(msg.from_user.id, from_code, from_name, to_code, to_name, date_api)
    await msg.answer(t(lang, "saved"))
    
    # Immediate check for the new route
    # Run in background to not block UI, or await if fast enough. 
    # User requested immediate 11:17 check for THIS ROUTE ONLY.
    # We call check_and_notify_for_user with force_send=True and specific_route_id.
    asyncio.create_task(check_and_notify_for_user(msg.bot, msg.from_user.id, force_send=True, specific_route_id=new_route_id))
    await state.clear()
    has = (await count_routes(msg.from_user.id)) > 0
    await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))

# --- ROUTES LIST ACTIONS ---
async def routes_list_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    txt = (msg.text or "").strip()
    if txt == t(lang, "back"):
         await state.clear()
         has = (await count_routes(msg.from_user.id)) > 0
         await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))
         return
    m = re.match(r"^(\d+)\.\s+", txt)
    if not m: return
    idx = int(m.group(1))
    routes = await list_routes(msg.from_user.id)
    if idx < 1 or idx > len(routes): return
    route = routes[idx - 1]
    await state.update_data(route_id=route["id"], route_index=idx)
    await state.set_state(RoutesFSM.view)
    await msg.answer(
        f"{t(lang, 'route_view_title').format(n=idx)}\n"
        f"{route['from_name']} → {route['to_name']}\n"
        f"📅 {fmt_date_for_ui(route['travel_date'])}",
        reply_markup=kb_route_actions(lang),
    )

async def route_view_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    txt = (msg.text or "").strip()
    if txt == t(lang, "back"):
        # 1. Restore Main Menu Keyboard (with "My Routes" active context)
        # Note: "Back" from "My Routes" (list) currently triggers on_my_routes logic? No.
        # on_my_routes sets state RoutesFSM.list.
        # This handler handles "Back" from View.
        
        # User wants "Main Menu buttons" to return.
        has = (await count_routes(msg.from_user.id)) > 0
        await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))

        routes = await list_routes(msg.from_user.id)
        await state.set_state(RoutesFSM.list)
        if not routes: 
            await msg.answer(t(lang, "no_routes"))
        else: 
            await msg.answer(t(lang, "select_route"), reply_markup=kb_routes_inline(routes))
        return
    if txt == t(lang, "edit"):
        await state.set_state(RoutesFSM.edit_menu)
        await msg.answer(t(lang, "edit"), reply_markup=kb_route_edit_menu(lang))
        return
    if txt == t(lang, "delete"):
        await state.set_state(RoutesFSM.delete_confirm)
        await msg.answer(t(lang, "delete_confirm"), reply_markup=kb_yes_no(lang))
        return

async def route_edit_menu_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    txt = (msg.text or "").strip()
    data = await state.get_data()
    route_id = int(data.get("route_id", 0))

    if txt == t(lang, "back"):
        routes = await list_routes(msg.from_user.id)
        idx = int(data.get("route_index", 1))
        route = next((r for r in routes if r["id"] == route_id), None)
        await state.set_state(RoutesFSM.view)
        if route:
            await msg.answer(
                f"{t(lang, 'route_view_title').format(n=idx)}\n"
                f"{route['from_name']} → {route['to_name']}\n"
                f"📅 {fmt_date_for_ui(route['travel_date'])}",
                reply_markup=kb_route_actions(lang),
            )
        else:
             await state.set_state(RoutesFSM.list)
             await msg.answer(t(lang, "no_routes"), reply_markup=kb_back(lang))
        return

    if txt == t(lang, "edit_from"):
        await state.set_state(RoutesFSM.edit_from_query)
        await msg.answer(t(lang, "enter_from"), reply_markup=kb_cancel(lang))
        return
    if txt == t(lang, "edit_to"):
        await state.set_state(RoutesFSM.edit_to_query)
        await msg.answer(t(lang, "enter_to"), reply_markup=kb_cancel(lang))
        return
    if txt == t(lang, "edit_date"):
        await state.set_state(RoutesFSM.edit_date)
        await msg.answer(t(lang, "enter_date"), reply_markup=kb_cancel(lang))
        return

async def edit_from_query_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    q = (msg.text or "").strip()
    try: stations = await search_stations(q, lang)
    except Exception: await msg.answer(t(lang, "unknown_error")); return
    if not stations: await msg.answer(t(lang, "city_not_found")); return
    await state.update_data(last_station_results=stations)
    await msg.answer(t(lang, "enter_from"), reply_markup=kb_stations_inline(stations, "edit_from"))

async def pick_edit_from(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = user["language"]
    code = cb.data.split(":")[-1]
    data = await state.get_data()
    route_id = int(data.get("route_id", 0))
    stations = data.get("last_station_results", []) or []
    station = next((s for s in stations if s.get("code") == code), None)
    if not station: await cb.answer(); return
    await update_route_field(route_id, "from_code", station["code"])
    await update_route_field(route_id, "from_name", station["name"])
    await state.set_state(RoutesFSM.edit_menu)
    await cb.message.edit_text(f"✅ {station['name']}")
    await cb.message.answer(t(lang, "updated"), reply_markup=kb_route_edit_menu(lang))
    await cb.answer()

async def edit_to_query_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    q = (msg.text or "").strip()
    try: stations = await search_stations(q, lang)
    except Exception: await msg.answer(t(lang, "unknown_error")); return
    if not stations: await msg.answer(t(lang, "city_not_found")); return
    await state.update_data(last_station_results=stations)
    await msg.answer(t(lang, "enter_to"), reply_markup=kb_stations_inline(stations, "edit_to"))

async def pick_edit_to(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = user["language"]
    code = cb.data.split(":")[-1]
    data = await state.get_data()
    route_id = int(data.get("route_id", 0))
    stations = data.get("last_station_results", []) or []
    station = next((s for s in stations if s.get("code") == code), None)
    if not station: await cb.answer(); return
    await update_route_field(route_id, "to_code", station["code"])
    await update_route_field(route_id, "to_name", station["name"])
    await state.set_state(RoutesFSM.edit_menu)
    await cb.message.edit_text(f"✅ {station['name']}")
    await cb.message.answer(t(lang, "updated"), reply_markup=kb_route_edit_menu(lang))
    await cb.answer()

async def edit_date_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    date_api = parse_date_ddmmyyyy(msg.text or "")
    if not date_api: await msg.answer(t(lang, "bad_date")); return
    data = await state.get_data()
    route_id = int(data.get("route_id", 0))
    await update_route_field(route_id, "travel_date", date_api)
    await state.set_state(RoutesFSM.edit_menu)
    await msg.answer(t(lang, "updated"), reply_markup=kb_route_edit_menu(lang))

async def delete_confirm_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    txt = (msg.text or "").strip()
    data = await state.get_data()
    route_id = int(data.get("route_id", 0))

    if txt == t(lang, "no"):
        await state.set_state(RoutesFSM.view)
        routes = await list_routes(msg.from_user.id)
        idx = int(data.get("route_index", 1))
        route = next((r for r in routes if r["id"] == route_id), None)
        if route:
            await msg.answer(
                f"{t(lang, 'route_view_title').format(n=idx)}\n"
                f"{route['from_name']} → {route['to_name']}\n"
                f"📅 {fmt_date_for_ui(route['travel_date'])}",
                reply_markup=kb_route_actions(lang),
            )
        else:
             await state.set_state(RoutesFSM.list)
             await msg.answer(t(lang, "no_routes"), reply_markup=kb_back(lang))
        return

    if txt == t(lang, "yes"):
        await delete_route(route_id)
        await state.clear()
        has = (await count_routes(msg.from_user.id)) > 0
        await msg.answer(t(lang, "route_deleted"), reply_markup=kb_main(lang, has))
        return

# --- HANDLERS: SETTINGS ---
async def on_settings_entry(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    await state.clear()
    await state.set_state(SettingsFSM.menu)
    await msg.answer(t(lang, "settings_title"), reply_markup=kb_settings_menu(lang))

async def settings_menu_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = user["language"]
    txt = (msg.text or "").strip()

    if txt == t(lang, "settings_lang"):
        await state.set_state(SettingsFSM.changing_lang)
        await msg.answer(t(lang, "choose_lang"), reply_markup=kb_lang_reply(lang))
        return

    if txt == t(lang, "settings_notify"):
        user = await get_user(msg.from_user.id)
        current_mode = user.get("notify_mode", "always")
        await msg.answer(t(lang, "settings_notify"), reply_markup=kb_notify_mode(lang, current_mode))
        return

    # Remove checkmark from button text before comparing
    if txt.replace(" ✅", "") == t(lang, "notify_always"):
        await set_notify_mode(msg.from_user.id, "always")
        user = await get_user(msg.from_user.id)
        await msg.answer(t(lang, "settings_saved"), reply_markup=kb_settings_menu(lang))
        return

    if txt.replace(" ✅", "") == t(lang, "notify_on_available"):
        await set_notify_mode(msg.from_user.id, "on_available")
        await msg.answer(t(lang, "settings_saved"), reply_markup=kb_settings_menu(lang))
        return

    if txt == t(lang, "back"):
        await state.clear()
        has = (await count_routes(msg.from_user.id)) > 0
        await msg.answer(t(lang, "menu_main"), reply_markup=kb_main(lang, has))
        return

async def changing_lang_handler(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    current_lang = user["language"]
    txt = (msg.text or "").strip()

    if txt == t(current_lang, "back"):
        await state.set_state(SettingsFSM.menu)
        await msg.answer(t(current_lang, "settings_title"), reply_markup=kb_settings_menu(current_lang))
        return

    new_lang = None
    if txt == TEXT["ru"]["lang_ru"]: new_lang = "ru"
    elif txt == TEXT["ru"]["lang_uz"]: new_lang = "uz"
    elif txt == TEXT["ru"]["lang_en"]: new_lang = "en"

    if new_lang:
        await set_language(msg.from_user.id, new_lang)
        # Update route names synchronously to new language
        await update_route_names_for_language(msg.from_user.id, new_lang)
        await state.set_state(SettingsFSM.menu)
        await msg.answer(t(new_lang, "settings_saved"), reply_markup=kb_settings_menu(new_lang))

# --- CALLBACKS ---
async def route_view_callback(cb: CallbackQuery, state: FSMContext):
    user = await get_user(cb.from_user.id)
    lang = user["language"]
    
    # data: "route_view:ID"
    try:
        route_id = int(cb.data.split(":")[-1])
    except:
        await cb.answer(t(lang, "unknown_error"))
        return

    routes = await list_routes(cb.from_user.id)
    route = next((r for r in routes if r["id"] == route_id), None)
    
    if not route:
        await cb.answer(t(lang, "no_routes")) # or "route not found"
        # Refresh list?
        return

    # Set state to VIEW
    # Calculate index for display (1-based)
    idx = 1
    for i, r in enumerate(routes, 1):
        if r["id"] == route_id:
            idx = i
            break
    
    await state.update_data(route_id=route["id"], route_index=idx)
    await state.set_state(RoutesFSM.view)
    
    await cb.message.answer(
        f"{t(lang, 'route_view_title').format(n=idx)}\n"
        f"{route['from_name']} → {route['to_name']}\n"
        f"📅 {fmt_date_for_ui(route['travel_date'])}",
        reply_markup=kb_route_actions(lang),
    )
    await cb.answer()

# --- MAIN ---
async def main():
    logger.info("Starting bot...")
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # --- REGISTER HANDLERS ---
    
    # 1. Global /start
    dp.message.register(on_start, Command("start"))

    # 2. Init Language
    dp.message.register(on_lang_chosen, InitFSM.lang)

    # 3. Global Commands (Cancel, Menu actions that are global)
    # Order matters. Specific filters first.
    dp.message.register(on_cancel, filter_cancel)

    # 4. Main Menu Buttons
    dp.message.register(on_add_route_start, filter_add_route)
    dp.message.register(on_my_routes, filter_my_routes)
    dp.message.register(on_check_routes, filter_check_routes)
    dp.message.register(on_settings_entry, filter_settings_cmd)

    # 5. Add Route Flow
    dp.message.register(add_route_from_query, AddRouteFSM.from_city_query)
    dp.callback_query.register(pick_from_station, F.data.startswith("pick:from:"))
    dp.message.register(add_route_to_query, AddRouteFSM.to_city_query)
    dp.callback_query.register(pick_to_station, F.data.startswith("pick:to:"))
    dp.message.register(add_route_date, AddRouteFSM.date)

    # 6. Routes List & View & Edit
    dp.message.register(routes_list_handler, RoutesFSM.list)
    
    # NEW Inline handler
    dp.callback_query.register(route_view_callback, F.data.startswith("route_view:"))
    
    dp.message.register(route_view_handler, RoutesFSM.view)
    dp.message.register(route_edit_menu_handler, RoutesFSM.edit_menu)

    # Edit Flow
    dp.message.register(edit_from_query_handler, RoutesFSM.edit_from_query)
    dp.callback_query.register(pick_edit_from, F.data.startswith("pick:edit_from:"))
    dp.message.register(edit_to_query_handler, RoutesFSM.edit_to_query)
    dp.callback_query.register(pick_edit_to, F.data.startswith("pick:edit_to:"))
    dp.message.register(edit_date_handler, RoutesFSM.edit_date)
    
    # Delete Confirm
    dp.message.register(delete_confirm_handler, RoutesFSM.delete_confirm)

    # 7. Settings
    dp.message.register(settings_menu_handler, SettingsFSM.menu)
    dp.message.register(changing_lang_handler, SettingsFSM.changing_lang)

    # --- SCHEDULER ---
    scheduler = AsyncIOScheduler()
    # "cron" trigger for strict alignment (0, 5, 10, ...)
    # If user wants 30 mins: minute="0,30"
    # For now testing 5 mins: minute="*/5"
    scheduler.add_job(scheduler_tick, "cron", minute="*/5", id="tick_30m", replace_existing=True, args=[bot])
    scheduler.start()
    logger.info("Scheduler started.")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
