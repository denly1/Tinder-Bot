from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

# Валидация имени (только буквы, пробелы, от 2 до 30 символов)
def validate_name(name: str) -> bool:
    return bool(re.fullmatch(r"[А-Яа-яA-Za-zЁё\s]{2,30}", name.strip()))

# Валидация возраста (от 18 до 99)
def validate_age(age_str: str) -> bool:
    if not age_str.isdigit():
        return False
    age = int(age_str)
    return 18 <= age <= 99

# Валидация города (от 2 до 50 символов, буквы, пробелы)
def validate_city(city: str) -> bool:
    return bool(re.fullmatch(r"[А-Яа-яA-Za-zЁё\s]{2,50}", city.strip()))

# Валидация интересов - список из заданных
INTERESTS_LIST = [
    "🎵 Музыка", "✈️ Путешествие", "📚 Чтение", "🎨 Дизайн", "📝 Блогинг",
    "🚗 Машины", "🧵 Рукоделие", "☦️ Религия", "🈷️ Изучение языков", "💼 Работа",
    "🏋️‍♂️ Спорт", "🎮 Игры", "💃 Танцы", "🎬 Кино и Сериалы", "🍳 Кулинария",
    "🖌️ Рисование", "🤝 Волонтерство"
]

def validate_interests(selected: list) -> bool:
    return all(item in INTERESTS_LIST for item in selected)

# Клавиатура выбора интересов (многострочная)
def get_interests_keyboard():
    keyboard = []
    row = []
    for i, interest in enumerate(INTERESTS_LIST, 1):
        row.append(interest)
        if i % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# Клавиатура выбора собственного пола
def get_gender_self_keyboard():
    keyboard = [["Парень 👨", "Девушка 👩"]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
from telegram import ReplyKeyboardMarkup

def get_admin_menu():
    keyboard = [
        ["История просмотров 📊", "Статистика 📈"],
        ["Выгрузка пользователей CSV 📄", "Заблокировать пользователя ⛔"],
        ["Разблокировать пользователя ✅", "Просмотр жалоб 📝"],
        ["Отключить ограничения 🔓", "Включить ограничения 🔒"],
        ["Рассылка 📨"],
        ["↩️ Выход"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Инлайн-клавиатура VIP покупки
def get_vip_inline_keyboard(payment_id: str | None = None):
    buttons = []
    buttons.append([InlineKeyboardButton("Купить VIP 300₽", callback_data="vip:buy")])
    if payment_id:
        buttons.append([InlineKeyboardButton("Проверить оплату", callback_data=f"vip:check:{payment_id}")])
    return InlineKeyboardMarkup(buttons)

# Клавиатуры для подтверждений в шагах анкеты
def get_done_keyboard():
    return ReplyKeyboardMarkup([["Готово"]], one_time_keyboard=True, resize_keyboard=True)

def get_skip_keyboard():
    return ReplyKeyboardMarkup([["Пропустить"]], one_time_keyboard=True, resize_keyboard=True)

def get_done_or_skip_keyboard():
    return ReplyKeyboardMarkup([["Готово", "Пропустить"]], one_time_keyboard=True, resize_keyboard=True)

# Меню модератора (без рассылок, статистику можно оставить по желанию)
def get_moderator_menu():
    keyboard = [
        ["Просмотр жалоб 📝"],
        ["Заблокировать пользователя ⛔", "Разблокировать пользователя ✅"],
        ["↩️ Выход"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура выбора пола интереса
def get_gender_interest_keyboard():
    keyboard = [
        ["Парни 👦", "Девушки 👧", "Без разницы 🔄"]
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


# Инлайн-клавиатура для выбора интересов с галочками
def get_interests_inline_keyboard(selected: list):
    buttons = []
    row = []
    for i, interest in enumerate(INTERESTS_LIST):
        is_selected = interest in selected
        mark = "✅" if is_selected else "☑️"
        row.append(InlineKeyboardButton(f"{mark} {interest}", callback_data=f"intsel:{i}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    # кнопка завершения
    buttons.append([InlineKeyboardButton("Готово", callback_data="intdone")])
    return InlineKeyboardMarkup(buttons)

# Клавиатура основного меню
def get_main_menu(is_admin=False):
    buttons = [
        "Профиль 👤",
        "Поиск 🔎",
        "Симпатии ❤️",
        "Настройки ⚙️",
        "VIP ⭐",
        "Поддержка 🆘",
    ]
    keyboard = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура действий под анкетой (reply, не inline)
def get_profile_actions_keyboard():
    keyboard = [
        ["❤️", "👎"],
        ["🚩 Пожаловаться", "↩️ Меню"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Валидация yes/no для курит/пьет/отношения
SMOKE_OPTIONS = ["🚭 Не курю", "🚬 Курю", "🚫 Не отвечать"]
DRINK_OPTIONS = ["🚫 Не пью", "🍷 Пью", "🚫 Не отвечать"]
RELATIONSHIP_OPTIONS = ["💔 Нет", "❤️ Да", "🚫 Не отвечать"]

def get_smoke_keyboard():
    return ReplyKeyboardMarkup([SMOKE_OPTIONS], one_time_keyboard=True, resize_keyboard=True)

def get_drink_keyboard():
    return ReplyKeyboardMarkup([DRINK_OPTIONS], one_time_keyboard=True, resize_keyboard=True)

def get_relationship_keyboard():
    return ReplyKeyboardMarkup([RELATIONSHIP_OPTIONS], one_time_keyboard=True, resize_keyboard=True)

# Проверка лимита просмотров (10 для обычных, безлимит для VIP)
def can_view(user):
    from datetime import datetime
    if user['vip']:
        return True
    today = date.today()
    if not user['last_view'] or user['last_view'] < today:
        # Сброс дневного лимита
        return True
    if user['daily_views'] < 10:
        return True
    return False

# Форматировать анкету для вывода пользователю
def format_profile(user):
    interests = ", ".join(user.get('interests', []) or [])
    bio = (user.get('bio') or '').strip()
    smoking = (user.get('smoking') or '').strip()
    drinking = (user.get('drinking') or '').strip()
    relationship = (user.get('relationship') or '').strip()

    def _show(val: str) -> bool:
        return bool(val) and ('Не отвечать' not in val)

    lines = [
        f"Имя: {user.get('name','')}",
        f"Возраст: {user.get('age','')}",
    ]
    if user.get('city'):
        lines.append(f"Город: {user.get('city')}")
    if interests:
        lines.append(f"Интересы: {interests}")
    if bio:
        lines.append(f"Описание: {bio}")
    if _show(smoking):
        lines.append(f"Курю: {smoking}")
    if _show(drinking):
        lines.append(f"Пью: {drinking}")
    if _show(relationship):
        lines.append(f"Отношения: {relationship}")

    # VIP признак
    try:
        if user.get('vip') is not None:
            lines.append(f"VIP: {'Да' if user.get('vip') else 'Нет'}")
    except Exception:
        pass
    return "\n".join(lines)

# --- Сохранение медиа в папках проекта /photos и /videos ---
BASE_MEDIA_DIR = Path('user_media')
BASE_MEDIA_DIR.mkdir(exist_ok=True)


def _unique_file_name(prefix: str, index: int, ext: str) -> str:
    return f"{prefix}_{index}_{uuid4().hex[:8]}{ext}"


def save_photo(tg_file, telegram_id: int, index: int) -> str:
    user_dir = BASE_MEDIA_DIR / str(telegram_id) / 'photos'
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = _unique_file_name(str(telegram_id), index, '.jpg')
    dest = user_dir / filename
    tg_file.download(custom_path=str(dest))
    return str(dest)


def save_video(tg_file, telegram_id: int, index: int) -> str:
    user_dir = BASE_MEDIA_DIR / str(telegram_id) / 'videos'
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = _unique_file_name(str(telegram_id), index, '.mp4')
    dest = user_dir / filename
    tg_file.download(custom_path=str(dest))
    return str(dest)
