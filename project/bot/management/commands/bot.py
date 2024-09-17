import logging
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
)
from ...models import Profile
from django.core.mail import send_mail
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
# устанавливаем более высокий уровень логирования для httpx, чтобы исключить логирование всех GET и POST запросов
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ASK_QUESTION = range(1)
FEEDBACK = range(1)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    p, _ = await sync_to_async(Profile.objects.get_or_create)(
        external_id=chat_id,
        defaults={'name': update.message.from_user.username}
    )

    keyboard_start = [
        [InlineKeyboardButton('Викторина: "Ваше тотемное животное"', callback_data='quiz')],
        [InlineKeyboardButton('Информация о Московском зоопарке', callback_data='info')],
        [InlineKeyboardButton('Связь с сотрудником зоопарка', callback_data='contact')],
        [InlineKeyboardButton('Оставить отзыв', callback_data='feedback')],
    ]
    markup = InlineKeyboardMarkup(keyboard_start)

    await update.message.reply_text('Вас приветствует телеграмм-бот Московского зоопарка!', reply_markup=markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Для начала работы бота введите /start')


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.from_user.id
    userdb = await sync_to_async(Profile.objects.get)(external_id=chat_id)
    logger.info('Пользователь %s задал вопрос: %s', user.first_name, update.message.text)

    question_count = userdb.question - 1
    if user.username:
        contact_info = f'https://t.me/{user.username}'
    else:
        contact_info = f'tg://openmessage?user_id={chat_id}'
    contact_message = (
        f'Пользователь telegram {user.first_name} задал боту вопрос: "{update.message.text}". '
        f'\nСтатус прохождения викторины: {userdb.status}'
        f'\nКоличество отвеченных вопросов: {question_count}'
        f'\nКоличество заработанных очков: {userdb.points}'
        f'\nТотемное животное: {userdb.totem}'
        f'\n\nСвязь с пользователем: {contact_info}'
    )
    send_mail(
        subject=f'Вопрос сотруднику от пользователя {user.first_name}',
        message=contact_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.DEFAULT_CONTACT_EMAIL
    )
    await update.message.reply_text(
        'Ваш вопрос будет переадресован сотруднику зоопарка. '
        'Как только сотрудник подготовит ответ, то свяжется с Вами через Телеграмм. '
        'Спасибо за проявленный интерес!'
    )
    return ConversationHandler.END


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    logger.info('Пользователь %s оставил отзыв: %s', user.first_name, update.message.text)

    feedback_message = (
        f'Пользователь telegram {user.first_name} оставил отзыв: "{update.message.text}".'
    )
    send_mail(
        subject=f'Отзыв о работе телеграм-бота от пользователя {user.first_name}',
        message=feedback_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.DEFAULT_FEEDBACK_EMAIL
    )
    await update.message.reply_text(
        'Спасибо за Ваш отзыв!'
    )
    return ConversationHandler.END


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = update.callback_query.from_user.id
    user = await sync_to_async(Profile.objects.get)(external_id=chat_id)
    await query.answer()
    response = query.data

    if response == 'quiz':
        if user.status == 'Не пройдено' and user.question == 1:
            keyboard_lg = [
                [InlineKeyboardButton('Вперед!', callback_data='next')]
            ]
            markup = InlineKeyboardMarkup(keyboard_lg)
            await query.edit_message_text('Приступим!', reply_markup=markup)
        elif user.status == 'Не пройдено' and user.question > 1:
            keyboard_mg = [
                [InlineKeyboardButton('Продолжаю!', callback_data='next')],
                [InlineKeyboardButton('Начать заново.', callback_data='reset')]
            ]
            markup = InlineKeyboardMarkup(keyboard_mg)
            await query.edit_message_text(
                'Вы уже приступили к прохождению викторины. Хотите продолжить или начать заново?',
                reply_markup=markup
            )
        else:
            bot_name = await context.bot.getMe()
            share_text = f'Моё тотемное животное: {user.totem}! Узнай и ты своё: https://t.me/{bot_name.username}'
            keyboard_end = [
                [InlineKeyboardButton(
                    'Поделиться результатом',
                    url=f'https://vk.com/share.php?url={settings.PHOTOS[user.totem]}&title={user.totem}&comment={share_text}'
                )],
                [InlineKeyboardButton(
                    'Программа опеки "Клуб друзей зоопарка"',
                    url='https://moscowzoo.ru/about/guardianship'
                )],
                [InlineKeyboardButton('Перезапускаем!', callback_data='reset')],
            ]
            markup = InlineKeyboardMarkup(keyboard_end)

            await query.edit_message_text(
                f'Вы уже прошли викторину. Ваше тотемное животное: {user.totem}.'
                f'\nВы можете поделиться результатом прохождения викторины в социальной сети.'
                f'\nА также можете принять участие в программе опеки "Клуб друзей зоопарка".'
                f'\nХотите перезапустить и начать заново?',
                reply_markup=markup
            )
    elif response == 'next':
        keyboard = [
            [InlineKeyboardButton(
                f'1: {list(settings.ANSWERS[user.question - 1].items())[0][0]}',
                callback_data=f'{list(settings.ANSWERS[user.question - 1].items())[0][1]}'
            )],
            [InlineKeyboardButton(
                f'2: {list(settings.ANSWERS[user.question - 1].items())[1][0]}',
                callback_data=f'{list(settings.ANSWERS[user.question - 1].items())[1][1]}'
            )],
            [InlineKeyboardButton(
                f'3: {list(settings.ANSWERS[user.question - 1].items())[2][0]}',
                callback_data=f'{list(settings.ANSWERS[user.question - 1].items())[2][1]}'
            )],
            [InlineKeyboardButton(
                f'4: {list(settings.ANSWERS[user.question - 1].items())[3][0]}',
                callback_data=f'{list(settings.ANSWERS[user.question - 1].items())[3][1]}'
            )]
        ]

        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f'{settings.QUESTIONS[user.question - 1]}', reply_markup=markup)
    elif response == 'reset':
        user.question = 1
        user.points = 0
        user.status = 'Не пройдено'
        user.totem = 'Не определено'
        await sync_to_async(user.save)()
        await query.delete_message()

        keyboard_lg = [
            [InlineKeyboardButton('Поехали!', callback_data='next')]
        ]
        markup = InlineKeyboardMarkup(keyboard_lg)
        await context.bot.send_message(chat_id=chat_id, text='Готовы к прохождению?', reply_markup=markup)
    elif response == 'info':
        keyboard_info = [
            [InlineKeyboardButton(
                'Сайт Московского зоопарка',
                url='https://moscowzoo.ru'
            )],
        ]
        markup = InlineKeyboardMarkup(keyboard_info)
        text = ('Московский зоопарк — один из старейших зоопарков Европы. '
                'Он был открыт 31 января 1864 года по старому стилю и назывался тогда зоосадом.'
                '\nМосковский зоопарк был организован Императорским русским обществом акклиматизации животных и '
                'растений. Начало его существования связано с замечательными именами профессоров Московского '
                'Университета Карла Францевича Рулье, Анатолия Петровича Богданова и Сергея Алексеевича Усова.')
        await query.edit_message_text(text=text, reply_markup=markup)
    elif response == 'contact':
        await query.delete_message()
        text = ('Вы можете задать вопрос сотруднику зоопарка или обратиться за помощью. '
                'Связь c Вами будет осуществлена через Telegram, убедитесь, что указали "Имя пользователя" в настройках. '
                'Задайте Ваши вопросы сотруднику зоопарка в следующем сообщении. '
                'Если передумали, то введите /cancel.')
        await context.bot.send_message(
            text=text,
            chat_id=chat_id
        )
        return ASK_QUESTION
    elif response == 'feedback':
        await query.delete_message()
        await context.bot.send_message(
            text='Оставьте отзыв о работе телеграм-бота в следующем сообщении. '                 
                 'Если передумали, то введите /cancel.',
            chat_id=chat_id
        )
        return FEEDBACK
    else:
        user.question += 1
        user.points += int(query.data)
        if user.question > len(settings.QUESTIONS):
            user.status = 'Пройдено'
            if 0 <= user.points <= 5:
                user.totem = 'сова'
            elif 6 <= user.points <= 10:
                user.totem = 'волк'
            elif 11 <= user.points <= 15:
                user.totem = 'лев'
            else:
                user.totem = 'змея'
            await sync_to_async(user.save)()
            await query.delete_message()
            bot_name = await context.bot.getMe()
            share_text = f'Моё тотемное животное: {user.totem}! Узнай и ты своё: https://t.me/{bot_name.username}'
            keyboard_end = [
                [InlineKeyboardButton(
                    'Поделиться результатом',
                    url=f'https://vk.com/share.php?url={settings.PHOTOS[user.totem]}&title={user.totem}&comment={share_text}'
                )],
                [InlineKeyboardButton(
                    'Программа опеки "Клуб друзей зоопарка"',
                    url='https://moscowzoo.ru/about/guardianship'
                )],
                [InlineKeyboardButton('Попробовать еще раз.', callback_data='reset')],
            ]
            markup = InlineKeyboardMarkup(keyboard_end)
            await context.bot.send_photo(
                chat_id,
                photo=f'{settings.PHOTOS[user.totem]}',
                caption=f'Поздравляем с прохождением викторины!'
                        f'\nВаше тотемное животное: {user.totem}.'
                        f'\nВы можете поделиться результатом прохождения викторины в социальной сети.'
                        f'\nА также Вы можете принять участие в программе опеки "Клуб друзей зоопарка".'
                        f'\nИ в дополнение, можно перезапустить викторину и попробовать пройти еще раз.',
                reply_markup=markup
            )
        else:
            await sync_to_async(user.save)()

            keyboard_next = [
                [InlineKeyboardButton('Следующий вопрос', callback_data='next')]
            ]
            markup = InlineKeyboardMarkup(keyboard_next)
            await query.edit_message_text(text="Ваш ответ учтен!", reply_markup=markup)


def handle_response(text: str):
    processed: str = text.lower()
    key_words = ['hello', 'ghbdtn', 'привет', 'здравствуйте', 'hi']

    if any(x in processed for x in key_words):
        return ('Вас приветствует телеграмм-бот Московского зоопарка!'
                '\nВоспользуйтесь меню или введите /help для вывода основных команд.')

    return '\nВоспользуйтесь меню или введите /help для вывода основных команд.'


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    logger.info('Пользователь (%s) написал в %s: "%s"', update.message.chat.id, message_type, text)

    response: str = handle_response(text)

    logger.info('Бот ответил: %s', response)
    await update.message.reply_text(response)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Апдейт %s привел к возникновению ошибки: %s', update, context.error)


async def cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("Пользователь %s прервал отправку вопроса сотруднику зоопарка.", user.first_name)
    await update.message.reply_text(
        "Если возникнет вопрос, Вы всегда можете обратиться к сотруднику, воспользовавшись основным меню (/start).",
    )

    return ConversationHandler.END


async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("Пользователь %s прервал отправку отзыва.", user.first_name)
    await update.message.reply_text(
        "При желании Вы можете оставить отзыв, воспользовавшись основным меню (/start).",
    )

    return ConversationHandler.END


class Command(BaseCommand):
    help = 'Телеграм-бот'

    def handle(self, *args, **options):
        logger.info('Запуск бота...')
        application = Application.builder().token(settings.TOKEN).build()
        application.add_handler(CommandHandler('start', start_command))
        application.add_handler(CommandHandler('help', help_command))

        ask_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button, pattern='contact')],
            states={
                ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question)]
            },
            fallbacks=[CommandHandler('cancel', cancel_ask)]
        )
        application.add_handler(ask_conv_handler)

        feedback_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button, pattern='feedback')],
            states={
                FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback)]
            },
            fallbacks=[CommandHandler('cancel', cancel_feedback)]
        )
        application.add_handler(feedback_conv_handler)

        application.add_handler((MessageHandler(filters.TEXT, handle_message)))
        application.add_handler(CallbackQueryHandler(button))

        application.add_error_handler(error)

        logger.info('Polling..')
        application.run_polling(poll_interval=1)
