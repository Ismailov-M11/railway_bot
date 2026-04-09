import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timezone, timedelta
from aiogram import Bot

from db import list_routes, set_route_state, get_route_state, list_users, get_user, update_route_field, increment_notification_count, delete_route, update_last_notified, reset_notification_count
from api import fetch_trains
from texts import t

logger = logging.getLogger("railway_bot")

# Simple formatters moved here from utils/formatters.py
def format_duration(lang: str, minutes_str: str) -> str:
    try:
        m = int(minutes_str)
    except:
        return minutes_str
    
    hours = m // 60
    mins = m % 60
    
    # Use keys from texts.py for full words
    fmt = t(lang, "time_h_m") # "{h} часов {m} минут"
    return fmt.format(h=hours, m=mins)

def get_number_emoji(n: int) -> str:
    # 0-9
    keycap_map = {
        0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣",
        5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"
    }
    if n <= 10:
        return keycap_map.get(n, str(n))
    
    # For > 10, combine digits: 12 -> 1️⃣2️⃣
    s = str(n)
    res = ""
    for char in s:
        digit = int(char)
        res += keycap_map.get(digit, char)
    return res

def car_icon(ctype: str) -> str:
    # Basic mapping
    if "плацкарт" in ctype.lower() or "plackart" in ctype.lower():
        return "🛏"
    if "купе" in ctype.lower() or "kupe" in ctype.lower():
        return "🚪"
    if "люкс" in ctype.lower() or "sv" in ctype.lower():
        return "💎"
    if "сидяч" in ctype.lower() or "o'rindiq" in ctype.lower():
        return "💺"
    return "🚃"

def parse_ticket_info(api_json: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]], int]:
    # Returns (is_available, [list of trains], travel_time_min)
    
    data = api_json.get("data", {})
    directions = data.get("directions", [])
    if isinstance(directions, dict):
        if not directions: return False, [], 0
        logger.info(f"Directions keys: {list(directions.keys())}")
        forward = next(iter(directions.values()))
    elif isinstance(directions, list):
        if not directions: return False, [], 0
        forward = directions[0]
    else:
        return False, [], 0

    trains = forward.get("trains", [])
    
    found_any = False
    result_trains = []
    min_time = 0

    for train in trains:
        # Check seats
        cars = train.get("cars", [])
        if not cars:
            continue
            
        train_cars_data = [] # List of dicts
        has_seats_train = False
        
        for car in cars:
            if not isinstance(car, dict): continue
            
            free = car.get("freeSeats", 0)
            if free > 0:
                has_seats_train = True
                found_any = True
                
                # Fix: type can be string "Плацкартный" or dict {"name": "..."}
                raw_type = car.get("type", "Gen")
                if isinstance(raw_type, dict):
                    ctype = raw_type.get("name", "Gen")
                else:
                    ctype = str(raw_type)
                
                # Try to get tariff from root or tariffs list
                tariff = car.get("tariff", 0)
                if not tariff:
                    tariffs = car.get("tariffs", [])
                    if isinstance(tariffs, list) and tariffs:
                         tariff = tariffs[0].get("tariff", 0)
                
                # Extract seat details
                seat_detail = car.get("seatDetail", {}) or {}
                # Ensure it's a dict
                if not isinstance(seat_detail, dict): seat_detail = {}
                
                # Format price with commas
                try: price_fmt = "{:,}".format(int(tariff))
                except: price_fmt = str(tariff)

                train_cars_data.append({
                    "type": ctype,
                    "free": free,
                    "price": price_fmt,
                    "up": seat_detail.get("up", 0),
                    "down": seat_detail.get("down", 0),
                    "lateral_up": seat_detail.get("lateralUp", 0),
                    "lateral_down": seat_detail.get("lateralDn", 0)
                })

        if has_seats_train:
            # simple logic: take first train duration or just keep overwriting
            min_time = train.get("duration", 0)
            
            # Extract time info
            dep_date_raw = train.get("departureDate", "")  # "15.01.2026 21:12"
            arr_date_raw = train.get("arrivalDate", "")    # "16.01.2026 11:08"
            time_str = train.get("timeOnWay", "")      # "13:56"
            
            # Request: display "15.01.2026 - 21:13"
            # API gives "15.01.2026 21:12" (space separated)
            # Reformat space to " - "
            dep_display = dep_date_raw.replace(" ", " - ")
            arr_display = arr_date_raw.replace(" ", " - ")

            # Origin Route (e.g. Андижан 1 - Кунград)
            # data.directions[0].trains[0].originRoute.depStationName / arvStationName
            origin_route = train.get("originRoute", {})
            route_name = f"{origin_route.get('depStationName', '?')} - {origin_route.get('arvStationName', '?')}"

            result_trains.append({
                "number": train.get("number", "???"),
                "type": train.get("brand", "") or train.get("type", ""),
                "route_name": route_name,
                "cars_data": train_cars_data,
                "dep_time": dep_display,
                "arr_time": arr_display,
                "duration": time_str
            })

    return found_any, result_trains, min_time

def fmt_date_for_ui(lang: str, date_str: str) -> str:
    # YYYY-MM-DD -> 15 Января 2026 года (if supported)
    try:
        parts = date_str.split("-")
        day = int(parts[2])
        month_idx = int(parts[1])
        year = parts[0]
        
        # Simple helper in texts.py or inline here? 
        # I cannot import get_month_name easily as it's not exported, assuming I added it or I'll implement lookup here
        # Actually I added "months" list to TEXT dict.
        from texts import t, TEXT
        months = TEXT.get(lang, TEXT["ru"]).get("months", [])
        m_name = months[month_idx] if 0 < month_idx < len(months) else parts[1]
        
        suffix = t(lang, "year_suffix")
        
        return f"{day} {m_name} {year}{suffix}"
    except:
        return date_str

async def build_route_message(lang: str, route: Dict[str, Any], api_json: Dict[str, Any]) -> Tuple[bool, str]:
    available, trains_data, time_on_way = parse_ticket_info(api_json)

    # Tashkent Time (UTC+5)
    tz_uz = timezone(timedelta(hours=5))
    ts = datetime.now(tz_uz).strftime("%H:%M")
    chk_line = t(lang, "check_time").format(ts=ts)
    
    # Header date
    date_ui = fmt_date_for_ui(lang, route["travel_date"])
    
    # Try to get localized route names from API if possible
    # parse_ticket_info returns a list of results, we can check the originRoute of the first train
    # BUT, originRoute is where the train started, which might be different from our search.
    # We should look at "from" and "to" in api_json root if available, but usually it's not.
    # However, api_json['data']['directions'] (list or dict)
    
    # HEURISTIC: Use the first train's departure station and arrival station from the search result segments
    # Actually, parse_ticket_info > trains > "station0" and "station1" in the train data? No.
    # The API returns trains that match the search.
    # api_json data structure:
    # "data": { "directions": [ { "trains": [ { "departureStation": "NAME", "arrivalStation": "NAME" ... } ] } ] }
    # These names are usually localized to the requested lang.
    
    from_name_loc = route["from_name"]
    to_name_loc = route["to_name"]
    
    if available and trains_data:
        # Use the first train's station names as they are likely what we searched for (or close enough)
        # We need to dig into api_json again or just use what we have in trains_data?
        # trains_data has "cars_data" etc, but not the station names of the query (it has route_name "Andijan - Kungrad" which is origin-destination of train).
        # Let's peek into api_json directly here since we have it.
        try:
            data = api_json.get("data", {})
            dur = data.get("directions", [])
            forward = []
            if isinstance(dur, list) and dur: forward = dur[0]
            elif isinstance(dur, dict) and dur: forward = next(iter(dur.values()))
            
            if forward:
                # The 'trains' list contains trains. 
                # usually each train object has 'departureStation' and 'arrivalStation' fields which are the ONES WE SEARCHED FOR (station0, station1).
                # ex: "departureStation": "TASHKENT", "arrivalStation": "SAMARKAND"
                ftrain = forward.get("trains", [])[0]
                fn = ftrain.get("departureStation", "")
                tn = ftrain.get("arrivalStation", "")
                if fn and tn:
                    from_name_loc = fn
                    to_name_loc = tn
        except:
             pass

    cars_text_parts = []
    if available:
        for idx, train in enumerate(trains_data, start=1):
            # 1️⃣. 🚈 Поезд 127Ф (Пассажирский)
            num = train["number"]
            ttype = train["type"] # e.g. "Afrosiyob" or "(Пассажирский)"
            
            # Number icon
            idx_emoji = get_number_emoji(idx)
            
            # Request: Change 🚈 to 🚄
            header_str = f"{idx_emoji}. 🚄 {t(lang, 'train_number').format(num=num).replace('🚄 ', '')}"
            
            # Append Type to Header line if present
            if ttype and ttype not in ["Gen"]:
                 # If it already has parens, don't add more?
                 # API sometimes returns "Пассажирский" (no parens) or "(Пассажирский)"
                 if "(" not in ttype:
                     header_str += f" ({ttype})"
                 else:
                     header_str += f" {ttype}"

            # 🛤 Андижан 1 - Кунград
            route_line_str = f"🛤 {train['route_name']}"
            
            # 🟢 Отбытие - 15.01.2026 - 21:13
            # 🔴 Прибытие - 16.01.2026 - 01:09
            dep_label = t(lang, "dep_time_label")
            arr_label = t(lang, "arr_time_label")
            dep_line = f"{dep_label} - {train['dep_time']}"
            arr_line = f"{arr_label} - {train['arr_time']}"
            
            # ⏳ Время в пути: 4 часа 15 минут
            dur_str = train["duration"]
            try:
                h, m = map(int, dur_str.split(":"))
                dur_fmt = format_duration(lang, str(h*60+m))
            except: 
                dur_fmt = dur_str
            dur_line = f"{t(lang, 'travel_time_label')}: {dur_fmt}"

            # SEATS
            # 🛏 Плацкартный — 222 мест — 142,980 сум 
            # ⬆️ Верхние: 68
            # ⬇️ Нижние: 64
            # ↖️ Боковые верхние: 45
            # ↙️ Боковые нижние: 45

            seat_lines = []
            for car in train["cars_data"]:
                ctype = car["type"]
                free = car["free"]
                price = car["price"]
                
                icon = car_icon(ctype)
                # Note: user wants "142,980 сум" -> handled in parse_ticket_info
                
                # Base line
                # "🛏 Плацкартный — 222 мест — 142,980 сум"
                # Using existing 'car_line' template? It was "{icon} {type_} — {seats} ta — {price} so‘mdan"
                # UPDATE: User manually patched texts.py to match their need.
                # However, car_line placeholders are {type_}, {seats}, {price}.
                
                # Format localized words for 'seats' (mest/ta) and currency
                currency = "сум"
                if lang == "uz": currency = "so‘m" # Updated to match user's explicit change in texts.py (implied)
                elif lang == "en": currency = "UZS"
                
                mest = "мест"
                if lang == "uz": mest = "ta"
                elif lang == "en": mest = "seats"
                
                # We CAN use the template from texts.py, but I'm building it manually here to be safe and match logic 100%
                # Actually, relying on texts.py template is better if it fits.
                # User edited texts.py car_line to: "{icon} {type_} — {seats} ta — {price} so‘m"
                # But that only works for UZ. The RU one is: "{icon} {type_} — {seats} мест — от {price} сум"
                # The user edit in 582 was generic? No, TEXT is dict. User likely edited just UZ or ALL?
                # User diff showed changes in "uz" block.
                # I will try to use t(lang, 'car_line') and pass args.
                
                s_line = t(lang, "car_line").format(icon=icon, type_=ctype, seats=free, price=price)
                seat_lines.append(s_line)
                
                # Directions
                # ⬆️ Верхние: 68
                up = car["up"]
                down = car["down"]
                l_up = car["lateral_up"]
                l_dn = car["lateral_down"]
                
                if up > 0: seat_lines.append(f"⬆️ {t(lang, 'seats_up')}: {up}")
                if down > 0: seat_lines.append(f"⬇️ {t(lang, 'seats_down')}: {down}")
                if l_up > 0: seat_lines.append(f"↖️ {t(lang, 'seats_lateral_up')}: {l_up}")
                if l_dn > 0: seat_lines.append(f"↙️ {t(lang, 'seats_lateral_down')}: {l_dn}")
                
                seat_lines.append("") # Empty line between car types

            full_block = f"{header_str}\n{route_line_str}\n{dep_line}\n{arr_line}\n{dur_line}\n\n" + "\n".join(seat_lines)
            cars_text_parts.append(full_block)
        
        cars_text = "\n".join(cars_text_parts)
    else:
        cars_text = t(lang, "ticket_none")

    text = t(lang, "route_line").format(
        from_=from_name_loc,
        to_=to_name_loc,
        date=date_ui,
        chk=chk_line,
        status="",
        cars=cars_text,
    ).strip() # Remove extra newlines if status is empty


    return available, text


async def update_route_names_for_language(telegram_id: int, lang: str) -> None:
    """
    Lightweight function to update route names when user changes language.
    Searches for each route's stations using the old name with new language.
    """
    from api import search_stations
    
    routes = await list_routes(telegram_id)
    logger.info(f"Updating route names for user {telegram_id} to language {lang}")
    
    for route in routes:
        try:
            loc_from = ""
            loc_to = ""
            
            # Search by OLD NAME with NEW LANGUAGE
            try:
                # FROM
                res = await search_stations(route["from_name"], lang)
                for s in res:
                    if str(s.get("code")) == str(route["from_code"]):
                        loc_from = s.get("name")
                        break
                
                # TO
                res = await search_stations(route["to_name"], lang)
                for s in res:
                    if str(s.get("code")) == str(route["to_code"]):
                        loc_to = s.get("name")
                        break
            except Exception as e:
                logger.warning(f"Failed to search stations for route {route['id']}: {e}")
                continue
            
            # Apply updates
            if loc_from and loc_from != route["from_name"]:
                await update_route_field(route["id"], "from_name", loc_from)
                try:
                    logger.info(f"Updated route {route['id']} from_name: {route['from_name'].encode('ascii', 'ignore')} -> {loc_from.encode('ascii', 'ignore')}")
                except:
                    pass
            
            if loc_to and loc_to != route["to_name"]:
                await update_route_field(route["id"], "to_name", loc_to)
                try:
                    logger.info(f"Updated route {route['id']} to_name: {route['to_name'].encode('ascii', 'ignore')} -> {loc_to.encode('ascii', 'ignore')}")
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error updating route {route['id']} names: {e}")
            continue


async def check_and_notify_for_user(bot: Bot, telegram_id: int, force_send: bool = False, update_names: bool = False, specific_route_id: int = None, on_route_deleted=None) -> int:
    # force_send: if True, sends message regardless of state/schedule (manual check)
    # update_names: if True, tries to resolve localized station names even if tickets not found
    # specific_route_id: if set, only check/notify this route (used for "immediate check" on creation)
    
    user = await get_user(telegram_id)
    lang = user["language"]
    mode = user["notify_mode"]

    routes = await list_routes(telegram_id)
    logger.info(f"Checking routes for {telegram_id}: found {len(routes)} routes")
    if not routes:
        if force_send and not specific_route_id:
            await bot.send_message(telegram_id, t(lang, "no_routes"))
        return 0

    sent_count = 0
    from api import search_stations # Import locally to avoid circular if any

    for route in routes:
        if specific_route_id and route["id"] != specific_route_id:
            continue

        # --- EXPIRED ROUTE CHECK ---
        # Delete route if travel date has already passed (Tashkent time UTC+5)
        try:
            tz_uz = timezone(timedelta(hours=5))
            today = datetime.now(tz_uz).date()
            travel_date = datetime.strptime(route["travel_date"], "%Y-%m-%d").date()
            if travel_date < today:
                await delete_route(route["id"])
                logger.info(f"Route {route['id']} deleted: travel date {route['travel_date']} has passed")
                try:
                    date_ui = fmt_date_for_ui(lang, route["travel_date"])
                    expired_text = t(lang, "route_expired").format(
                        from_=route["from_name"],
                        to_=route["to_name"],
                        date=date_ui,
                    )
                    await bot.send_message(telegram_id, expired_text)
                except Exception as e:
                    logger.warning(f"Failed to send expired route notification: {e}")
                if on_route_deleted:
                    try:
                        await on_route_deleted(telegram_id)
                    except Exception as e:
                        logger.warning(f"on_route_deleted callback error: {e}")
                continue
        except Exception as e:
            logger.error(f"Error checking expiry for route {route['id']}: {e}")
        # --- END EXPIRED ROUTE CHECK ---

        logger.info(f"Checking route {route['id']}...")
        try:
            api_json = await fetch_trains(route["from_code"], route["to_code"], route["travel_date"], lang)
            
            # --- START LOCALIZATION UPDATE ---
            loc_from = ""
            loc_to = ""

            # 1. FORCE UPDATE (Language Switch)
            # User strategy: take existing name, search with new lang, find matching code.
            if update_names:
                try:
                    # FROM
                    res = await search_stations(route["from_name"], lang)
                    for s in res:
                        if str(s.get("code")) == str(route["from_code"]):
                            loc_from = s.get("name")
                            break
                    # TO
                    res = await search_stations(route["to_name"], lang)
                    for s in res:
                        if str(s.get("code")) == str(route["to_code"]):
                            loc_to = s.get("name")
                            break
                except Exception as e:
                    logger.warning(f"Force localization search failed: {e}")

            # 2. Extract from API Response (Normal Operation)
            # Only if not already set by forced update
            if not loc_from or not loc_to:
                try:
                    data = api_json.get("data", {})
                    directions = data.get("directions", [])
                    forward = None
                    if isinstance(directions, list) and directions: forward = directions[0]
                    elif isinstance(directions, dict) and directions: forward = next(iter(directions.values()))
                    
                    if forward:
                        trains = forward.get("trains", [])
                        if trains:
                            ft = trains[0]
                            # Only update if still empty
                            if not loc_from:
                                loc_from = ft.get("departureStation", "")
                            if not loc_to:
                                loc_to = ft.get("arrivalStation", "")
                except:
                    pass

            # Apply updates
            if loc_from and loc_from != route["from_name"]:
                await update_route_field(route["id"], "from_name", loc_from)
                route["from_name"] = loc_from
            
            if loc_to and loc_to != route["to_name"]:
                await update_route_field(route["id"], "to_name", loc_to)
                route["to_name"] = loc_to
            # --- END LOCALIZATION UPDATE ---

            available, text = await build_route_message(lang, route, api_json)
            logger.info(f"Available: {available}, Text len: {len(text)}")
            
            # State & Notification Logic
            last_av, last_check, notif_sent, last_notified_iso = await get_route_state(route["id"])
            
            emoji_to_send = "🎉" if available else "😔"

            user_notify_mode = user.get("notify_mode", "always")
            
            last_notified_time = None
            if last_notified_iso:
                try: 
                    last_notified_time = datetime.fromisoformat(last_notified_iso)
                    logger.info(f"Route {route['id']}: last_notified_iso={last_notified_iso}, parsed to {last_notified_time}")
                except Exception as e:
                    logger.error(f"Route {route['id']}: Failed to parse last_notified_iso={last_notified_iso}: {e}")
            else:
                logger.info(f"Route {route['id']}: last_notified_iso is NULL/None")

            should_send = False
            
            if force_send:
                should_send = True
            
            elif available:
                # TICKET FOUND: Always notify immediately and every 5 mins
                should_send = True
                
            elif not available:
                # NO TICKETS
                
                if user_notify_mode == "always":
                    # MODE 1: "Каждые 30 минут"
                    # Always send "no tickets" every 30 minutes
                    # Reset streak counter if it was active
                    if notif_sent > 0:
                        await reset_notification_count(route["id"])
                    
                    # Check 30-minute throttle
                    if not last_notified_time:
                         # New route - don't send immediately.
                         should_send = False
                         logger.info(f"Route {route['id']}: New route, waiting for next boundary")
                    else:
                         now = datetime.now()
                         # Determine the most recent 30-minute boundary
                         if now.minute < 30:
                             boundary = now.replace(minute=0, second=0, microsecond=0)
                         else:
                             boundary = now.replace(minute=30, second=0, microsecond=0)
                         
                         # If last notification was BEFORE this boundary, it means we entered a new block
                         if last_notified_time < boundary:
                             should_send = True
                             logger.info(f"Route {route['id']}: Boundary {boundary} passed (last: {last_notified_time}). Sending.")
                         else:
                             should_send = False
                             minutes_until_next = 30 - (now.minute % 30)
                             if (now.minute % 5) == 0:
                                 logger.info(f"Route {route['id']}: Waiting for next boundary ({minutes_until_next} min left). Last: {last_notified_time}")
                
                elif user_notify_mode == "on_available":
                    # MODE 2: "Только при появлении билетов"
                    # Send ONE "no tickets" message if tickets disappeared during active streak
                    # Then continue monitoring silently
                    if notif_sent > 0:
                        # Tickets disappeared during active streak - send ONE notification
                        should_send = True
                        logger.info(f"Route {route['id']}: Tickets disappeared during streak (count was {notif_sent}), sending ONE 'no tickets' message")
                        await reset_notification_count(route["id"])
                    else:
                        # No active streak - stay silent
                        should_send = False

            if should_send:
                try:
                    logger.info(f"Route {route['id']}: SENDING notification (available={available}, mode={user_notify_mode}, count={notif_sent})")
                    await bot.send_message(telegram_id, text)
                    sent_count += 1
                    
                    # Update last_notified
                    await update_last_notified(route["id"])

                    # Send emoji as separate message
                    await bot.send_message(telegram_id, emoji_to_send)
                    
                    if available:
                        # Increment count
                        count = await increment_notification_count(route["id"])
                        logger.info(f"Route {route['id']}: Notification count now {count}/5")
                        if count >= 5: # Limit reached
                            # Auto-delete
                            await delete_route(route["id"])
                            # Send ✅ as separate message
                            await bot.send_message(telegram_id, "✅")
                            logger.info(f"Route {route['id']}: Deleted after 5 notifications")
                            if on_route_deleted:
                                try:
                                    await on_route_deleted(telegram_id)
                                except Exception as e:
                                    logger.warning(f"on_route_deleted callback error: {e}")
                except Exception as e:
                    logger.error(f"Send error: {e}")
            else:
                logger.info(f"Route {route['id']}: SKIPPING notification (available={available}, mode={user_notify_mode}, last_notified={last_notified_iso})")
            
            # Update state
            await set_route_state(route["id"], available)

        except Exception as e:
            logger.error(f"Error checking route {route['id']}: {e}")
            if force_send:
                await bot.send_message(telegram_id, f"{t(lang, 'unknown_error')}\nDebug: {str(e)}")
            continue
    
    return sent_count


async def scheduler_tick(bot: Bot, on_route_deleted=None):
    # every 5 minutes (User requested 5 mins for testing)
    uids = await list_users()
    for uid in uids:
        await check_and_notify_for_user(bot, uid, force_send=False, on_route_deleted=on_route_deleted)
