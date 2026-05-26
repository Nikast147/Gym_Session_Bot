import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import re

# ============================
# НАЛАШТУВАННЯ
# ============================
bot = telebot.TeleBot('8976382648:AAGb9XkNnGv8SYKebHFPFlVV2r0z_8jdiz4')

# Стан користувача (для FSM)
user_states = {}

# Стани реєстрації та запису
STATE_REGISTER_NAME = 'register_name'
STATE_REGISTER_PHONE = 'register_phone'
STATE_BOOKING_TYPE = 'booking_type'
STATE_BOOKING_TRAINER = 'booking_trainer'
STATE_BOOKING_DATE = 'booking_date'
STATE_BOOKING_TIME = 'booking_time'

# Типи тренувань
TRAINING_TYPES = ['🏋️ Силове', '🧘 Йога', '🥊 Бокс', '🏃 Кардіо']

# Тренери
TRAINERS = ['Олексій', 'Марія', 'Дмитро', 'Ольга']

# Доступні слоти часу
TIME_SLOTS = ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00']


# ============================
# БАЗА ДАНИХ
# ============================
def init_db():
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            training_type TEXT NOT NULL,
            trainer TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        )
    ''')

    conn.commit()
    conn.close()


def get_user(telegram_id):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def register_user(telegram_id, name, phone):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO users (telegram_id, name, phone) VALUES (?, ?, ?)',
        (telegram_id, name, phone)
    )
    conn.commit()
    conn.close()


def create_booking(telegram_id, training_type, trainer, date, time):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO bookings (telegram_id, training_type, trainer, date, time) VALUES (?, ?, ?, ?, ?)',
        (telegram_id, training_type, trainer, date, time)
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id


def get_user_bookings(telegram_id):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT id, training_type, trainer, date, time 
           FROM bookings 
           WHERE telegram_id = ? AND status = "active" AND date >= ?
           ORDER BY date, time''',
        (telegram_id, datetime.now().strftime('%Y-%m-%d'))
    )
    bookings = cursor.fetchall()
    conn.close()
    return bookings


def cancel_booking(booking_id, telegram_id):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE bookings SET status = "cancelled" WHERE id = ? AND telegram_id = ?',
        (booking_id, telegram_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def is_slot_taken(date, time, trainer):
    conn = sqlite3.connect('gym_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT COUNT(*) FROM bookings 
           WHERE date = ? AND time = ? AND trainer = ? AND status = "active"''',
        (date, time, trainer)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


# ============================
# ДОПОМІЖНІ ФУНКЦІЇ
# ============================
def set_state(user_id, state, data=None):
    user_states[user_id] = {'state': state, 'data': data or {}}


def get_state(user_id):
    return user_states.get(user_id, {})


def clear_state(user_id):
    user_states.pop(user_id, None)


def get_next_7_days():
    days = []
    for i in range(7):
        day = datetime.now() + timedelta(days=i)
        days.append(day.strftime('%Y-%m-%d'))
    return days


def format_date(date_str):
    date = datetime.strptime(date_str, '%Y-%m-%d')
    days_ua = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    return f"{days_ua[date.weekday()]} {date.strftime('%d.%m')}"


def validate_phone(phone):
    # Приймає формати: +380XXXXXXXXX, 0XXXXXXXXX, 380XXXXXXXXX
    pattern = r'^(\+?380|0)\d{9}$'
    return re.match(pattern, phone.replace(' ', '').replace('-', ''))


# ============================
# КЛАВІАТУРИ
# ============================
def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('📅 Записатись'),
        types.KeyboardButton('📋 Мої записи'),
        types.KeyboardButton('❌ Скасувати запис'),
        types.KeyboardButton('👤 Мій профіль'),
        types.KeyboardButton('ℹ️ Інфо про зал'),
        types.KeyboardButton('📞 Контакти')
    )
    return markup


def training_type_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(t, callback_data=f'type_{t}') for t in TRAINING_TYPES]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back_main'))
    return markup


def trainer_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(t, callback_data=f'trainer_{t}') for t in TRAINERS]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back_type'))
    return markup


def date_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=4)
    days = get_next_7_days()
    buttons = [types.InlineKeyboardButton(format_date(d), callback_data=f'date_{d}') for d in days]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back_trainer'))
    return markup


def time_keyboard(date, trainer):
    markup = types.InlineKeyboardMarkup(row_width=4)
    buttons = []
    for t in TIME_SLOTS:
        if is_slot_taken(date, t, trainer):
            buttons.append(types.InlineKeyboardButton(f'🚫 {t}', callback_data='slot_taken'))
        else:
            buttons.append(types.InlineKeyboardButton(f'✅ {t}', callback_data=f'time_{t}'))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back_date'))
    return markup


def cancel_booking_keyboard(bookings):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for b in bookings:
        bid, btype, trainer, date, time = b
        label = f'{format_date(date)} {time} | {btype} | {trainer}'
        markup.add(types.InlineKeyboardButton(f'❌ {label}', callback_data=f'cancel_{bid}'))
    markup.add(types.InlineKeyboardButton('🔙 Назад', callback_data='back_main'))
    return markup


# ============================
# ОБРОБНИКИ КОМАНД
# ============================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = get_user(message.from_user.id)
    if user:
        bot.send_message(
            message.chat.id,
            f'👋 З поверненням, *{user[2]}*!\n\nОберіть дію з меню нижче.',
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            f'👋 Привіт! Ласкаво просимо до бота спортзалу!\n\n'
            f'Для початку потрібно пройти реєстрацію.\n\n'
            f'Введіть своє *ім\'я*:',
            parse_mode='Markdown'
        )
        set_state(message.from_user.id, STATE_REGISTER_NAME)


@bot.message_handler(commands=['help'])
def cmd_help(message):
    text = (
        '📖 *Довідка*\n\n'
        '📅 *Записатись* — вибрати тренування та час\n'
        '📋 *Мої записи* — переглянути активні записи\n'
        '❌ *Скасувати запис* — скасувати бронювання\n'
        '👤 *Мій профіль* — переглянути свої дані\n'
        'ℹ️ *Інфо про зал* — розклад та правила\n'
        '📞 *Контакти* — зв\'язатись з нами\n\n'
        'Команди:\n'
        '/start — головне меню\n'
        '/help — ця довідка'
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


# ============================
# ОБРОБНИК ТЕКСТОВИХ ПОВІДОМЛЕНЬ
# ============================
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    uid = message.from_user.id
    state_data = get_state(uid)
    state = state_data.get('state')

    # --- РЕЄСТРАЦІЯ ---
    if state == STATE_REGISTER_NAME:
        name = message.text.strip()
        if len(name) < 2:
            bot.send_message(message.chat.id, '⚠️ Ім\'я занадто коротке. Введіть ще раз:')
            return
        set_state(uid, STATE_REGISTER_PHONE, {'name': name})
        bot.send_message(
            message.chat.id,
            f'✅ Чудово, *{name}*!\n\nТепер введіть свій номер телефону\n_(формат: 0XXXXXXXXX або +380XXXXXXXXX)_:',
            parse_mode='Markdown'
        )
        return

    if state == STATE_REGISTER_PHONE:
        phone = message.text.strip()
        if not validate_phone(phone):
            bot.send_message(
                message.chat.id,
                '⚠️ Невірний формат номера. Введіть у форматі *0XXXXXXXXX* або *+380XXXXXXXXX*:',
                parse_mode='Markdown'
            )
            return
        name = state_data['data']['name']
        register_user(uid, name, phone)
        clear_state(uid)
        bot.send_message(
            message.chat.id,
            f'🎉 Реєстрацію завершено!\n\n'
            f'👤 Ім\'я: *{name}*\n'
            f'📱 Телефон: *{phone}*\n\n'
            f'Тепер ви можете записатись на тренування!',
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        return

    # --- ПЕРЕВІРКА РЕЄСТРАЦІЇ ДЛЯ ІНШИХ ДІЙ ---
    user = get_user(uid)
    if not user:
        bot.send_message(
            message.chat.id,
            '⚠️ Спочатку потрібно зареєструватись. Введіть /start'
        )
        return

    # --- ГОЛОВНЕ МЕНЮ ---
    if message.text == '📅 Записатись':
        bot.send_message(
            message.chat.id,
            '🏋️ *Оберіть тип тренування:*',
            parse_mode='Markdown',
            reply_markup=training_type_keyboard()
        )
        set_state(uid, STATE_BOOKING_TYPE, {})

    elif message.text == '📋 Мої записи':
        bookings = get_user_bookings(uid)
        if not bookings:
            bot.send_message(message.chat.id, '📭 У вас немає активних записів.')
        else:
            text = '📋 *Ваші активні записи:*\n\n'
            for b in bookings:
                bid, btype, trainer, date, time = b
                text += (
                    f'🔹 *#{bid}*\n'
                    f'   📌 {btype}\n'
                    f'   👨‍🏫 Тренер: {trainer}\n'
                    f'   📅 {format_date(date)} о {time}\n\n'
                )
            bot.send_message(message.chat.id, text, parse_mode='Markdown')

    elif message.text == '❌ Скасувати запис':
        bookings = get_user_bookings(uid)
        if not bookings:
            bot.send_message(message.chat.id, '📭 Немає записів для скасування.')
        else:
            bot.send_message(
                message.chat.id,
                '❌ *Оберіть запис для скасування:*',
                parse_mode='Markdown',
                reply_markup=cancel_booking_keyboard(bookings)
            )

    elif message.text == '👤 Мій профіль':
        bookings = get_user_bookings(uid)
        text = (
            f'👤 *Ваш профіль*\n\n'
            f'📛 Ім\'я: *{user[2]}*\n'
            f'📱 Телефон: *{user[3]}*\n'
            f'📅 Активних записів: *{len(bookings)}*\n'
            f'🗓 Дата реєстрації: *{user[4][:10]}*'
        )
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

    elif message.text == 'ℹ️ Інфо про зал':
        text = (
            'ℹ️ *Про наш зал*\n\n'
            '🕗 Графік роботи:\n'
            '   Пн–Пт: 07:00 – 22:00\n'
            '   Сб–Нд: 09:00 – 20:00\n\n'
            '🏋️ Доступні тренування:\n'
            '   • Силові тренування\n'
            '   • Йога\n'
            '   • Бокс\n'
            '   • Кардіо\n\n'
            '💪 Наші тренери:\n'
            '   • Олексій — силові\n'
            '   • Марія — йога\n'
            '   • Дмитро — бокс і кардіо\n'
            '   • Ольга — силові та йога'
        )
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

    elif message.text == '📞 Контакти':
        text = (
            '📞 *Контакти*\n\n'
            '📍 Адреса: вул. Мала Морська, 108\n'
            '📱 Телефон: +38 (093) 188-86-78\n'
            '💬 Instagram: 100tonn\\_nikolaev'
        )
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

    else:
        bot.send_message(
            message.chat.id,
            '❓ Не розумію команду. Скористайтесь меню нижче.',
            reply_markup=main_menu_keyboard()
        )


# ============================
# ОБРОБНИК CALLBACK (INLINE КНОПКИ)
# ============================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    data = call.data
    state_data = get_state(uid)
    booking_data = state_data.get('data', {})

    # --- ЗАЙНЯТИЙ СЛОТ ---
    if data == 'slot_taken':
        bot.answer_callback_query(call.id, '🚫 Цей час вже зайнятий!')
        return

    # --- НАЗАД ДО ГОЛОВНОГО МЕНЮ ---
    if data == 'back_main':
        clear_state(uid)
        bot.edit_message_text(
            '🏠 Головне меню',
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
        return

    # --- ВИБІР ТИПУ ТРЕНУВАННЯ ---
    if data.startswith('type_'):
        training_type = data.replace('type_', '')
        set_state(uid, STATE_BOOKING_TRAINER, {'training_type': training_type})
        bot.edit_message_text(
            f'✅ Тип: *{training_type}*\n\n👨‍🏫 *Оберіть тренера:*',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=trainer_keyboard()
        )

    # --- НАЗАД ДО ТИПУ ---
    elif data == 'back_type':
        set_state(uid, STATE_BOOKING_TYPE, {})
        bot.edit_message_text(
            '🏋️ *Оберіть тип тренування:*',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=training_type_keyboard()
        )

    # --- ВИБІР ТРЕНЕРА ---
    elif data.startswith('trainer_'):
        trainer = data.replace('trainer_', '')
        booking_data['trainer'] = trainer
        set_state(uid, STATE_BOOKING_DATE, booking_data)
        bot.edit_message_text(
            f'✅ Тип: *{booking_data["training_type"]}*\n'
            f'✅ Тренер: *{trainer}*\n\n'
            f'📅 *Оберіть дату:*',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=date_keyboard()
        )

    # --- НАЗАД ДО ТРЕНЕРА ---
    elif data == 'back_trainer':
        set_state(uid, STATE_BOOKING_TRAINER, booking_data)
        bot.edit_message_text(
            f'✅ Тип: *{booking_data.get("training_type", "")}*\n\n'
            f'👨‍🏫 *Оберіть тренера:*',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=trainer_keyboard()
        )

    # --- ВИБІР ДАТИ ---
    elif data.startswith('date_'):
        date = data.replace('date_', '')
        booking_data['date'] = date
        set_state(uid, STATE_BOOKING_TIME, booking_data)
        bot.edit_message_text(
            f'✅ Тип: *{booking_data["training_type"]}*\n'
            f'✅ Тренер: *{booking_data["trainer"]}*\n'
            f'✅ Дата: *{format_date(date)}*\n\n'
            f'🕐 *Оберіть час:*\n_✅ — вільно  🚫 — зайнято_',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=time_keyboard(date, booking_data['trainer'])
        )

    # --- НАЗАД ДО ДАТИ ---
    elif data == 'back_date':
        set_state(uid, STATE_BOOKING_DATE, booking_data)
        bot.edit_message_text(
            f'✅ Тип: *{booking_data.get("training_type", "")}*\n'
            f'✅ Тренер: *{booking_data.get("trainer", "")}*\n\n'
            f'📅 *Оберіть дату:*',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=date_keyboard()
        )

    # --- ВИБІР ЧАСУ ТА ПІДТВЕРДЖЕННЯ ---
    elif data.startswith('time_'):
        time = data.replace('time_', '')
        booking_data['time'] = time

        # Перевірка ще раз перед записом
        if is_slot_taken(booking_data['date'], time, booking_data['trainer']):
            bot.answer_callback_query(call.id, '🚫 Цей час щойно зайняли!')
            return

        # Зберегти запис
        booking_id = create_booking(
            uid,
            booking_data['training_type'],
            booking_data['trainer'],
            booking_data['date'],
            time
        )
        clear_state(uid)

        # Підтвердження
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(
            types.InlineKeyboardButton('🏠 Головне меню', callback_data='back_main')
        )

        bot.edit_message_text(
            f'🎉 *Запис підтверджено!*\n\n'
            f'📌 Тип: *{booking_data["training_type"]}*\n'
            f'👨‍🏫 Тренер: *{booking_data["trainer"]}*\n'
            f'📅 Дата: *{format_date(booking_data["date"])}*\n'
            f'🕐 Час: *{time}*\n'
            f'🔖 Номер запису: *#{booking_id}*\n\n'
            f'_Чекаємо на вас! 💪_',
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=confirm_markup
        )

    # --- СКАСУВАННЯ ЗАПИСУ ---
    elif data.startswith('cancel_'):
        booking_id = int(data.replace('cancel_', ''))
        success = cancel_booking(booking_id, uid)
        if success:
            bot.answer_callback_query(call.id, '✅ Запис скасовано!')
            bot.edit_message_text(
                f'✅ Запис *#{booking_id}* успішно скасовано.',
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, '⚠️ Помилка скасування')

    bot.answer_callback_query(call.id)



bot.polling(non_stop=True)