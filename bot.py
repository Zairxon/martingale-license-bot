import os
import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Конфигурация бота
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 295608267
DB_FILE = 'licenses.db'

# Цена полной лицензии в долларах
LICENSE_PRICE = 100

# Описание EA
EA_DESCRIPTION = """
🤖 **АВТОМАТИЧЕСКИЙ ТОРГОВЫЙ СОВЕТНИК**
📊 **Тип:** Мартингейл стратегия
💰 **Символы:** BTCUSD, XAUUSD (Gold)

⚙️ **НАСТРОЙКИ ПО УМОЛЧАНИЮ:**

📈 **BTCUSD:**
• Начальный лот: 0.01
• Take Profit: 10000 пунктов  
• Расстояние стопов: 3000 пунктов
• Максимум удвоений: 15

🥇 **XAUUSD (Gold):**
• Начальный лот: 0.01
• Take Profit: 1000 пунктов
• Расстояние стопов: 300 пунктов  
• Максимум удвоений: 10

🎯 **ОСОБЕННОСТИ:**
✅ VPS оптимизированный
✅ Автоматическое определение тренда
✅ Защита от больших просадок
✅ Умная система стоп-лоссов
✅ Автоматический перезапуск сессий

⚠️ **ВНИМАНИЕ:** 
Мартингейл стратегия требует достаточного депозита и понимания рисков.
Рекомендуемый депозит: от $1000 на 0.01 лот.
"""

# Подробная инструкция
EA_INSTRUCTION = """
📖 **ПОДРОБНАЯ ИНСТРУКЦИЯ ПО УСТАНОВКЕ И НАСТРОЙКЕ**

🔧 **УСТАНОВКА:**
1. Скачайте файл EA после получения лицензии
2. Поместите файл в папку: MetaTrader 5/MQL5/Experts/
3. Перезапустите MetaTrader 5
4. Перетащите EA на график нужного символа

🎯 **НАСТРОЙКИ ДЛЯ РАЗНЫХ СИМВОЛОВ:**

📊 **BTCUSD (Bitcoin):**
```
Начальный лот: 0.01
Take Profit: 10000 пунктов
Buy Stop Distance: 3000 пунктов
Максимум удвоений: 15
Максимальный лот: 50.0
```

🥇 **XAUUSD (Золото):**
```
Начальный лот: 0.01  
Take Profit: 1000 пунктов
Buy Stop Distance: 300 пунктов
Максимум удвоений: 10
Максимальный лот: 5.0
```

💼 **ДРУГИЕ ВАЛЮТНЫЕ ПАРЫ:**
```
Начальный лот: 0.01
Take Profit: 500 пунктов
Buy Stop Distance: 150 пунктов
Максимум удвоений: 8
Максимальный лот: 2.0
```

⚡ **VPS НАСТРОЙКИ:**
```
Макс попыток: 3
Задержка повтора: 500 мс
Мин тиков для старта: 1
Задержка между сессиями: 5 сек
```

🎛️ **ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ:**
• Магический номер: 123456 (измените для разных графиков)
• Сброс после TP: true (рекомендуется)
• Использовать MA: true (анализ тренда)
• Период тренда: 20

💡 **РЕКОМЕНДАЦИИ:**
1. Торгуйте только на VPS для стабильности
2. Используйте ECN счета с низким спредом
3. Мониторьте первые сделки внимательно
4. Не запускайте на нескольких парах одновременно без достаточного депозита

⚠️ **УПРАВЛЕНИЕ РИСКАМИ:**
• Депозит $500+ для 0.01 лота на XAUUSD
• Депозит $1000+ для 0.01 лота на BTCUSD  
• Никогда не используйте весь депозит
• Следите за новостями рынка

🆘 **ПОДДЕРЖКА:**
При проблемах с настройкой обращайтесь к администратору.
"""

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            license_key TEXT UNIQUE,
            license_type TEXT DEFAULT 'trial',
            license_status TEXT DEFAULT 'inactive',
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для файлов EA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ea_files (
            id INTEGER PRIMARY KEY,
            filename TEXT NOT NULL,
            file_data BLOB NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_license_key():
    """Генерация лицензионного ключа"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

def register_user(user_id, username):
    """Регистрация пользователя"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                      (user_id, username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка регистрации пользователя: {e}")

def get_user_license(user_id):
    """Получить лицензию пользователя"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT license_key, license_status, license_type, expires_at FROM users WHERE user_id = ?', 
                      (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result
    except Exception as e:
        print(f"Ошибка получения лицензии: {e}")
        return None

def create_trial_license(user_id):
    """Создание пробной лицензии"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем, была ли уже пробная лицензия
        cursor.execute('SELECT license_key FROM users WHERE user_id = ? AND license_type = "trial"', 
                      (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return None, "У вас уже была пробная лицензия"
        
        # Создаем новую пробную лицензию
        license_key = generate_license_key()
        expires_at = datetime.now() + timedelta(days=3)
        
        cursor.execute('''
            UPDATE users 
            SET license_key = ?, license_type = 'trial', license_status = 'active', expires_at = ?
            WHERE user_id = ?
        ''', (license_key, expires_at, user_id))
        
        conn.commit()
        conn.close()
        
        return license_key, None
    except Exception as e:
        print(f"Ошибка создания пробной лицензии: {e}")
        return None, "Ошибка создания лицензии"

def save_ea_file(file_data, filename):
    """Сохранить файл EA в базу данных"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Удаляем старые файлы и вставляем новый
        cursor.execute('DELETE FROM ea_files')
        cursor.execute('INSERT INTO ea_files (filename, file_data) VALUES (?, ?)', 
                      (filename, file_data))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка сохранения файла: {e}")
        return False

def get_ea_file():
    """Получить файл EA из базы данных"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT file_data FROM ea_files ORDER BY upload_date DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        
        # Если файла нет в БД, возвращаем None
        return None
    except Exception as e:
        print(f"Ошибка получения файла: {e}")
        return None

def get_license_stats():
    """Получить статистику лицензий"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE license_status = "active"')
        active_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE license_type = "trial"')
        trial_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE license_type = "full"')
        full_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'active_licenses': active_licenses,
            'trial_licenses': trial_licenses,
            'full_licenses': full_licenses
        }
    except Exception as e:
        print(f"Ошибка получения статистики: {e}")
        return None

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = [
        [InlineKeyboardButton("🆓 Получить 3 дня БЕСПЛАТНО", callback_data="get_trial")],
        [InlineKeyboardButton("💰 Купить полную лицензию ($100)", callback_data="buy_license")],
        [InlineKeyboardButton("📊 Мой статус", callback_data="check_status")],
        [InlineKeyboardButton("📖 Описание советника", callback_data="show_description")],
        [InlineKeyboardButton("📖 Инструкция", callback_data="show_instruction")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_start_command(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Регистрируем пользователя
    register_user(user_id, username)
    
    welcome_text = (
        "🤖 **Добро пожаловать в Martingale EA License Bot!**\n\n"
        "🎯 **Этот бот предоставляет доступ к торговому советнику:**\n"
        "• Автоматическая торговля по стратегии Мартингейл\n"
        "• Поддержка BTCUSD и XAUUSD\n"
        "• VPS оптимизированная версия\n\n"
        "💡 **Доступные опции:**\n"
        "🆓 **Пробная лицензия** - 3 дня бесплатно\n"
        "💰 **Полная лицензия** - $100 (безлимитный доступ)\n\n"
        "⬇️ Выберите действие:"
    )
    
    await message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def handle_help_command(message):
    """Обработчик команды /help"""
    help_text = (
        "❓ **Справка по боту**\n\n"
        "🔹 **/start** - главное меню\n"
        "🔹 **🆓 Пробная лицензия** - 3 дня бесплатного доступа\n"
        "🔹 **💰 Полная лицензия** - безлимитный доступ за $100\n"
        "🔹 **📊 Мой статус** - проверить текущую лицензию\n"
        "🔹 **📖 Описание** - детали о торговом советнике\n"
        "🔹 **📖 Инструкция** - руководство по установке\n\n"
        "📞 **Поддержка:** @YourSupportBot"
    )
    
    await message.reply_text(help_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def handle_get_trial(query):
    """Обработчик получения пробной лицензии"""
    user_id = query.from_user.id
    
    license_key, error = create_trial_license(user_id)
    
    if error:
        await query.message.reply_text(
            f"❌ **Ошибка!**\n\n{error}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("📁 Скачать EA", callback_data="download_ea")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    
    await query.message.reply_text(
        f"🎉 **Пробная лицензия активирована!**\n\n"
        f"🔑 **Ваш лицензионный ключ:**\n`{license_key}`\n\n"
        f"⏰ **Срок действия:** 3 дня\n\n"
        f"📋 **Что дальше:**\n"
        f"1. Скачайте EA по кнопке ниже\n"
        f"2. Установите в MetaTrader 5\n"
        f"3. Введите ключ в настройках EA\n\n"
        f"💡 **Сохраните ключ** - он понадобится для запуска советника!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_check_status(query):
    """Обработчик проверки статуса лицензии"""
    user_id = query.from_user.id
    license_data = get_user_license(user_id)
    
    if not license_data or not license_data[0]:
        await query.message.reply_text(
            "❌ **Лицензия не найдена**\n\n"
            "У вас пока нет активной лицензии.\n"
            "Получите пробную или купите полную лицензию.",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        return
    
    license_key, status, license_type, expires_at = license_data
    
    # Проверяем не истекла ли лицензия
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
        status = "expired"
    
    status_emoji = "✅" if status == "active" else "❌"
    type_emoji = "🆓" if license_type == "trial" else "💰"
    
    status_text = (
        f"{status_emoji} **Статус лицензии**\n\n"
        f"🔑 **Ключ:** `{license_key}`\n"
        f"{type_emoji} **Тип:** {license_type.title()}\n"
        f"📊 **Статус:** {status.title()}\n"
    )
    
    if expires_at and license_type == "trial":
        status_text += f"⏰ **Истекает:** {expires_at}\n"
    elif license_type == "full":
        status_text += f"♾️ **Срок:** Безлимитный\n"
    
    if status == "active":
        keyboard = [
            [InlineKeyboardButton("📁 Скачать EA", callback_data="download_ea")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🆓 Получить пробную лицензию", callback_data="get_trial")],
            [InlineKeyboardButton("💰 Купить полную лицензию", callback_data="buy_license")],
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ]
    
    await query.message.reply_text(
        status_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_show_description(query):
    """Обработчик показа описания EA"""
    keyboard = [
        [InlineKeyboardButton("📖 Подробная инструкция", callback_data="show_instruction")],
        [InlineKeyboardButton("🆓 Получить пробную лицензию", callback_data="get_trial")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    
    await query.message.reply_text(
        EA_DESCRIPTION,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_show_instruction(query):
    """Обработчик показа инструкции"""
    keyboard = [
        [InlineKeyboardButton("📖 Описание советника", callback_data="show_description")],
        [InlineKeyboardButton("🆓 Получить пробную лицензию", callback_data="get_trial")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    
    await query.message.reply_text(
        EA_INSTRUCTION,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_buy_license(query):
    """Обработчик покупки полной лицензии"""
    await query.message.reply_text(
        f"💰 **Покупка полной лицензии**\n\n"
        f"💵 **Стоимость:** ${LICENSE_PRICE}\n"
        f"♾️ **Срок действия:** Безлимитный\n\n"
        f"📞 **Для покупки обратитесь к администратору:**\n"
        f"@YourSupportBot\n\n"
        f"💳 **Способы оплаты:**\n"
        f"• Криптовалюта (BTC, USDT)\n"
        f"• PayPal\n"
        f"• Банковская карта\n\n"
        f"⚡ Лицензия активируется в течение 1 часа после оплаты!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
        ])
    )

async def handle_download_ea(query):
    """Обработчик скачивания EA"""
    user_id = query.from_user.id
    license_data = get_user_license(user_id)
    
    if not license_data or license_data[1] == 'inactive':
        await query.message.reply_text(
            "❌ **Нет активной лицензии!**\n\n"
            "Для скачивания EA нужна активная лицензия.\n"
            "Получите пробную или купите полную лицензию.",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        return
    
    license_key = license_data[0]
    
    # Отправляем инструкцию
    await query.message.reply_text(
        f"📁 **Скачивание EA**\n\n"
        f"🔑 **Ваш лицензионный ключ:** `{license_key}`\n\n"
        f"📋 **Инструкция:**\n"
        f"1. Скачайте файл который придет следующим сообщением\n"
        f"2. Поместите EA в папку: MQL5/Experts/\n"
        f"3. Перезапустите MetaTrader 5\n"
        f"4. При запуске EA введите ваш ключ: `{license_key}`\n\n"
        f"⏳ Отправляю файл...",
        parse_mode='Markdown'
    )
    
    # Отправляем файл EA
    try:
        ea_file_data = get_ea_file()
        if ea_file_data:
            await query.message.reply_document(
                document=ea_file_data,
                filename="Simple_VPS_Optimized_Version.ex5",
                caption=f"🤖 **Торговый советник**\n\n🔑 **Лицензионный ключ:** `{license_key}`\n\n❗ Сохраните ключ - он понадобится при запуске EA!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            await query.message.reply_text(
                "❌ **Ошибка!**\n\nФайл EA временно недоступен. Обратитесь к администратору.",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        print(f"Ошибка отправки файла: {e}")
        await query.message.reply_text(
            "❌ **Ошибка отправки файла!**\n\nПопробуйте позже или обратитесь к администратору.",
            reply_markup=get_main_keyboard()
        )

async def handle_admin_stats(message):
    """Обработчик статистики для админа"""
    stats = get_license_stats()
    
    if not stats:
        await message.reply_text("❌ Ошибка получения статистики")
        return
    
    stats_text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {stats['total_users']}\n"
        f"✅ **Активных лицензий:** {stats['active_licenses']}\n"
        f"🆓 **Пробных лицензий:** {stats['trial_licenses']}\n"
        f"💰 **Полных лицензий:** {stats['full_licenses']}\n\n"
        f"💵 **Потенциальный доход:** ${stats['full_licenses'] * LICENSE_PRICE}"
    )
    
    await message.reply_text(stats_text, parse_mode='Markdown')

async def handle_admin_upload_ea(message):
    """Обработчик загрузки EA файла админом"""
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("❌ Доступ запрещен!")
        return
    
    if not message.document:
        await message.reply_text("❌ Отправьте .ex5 файл!")
        return
    
    if not message.document.file_name.endswith('.ex5'):
        await message.reply_text("❌ Нужен файл с расширением .ex5!")
        return
    
    try:
        # Скачиваем файл
        file = await message.document.get_file()
        file_data = await file.download_as_bytearray()
        
        # Сохраняем в базу данных
        if save_ea_file(file_data, message.document.file_name):
            await message.reply_text(
                f"✅ **Файл EA загружен успешно!**\n\n"
                f"📁 **Имя файла:** {message.document.file_name}\n"
                f"📊 **Размер:** {len(file_data)} байт\n\n"
                f"Теперь пользователи смогут скачивать обновленную версию EA.",
                parse_mode='Markdown'
            )
        else:
            await message.reply_text("❌ Ошибка сохранения файла!")
            
    except Exception as e:
        print(f"Ошибка загрузки файла: {e}")
        await message.reply_text("❌ Ошибка при загрузке файла!")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    query = update.callback_query
    data = query.data
    
    await query.answer()
    
    if data == "get_trial":
        await handle_get_trial(query)
    elif data == "check_status":
        await handle_check_status(query)
    elif data == "show_description":
        await handle_show_description(query)
    elif data == "show_instruction":
        await handle_show_instruction(query)
    elif data == "buy_license":
        await handle_buy_license(query)
    elif data == "download_ea":
        await handle_download_ea(query)
    elif data == "back_to_menu":
        await handle_start_command(query.message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    message = update.message
    user_id = message.from_user.id
    text = message.text
    
    # Регистрируем пользователя если новый
    register_user(user_id, message.from_user.username or "Unknown")
    
    # Админские команды
    if user_id == ADMIN_ID:
        if text == "/stats":
            await handle_admin_stats(message)
            return
        elif text == "/upload_ea":
            await message.reply_text(
                "📁 **Загрузка EA файла**\n\n"
                "Отправьте .ex5 файл для загрузки в систему.\n"
                "Этот файл будут получать пользователи при скачивании EA.",
                parse_mode='Markdown'
            )
            return
        elif message.document:
            await handle_admin_upload_ea(message)
            return
    
    # Обычные команды
    if text == "/start":
        await handle_start_command(message)
    elif text == "/help":
        await handle_help_command(message)
    else:
        await message.reply_text(
            "❓ Неизвестная команда. Используйте /start для главного меню.",
            reply_markup=get_main_keyboard()
        )

if __name__ == '__main__':
    # Инициализация базы данных
    init_database()
    
    print("🤖 Бот запускается...")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    print("📋 ИНСТРУКЦИЯ ДЛЯ АДМИНИСТРАТОРА:")
    print("1. Отправьте боту команду /upload_ea")
    print("2. Отправьте .ex5 файл боту")
    print("3. Бот автоматически сохранит файл в базу данных")
    print("4. После этого пользователи смогут скачивать файл")
    print("=" * 50)
    
    # Запуск бота
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", lambda update, context: handle_message(update, context)))
    application.add_handler(CommandHandler("help", lambda update, context: handle_message(update, context)))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запуск
    application.run_polling()
