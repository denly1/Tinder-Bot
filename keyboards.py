from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню для всех
def main_menu(is_admin=False):
    base_buttons = [
        ["Профиль👤", "Поиск🔍", "Симпатии💕"],
        ["Настройки⚙️", "VIP⭐", "Поддержка📞"]
    ]
    if is_admin:
        base_buttons.append(["История просмотров", "Статистика", "Выгрузка CSV"])
    return ReplyKeyboardMarkup(base_buttons, resize_keyboard=True)

# Кнопки для выбора пола, кого ищет
def gender_interest_keyboard():
    buttons = [
        [KeyboardButton("Парни")],
        [KeyboardButton("Девушки")],
        [KeyboardButton("Без разницы")]
    ]
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

# Интересы с эмодзи
def interests_keyboard():
    interests = [
        "🎵 Музыка", "✈️ Путешествие", "📚 Чтение", "🎨 Дизайн", "📝 Блогинг",
        "🚗 Машины", "🧶 Рукоделие", "✝️ Религия", "🗣️ Изучение языков", "💼 Работа",
        "🏋️ Спорт", "🎮 Игры", "💃 Танцы", "🎬 Кино и Сериалы", "🍳 Кулинария",
        "🖌️ Рисование", "🤝 Волонтерство"
    ]
    # Делим по 3 кнопки в ряд для удобства
    buttons = [interests[i:i+3] for i in range(0, len(interests), 3)]
    kb_buttons = [[KeyboardButton(text) for text in row] for row in buttons]
    return ReplyKeyboardMarkup(kb_buttons, resize_keyboard=True, one_time_keyboard=True)

# Клавиатура для опроса курит/пьет/были отношения
def habits_keyboard():
    buttons = [
        ["🚭 Не курю", "🚬 Курю", "🤷 Не отвечать"],
        ["🚫 Не пью", "🍷 Пью", "🤷 Не отвечать"],
        ["💔 Не были", "❤️ Были", "🤷 Не отвечать"]
    ]
    kb_buttons = [[KeyboardButton(text) for text in row] for row in buttons]
    return ReplyKeyboardMarkup(kb_buttons, resize_keyboard=True, one_time_keyboard=True)

# Клавиатура под анкетой для жалобы
def complaint_button(reported_id):
    keyboard = [
        [InlineKeyboardButton("Пожаловаться 🚩", callback_data=f"complain:{reported_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Кнопка техподдержки с переходом на канал
def support_keyboard():
    keyboard = [
        [InlineKeyboardButton("Написать в техподдержку", url="https://t.me/your_support_channel")]
    ]
    return InlineKeyboardMarkup(keyboard)
