import logging
import os
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler, PreCheckoutQueryHandler
)
from handlers import (
    start, skip_video, menu_handler,
    complain_command, on_callback,
    admin_command, admin_block, admin_unblock, admin_send, admin_broadcast,
    complaints_list, users_csv, admin_view_reports, moder_command,
    admin_add_moder, admin_del_moder,
    precheckout_callback, successful_payment_callback
)
from db import init_db
from registration import build_conversation_handler
from settings_handlers import register_settings_handlers

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "825042510"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Регистрация через ConversationHandler (обрабатывает /start)
    dp.add_handler(build_conversation_handler())

    # Главное меню
    dp.add_handler(MessageHandler(
        Filters.regex(r"^(Профиль|Поиск|Симпатии|Настройки|VIP|Поддержка)$"),
        menu_handler,
    ))
    # Кнопки админ/модератора
    dp.add_handler(MessageHandler(
        Filters.regex(r"^(История просмотров|Статистика|Выгрузка пользователей CSV|Просмотр жалоб|Заблокировать пользователя|Разблокировать пользователя|↩️ Выход)$"),
        menu_handler,
    ))

    # Зарегистрируем хендлеры настроек и их ConversationHandler ДО общего текстового ловца
    register_settings_handlers(dp)

    # Общий обработчик текста для ввода ID и прочих шагов меню (после специфичных regex)
    dp.add_handler(MessageHandler(
        Filters.text & (~Filters.command),
        menu_handler,
    ))

    # Жалобы
    dp.add_handler(CommandHandler("complain", complain_command))

    # Админ команды
    dp.add_handler(CommandHandler("admin", admin_command))
    dp.add_handler(CommandHandler("moder", moder_command))
    dp.add_handler(CommandHandler("block", admin_block))
    dp.add_handler(CommandHandler("unblock", admin_unblock))
    dp.add_handler(CommandHandler("send", admin_send))
    dp.add_handler(CommandHandler("broadcast", admin_broadcast))
    dp.add_handler(CommandHandler("addmoder", admin_add_moder))
    dp.add_handler(CommandHandler("delmoder", admin_del_moder))
    dp.add_handler(CommandHandler("complaints", complaints_list))
    dp.add_handler(CommandHandler("users_csv", users_csv))
    dp.add_handler(CommandHandler("view_reports", admin_view_reports))
    # Общий обработчик всех прочих callback'ов
    dp.add_handler(CallbackQueryHandler(on_callback))
    # Telegram Payments
    dp.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dp.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))

    # Инициализация базы
    init_db()

    logger.info("Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
