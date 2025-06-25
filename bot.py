import os
import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Конфигурация
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 295698267
LICENSE_PRICE = 100

# Банковские реквизиты
VISA_CARD = "4278 3100 2430 7167"
HUMO_CARD = "9860 1001 2541 9018"
CARD_OWNER = "Asqarov Rasulbek"

print(f"🚀 Запуск бота...")
print(f"👨‍💼 Admin ID: {ADMIN_ID}")
print(f"💳 VISA: {VISA_CARD}")
print(f"💳 HUMO: {HUMO_CARD}")
print(f"👤 Владелец: {CARD_OWNER}")

# База данных
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        license_key TEXT,
        license_type TEXT DEFAULT 'none',
        license_status TEXT DEFAULT 'inactive',
        expires_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        amount INTEGER DEFAULT 100,
        status TEXT DEFAULT 'pending',
        receipt_file_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ea_files (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        file_data BLOB
    )''')
    
    conn.commit()
    conn.close()

def generate_key():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def register_user(user_id, username):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def get_user_license(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT license_key, license_type, license_status, expires_at FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def create_trial_license(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Проверяем была ли пробная лицензия
    c.execute('SELECT license_type FROM users WHERE user_id = ? AND license_type = "trial"', (user_id,))
    if c.fetchone():
        conn.close()
        return None, "У вас уже была пробная лицензия"
    
    # Создаем пробную лицензию
    key = generate_key()
    expires = (datetime.now() + timedelta(days=3)).isoformat()
    
    c.execute('''UPDATE users SET 
        license_key = ?, license_type = 'trial', license_status = 'active', expires_at = ?
        WHERE user_id = ?''', (key, expires, user_id))
    
    conn.commit()
    conn.close()
    return key, None

def create_full_license(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    key = generate_key()
    c.execute('''UPDATE users SET 
        license_key = ?, license_type = 'full', license_status = 'active', expires_at = NULL
        WHERE user_id = ?''', (key, user_id))
    
    conn.commit()
    conn.close()
    return key

def create_payment_request(user_id, username):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO payments (user_id, username) VALUES (?, ?)', (user_id, username))
    payment_id = c.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def save_receipt(payment_id, file_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('UPDATE payments SET receipt_file_id = ? WHERE id = ?', (file_id, payment_id))
    conn.commit()
    conn.close()

def approve_payment(payment_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute('SELECT user_id FROM payments WHERE id = ?', (payment_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return None
    
    user_id = result[0]
    license_key = create_full_license(user_id)
    
    c.execute('UPDATE payments SET status = "approved" WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    return license_key, user_id

def reject_payment(payment_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute('SELECT user_id FROM payments WHERE id = ?', (payment_id,))
    result = c.fetchone()
    if not result:
        conn.close()
        return None
    
    user_id = result[0]
    c.execute('UPDATE payments SET status = "rejected" WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    return user_id

def save_ea_file(file_data, filename):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('DELETE FROM ea_files')
    c.execute('INSERT INTO ea_files (filename, file_data) VALUES (?, ?)', (filename, file_data))
    conn.commit()
    conn.close()

def get_ea_file():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('SELECT file_data FROM ea_files LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_stats():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE license_status = "active"')
    active = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE license_type = "trial"')
    trial = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE license_type = "full"')
    full = c.fetchone()[0]
    
    conn.close()
    return {'total': total_users, 'active': active, 'trial': trial, 'full': full}

# Клавиатуры
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🆓 3 дня БЕСПЛАТНО", callback_data="trial")],
        [InlineKeyboardButton("💰 Купить лицензию $100", callback_data="buy")],
        [InlineKeyboardButton("📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton("📖 Описание", callback_data="info")],
        [InlineKeyboardButton("📋 Инструкция", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Тексты
EA_INFO = """
🤖 **ТОРГОВЫЙ СОВЕТНИК - СТРАТЕГИЯ БОГДАНОВА**

📊 **Работает с:** BTCUSD, XAUUSD (Gold)
⚡ **VPS оптимизирован**
🛡️ **Защита от просадок**
🔄 **Автоматическая торговля**

💰 **Рекомендуемый депозит:** от $1000
"""

INSTRUCTION = """
📖 **ИНСТРУКЦИЯ ПО УСТАНОВКЕ**

1️⃣ Скачайте файл EA после получения лицензии
2️⃣ Поместите в папку MetaTrader 5/MQL5/Experts/
3️⃣ Перезапустите MetaTrader 5
4️⃣ Перетащите EA на график
5️⃣ Введите лицензионный ключ

📞 **Поддержка:** @rasul_asqarov_rfx
👥 **Группа:** t.me/RFx_Group
"""

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username or "Unknown")
    
    text = """
🤖 **Добро пожаловать в EA License Bot!**

🎯 **Автоматическая торговля по стратегии Богданова**
📊 BTCUSD и XAUUSD
⚡ VPS оптимизация

💡 **Доступные опции:**
🆓 Пробная лицензия - 3 дня бесплатно
💰 Полная лицензия - $100 (навсегда)

👥 Группа: t.me/RFx_Group
📞 Поддержка: @rasul_asqarov_rfx
"""
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    stats = get_stats()
    text = f"""📊 **Статистика бота**

👥 Всего пользователей: {stats['total']}
✅ Активных лицензий: {stats['active']}
🆓 Пробных: {stats['trial']}
💰 Полных: {stats['full']}

💵 Доход: ${stats['full'] * LICENSE_PRICE}"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    await update.message.reply_text("📁 Отправьте .ex5 файл для загрузки")

# Обработчик callback'ов
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "trial":
        key, error = create_trial_license(user_id)
        if error:
            await query.message.reply_text(f"❌ {error}", reply_markup=main_keyboard())
        else:
            text = f"""🎉 **Пробная лицензия активирована!**

🔑 **Ваш ключ:** `{key}`
⏰ **Срок:** 3 дня

📁 Теперь можете скачать EA"""
            
            keyboard = [
                [InlineKeyboardButton("📁 Скачать EA", callback_data="download")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]
            await query.message.reply_text(text, parse_mode='Markdown', 
                                         reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "buy":
        payment_id = create_payment_request(user_id, query.from_user.username or "Unknown")
        context.user_data['payment_id'] = payment_id
        
        text = f"""💳 **ОПЛАТА ЛИЦЕНЗИИ**

💵 **Сумма:** ${LICENSE_PRICE}

💳 **РЕКВИЗИТЫ:**
🏦 **VISA:** `{VISA_CARD}`
🏦 **HUMO:** `{HUMO_CARD}`
👤 **Владелец:** {CARD_OWNER}

📝 **Инструкция:**
1. Переведите ${LICENSE_PRICE} на любую карту
2. Сделайте скриншот чека
3. Нажмите "Я оплатил"
4. Отправьте фото чека

📞 Поддержка: @rasul_asqarov_rfx"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Я оплатил", callback_data="paid")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.message.reply_text(text, parse_mode='Markdown',
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "paid":
        await query.message.reply_text("""📸 **Отправьте чек об оплате**

📋 Пришлите фото чека на сумму ${} 

✅ Чек должен содержать:
• Сумму платежа
• Дату и время
• Номер карты получателя
• Имя получателя

⏱️ Обработка: 10-30 минут""".format(LICENSE_PRICE))
        
        context.user_data['waiting_receipt'] = True
    
    elif data == "status":
        license_data = get_user_license(user_id)
        
        if not license_data or not license_data[0]:
            text = """❌ **Лицензия не найдена**

У вас пока нет активной лицензии.
Получите пробную или купите полную."""
            await query.message.reply_text(text, reply_markup=main_keyboard())
        else:
            key, license_type, status, expires = license_data
            
            # Проверяем истечение
            if expires and datetime.now() > datetime.fromisoformat(expires):
                status = "expired"
            
            status_emoji = "✅" if status == "active" else "❌"
            type_emoji = "🆓" if license_type == "trial" else "💰"
            
            text = f"""{status_emoji} **Статус лицензии**

🔑 **Ключ:** `{key}`
{type_emoji} **Тип:** {license_type.title()}
📊 **Статус:** {status.title()}"""
            
            if expires and license_type == "trial":
                text += f"\n⏰ **Истекает:** {expires[:10]}"
            elif license_type == "full":
                text += f"\n♾️ **Срок:** Безлимитный"
            
            keyboard = []
            if status == "active":
                keyboard.append([InlineKeyboardButton("📁 Скачать EA", callback_data="download")])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
            
            await query.message.reply_text(text, parse_mode='Markdown',
                                         reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "info":
        keyboard = [
            [InlineKeyboardButton("📋 Инструкция", callback_data="help")],
            [InlineKeyboardButton("🆓 Пробная лицензия", callback_data="trial")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.message.reply_text(EA_INFO, parse_mode='Markdown',
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "help":
        keyboard = [
            [InlineKeyboardButton("📖 Описание", callback_data="info")],
            [InlineKeyboardButton("🆓 Пробная лицензия", callback_data="trial")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.message.reply_text(INSTRUCTION, parse_mode='Markdown',
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "download":
        license_data = get_user_license(user_id)
        
        if not license_data or license_data[2] != 'active':
            await query.message.reply_text("❌ Нет активной лицензии!", reply_markup=main_keyboard())
            return
        
        key = license_data[0]
        
        await query.message.reply_text(f"""📁 **Скачивание EA**

🔑 **Ваш ключ:** `{key}`

📋 Инструкция:
1. Скачайте файл ниже
2. Установите в MT5/MQL5/Experts/
3. Введите ключ при запуске

⏳ Отправляю файл...""", parse_mode='Markdown')
        
        ea_data = get_ea_file()
        if ea_data:
            await query.message.reply_document(
                document=ea_data,
                filename="Bogdanov_Strategy_EA.ex5",
                caption=f"🔑 **Лицензионный ключ:** `{key}`\n\n💡 Сохраните ключ!",
                parse_mode='Markdown',
                reply_markup=main_keyboard()
            )
        else:
            await query.message.reply_text("❌ Файл EA недоступен. Обратитесь к администратору.",
                                         reply_markup=main_keyboard())
    
    elif data == "back":
        await start_command(update, context)
    
    elif data.startswith("approve_"):
        if not is_admin(user_id):
            await query.answer("❌ Доступ запрещен!")
            return
        
        payment_id = int(data.split("_")[1])
        result = approve_payment(payment_id)
        
        if result:
            license_key, user_id = result
            
            # Уведомляем пользователя
            try:
                keyboard = [[InlineKeyboardButton("📁 Скачать EA", callback_data="download")]]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"""🎉 **ПЛАТЕЖ ПОДТВЕРЖДЕН!**

✅ Полная лицензия активирована!

🔑 **Ключ:** `{license_key}`
♾️ **Срок:** Безлимитный

📁 Можете скачать EA""",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                pass
            
            await query.message.edit_text(f"✅ **Платеж одобрен**\n🔑 Ключ: `{license_key}`", 
                                        parse_mode='Markdown')
    
    elif data.startswith("reject_"):
        if not is_admin(user_id):
            await query.answer("❌ Доступ запрещен!")
            return
        
        payment_id = int(data.split("_")[1])
        user_id = reject_payment(payment_id)
        
        if user_id:
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="""❌ **ПЛАТЕЖ ОТКЛОНЕН**

К сожалению, ваш платеж не прошел проверку.

**Возможные причины:**
• Неверная сумма
• Неразборчивый чек
• Платеж не поступил

📞 Обратитесь: @rasul_asqarov_rfx""",
                    parse_mode='Markdown',
                    reply_markup=main_keyboard()
                )
            except:
                pass
            
            await query.message.edit_text("❌ **Платеж отклонен**")

# Обработчик фото
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_receipt'):
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    payment_id = context.user_data.get('payment_id')
    
    if not payment_id:
        await update.message.reply_text("❌ Ошибка: заявка не найдена!")
        return
    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    # Сохраняем чек
    save_receipt(payment_id, file_id)
    
    # Отправляем админу
    try:
        keyboard = [
            [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{payment_id}"),
             InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payment_id}")]
        ]
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=f"""💳 **НОВАЯ ЗАЯВКА**

👤 @{username} (ID: {user_id})
💵 Сумма: ${LICENSE_PRICE}
🆔 Заявка: {payment_id}

💳 Проверьте реквизиты:
VISA: {VISA_CARD}
HUMO: {HUMO_CARD}
Владелец: {CARD_OWNER}""",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await update.message.reply_text("""✅ **Чек получен!**

📸 Ваш чек отправлен на проверку
⏱️ Обработка: 10-30 минут
🔔 Вы получите уведомление

📞 Вопросы: @rasul_asqarov_rfx""", reply_markup=main_keyboard())
        
        context.user_data.pop('waiting_receipt', None)
        context.user_data.pop('payment_id', None)
        
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")
        await update.message.reply_text("❌ Ошибка обработки. Обратитесь к администратору.")

# Обработчик документов
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    if not update.message.document.file_name.endswith('.ex5'):
        await update.message.reply_text("❌ Нужен файл .ex5!")
        return
    
    try:
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()
        
        save_ea_file(file_data, update.message.document.file_name)
        
        await update.message.reply_text(f"""✅ **Файл EA загружен!**

📁 {update.message.document.file_name}
📊 {len(file_data)} байт

Пользователи могут скачивать файл.""")
        
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        await update.message.reply_text("❌ Ошибка загрузки файла!")

# Главная функция
def main():
    if not TOKEN:
        print("❌ Не найден BOT_TOKEN!")
        return
    
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("upload", upload_command))
    
    # Callback'и
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Сообщения
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    
    print("✅ Бот запущен!")
    print("📋 Админские команды:")
    print("• /stats - статистика")
    print("• /upload - загрузка EA")
    print("🚫 Платежи ТОЛЬКО через бота!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
