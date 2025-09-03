import os
import json
import base64
import requests
from datetime import datetime, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import CallbackContext
from db import (
    get_connection,
    get_next_profile_for_user,
    can_increment_view,
    increment_view,
    record_view,
    add_like,
    add_complaint,
    get_new_likes,
    get_unseen_likes,
    mark_inbox_seen,
    count_unseen_likes,
    list_users_for_csv,
    list_complaints,
    is_blocked as db_is_blocked,
    list_active_user_ids,
    set_app_setting,
    is_limits_disabled,
    touch_last_active,
    create_payment_record,
    update_payment_status,
    set_vip_until,
    is_vip_active,
)
from utils import (
    get_main_menu, get_admin_menu, get_moderator_menu,
    format_profile, get_interests_inline_keyboard,
    get_profile_actions_keyboard,
    get_vip_inline_keyboard,
)
from telegram import LabeledPrice

# Папки для хранения медиа
PHOTO_DIR = "photos"
VIDEO_DIR = "videos"
# Поддержка нескольких админов: читаем из окружения ADMIN_ID или ADMIN_IDS (через запятую/пробел)
_ADMIN_IDS_ENV = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or ""
try:
    _parsed_ids = [int(x) for x in _ADMIN_IDS_ENV.replace(',', ' ').split() if x.strip()]
except Exception:
    _parsed_ids = []
ADMIN_IDS = set(_parsed_ids) if _parsed_ids else {825042510}
# Набор модераторов (можно вынести в БД/настройки). По умолчанию включает всех админов
MODERATOR_IDS = set(ADMIN_IDS)
MAX_DAILY_VIEWS = 10

if not os.path.exists(PHOTO_DIR):
    os.mkdir(PHOTO_DIR)
if not os.path.exists(VIDEO_DIR):
    os.mkdir(VIDEO_DIR)

def start(update: Update, context: CallbackContext):
    if db_is_blocked(update.effective_user.id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return
    update.message.reply_text(
        "Привет! Нажмите /start чтобы создать анкету. После регистрации используйте меню ниже.",
        reply_markup=get_main_menu(update.effective_user.id in ADMIN_IDS),
    )

def skip_video(update: Update, context: CallbackContext):
    update.message.reply_text("Команда недоступна сейчас.")

def menu_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    is_moder = (user_id in MODERATOR_IDS) or is_admin
    try:
        touch_last_active(user_id)
    except Exception:
        pass
    if db_is_blocked(user_id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return
    text = update.message.text

    # Ожидание текста для рассылки (только админ/модера)
    if is_admin and context.user_data.get('awaiting_broadcast'):
        context.user_data.pop('awaiting_broadcast', None)
        msg = text.strip()
        if not msg:
            update.message.reply_text("Текст пустой. Повторите выбор через меню.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
            return
        users = list_active_user_ids()
        sent = 0
        for uid in users:
            try:
                context.bot.send_message(chat_id=uid, text=msg)
                sent += 1
            except Exception:
                pass
        update.message.reply_text(f"Рассылка отправлена {sent} пользователям.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
        return

    # Обработка ожидаемого ввода ID для блокировки/разблокировки (для админов/модераторов)
    if is_moder and context.user_data.get('awaiting_block_id'):
        context.user_data.pop('awaiting_block_id', None)
        try:
            target_id = int(text)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Повторите выбор через меню.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
            return
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET blocked = TRUE WHERE telegram_id = %s", (target_id,))
        conn.commit()
        cur.close()
        conn.close()
        update.message.reply_text(f"Пользователь {target_id} заблокирован.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
        return

    if is_moder and context.user_data.get('awaiting_unblock_id'):
        context.user_data.pop('awaiting_unblock_id', None)
        try:
            target_id = int(text)
        except ValueError:
            update.message.reply_text("ID должен быть числом. Повторите выбор через меню.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
            return
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET blocked = FALSE WHERE telegram_id = %s", (target_id,))
        conn.commit()
        cur.close()
        conn.close()
        update.message.reply_text(f"Пользователь {target_id} разблокирован.", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
        return

    if text.startswith("Профиль"):
        show_profile(update, context)
    elif text.startswith("Поиск"):
        show_next_profile(update, context)
    elif text.startswith("Симпатии"):
        show_likes(update, context)
    elif text.startswith("Настройки"):
        settings_menu(update, context)
    elif text.startswith("VIP"):
        active = False
        try:
            active = is_vip_active(user_id)
        except Exception:
            pass
        status = "Активен ✅" if active else "Не активен ❌"
        vip_text = (
            "💎 VIP-статус — твой ключ к успешным знакомствам! 💎\n"
            "🔥 Хочешь выйти за рамки ограничений? 🔥\n"
            "С VIP ты получаешь:\n"
            "✅ Безлимитный доступ — смотри анкеты без ограничений в день.\n"
            "✅ Прямые контакты — видишь @юзернеймы людей и можешь написать им напрямую, не дожидаясь взаимного лайка!\n"
            "(Работает, если у человека есть юзернейм и он не скрыл его в настройках приватности)\n"
            "✅ Больше matches — твоя анкета чаще показывается другим, а значит, шансы на взаимные симпатии вырастают в разы!\n"
            "🚀 Не упусти возможность знакомиться первым!\n"
            "Чем раньше ты станешь VIP — тем быстрее найдёшь того, кто тебе по-настоящему подходит.\n"
            "💬 P.S. Самые интересные люди часто скрываются за анонимностью — но с VIP ты сможешь увидеть их первым!\n"
            "✨ Активируй VIP сейчас и открой все двери к новым знакомствам\n\n"
            f"Статус VIP: {status}\nСтоимость: 300 ₽ / месяц"
        )
        update.message.reply_text(vip_text, reply_markup=get_vip_inline_keyboard())
    elif text.startswith("Поддержка"):
        update.message.reply_text(
            "Техподдержка: https://t.me/your_support_channel\nАдмин: @your_admin",
            reply_markup=get_main_menu(is_admin),
        )
    elif (text.startswith("История просмотров")) and is_admin:
        admin_views_history(update, context)
    elif (text.startswith("Статистика")) and is_admin:
        admin_stats(update, context)
    elif (text.startswith("Выгрузка пользователей CSV") or text.startswith("Выгрузка CSV")) and is_admin:
        users_csv(update, context)
    elif text.startswith("Просмотр жалоб") and (is_admin or is_moder):
        complaints_list(update, context)
    elif text.startswith("Отключить ограничения") and is_admin:
        set_app_setting("limits_disabled", "true")
        update.message.reply_text("Ограничения отключены: пользователи видят анкеты без лимитов.", reply_markup=get_admin_menu())
    elif text.startswith("Включить ограничения") and is_admin:
        set_app_setting("limits_disabled", "false")
        update.message.reply_text("Ограничения включены: обычные пользователи снова имеют лимит.", reply_markup=get_admin_menu())
    elif text.startswith("Рассылка") and is_admin:
        update.message.reply_text("Введите текст рассылки. Он будет отправлен всем активным пользователям.", reply_markup=get_admin_menu())
        context.user_data['awaiting_broadcast'] = True
    elif text.startswith("Заблокировать пользователя") and (is_admin or is_moder):
        update.message.reply_text("Введите ID пользователя для блокировки:", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
        context.user_data['awaiting_block_id'] = True
    elif text.startswith("Разблокировать пользователя") and (is_admin or is_moder):
        update.message.reply_text("Введите ID пользователя для разблокировки:", reply_markup=(get_admin_menu() if is_admin else get_moderator_menu()))
        context.user_data['awaiting_unblock_id'] = True
    elif text in ["↩️ Выход"] and (is_admin or is_moder):
        update.message.reply_text("Выход из меню.", reply_markup=get_main_menu(False))
    # Действия под анкетой (reply-кнопки)
    elif text == "❤️":
        to_user = context.user_data.get('current_profile')
        if not to_user:
            show_next_profile(update, context)
            return
        mutual = add_like(user_id, to_user)
        if mutual:
            try:
                u1 = context.bot.get_chat(user_id); u1n = f"@{u1.username}" if getattr(u1, 'username', None) else str(user_id)
            except Exception:
                u1n = str(user_id)
            try:
                u2 = context.bot.get_chat(to_user); u2n = f"@{u2.username}" if getattr(u2, 'username', None) else str(to_user)
            except Exception:
                u2n = str(to_user)
            context.bot.send_message(chat_id=user_id, text=f"Взаимная симпатия с {u2n}!")
            context.bot.send_message(chat_id=to_user, text=f"Взаимная симпатия с {u1n}!")
        # уведомление получателю лайка (коротко)
        try:
            cnt = count_unseen_likes(to_user)
            if cnt > 0:
                note = f"Вам поставили симпатии: {cnt}." if cnt > 1 else "Вам поставили симпатию."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("Посмотреть", callback_data="see_likes")]])
                context.bot.send_message(chat_id=to_user, text=note, reply_markup=kb)
        except Exception:
            pass
        # показать следующую анкету
        show_next_profile(update, context)
    elif text == "👎":
        show_next_profile(update, context)
    elif text.startswith("↩️"):
        update.message.reply_text("Главное меню", reply_markup=get_main_menu(is_admin))
    elif text.startswith("🚩 Пожаловаться"):
        to_user = context.user_data.get('current_profile')
        if to_user:
            add_complaint(user_id, to_user)
            update.message.reply_text("Жалоба отправлена модераторам.")
        show_next_profile(update, context)
    else:
        update.message.reply_text("Неизвестная команда.", reply_markup=get_main_menu(is_admin))

def show_profile(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if db_is_blocked(user_id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, age, city, gender_interest, interests, photos, videos, vip FROM users WHERE telegram_id=%s",
        (user_id,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        update.message.reply_text("Анкета не найдена. Нажмите /start чтобы создать.", reply_markup=get_main_menu())
        return
    name = user["name"]
    age = user["age"]
    city = user["city"]
    gender_interest = user["gender_interest"]
    interests = user.get("interests") or []
    photos = user.get("photos") or []
    videos = user.get("videos") or []
    vip = user.get("vip", False)
    interests_str = ", ".join(interests)
    vip_status = "Да" if vip else "Нет"
    bio = user.get("bio") or ""
    text = (
        f"👤 Имя: {name}\n"
        f"Возраст: {age}\n"
        f"Город: {city}\n"
        f"Ищу: {gender_interest}\n"
        f"Интересы: {interests_str}\n"
        + (f"Описание: {bio}\n" if bio else "") +
        f"VIP: {vip_status}"
    )
    media = []
    for p in photos:
        if p and os.path.exists(p):
            media.append(InputMediaPhoto(open(p, 'rb')))
    for v in videos:
        if v and os.path.exists(v):
            media.append(InputMediaVideo(open(v, 'rb')))
    if not media:
        update.message.reply_text(text)
    elif len(media) == 1:
        first = media[0]
        if isinstance(first, InputMediaPhoto):
            update.message.reply_photo(photo=first.media, caption=text)
        else:
            update.message.reply_video(video=first.media, caption=text)
    else:
        # Вставляем текст как caption к первому медиа, чтобы было одно сообщение-группа
        first = media[0]
        if isinstance(first, InputMediaPhoto):
            media[0] = InputMediaPhoto(first.media, caption=text)
        else:
            media[0] = InputMediaVideo(first.media, caption=text)
        update.message.reply_media_group(media)

    update.message.reply_text("Для жалобы на пользователя используйте кнопку под анкетой во время поиска или команду /complain <telegram_id>.", reply_markup=get_main_menu())


def _profile_inline_kb(profile_telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 Лайк", callback_data=f"like:{profile_telegram_id}"),
                InlineKeyboardButton("➡️ Далее", callback_data="next")
            ],
            [InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"complain:{profile_telegram_id}")],
        ]
    )


def show_next_profile(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if db_is_blocked(user_id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return
    # Проверим наличие своей анкеты для корректной работы поиска
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE telegram_id=%s", (user_id,))
    has_me = cur.fetchone() is not None
    cur.close()
    conn.close()
    if not has_me:
        update.message.reply_text("Сначала создайте анкету через /start.")
        return
    if not can_increment_view(user_id):
        upsell = (
            "✨ Твой личный лимит знакомств почти исчерпан! ✨\n"
            "Сегодня ты просмотрел(а) *10 из 10* доступных анкет.\n"
            "Хочешь продолжать поиски своей идеальной пары?\n\n"
            "\n💎 VIP-статус — твой ключ к успешным знакомствам! 💎\n"
            "🔥 Хочешь выйти за рамки ограничений? 🔥\n"
            "С VIP ты получаешь:\n"
            "✅ Безлимитный доступ — смотри анкеты без ограничений в день.\n"
            "✅ Прямые контакты — видишь @юзернеймы людей и можешь написать им напрямую, не дожидаясь взаимного лайка!\n"
            "(Работает, если у человека есть юзернейм и он не скрыл его в настройках приватности)\n\n"
            "🚀 Не упусти возможность знакомиться первым!\n"
            "Чем раньше ты станешь VIP — тем быстрее найдёшь того, кто тебе по-настоящему подходит.\n"
            "💬 P.S. Самые интересные люди часто скрываются за анонимностью — но с VIP ты сможешь увидеть их первым!\n"
            "✨ Активируй VIP сейчас и открой все двери к новым знакомствам! ✨"
        )
        (update.message or update.callback_query.message).reply_text(upsell, reply_markup=get_vip_inline_keyboard())
        return
    profile = get_next_profile_for_user(user_id)
    if not profile:
        (update.message or update.callback_query.message).reply_text("Пока нет анкет для просмотра.", reply_markup=get_main_menu())
        return
    increment_view(user_id)
    record_view(user_id, profile["telegram_id"])
    # сохранить текущий профиль для reply-кнопок
    context.user_data['current_profile'] = profile["telegram_id"]
    # Формируем текст анкеты. Для VIP показываем @username, если доступен
    try:
        # Узнаем, VIP ли текущий пользователь
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT vip FROM users WHERE telegram_id=%s", (user_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        viewer_is_vip = bool(row and row.get('vip'))
    except Exception:
        viewer_is_vip = False
    uname = ""
    if viewer_is_vip:
        try:
            chat = context.bot.get_chat(profile["telegram_id"]) ; uname = f"@{chat.username}" if getattr(chat, 'username', None) else ""
        except Exception:
            uname = ""
    # базовый текст
    text = format_profile(profile)
    if viewer_is_vip and uname:
        text = f"{text}\nКонтакт: {uname}"
    # отправляем медиа группой с caption на первом элементе, если есть
    media = []
    for p in profile.get("photos", []) or []:
        if p and os.path.exists(p):
            media.append(InputMediaPhoto(open(p, 'rb')))
    for v in profile.get("videos", []) or []:
        if v and os.path.exists(v):
            media.append(InputMediaVideo(open(v, 'rb')))
    if not media:
        (update.message or update.callback_query.message).reply_text(text, reply_markup=get_main_menu())
    elif len(media) == 1:
        first = media[0]
        if isinstance(first, InputMediaPhoto):
            (update.message or update.callback_query.message).reply_photo(photo=first.media, caption=text)
        else:
            (update.message or update.callback_query.message).reply_video(video=first.media, caption=text)
    else:
        first = media[0]
        if isinstance(first, InputMediaPhoto):
            media[0] = InputMediaPhoto(first.media, caption=text)
        else:
            media[0] = InputMediaVideo(first.media, caption=text)
        (update.message or update.callback_query.message).reply_media_group(media)
    # кнопки под анкетой (reply)
    (update.message or update.callback_query.message).reply_text("Выберите действие:", reply_markup=get_profile_actions_keyboard())


def show_likes(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    rows = get_new_likes(user_id)
    if not rows:
        update.message.reply_text("Новых симпатий нет.", reply_markup=get_main_menu())
        return
    text_lines = ["Новые симпатии:"]
    # Соберём уникальные from_user и получим их username или имя
    for r in rows:
        from_id = r['from_user'] if isinstance(r, dict) else r[0]
        created = r['created_at'] if isinstance(r, dict) else r[1]
        try:
            chat = context.bot.get_chat(from_id)
            uname = f"@{chat.username}" if getattr(chat, 'username', None) else None
        except Exception:
            uname = None
        display = uname
        if not display:
            # fallback к имени из профиля в БД
            try:
                from db import get_user
                u = get_user(from_id)
                display = u.get('name') if u else str(from_id)
            except Exception:
                display = str(from_id)
        text_lines.append(f"От: {display} ({created})")
    update.message.reply_text("\n".join(text_lines), reply_markup=get_main_menu())

def _send_full_profile(context: CallbackContext, chat_id: int, profile_user_id: int):
    # Получаем профиль из БД
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, age, city, gender_interest, interests, photos, videos,
               vip, bio, smoking, drinking, relationship
        FROM users WHERE telegram_id=%s
        """,
        (profile_user_id,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        try:
            context.bot.send_message(chat_id=chat_id, text="Анкета пользователя не найдена")
        except Exception:
            pass
        return
    # Попробуем получить @username
    try:
        chat = context.bot.get_chat(profile_user_id)
        uname = f"@{chat.username}" if getattr(chat, 'username', None) else ""
    except Exception:
        uname = ""
    bio = (user.get('bio') or '').strip()
    smoking = (user.get('smoking') or '').strip()
    drinking = (user.get('drinking') or '').strip()
    relationship = (user.get('relationship') or '').strip()
    def _show(val: str) -> bool:
        return bool(val) and ('Не отвечать' not in val)
    lines = [
        f"👤 Имя: {user.get('name','')}{' ('+uname+')' if uname else ''}",
        f"Возраст: {user.get('age','')}",
        f"Город: {user.get('city','')}",
        f"Ищу: {user.get('gender_interest','')}",
        f"Интересы: {', '.join(user.get('interests') or [])}",
    ]
    if bio:
        lines.append(f"Описание: {bio}")
    if _show(smoking):
        lines.append(f"Курю: {smoking}")
    if _show(drinking):
        lines.append(f"Пью: {drinking}")
    if _show(relationship):
        lines.append(f"Отношения: {relationship}")
    lines.append(f"VIP: {'Да' if user.get('vip') else 'Нет'}")
    text = "\n".join(lines)
    media = []
    for p in (user.get('photos') or []):
        if p and os.path.exists(p):
            media.append(InputMediaPhoto(open(p, 'rb')))
    for v in (user.get('videos') or []):
        if v and os.path.exists(v):
            media.append(InputMediaVideo(open(v, 'rb')))
    try:
        if not media:
            context.bot.send_message(chat_id=chat_id, text=text)
        elif len(media) == 1:
            first = media[0]
            if isinstance(first, InputMediaPhoto):
                context.bot.send_photo(chat_id=chat_id, photo=first.media, caption=text)
            else:
                context.bot.send_video(chat_id=chat_id, video=first.media, caption=text)
        else:
            first = media[0]
            if isinstance(first, InputMediaPhoto):
                media[0] = InputMediaPhoto(first.media, caption=text)
            else:
                media[0] = InputMediaVideo(first.media, caption=text)
            context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception:
        pass


def _send_profile_without_username(context: CallbackContext, chat_id: int, profile_user_id: int):
    # Получаем профиль из БД. Для VIP-пользователя (viewer=chat_id) показываем @username, для обычного — скрываем.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, age, city, gender_interest, interests, photos, videos,
               vip, bio, smoking, drinking, relationship
        FROM users WHERE telegram_id=%s
        """,
        (profile_user_id,),
    )
    user = cur.fetchone()
    # узнаем VIP статус смотрящего
    cur.execute("SELECT vip FROM users WHERE telegram_id=%s", (chat_id,))
    viewer_row = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        try:
            context.bot.send_message(chat_id=chat_id, text="Анкета пользователя не найдена")
        except Exception:
            pass
        return
    bio = (user.get('bio') or '').strip()
    smoking = (user.get('smoking') or '').strip()
    drinking = (user.get('drinking') or '').strip()
    relationship = (user.get('relationship') or '').strip()
    def _show(val: str) -> bool:
        return bool(val) and ('Не отвечать' not in val)
    lines = [
        f"👤 Имя: {user.get('name','')}",
        f"Возраст: {user.get('age','')}",
        f"Город: {user.get('city','')}",
        f"Ищу: {user.get('gender_interest','')}",
        f"Интересы: {', '.join(user.get('interests') or [])}",
    ]
    if bio:
        lines.append(f"Описание: {bio}")
    if _show(smoking):
        lines.append(f"Курю: {smoking}")
    if _show(drinking):
        lines.append(f"Пью: {drinking}")
    if _show(relationship):
        lines.append(f"Отношения: {relationship}")
    lines.append(f"VIP: {'Да' if user.get('vip') else 'Нет'}")
    text = "\n".join(lines)
    # Если смотрящий — VIP, покажем @username, если есть
    try:
        viewer_is_vip = bool(viewer_row and viewer_row.get('vip'))
    except Exception:
        viewer_is_vip = False
    if viewer_is_vip:
        try:
            chat = context.bot.get_chat(profile_user_id)
            uname = f"@{chat.username}" if getattr(chat, 'username', None) else ""
        except Exception:
            uname = ""
        if uname:
            text = f"{text}\nКонтакт: {uname}"
    media = []
    for p in (user.get('photos') or []):
        if p and os.path.exists(p):
            media.append(InputMediaPhoto(open(p, 'rb')))
    for v in (user.get('videos') or []):
        if v and os.path.exists(v):
            media.append(InputMediaVideo(open(v, 'rb')))
    try:
        if not media:
            context.bot.send_message(chat_id=chat_id, text=text)
        elif len(media) == 1:
            first = media[0]
            if isinstance(first, InputMediaPhoto):
                context.bot.send_photo(chat_id=chat_id, photo=first.media, caption=text)
            else:
                context.bot.send_video(chat_id=chat_id, video=first.media, caption=text)
        else:
            first = media[0]
            if isinstance(first, InputMediaPhoto):
                media[0] = InputMediaPhoto(first.media, caption=text)
            else:
                media[0] = InputMediaVideo(first.media, caption=text)
            context.bot.send_media_group(chat_id=chat_id, media=media)
    except Exception:
        pass


def settings_menu(update: Update, context: CallbackContext):
    # Короткое меню настроек с кнопками
    user_id = update.effective_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, age, city, gender_interest, interests, age_min_preference, age_max_preference, city_filter_enabled FROM users WHERE telegram_id=%s", (user_id,))
    u = cur.fetchone()
    cur.close()
    conn.close()
    if not u:
        update.message.reply_text("Анкета не найдена. Нажмите /start чтобы создать.", reply_markup=get_main_menu())
        return
    name, age, city, gi, interests = u["name"], u["age"], u["city"], u["gender_interest"], u["interests"]
    amin = u.get("age_min_preference")
    amax = u.get("age_max_preference")
    cfilter = bool(u.get("city_filter_enabled") if u.get("city_filter_enabled") is not None else True)
    age_pref_text = f"{amin}-{amax}" if amin and amax else "по умолчанию"
    city_filter_text = "Вкл" if cfilter else "Выкл"
    text = (
        "Настройки профиля:\n"
        f"Имя: {name}\nВозраст: {age}\nГород: {city}\nИщу: {gi}\nИнтересы: {', '.join(interests) if interests else '—'}\n\n"
        f"Фильтр возраста: {age_pref_text}\nФильтр города: {city_filter_text}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Изменить имя", callback_data="edit:name"), InlineKeyboardButton("Изменить возраст", callback_data="edit:age")],
        [InlineKeyboardButton("Изменить город", callback_data="edit:city"), InlineKeyboardButton("Изменить описание", callback_data="edit:bio")],
        [InlineKeyboardButton("Изменить фотографии", callback_data="photos:change"), InlineKeyboardButton("Изменить интересы", callback_data="intdone_force_open")],
        [InlineKeyboardButton("Фильтр возраста", callback_data="agepref:start"), InlineKeyboardButton("Фильтр города Вкл/Выкл", callback_data="cityfilter:toggle")],
        [InlineKeyboardButton("Удалить аккаунт", callback_data="delete:confirm")],
    ])
    update.message.reply_text(text, reply_markup=kb)



def complain_command(update: Update, context: CallbackContext):
    if db_is_blocked(update.effective_user.id):
        update.message.reply_text("Ваш аккаунт заблокирован и не может пользоваться ботом.")
        return
    if len(context.args) != 1:
        update.message.reply_text("Использование: /complain <telegram_id>", reply_markup=get_main_menu())
        return
    try:
        reported_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("ID пользователя должен быть числом.", reply_markup=get_main_menu())
        return
    reporter_id = update.effective_user.id
    reason = "Пользователь пожаловался через команду"
    add_complaint(reporter_id, reported_id, reason)
    update.message.reply_text(f"Жалоба на пользователя {reported_id} принята.", reply_markup=get_main_menu())


def on_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    if data == "next":
        query.answer()
        # прокинем в обычный поток
        show_next_profile(update, context)
        return
    if data.startswith("like:"):
        to_user = int(data.split(":", 1)[1])
        query.answer("Лайк отправлен")
        mutual = add_like(user_id, to_user)
        if mutual:
            # Попробуем указать username
            try:
                u1 = context.bot.get_chat(user_id); u1n = f"@{u1.username}" if getattr(u1, 'username', None) else str(user_id)
            except Exception:
                u1n = str(user_id)
            try:
                u2 = context.bot.get_chat(to_user); u2n = f"@{u2.username}" if getattr(u2, 'username', None) else str(to_user)
            except Exception:
                u2n = str(to_user)
            context.bot.send_message(chat_id=user_id, text=f"Взаимная симпатия с {u2n}!")
            context.bot.send_message(chat_id=to_user, text=f"Взаимная симпатия с {u1n}!")
        # Уведомление получателю лайка с кнопкой "Посмотреть"
        try:
            likes = get_new_likes(to_user) or []
            cnt = len(likes)
            note = "Кому-то понравилась ваша анкета" if cnt < 3 else f"Кому-то понравилась ваша анкета (ещё {cnt})"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Посмотреть", callback_data="see_likes")]])
            context.bot.send_message(chat_id=to_user, text=note, reply_markup=kb)
        except Exception:
            pass
        return
    if data.startswith("complain:"):
        reported_id = int(data.split(":", 1)[1])
        add_complaint(user_id, reported_id)
        query.answer("Жалоба отправлена")
        context.bot.send_message(chat_id=user_id, text="Жалоба отправлена модераторам.")
        return
    if data.startswith("compview:"):
        # Просмотр полной анкеты по жалобе: только для админа/модера
        rid = update.effective_user.id
        if (rid not in ADMIN_IDS) and (rid not in MODERATOR_IDS):
            query.answer()
            context.bot.send_message(chat_id=rid, text="Нет доступа.")
            return
        try:
            target = int(data.split(":",1)[1])
        except Exception:
            query.answer()
            return
        query.answer()
        _send_full_profile(context, rid, target)
        return
    if data == "see_likes":
        query.answer()
        rows = get_unseen_likes(user_id)
        if not rows:
            context.bot.send_message(chat_id=user_id, text="Симпатий больше нет, нажмите на Поиск чтобы смотреть анкеты.")
            return
        queue = [ (r['from_user'] if isinstance(r, dict) else r[0]) for r in rows ]
        context.user_data['likes_queue'] = queue
        # отправим первую
        next_id = context.user_data['likes_queue'].pop(0)
        context.user_data['current_like_from'] = next_id
        _send_profile_without_username(context, user_id, next_id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❤️", callback_data=f"likes:like:{next_id}"), InlineKeyboardButton("👎", callback_data=f"likes:dislike:{next_id}")]])
        context.bot.send_message(chat_id=user_id, text="Ваша реакция?", reply_markup=kb)
        return
    if data.startswith("likes:like:"):
        to_like = int(data.split(":", 2)[2])
        query.answer("Лайк")
        mutual = add_like(user_id, to_like)
        # пометим просмотренным
        try:
            mark_inbox_seen(user_id, to_like)
        except Exception:
            pass
        if mutual:
            # раскроем username через отдельное сообщение
            try:
                u = context.bot.get_chat(to_like); uname = f"@{u.username}" if getattr(u, 'username', None) else str(to_like)
            except Exception:
                uname = str(to_like)
            context.bot.send_message(chat_id=user_id, text=f"Взаимная симпатия с {uname}!")
        # показать следующий из очереди
        queue = context.user_data.get('likes_queue', [])
        if queue:
            next_id = queue.pop(0)
            context.user_data['likes_queue'] = queue
            context.user_data['current_like_from'] = next_id
            _send_profile_without_username(context, user_id, next_id)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❤️", callback_data=f"likes:like:{next_id}"), InlineKeyboardButton("👎", callback_data=f"likes:dislike:{next_id}")]])
            context.bot.send_message(chat_id=user_id, text="Ваша реакция?", reply_markup=kb)
        else:
            context.bot.send_message(chat_id=user_id, text="Симпатий больше нет, нажмите на Поиск чтобы смотреть анкеты.")
        return
    if data.startswith("likes:dislike:"):
        to_dislike = int(data.split(":", 2)[2])
        query.answer("Пропустить")
        try:
            mark_inbox_seen(user_id, to_dislike)
        except Exception:
            pass
        queue = context.user_data.get('likes_queue', [])
        if queue:
            next_id = queue.pop(0)
            context.user_data['likes_queue'] = queue
            context.user_data['current_like_from'] = next_id
            _send_profile_without_username(context, user_id, next_id)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("❤️", callback_data=f"likes:like:{next_id}"), InlineKeyboardButton("👎", callback_data=f"likes:dislike:{next_id}")]])
            context.bot.send_message(chat_id=user_id, text="Ваша реакция?", reply_markup=kb)
        else:
            context.bot.send_message(chat_id=user_id, text="Симпатий больше нет, нажмите на Поиск чтобы смотреть анкеты.")
        return
    # VIP через Telegram Payments
    if data == "vip:buy":
        query.answer()
        _send_vip_invoice(context, user_id)
        return

# --- Админские команды ---

def admin_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    update.message.reply_text("Админ-меню:", reply_markup=get_admin_menu())

def moder_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if (user_id not in MODERATOR_IDS) and (user_id not in ADMIN_IDS):
        update.message.reply_text("Нет доступа.")
        return
    update.message.reply_text("Модератор-меню:", reply_markup=get_moderator_menu())

def admin_block(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /block <user_id>")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET blocked = TRUE WHERE telegram_id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    update.message.reply_text(f"Пользователь {user_id} заблокирован.")

def admin_unblock(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /unblock <user_id>")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET blocked = FALSE WHERE telegram_id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    update.message.reply_text(f"Пользователь {user_id} разблокирован.")

def admin_send(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        user_id = int(context.args[0])
        message = " ".join(context.args[1:])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /send <user_id> <сообщение>")
        return
    context.bot.send_message(chat_id=user_id, text=message)
    update.message.reply_text(f"Сообщение отправлено пользователю {user_id}.")

def admin_broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    message = " ".join(context.args)
    users = list_active_user_ids()
    count = 0
    for uid in users:
        try:
            context.bot.send_message(chat_id=uid, text=message)
            count += 1
        except:
            pass
    update.message.reply_text(f"Сообщение отправлено {count} пользователям.")

def admin_add_moder(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        uid = int(context.args[0])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /addmoder <user_id>")
        return
    MODERATOR_IDS.add(uid)
    update.message.reply_text(f"Пользователь {uid} добавлен в модераторы.")

def admin_del_moder(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        uid = int(context.args[0])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /delmoder <user_id>")
        return
    if uid in MODERATOR_IDS:
        MODERATOR_IDS.remove(uid)
        update.message.reply_text(f"Пользователь {uid} удалён из модераторов.")
    else:
        update.message.reply_text("Пользователь не является модератором.")

def complaints_list(update: Update, context: CallbackContext):
    if (update.effective_user.id not in ADMIN_IDS) and (update.effective_user.id not in MODERATOR_IDS):
        update.message.reply_text("Нет доступа.")
        return
    rows = list_complaints()
    if not rows:
        update.message.reply_text("Жалоб нет.")
        return
    # На каждую жалобу отправим сообщение с кнопкой для просмотра анкеты
    for r in rows:
        rid = r["id"] if isinstance(r, dict) else r[0]
        reporter_id = r["reporter_id"] if isinstance(r, dict) else r[1]
        reported_id = r["reported_id"] if isinstance(r, dict) else r[2]
        reason = r["reason"] if isinstance(r, dict) else r[3]
        created_at = r["created_at"] if isinstance(r, dict) else r[4]
        text = f"Жалоба ID:{rid}\nНа: {reported_id}\nОт: {reporter_id}\nПричина: {reason}\nКогда: {created_at}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Посмотреть анкету", callback_data=f"compview:{reported_id}")]])
        update.message.reply_text(text, reply_markup=kb)

def users_csv(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    import csv
    from io import StringIO, BytesIO
    rows = list_users_for_csv()
    text_buf = StringIO()
    writer = csv.writer(text_buf)
    writer.writerow([
        'telegram_id','name','age','city','gender_interest','interests','smoking','drinking','relationship',
        'vip','blocked','last_view','daily_views','photos_count','videos_count'
    ])
    for r in rows:
        if isinstance(r, dict):
            writer.writerow([
                r.get('telegram_id'), r.get('name'), r.get('age'), r.get('city'), r.get('gender_interest'),
                ", ".join(r.get('interests') or []), r.get('smoking'), r.get('drinking'), r.get('relationship'),
                1 if r.get('vip') else 0, 1 if r.get('blocked') else 0, r.get('last_view'), r.get('daily_views'),
                r.get('photos_count'), r.get('videos_count')
            ])
        else:
            # r is a tuple in column order from list_users_for_csv
            telegram_id, name, age, city, gi, interests, smoking, drinking, relationship, vip, blocked, last_view, daily_views, photos_count, videos_count = r
            interests_s = ", ".join(interests) if isinstance(interests, list) else str(interests)
            writer.writerow([
                telegram_id, name, age, city, gi, interests_s, smoking, drinking, relationship,
                1 if vip else 0, 1 if blocked else 0, last_view, daily_views, photos_count, videos_count
            ])
    data = text_buf.getvalue().encode('utf-8')
    bin_buf = BytesIO(data)
    bin_buf.name = 'users.csv'
    update.message.reply_document(document=bin_buf)


def admin_stats(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE vip=TRUE")
    vip = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE blocked=TRUE")
    blocked = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM complaints")
    comp = cur.fetchone()["c"]
    cur.close()
    conn.close()
    update.message.reply_text(
        f"Пользователи: {total}\nVIP: {vip}\nЗаблокировано: {blocked}\nЖалобы: {comp}",
        reply_markup=get_main_menu(True),
    )


def _payment_provider_token() -> str:
    # Провайдер Telegram Payments (YooKassa через BotFather)
    # В бою лучше хранить в переменных окружения. Здесь используем live-токен по умолчанию.
    return os.getenv("PAYMENT_PROVIDER_TOKEN", "390540012:LIVE:76203")

VIP_PRICE_AMOUNT = 30000  # 300 RUB в копейках

def _send_vip_invoice(context: CallbackContext, user_id: int):
    prices = [LabeledPrice(label="VIP 30 дней", amount=VIP_PRICE_AMOUNT)]
    try:
        provider_data = {
            # Чек для ЮKassa (54‑ФЗ). Ускоряет проход платежа по карте.
            "receipt": {
                "items": [
                    {
                        "description": "VIP 30 дней",
                        "quantity": "1.0",
                        "amount": {"value": "300.00", "currency": "RUB"},
                        # Выберите корректный НДС вашего ИП/ООО (1..6). 1 — без НДС.
                        "vat_code": 1
                    }
                ]
            },
            # Захват платежа сразу после авторизации
            "capture": True,
        }
        context.bot.send_invoice(
            chat_id=user_id,
            title="VIP подписка",
            description=(
                "VIP снимает все лимиты на просмотры и лайки на 30 дней.\n"
                "Преимущества: безлимитные просмотры и лайки, приоритет в показах, \n"
                "видимость @username другой стороны (если есть)."
            ),
            payload="vip_month_300",
            provider_token=_payment_provider_token(),
            start_parameter="vip-sub",
            currency="RUB",
            prices=prices,
            provider_data=json.dumps(provider_data),
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
        )
    except Exception as e:
        try:
            context.bot.send_message(chat_id=user_id, text="Не удалось создать счёт. Попробуйте позже или обратитесь в поддержку.")
        except Exception:
            pass
        # Логируем неуспешный старт платежа
        try:
            from db import create_payment_record
            pid = f"invoice_fail:{user_id}:{int(datetime.utcnow().timestamp())}"
            create_payment_record(pid, user_id, VIP_PRICE_AMOUNT, "RUB", status="failed")
        except Exception:
            pass

def precheckout_callback(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    try:
        # Валидация payload/currency/amount
        if query.invoice_payload != "vip_month_300":
            query.answer(ok=False, error_message="Неверный платёж. Обратитесь в поддержку.")
            try:
                from db import create_payment_record
                pid = f"pre_fail:{query.from_user.id}:{int(datetime.utcnow().timestamp())}"
                create_payment_record(pid, query.from_user.id, query.total_amount or VIP_PRICE_AMOUNT, query.currency or "RUB", status="failed")
            except Exception:
                pass
            return
        if query.currency != "RUB":
            query.answer(ok=False, error_message="Поддерживается только валюта RUB.")
            try:
                from db import create_payment_record
                pid = f"pre_fail:{query.from_user.id}:{int(datetime.utcnow().timestamp())}"
                create_payment_record(pid, query.from_user.id, query.total_amount or VIP_PRICE_AMOUNT, query.currency or "RUB", status="failed")
            except Exception:
                pass
            return
        if query.total_amount != VIP_PRICE_AMOUNT:
            query.answer(ok=False, error_message="Сумма платежа не совпадает.")
            try:
                from db import create_payment_record
                pid = f"pre_fail:{query.from_user.id}:{int(datetime.utcnow().timestamp())}"
                create_payment_record(pid, query.from_user.id, query.total_amount or VIP_PRICE_AMOUNT, query.currency or "RUB", status="failed")
            except Exception:
                pass
            return
        query.answer(ok=True)
    except Exception:
        try:
            query.answer(ok=False, error_message="Ошибка проверки платежа. Попробуйте позже.")
        except Exception:
            pass
        try:
            from db import create_payment_record
            pid = f"pre_fail:{query.from_user.id}:{int(datetime.utcnow().timestamp())}"
            create_payment_record(pid, query.from_user.id, getattr(query, 'total_amount', None) or VIP_PRICE_AMOUNT, getattr(query, 'currency', None) or "RUB", status="failed")
        except Exception:
            pass

def successful_payment_callback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    sp = update.message.successful_payment
    # Защитимся от отсутствия объекта
    if not sp:
        update.message.reply_text("Платёж не распознан. Если деньги списались — напишите в поддержку.")
        return
    # Фиксируем оплату в БД и активируем VIP
    try:
        from db import create_payment_record, update_payment_status
        payment_id = sp.provider_payment_charge_id or f"tg:{user_id}:{int(datetime.utcnow().timestamp())}"
        amount = sp.total_amount
        currency = sp.currency
        try:
            create_payment_record(payment_id, user_id, amount, currency, status="paid")
        except Exception:
            # Если запись уже создавалась — обновим статус
            try:
                update_payment_status(payment_id, "paid")
            except Exception:
                pass
        until = datetime.utcnow() + timedelta(days=30)
        set_vip_until(user_id, until)
        update.message.reply_text(
            "Оплата успешна! VIP активирован на 30 дней ✅\n"
            "Спасибо за поддержку! Приятных знакомств."
        )
    except Exception:
        # Сообщим пользователю и не упадём
        update.message.reply_text(
            "Оплата прошла, но возникла ошибка при активации VIP. Мы разберёмся, VIP будет выдан."
        )
    # Уведомим админов об успешной оплате
    try:
        for aid in ADMIN_IDS:
            try:
                context.bot.send_message(chat_id=aid, text=f"Оплата VIP: user {user_id}, сумма {sp.total_amount/100:.2f} {sp.currency}")
            except Exception:
                pass
    except Exception:
        pass


def admin_views_history(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT viewer_id, viewed_id, created_at FROM views ORDER BY created_at DESC LIMIT 20")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        update.message.reply_text("История просмотров пуста.")
        return
    lines = ["Последние просмотры:"]
    for r in rows:
        viewer = r["viewer_id"] if isinstance(r, dict) else r[0]
        viewed = r["viewed_id"] if isinstance(r, dict) else r[1]
        ts = r["created_at"] if isinstance(r, dict) else r[2]
        lines.append(f"{viewer} -> {viewed} ({ts})")
    update.message.reply_text("\n".join(lines), reply_markup=get_main_menu(True))


def admin_view_reports(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Нет доступа.")
        return
    try:
        target_id = int(context.args[0])
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /view_reports <user_id>")
        return
    # фильтруем по reported_id
    rows = [r for r in list_complaints() if (r.get('reported_id') if isinstance(r, dict) else r[2]) == target_id]
    if not rows:
        update.message.reply_text("Жалоб на пользователя нет")
        return
    text = f"Жалобы на {target_id}:\n"
    for r in rows:
        reporter_id = r.get('reporter_id') if isinstance(r, dict) else r[1]
        reason = r.get('reason') if isinstance(r, dict) else r[3]
        created_at = r.get('created_at') if isinstance(r, dict) else r[4]
        text += f"От {reporter_id} — {reason} ({created_at})\n"
    update.message.reply_text(text)
