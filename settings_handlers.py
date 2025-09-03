from telegram.ext import CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext
from db import (
    update_user_field, update_user_interests, delete_user, update_user_photos,
    set_age_preference, set_city_filter_enabled, set_user_city, get_user,
)
from utils import get_interests_inline_keyboard, INTERESTS_LIST, get_main_menu, get_done_keyboard, save_photo


def _parse_arg(text: str) -> str:
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def set_name(update: Update, context: CallbackContext):
    value = _parse_arg(update.message.text)
    if not value:
        update.message.reply_text("Использование: /setname Иван")
        return
    update_user_field(update.effective_user.id, "name", value)
    update.message.reply_text("Имя обновлено.", reply_markup=get_main_menu())


def set_age(update: Update, context: CallbackContext):
    value = _parse_arg(update.message.text)
    if not value.isdigit() or not (18 <= int(value) <= 99):
        update.message.reply_text("Возраст от 18 до 99. Пример: /setage 25")
        return
    update_user_field(update.effective_user.id, "age", int(value))
    update.message.reply_text("Возраст обновлён.", reply_markup=get_main_menu())


def set_city(update: Update, context: CallbackContext):
    value = _parse_arg(update.message.text)
    if not value:
        update.message.reply_text("Использование: /setcity Москва")
        return
    # Обновим город с нормализацией
    set_user_city(update.effective_user.id, value)
    update.message.reply_text("Город обновлён.", reply_markup=get_main_menu())


def set_gi(update: Update, context: CallbackContext):
    value = _parse_arg(update.message.text)
    allowed = ["Парни", "Девушки", "Без разницы"]
    norm = None
    for a in allowed:
        if value.startswith(a):
            norm = a
            break
    if not norm:
        update.message.reply_text("Пример: /setgi Парни|Девушки|Без разницы")
        return
    update_user_field(update.effective_user.id, "gender_interest", norm)
    update.message.reply_text("Предпочтения обновлены.", reply_markup=get_main_menu())


def set_bio(update: Update, context: CallbackContext):
    value = _parse_arg(update.message.text)
    if len(value) > 500:
        update.message.reply_text("Слишком длинное описание. До 500 символов.")
        return
    update_user_field(update.effective_user.id, 'bio', value)
    update.message.reply_text("Описание обновлено.", reply_markup=get_main_menu())


def edit_interests(update: Update, context: CallbackContext):
    context.user_data['edit_interests'] = []
    update.message.reply_text(
        "Отметьте интересы галочками и нажмите Готово.",
        reply_markup=get_interests_inline_keyboard([]),
    )

# --- Inline edits for name, age, city, bio ---
def edit_name_start_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    q.edit_message_text("Введите новое имя (2-30 букв):")
    return EDIT_NAME

def edit_name_step(update: Update, context: CallbackContext):
    value = (update.message.text or '').strip()
    if not value or len(value) < 2 or len(value) > 30:
        update.message.reply_text("Некорректное имя. Введите 2-30 символов.")
        return EDIT_NAME
    update_user_field(update.effective_user.id, 'name', value)
    update.message.reply_text("Имя обновлено.", reply_markup=get_main_menu())
    return ConversationHandler.END

def edit_age_start_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    q.edit_message_text("Введите новый возраст (18-99):")
    return EDIT_AGE

def edit_age_step(update: Update, context: CallbackContext):
    value = (update.message.text or '').strip()
    if not value.isdigit() or not (18 <= int(value) <= 99):
        update.message.reply_text("Возраст от 18 до 99. Попробуйте снова.")
        return EDIT_AGE
    update_user_field(update.effective_user.id, 'age', int(value))
    update.message.reply_text("Возраст обновлён.", reply_markup=get_main_menu())
    return ConversationHandler.END

def edit_city_start_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    q.edit_message_text("Введите новый город:")
    return EDIT_CITY

def edit_city_step(update: Update, context: CallbackContext):
    value = (update.message.text or '').strip()
    if not value or len(value) < 2:
        update.message.reply_text("Слишком короткое название. Попробуйте снова.")
        return EDIT_CITY
    set_user_city(update.effective_user.id, value)
    update.message.reply_text("Город обновлён.", reply_markup=get_main_menu())
    return ConversationHandler.END

def edit_bio_start_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    q.edit_message_text("Введите описание анкеты (до 500 символов):")
    return EDIT_BIO

def edit_bio_step(update: Update, context: CallbackContext):
    value = (update.message.text or '').strip()
    if len(value) > 500:
        update.message.reply_text("Слишком длинное описание. До 500 символов.")
        return EDIT_BIO
    update_user_field(update.effective_user.id, 'bio', value)
    update.message.reply_text("Описание обновлено.", reply_markup=get_main_menu())
    return ConversationHandler.END

# Photos change via inline button
def change_photos_start_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    context.user_data['new_photos'] = []
    q.edit_message_text(
        "Отправьте новые фото (по одному). Когда закончите — нажмите 'Готово'.\nСтарые фото будут заменены на новые.")
    q.message.reply_text("Жду фото…", reply_markup=get_done_keyboard())
    return CP_PHOTOS

# Delete confirm via inline
def delete_confirm_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Да, удалить", callback_data="delete:yes"), InlineKeyboardButton("Отмена", callback_data="delete:no")]
    ])
    q.edit_message_text("Удалить аккаунт? Это действие необратимо.", reply_markup=kb)

def delete_confirm_choice_cb(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    if q.data == 'delete:yes':
        delete_user(q.from_user.id)
        q.edit_message_text("Аккаунт удалён.")
    else:
        q.edit_message_text("Удаление отменено.")


def edit_interests_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    selected = context.user_data.get('edit_interests', [])
    if data == 'intdone':
        update_user_interests(query.from_user.id, selected)
        query.answer('Сохранено')
        query.edit_message_text("Интересы обновлены.")
        return
    if data.startswith('intsel:'):
        idx = int(data.split(':', 1)[1])
        interest = INTERESTS_LIST[idx]
        if interest in selected:
            selected.remove(interest)
        else:
            selected.append(interest)
        context.user_data['edit_interests'] = selected
        query.answer('Обновлено')
        query.edit_message_reply_markup(reply_markup=get_interests_inline_keyboard(selected))


# --- Инлайн-настройки: Фильтр возраста и Фильтр города ---
AGE_PREF_INPUT = range(1)
EDIT_NAME, EDIT_AGE, EDIT_CITY, EDIT_BIO = range(4)

def agepref_start_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("Введите диапазон возраста в формате 18-30")
    return AGE_PREF_INPUT

def agepref_input_step(update: Update, context: CallbackContext):
    text = (update.message.text or '').strip()
    try:
        parts = text.replace(' ', '').split('-')
        if len(parts) != 2:
            raise ValueError
        a1, a2 = int(parts[0]), int(parts[1])
        if not (18 <= a1 <= 99 and 18 <= a2 <= 99 and a1 <= a2):
            raise ValueError
    except Exception:
        update.message.reply_text("Неверный формат. Пример: 20-30")
        return AGE_PREF_INPUT
    set_age_preference(update.effective_user.id, a1, a2)
    update.message.reply_text("Фильтр возраста обновлён.", reply_markup=get_main_menu())
    return ConversationHandler.END

def cityfilter_toggle_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    u = get_user(uid)
    cur = bool(u.get('city_filter_enabled') if u and (u.get('city_filter_enabled') is not None) else True)
    set_city_filter_enabled(uid, not cur)
    query.answer("Переключено")
    new_state = "Вкл" if not cur else "Выкл"
    query.edit_message_text(f"Фильтр города: {new_state}. Откройте настройки снова для обновления меню.")

def interests_open_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data['edit_interests'] = []
    query.edit_message_text("Отметьте интересы галочками и нажмите Готово.")
    query.message.reply_text(
        "Выбор интересов:",
        reply_markup=get_interests_inline_keyboard([]),
    )


def delete_me(update: Update, context: CallbackContext):
    delete_user(update.effective_user.id)
    update.message.reply_text("Аккаунт удалён.", reply_markup=get_main_menu())

# --- Смена фотографий ---
CP_PHOTOS = range(1)

def change_photos_start(update: Update, context: CallbackContext):
    context.user_data['new_photos'] = []
    update.message.reply_text(
        "Отправьте новые фото (по одному). Когда закончите — нажмите 'Готово'.\n"
        "Старые фото будут заменены на новые после нажатия 'Готово'.",
        reply_markup=get_done_keyboard(),
    )
    return CP_PHOTOS

def change_photos_step(update: Update, context: CallbackContext):
    if update.message.text and update.message.text.strip().lower() == 'готово':
        photos = context.user_data.get('new_photos', [])
        if not photos:
            update.message.reply_text("Вы не добавили ни одного фото. Загрузка отменена.", reply_markup=get_main_menu())
            return ConversationHandler.END
        update_user_photos(update.effective_user.id, photos)
        update.message.reply_text("Фото обновлены.", reply_markup=get_main_menu())
        context.user_data.pop('new_photos', None)
        return ConversationHandler.END

    if update.message.photo:
        photo_file = update.message.photo[-1].get_file()
        idx = len(context.user_data.get('new_photos', [])) + 1
        path = save_photo(photo_file, update.effective_user.id, idx)
        arr = context.user_data.get('new_photos', [])
        arr.append(path)
        context.user_data['new_photos'] = arr
        update.message.reply_text(f"Фото {idx} сохранено. Можете отправить ещё или нажать 'Готово'.", reply_markup=get_done_keyboard())
        return CP_PHOTOS

    update.message.reply_text("Пожалуйста, отправьте фото или нажмите 'Готово'.", reply_markup=get_done_keyboard())
    return CP_PHOTOS


def register_settings_handlers(dp):
    dp.add_handler(CommandHandler('setname', set_name))
    dp.add_handler(CommandHandler('setage', set_age))
    dp.add_handler(CommandHandler('setcity', set_city))
    dp.add_handler(CommandHandler('setgi', set_gi))
    dp.add_handler(CommandHandler('setbio', set_bio))
    dp.add_handler(CommandHandler('edit_interests', edit_interests))
    dp.add_handler(CallbackQueryHandler(edit_interests_cb, pattern=r'^(intsel:\d+|intdone)$'))
    dp.add_handler(CallbackQueryHandler(interests_open_cb, pattern=r'^intdone_force_open$'))
    # Инлайн-настройки
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(agepref_start_cb, pattern=r'^agepref:start$')],
        states={
            AGE_PREF_INPUT: [MessageHandler(Filters.text & (~Filters.command), agepref_input_step)],
        },
        fallbacks=[],
        allow_reentry=True,
    ))
    dp.add_handler(CallbackQueryHandler(cityfilter_toggle_cb, pattern=r'^cityfilter:toggle$'))
    # Inline edit flows
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_name_start_cb, pattern=r'^edit:name$')],
        states={EDIT_NAME: [MessageHandler(Filters.text & (~Filters.command), edit_name_step)]},
        fallbacks=[], allow_reentry=True,
    ))
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_age_start_cb, pattern=r'^edit:age$')],
        states={EDIT_AGE: [MessageHandler(Filters.text & (~Filters.command), edit_age_step)]},
        fallbacks=[], allow_reentry=True,
    ))
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_city_start_cb, pattern=r'^edit:city$')],
        states={EDIT_CITY: [MessageHandler(Filters.text & (~Filters.command), edit_city_step)]},
        fallbacks=[], allow_reentry=True,
    ))
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_bio_start_cb, pattern=r'^edit:bio$')],
        states={EDIT_BIO: [MessageHandler(Filters.text & (~Filters.command), edit_bio_step)]},
        fallbacks=[], allow_reentry=True,
    ))
    # Photos change via inline
    dp.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(change_photos_start_cb, pattern=r'^photos:change$')],
        states={CP_PHOTOS: [MessageHandler((Filters.photo | Filters.text) & (~Filters.command), change_photos_step)]},
        fallbacks=[], allow_reentry=True,
    ))
    # Delete via inline
    dp.add_handler(CallbackQueryHandler(delete_confirm_cb, pattern=r'^delete:confirm$'))
    dp.add_handler(CallbackQueryHandler(delete_confirm_choice_cb, pattern=r'^delete:(yes|no)$'))
    dp.add_handler(CommandHandler('delete', delete_me))
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('change_photos', change_photos_start)],
        states={
            CP_PHOTOS: [MessageHandler((Filters.photo | Filters.text) & (~Filters.command), change_photos_step)],
        },
        fallbacks=[],
        allow_reentry=True,
    ))


