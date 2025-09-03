from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler, MessageHandler, Filters, CommandHandler, CallbackQueryHandler
from db import add_user, update_user_photos, update_user_videos, is_blocked as db_is_blocked, get_user
from utils import (
    validate_name,
    validate_age,
    validate_city,
    save_photo,
    save_video,
    get_gender_self_keyboard,
    get_gender_interest_keyboard,
    get_interests_inline_keyboard,
    get_smoke_keyboard,
    get_drink_keyboard,
    get_relationship_keyboard,
    get_main_menu,
    get_done_keyboard,
    get_skip_keyboard,
)

# Состояния регистрации
(
    R_NAME,
    R_AGE,
    R_CITY,
    R_GENDER_SELF,
    R_GENDER_INTEREST,
    R_INTERESTS,
    R_PHOTOS,
    R_VIDEOS,
    R_HABITS,
    R_CONFIRM
) = range(10)

def start_registration(update: Update, context: CallbackContext):
    if db_is_blocked(update.effective_user.id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return ConversationHandler.END
    # Если анкета уже существует — не запускать регистрацию, показать меню
    existing = get_user(update.effective_user.id)
    if existing:
        from utils import get_main_menu
        update.message.reply_text("У вас уже есть анкета. Используйте меню ниже.", reply_markup=get_main_menu())
        return ConversationHandler.END
    update.message.reply_text(
        "Привет! Я помогу создать анкету для знакомств.\n\n"
        "Начнём. Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return R_NAME

def r_name(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    if not validate_name(name):
        update.message.reply_text("Некорректное имя. Пожалуйста, введи имя только буквами, 2-30 символов.")
        return R_NAME
    context.user_data['name'] = name
    update.message.reply_text("Сколько тебе лет?")
    return R_AGE

def r_age(update: Update, context: CallbackContext):
    age = update.message.text.strip()
    if not validate_age(age):
        update.message.reply_text("Некорректный возраст. Введи число от 18 до 99.")
        return R_AGE
    context.user_data['age'] = int(age)
    update.message.reply_text("Из какого ты города?")
    return R_CITY

def r_city(update: Update, context: CallbackContext):
    city = update.message.text.strip()
    if not validate_city(city):
        update.message.reply_text("Некорректное название города. Пожалуйста, без цифр и спецсимволов.")
        return R_CITY
    context.user_data['city'] = city
    update.message.reply_text("Укажи свой пол", reply_markup=get_gender_self_keyboard())
    return R_GENDER_SELF

def r_gender_self(update: Update, context: CallbackContext):
    raw = update.message.text.strip().lower()
    if raw.startswith("парень") or "👨" in raw:
        context.user_data['gender'] = "Парень"
    elif raw.startswith("девушка") or "👩" in raw:
        context.user_data['gender'] = "Девушка"
    else:
        update.message.reply_text("Пожалуйста, выбери из предложенных вариантов.")
        return R_GENDER_SELF
    update.message.reply_text("Кого ты ищешь?", reply_markup=get_gender_interest_keyboard())
    return R_GENDER_INTEREST

def r_gender_interest(update: Update, context: CallbackContext):
    raw = update.message.text.strip()
    normalized = None
    if raw.startswith("Парни"):
        normalized = "Парни"
    elif raw.startswith("Девушки"):
        normalized = "Девушки"
    elif raw.startswith("Без разницы"):
        normalized = "Без разницы"
    if not normalized:
        update.message.reply_text("Пожалуйста, выбери из предложенных вариантов.")
        return R_GENDER_INTEREST
    context.user_data['gender_interest'] = normalized
    context.user_data['interests'] = []
    update.message.reply_text(
        "Выбери свои интересы, отмечая галочками. Когда закончишь — нажми Готово.",
    )
    update.message.reply_text(
        "Список интересов:",
        reply_markup=get_interests_inline_keyboard(context.user_data['interests'])
    )
    return R_INTERESTS

def r_interests(update: Update, context: CallbackContext):
    # Обработка инлайн-кнопок идёт в отдельном обработчике
    update.message.reply_text("Используйте кнопки ниже, затем нажмите Готово.")
    return R_INTERESTS


def interests_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    selected = context.user_data.get('interests', [])
    if data == 'intdone':
        if not selected:
            query.answer('Выберите хотя бы один интерес')
            return R_INTERESTS
        query.answer('Готово')
        query.edit_message_text(
            "Отправьте минимум 3 своих настоящих фото, иначе анкета будет отправлена на модерацию.\n"
            "Загружайте по одному. Когда закончите — нажмите Готово."
        )
        context.user_data['photos'] = []
        return R_PHOTOS
    if data.startswith('intsel:'):
        idx = int(data.split(':', 1)[1])
        from utils import INTERESTS_LIST
        interest = INTERESTS_LIST[idx]
        if interest in selected:
            selected.remove(interest)
        else:
            selected.append(interest)
        context.user_data['interests'] = selected
        query.answer('Обновлено')
        query.edit_message_reply_markup(reply_markup=get_interests_inline_keyboard(selected))
        return R_INTERESTS
    query.answer()
    return R_INTERESTS

def r_photos(update: Update, context: CallbackContext):
    if update.message.text and update.message.text.strip().lower() == "готово":
        photos = context.user_data.get('photos', [])
        if len(photos) < 3:
            update.message.reply_text("Нужно минимум 3 фото. Продолжайте отправлять фотографии.")
            return R_PHOTOS
        update.message.reply_text("Теперь можно добавить видео в анкету. Отправь видео или напиши 'Пропустить'.")
        context.user_data['videos'] = []
        return R_VIDEOS

    if update.message.photo:
        photo_file = update.message.photo[-1].get_file()
        photo_index = len(context.user_data.get('photos', [])) + 1
        path = save_photo(photo_file, update.effective_user.id, photo_index)
        photos = context.user_data.get('photos', [])
        photos.append(path)
        context.user_data['photos'] = photos
        update.message.reply_text(
            f"Фото {photo_index} сохранено. Можно отправить следующее или нажать 'Готово'.",
            reply_markup=get_done_keyboard(),
        )
        return R_PHOTOS
    else:
        update.message.reply_text("Пожалуйста, отправь фото.", reply_markup=get_done_keyboard())
        return R_PHOTOS

def r_videos(update: Update, context: CallbackContext):
    if update.message.text and update.message.text.strip().lower() == "пропустить":
        # Идем дальше к опросу привычек
        update.message.reply_text("Куришь ли ты?", reply_markup=get_smoke_keyboard())
        return R_HABITS

    if update.message.video:
        video_file = update.message.video.get_file()
        video_index = len(context.user_data.get('videos', [])) + 1
        path = save_video(video_file, update.effective_user.id, video_index)
        videos = context.user_data.get('videos', [])
        videos.append(path)
        context.user_data['videos'] = videos
        if len(videos) >= 3:
            update.message.reply_text("Достигнут лимит в 3 видео. Переходим к опросу.")
            update.message.reply_text("Куришь ли ты?", reply_markup=get_smoke_keyboard())
            return R_HABITS
        update.message.reply_text(
            f"Видео {video_index} сохранено. Можно отправить следующее или нажать 'Пропустить'.",
            reply_markup=get_skip_keyboard(),
        )
        return R_VIDEOS
    else:
        update.message.reply_text(
            "Пожалуйста, отправь видео или нажми 'Пропустить'.",
            reply_markup=get_skip_keyboard(),
        )
        return R_VIDEOS

def r_habits(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    def normalize_smoking(txt: str):
        t = txt.lower()
        if t.startswith("🚭") or "не курю" in t:
            return "Не курю"
        if t.startswith("🚬") or "курю" in t:
            return "Курю"
        if "не отвечать" in t:
            return "Не отвечать"
        return None

    def normalize_drinking(txt: str):
        t = txt.lower()
        if t.startswith("🚫") or "не пью" in t:
            return "Не пью"
        if t.startswith("🍷") or "пью" in t:
            return "Пью"
        if "не отвечать" in t:
            return "Не отвечать"
        return None

    def normalize_relationship(txt: str):
        t = txt.lower()
        if t.startswith("💔") or "нет" in t or "не были" in t or "не было" in t:
            return "Нет"
        if t.startswith("❤️") or "да" in t or "были" in t or "было" in t:
            return "Да"
        if "не отвечать" in t:
            return "Не отвечать"
        return None

    if 'smoking' not in context.user_data:
        value = normalize_smoking(text)
        if value is None:
            update.message.reply_text("Выбери вариант из списка.")
            return R_HABITS
        context.user_data['smoking'] = value
        update.message.reply_text("Пьёшь ли ты?", reply_markup=get_drink_keyboard())
        return R_HABITS

    if 'drinking' not in context.user_data:
        value = normalize_drinking(text)
        if value is None:
            update.message.reply_text("Выбери вариант из списка.")
            return R_HABITS
        context.user_data['drinking'] = value
        update.message.reply_text("Были ли у тебя отношения?", reply_markup=get_relationship_keyboard())
        return R_HABITS

    if 'relationship' not in context.user_data:
        value = normalize_relationship(text)
        if value is None:
            update.message.reply_text("Выбери вариант из списка.")
            return R_HABITS
        context.user_data['relationship'] = value

        data = context.user_data
        try:
            add_user(
                telegram_id=update.effective_user.id,
                name=data['name'],
                age=data['age'],
                city=data['city'],
                gender=data.get('gender'),
                gender_interest=data['gender_interest'],
                interests=data['interests'],
                smoking=data.get('smoking'),
                drinking=data.get('drinking'),
                relationship=data.get('relationship'),
            )
            update_user_photos(update.effective_user.id, data.get('photos', []))
            update_user_videos(update.effective_user.id, data.get('videos', []))
        except Exception as e:
            update.message.reply_text("Ошибка сохранения анкеты. Попробуйте позже.")
            return ConversationHandler.END

        update.message.reply_text(
            "Анкета создана! Вы можете начинать искать знакомых.\n"
            "Минимум 3 фото и ответы на вопросы помогают найти нужного человека.",
            reply_markup=get_main_menu(),
        )
        context.user_data.clear()
        return ConversationHandler.END


def build_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('start', start_registration)],
        states={
            R_NAME: [MessageHandler(Filters.text & (~Filters.command), r_name)],
            R_AGE: [MessageHandler(Filters.text & (~Filters.command), r_age)],
            R_CITY: [MessageHandler(Filters.text & (~Filters.command), r_city)],
            R_GENDER_SELF: [MessageHandler(Filters.text & (~Filters.command), r_gender_self)],
            R_GENDER_INTEREST: [MessageHandler(Filters.text & (~Filters.command), r_gender_interest)],
            R_INTERESTS: [
                MessageHandler(Filters.text & (~Filters.command), r_interests),
                CallbackQueryHandler(interests_callback, pattern=r"^(intsel:\d+|intdone)$"),
            ],
            R_PHOTOS: [MessageHandler((Filters.photo | Filters.text) & (~Filters.command), r_photos)],
            R_VIDEOS: [MessageHandler((Filters.video | Filters.text) & (~Filters.command), r_videos)],
            R_HABITS: [MessageHandler(Filters.text & (~Filters.command), r_habits)],
        },
        fallbacks=[],
        allow_reentry=True,
    )
