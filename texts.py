from typing import Dict

TEXT: Dict[str, Dict[str, str]] = {
    "ru": {
        "hello_3": "🇷🇺 Привет! Я бот для отслеживания ж/д билетов. Я помогу вам найти билеты и уведомлю, когда они появятся.\n\n🇺🇿 Salom! Men temir yo'l chiptalarini kuzatib boruvchi botman. Men sizga chiptalarni topishda yordam beraman va ular paydo bo'lganda sizni xabardor qilaman.\n\n🇬🇧 Hi! I am a bot for tracking railway tickets. I'll help you find tickets and notify you when they appear.",
        "choose_lang": "🌍 Выберите язык / Tilni tanlang / Choose language",
        "lang_ru": "🇷🇺 Русский",
        "lang_uz": "🇺🇿 O'zbekcha",
        "lang_en": "🇬🇧 English",

        "add": "➕ Добавить маршрут",
        "my": "📋 Мои маршруты",
        "settings": "⚙️ Настройки",
        "check": "🔍 Проверить маршруты",
        "menu_main": "🏠 Главное меню",

        "cancel": "❌ Отмена",
        "back": "⬅️ Назад",

        "enter_from": "Введите название начального города:",
        "enter_to": "Введите название конечного города:",
        "enter_date": "Введите дату (DD.MM.YYYY)",

        "city_not_found": "❌ Не удалось найти город. Попробуйте ещё раз.",
        "bad_date": "❌ Неверный формат даты.",
        "date_past": "❌ Дата уже прошла. Введите текущую или будущую дату:",
        "saved": "✅ Маршрут успешно установлен.",
        "max_routes": "❌ У вас уже установлено максимальное количество маршрутов (5).",

        "no_routes": "📭 У вас ещё нет установленных маршрутов.",
        "route_deleted": "🗑 Маршрут успешно удалён.",
        "delete_confirm": "❓ Вы действительно хотите удалить маршрут?",
        "yes": "✅ Да",
        "no": "❌ Нет",

        "route_view_title": "📍 Маршрут №{n}",
        "edit": "✏️ Изменить маршрут",
        "delete": "🗑 Удалить маршрут",

        "edit_from": "🏙 Изменить начальную точку",
        "edit_to": "🏁 Изменить конечную точку",
        "edit_date": "📅 Изменить дату",
        "updated": "✅ Данные успешно изменены.",

        "settings_title": "⚙️ Настройки",
        "settings_lang": "🌍 Изменить язык",
        "settings_notify": "🔔 Тип уведомлений",
        "notify_always": "⏰ Каждые 30 минут",
        "notify_on_available": "⚡ Только при появлении билетов",
        "settings_saved": "✅ Настройки сохранены.",

        "checking": "⏳ Проверяю…",
        "ticket_none": "❌ Билетов нет",
        "ticket_yes": "✅ Билеты есть",
        "check_time": "⏰ Проверка: {ts}",
        "trip_time": "⏱ В пути: {t}",
        "route_line": "🚆 {from_} → {to_}\n📅 {date}\n\n{chk}\n\n{cars}\n\n{status}",
        "cars_empty": "",
        "car_line": "{icon} {type_} — {seats} мест — от {price} сум",
        "train_number": "🚄 Поезд {num}",
        "unknown_error": "⚠️ Произошла ошибка. Попробуйте позже.",
        "select_route": "📋 Ваши маршруты:",
        "seats_up": "Верхние",
        "seats_down": "Нижние",
        "seats_lateral_up": "Боковые верхние",
        "seats_lateral_down": "Боковые нижние",
        "dep_time_label": "🟢 Отбытие",
        "arr_time_label": "🔴 Прибытие",
        "travel_time_label": "⏳ Время в пути",
        "train_route_label": "🛤 {route}",
        "time_h_m": "{h} часов {m} минут",
        "year_suffix": " года",
        "months": ["", "Января", "Февраля", "Марта", "Апреля", "Мая", "Июня", "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря"],
        "route_expired": "🗓 Маршрут {from_} → {to_} на {date} удалён, так как дата поездки уже прошла.",
    },
    "uz": {
        "hello_3": "🇷🇺 Привет! Я бот для отслеживания ж/д билетов. Я помогу вам найти билеты и уведомлю, когда они появятся.\n\n🇺🇿 Salom! Men temir yo'l chiptalarini kuzatib boruvchi botman. Men sizga chiptalarni topishda yordam beraman va ular paydo bo'lganda sizni xabardor qilaman.\n\n🇬🇧 Hi! I am a bot for tracking railway tickets. I'll help you find tickets and notify you when they appear.",
        "choose_lang": "🌍 Tilni tanlang:",
        "lang_ru": "🇷🇺 Русский",
        "lang_uz": "🇺🇿 O'zbekcha",
        "lang_en": "🇬🇧 English",

        "add": "➕ Yo'nalish qo‘shish",
        "my": "📋 Mening yo'nalishlarim",
        "settings": "⚙️ Sozlamalar",
        "check": "🔍 Yo'nalishlarni tekshirish",
        "menu_main": "🏠 Bosh sahifa",

        "cancel": "❌ Bekor qilish",
        "back": "⬅️ Orqaga",

        "enter_from": "Boshlang‘ich shaharni kiriting:",
        "enter_to": "Yakuniy shaharni kiriting:",
        "enter_date": "Sanani kiriting (DD.MM.YYYY)",

        "city_not_found": "❌ Shahar topilmadi. Qayta urinib ko‘ring.",
        "bad_date": "❌ Sana formati noto’g’ri.",
        "date_past": "❌ Sana o’tib ketgan. Hozirgi yoki kelajakdagi sanani kiriting:",
        "saved": "✅ Yo'nalish muvaffaqiyatli qo‘shildi.",
        "max_routes": "❌ Sizda maksimal yo'nalishlar soni (5) mavjud.",

        "no_routes": "📭 Sizda hali yo'nalishlar yo‘q.",
        "route_deleted": "🗑 Yo'nalish o‘chirildi.",
        "delete_confirm": "❓ Rostdan ham yo'nalishni o‘chirmoqchimisiz?",
        "yes": "✅ Ha",
        "no": "❌ Yo‘q",

        "route_view_title": "📍 Yo'nalish №{n}",
        "edit": "✏️ Yo'nalishni o‘zgartirish",
        "delete": "🗑 Yo'nalishni o‘chirish",

        "edit_from": "🏙 Boshlang‘ich nuqtani o‘zgartirish",
        "edit_to": "🏁 Yakuniy nuqtani o‘zgartirish",
        "edit_date": "📅 Sanani o‘zgartirish",
        "updated": "✅ Ma’lumotlar yangilandi.",

        "settings_title": "⚙️ Sozlamalar",
        "settings_lang": "🌍 Tilni o‘zgartirish",
        "settings_notify": "🔔 Bildirishnoma turi",
        "notify_always": "⏰ Har 30 daqiqada",
        "notify_on_available": "⚡ Faqat bilet paydo bo‘lsa",
        "settings_saved": "✅ Sozlamalar saqlandi.",

        "checking": "⏳ Tekshiryapman…",
        "ticket_none": "❌ Bilet yo‘q",
        "ticket_yes": "✅ Bilet bor",
        "check_time": "⏰ Tekshiruv: {ts}",
        "trip_time": "⏱ Yo‘lda: {t}",
        "route_line": "🚆 {from_} → {to_}\n📅 {date}\n\n{chk}\n\n{cars}\n\n{status}",
        "cars_empty": "",
        "car_line": "{icon} {type_} — {seats} ta — {price} so‘m",
        "train_number": "🚄 Poyezd {num}",
        "unknown_error": "⚠️ Xatolik yuz berdi. Keyinroq urinib ko‘ring.",
        "select_route": "📋 Sizning yo'nalishlaringiz:",
        "seats_up": "Yuqori",
        "seats_down": "Past",
        "seats_lateral_up": "Yon yuqori",
        "seats_lateral_down": "Yon past",
        "dep_time_label": "🟢 Jo‘nash",
        "arr_time_label": "🔴 Yetib borish",
        "travel_time_label": "⏳ Yo‘l vaqti",
        "train_route_label": "🛤 {route}",
        "time_h_m": "{h} soat {m} daqiqa",
        "year_suffix": " yil",
        "months": ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"],
        "route_expired": "🗓 {from_} → {to_} yo'nalishi {date} sanasi uchun o'chirildi, chunki sayohat sanasi o'tib ketdi.",
    },
    "en": {
        "hello_3": "🇷🇺 Привет! Я бот для отслеживания ж/д билетов. Я помогу вам найти билеты и уведомлю, когда они появятся.\n\n🇺🇿 Salom! Men temir yo'l chiptalarini kuzatib boruvchi botman. Men sizga chiptalarni topishda yordam beraman va ular paydo bo'lganda sizni xabardor qilaman.\n\n🇬🇧 Hi! I am a bot for tracking railway tickets. I'll help you find tickets and notify you when they appear.",
        "choose_lang": "🌍 Choose language:",
        "lang_ru": "🇷🇺 Русский",
        "lang_uz": "🇺🇿 Uzbek",
        "lang_en": "🇬🇧 English",

        "add": "➕ Add route",
        "my": "📋 My routes",
        "settings": "⚙️ Settings",
        "check": "🔍 Check routes",
        "menu_main": "🏠 Main menu",

        "cancel": "❌ Cancel",
        "back": "⬅️ Back",

        "enter_from": "Enter departure city:",
        "enter_to": "Enter destination city:",
        "enter_date": "Enter date (DD.MM.YYYY)",

        "city_not_found": "❌ City not found. Try again.",
        "bad_date": "❌ Invalid date format.",
        "date_past": "❌ This date has already passed. Please enter a current or future date:",
        "saved": "✅ Route created successfully.",
        "max_routes": "❌ You already have the maximum number of routes (5).",

        "no_routes": "📭 You don't have any routes yet.",
        "route_deleted": "🗑 Route deleted.",
        "delete_confirm": "❓ Are you sure you want to delete this route?",
        "yes": "✅ Yes",
        "no": "❌ No",

        "route_view_title": "📍 Route #{n}",
        "edit": "✏️ Edit route",
        "delete": "🗑 Delete route",

        "edit_from": "🏙 Change departure",
        "edit_to": "🏁 Change destination",
        "edit_date": "📅 Change date",
        "updated": "✅ Updated successfully.",

        "settings_title": "⚙️ Settings",
        "settings_lang": "🌍 Change language",
        "settings_notify": "🔔 Notification mode",
        "notify_always": "⏰ Every 30 minutes",
        "notify_on_available": "⚡ Only when tickets appear",
        "settings_saved": "✅ Settings saved.",

        "checking": "⏳ Checking…",
        "ticket_none": "❌ No tickets",
        "ticket_yes": "✅ Tickets available",
        "check_time": "⏰ Checked: {ts}",
        "trip_time": "⏱ Travel time: {t}",
        "route_line": "🚆 {from_} → {to_}\n📅 {date}\n\n{chk}\n\n{cars}\n\n{status}",
        "cars_empty": "",
        "car_line": "{icon} {type_} — {seats} seats — from {price} UZS",
        "train_number": "🚄 Train {num}",
        "unknown_error": "⚠️ Something went wrong. Please try later.",
        "select_route": "📋 Your routes:",
        "seats_up": "Upper",
        "seats_down": "Lower",
        "seats_lateral_up": "Lat. Upper",
        "seats_lateral_down": "Lat. Lower",
        "dep_time_label": "🟢 Departure",
        "arr_time_label": "🔴 Arrival",
        "travel_time_label": "⏳ Travel time",
        "train_route_label": "🛤 {route}",
        "time_h_m": "{h} hours {m} minutes",
        "year_suffix": "",
        "months": ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "route_expired": "🗓 Route {from_} → {to_} for {date} has been deleted because the travel date has passed.",
    },
}

def t(lang: str, key: str) -> str:
    # Special handling for month list? No, just get via key
    val = TEXT.get(lang, TEXT["ru"]).get(key, key)
    return val

def get_month_name(lang: str, month_idx: int) -> str:
    try:
        months = TEXT.get(lang, TEXT["ru"]).get("months", [])
        return months[month_idx]
    except IndexError: # Changed from generic 'except' to specific 'IndexError' for robustness
        return ""
