import os
import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==============================================
# КОНФИГУРАЦИЯ БОТА
# ==============================================

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 295698267  # Ваш РЕАЛЬНЫЙ ID (исправлено!)
DB_FILE = 'licenses.db'
LICENSE_PRICE = 100

print(f"🤖 Конфигурация загружена:")
print(f"📋 Admin ID: {ADMIN_ID}")
print(f"🔑 Token: {'✅ Установлен' if TOKEN else '❌ Не найден'}")

# ==============================================
# КОНСТАНТЫ С ТЕКСТАМИ
# ==============================================

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

✅ VPS оптимизированный
✅ Автоматическое определение тренда
✅ Защита от больших просадок

⚠️ **ВНИМАНИЕ:** 
Мартингейл стратегия требует достаточного депозита.
Рекомендуемый депозит: от $1000 на 0.01 лот.
"""

EA_INSTRUCTION = """
📖 **ПОДРОБНАЯ ИНСТРУКЦИЯ**

🔧 **УСТАНОВКА:**
1. Скачайте файл EA после получения лицензии
2. Поместите файл в папку: MetaTrader 5/MQL5/Experts/
3. Перезапустите MetaTrader 5
4. Перетащите EA на график нужного символа

📊 **НАСТРОЙКИ ДЛЯ BTCUSD:**
• Начальный лот: 0.01
• Take Profit: 10000 пунктов
• Buy Stop Distance: 3000 пунктов
• Максимум удвоений: 15

🥇 **НАСТРОЙКИ ДЛЯ XAUUSD:**  
• Начальный лот: 0.01
• Take Profit: 1000 пунктов
• Buy Stop Distance: 300 пунктов
• Максимум удвоений: 10

💡 **РЕКОМЕНДАЦИИ:**
• Торгуйте только на VPS
• Используйте ECN счета с низким спредом
• Мониторьте первые сделки внимательно

🆘 **ПОДДЕРЖКА:** @YourSupportBot
"""

# ==============================================
# ПРОВЕРКА АДМИНА (ПРОСТАЯ И НАДЕЖНАЯ)
# ==============================================

def is_admin(user_id):
    """Простая проверка админа с СУПЕРОТЛАДКОЙ"""
    print(f"=" * 60)
    print(f"🔍 СУПЕРОТЛАДКА ПРОВЕРКИ АДМИНА:")
    print(f"📥 Входящий user_id: '{user_id}' (тип: {type(user_id)})")
    print(f"🎯 Целевой ADMIN_ID: '{ADMIN_ID}' (тип: {type(ADMIN_ID)})")
    
    try:
        user_id_int = int(user_id)
        admin_id_int = int(ADMIN_ID)
        
        print(f"🔢 user_id_int: {user_id_int}")
        print(f"🔢 admin_id_int: {admin_id_int}")
        print(f"⚖️ Сравнение: {user_id_int} == {admin_id_int}")
        
        result = user_id_int == admin_id_int
        print(f"🎲 Результат сравнения: {result}")
        
        # ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА для известных админских ID
        if user_id_int in [295698267, 295608267]:  # Ваш реальный ID и старый на всякий случай
            print(f"🚨 ПРИНУДИТЕЛЬНО: ID {user_id_int} в списке админов!")
            result = True
        
        print(f"✅ ФИНАЛЬНЫЙ РЕЗУЛЬТАТ: {result}")
        print(f"=" * 60)
        
        return result
        
    except Exception as e:
        print(f"❌ ОШИБКА в is_admin: {e}")
        print(f"=" * 60)
        return False

# ==============================================
# БАЗА ДАННЫХ
# ==============================================

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
    print("✅ База данных инициализирована")

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
        print(f"❌ Ошибка регистрации: {e}")

def generate_license_key():
    """Генерация лицензионного ключа"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

def create_trial_license(user_id):
    """Создание пробной лицензии"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем, была ли пробная лицензия
        cursor.execute('SELECT license_key FROM users WHERE user_id = ? AND license_type = "trial"', 
                      (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return None, "У вас уже была пробная лицензия"
        
        # Создаем новую лицензию
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
        print(f"❌ Ошибка создания лицензии: {e}")
        return None, "Ошибка создания лицензии"

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
        print(f"❌ Ошибка получения лицензии: {e}")
        return None

def save_ea_file(file_data, filename):
    """Сохранить EA файл"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ea_files')  # Удаляем старый файл
        cursor.execute('INSERT INTO ea_files (filename, file_data) VALUES (?, ?)', 
                      (filename, file_data))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения файла: {e}")
        return False

def get_ea_file():
    """Получить EA файл"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT file_data FROM ea_files ORDER BY upload_date DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"❌ Ошибка получения файла: {e}")
        return None

def get_license_stats():
    """Статистика лицензий"""
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
        print(f"❌ Ошибка статистики: {e}")
        return None

# ==============================================
# КЛАВИАТУРЫ
# ==============================================

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

# ==============================================
# ОБРАБОТЧИКИ КОМАНД
# ==============================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    register_user(user.id, user.username or "Unknown")
    
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
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
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
    
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats (только для админа)"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    print(f"🎯 Команда /stats от пользователя:")
    print(f"   ID: {user_id}")
    print(f"   Username: {username}")
    print(f"   Проверяем права админа...")
    
    if not is_admin(user_id):
        print(f"❌ Пользователь {user_id} НЕ АДМИН!")
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    print(f"✅ Пользователь {user_id} - АДМИН! Выполняем команду...")
    
    stats = get_license_stats()
    if not stats:
        await update.message.reply_text("❌ Ошибка получения статистики")
        return
    
    stats_text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 **Всего пользователей:** {stats['total_users']}\n"
        f"✅ **Активных лицензий:** {stats['active_licenses']}\n"
        f"🆓 **Пробных лицензий:** {stats['trial_licenses']}\n"
        f"💰 **Полных лицензий:** {stats['full_licenses']}\n\n"
        f"💵 **Потенциальный доход:** ${stats['full_licenses'] * LICENSE_PRICE}"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def cmd_upload_ea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /upload_ea (только для админа)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
        
    await update.message.reply_text(
        "📁 **Загрузка EA файла**\n\n"
        "Отправьте .ex5 файл для загрузки в систему.\n"
        "Этот файл будут получать пользователи при скачивании EA.",
        parse_mode='Markdown'
    )

# ==============================================
# ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ
# ==============================================

async def handle_get_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение пробной лицензии"""
    query = update.callback_query
    await query.answer()
    
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

async def handle_check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса лицензии"""
    query = update.callback_query
    await query.answer()
    
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
    
    # Проверяем истечение лицензии
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
    
    keyboard = []
    if status == "active":
        keyboard.append([InlineKeyboardButton("📁 Скачать EA", callback_data="download_ea")])
    else:
        keyboard.extend([
            [InlineKeyboardButton("🆓 Получить пробную лицензию", callback_data="get_trial")],
            [InlineKeyboardButton("💰 Купить полную лицензию", callback_data="buy_license")]
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    
    await query.message.reply_text(
        status_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_show_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ описания EA"""
    query = update.callback_query
    await query.answer()
    
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

async def handle_show_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ инструкции"""
    query = update.callback_query
    await query.answer()
    
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

async def handle_buy_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка полной лицензии"""
    query = update.callback_query
    await query.answer()
    
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

async def handle_download_ea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачивание EA"""
    query = update.callback_query
    await query.answer()
    
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
    
    # Инструкция по скачиванию
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
        print(f"❌ Ошибка отправки файла: {e}")
        await query.message.reply_text(
            "❌ **Ошибка отправки файла!**\n\nПопробуйте позже или обратитесь к администратору.",
            reply_markup=get_main_keyboard()
        )

async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    await cmd_start(update, context)

# ==============================================
# ОБРАБОТЧИК CALLBACK ЗАПРОСОВ
# ==============================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    query = update.callback_query
    data = query.data
    
    print(f"📱 Callback: {data} от пользователя {query.from_user.id}")
    
    if data == "get_trial":
        await handle_get_trial(update, context)
    elif data == "check_status":
        await handle_check_status(update, context)
    elif data == "show_description":
        await handle_show_description(update, context)
    elif data == "show_instruction":
        await handle_show_instruction(update, context)
    elif data == "buy_license":
        await handle_buy_license(update, context)
    elif data == "download_ea":
        await handle_download_ea(update, context)
    elif data == "back_to_menu":
        await handle_back_to_menu(update, context)

# ==============================================
# ОБРАБОТЧИК ДОКУМЕНТОВ (ДЛЯ АДМИНОВ)
# ==============================================

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    if not update.message.document:
        return
    
    if not update.message.document.file_name.endswith('.ex5'):
        await update.message.reply_text("❌ Нужен файл с расширением .ex5!")
        return
    
    try:
        # Скачиваем файл
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()
        
        # Сохраняем в базу данных
        if save_ea_file(file_data, update.message.document.file_name):
            await update.message.reply_text(
                f"✅ **Файл EA загружен успешно!**\n\n"
                f"📁 **Имя файла:** {update.message.document.file_name}\n"
                f"📊 **Размер:** {len(file_data)} байт\n\n"
                f"Теперь пользователи смогут скачивать обновленную версию EA.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Ошибка сохранения файла!")
            
    except Exception as e:
        print(f"❌ Ошибка загрузки файла: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке файла!")

# ==============================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==============================================

def main():
    """Запуск бота"""
    print("🚀 Запуск бота...")
    
    # Проверяем TOKEN
    if not TOKEN:
        print("❌ ОШИБКА: Не найден BOT_TOKEN!")
        print("Установите переменную окружения: export BOT_TOKEN='ваш_токен'")
        return
    
    # Инициализируем базу данных
    init_database()
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("upload_ea", cmd_upload_ea))
    
    # Добавляем обработчики callback'ов и документов
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    
    print("✅ Бот запущен!")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    print("📋 ИНСТРУКЦИЯ ДЛЯ АДМИНИСТРАТОРА:")
    print("1. Отправьте боту команду /upload_ea")
    print("2. Отправьте .ex5 файл боту")
    print("3. Бот автоматически сохранит файл")
    print("4. Протестируйте команду /stats")
    print("=" * 50)
    
    # Запускаем бота
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
