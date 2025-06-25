#!/usr/bin/env python3
import os
import sqlite3
import secrets
import string
import logging
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("❌ Ошибка: установите python-telegram-bot")
    print("pip install python-telegram-bot")
    exit(1)

# ===============================
# КОНФИГУРАЦИЯ
# ===============================

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 295698267
LICENSE_PRICE = 100

# Банковские реквизиты
VISA_CARD = "4278 3100 2430 7167"
HUMO_CARD = "9860 1001 2541 9018"
CARD_OWNER = "Asqarov Rasulbek"

print("🚀 Запуск бота...")
print(f"👨‍💼 Admin ID: {ADMIN_ID}")
print(f"💳 VISA: {VISA_CARD}")
print(f"💳 HUMO: {HUMO_CARD}")

# ===============================
# БАЗА ДАННЫХ
# ===============================

def init_db():
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        # Таблица пользователей
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            license_key TEXT,
            license_type TEXT DEFAULT 'none',
            license_status TEXT DEFAULT 'inactive',
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Таблица платежей
        c.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            amount INTEGER DEFAULT 100,
            status TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Таблица EA файлов
        c.execute('''CREATE TABLE IF NOT EXISTS ea_files (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            file_data BLOB
        )''')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")

# ===============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================

def generate_key():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

def is_admin(user_id):
    return int(user_id) == ADMIN_ID

# ===============================
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ===============================

def register_user(user_id, username):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")

def get_user_license(user_id):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('SELECT license_key, license_type, license_status, expires_at FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка получения лицензии: {e}")
        return None

def create_trial_license(user_id):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        # Проверяем была ли пробная лицензия
        c.execute('SELECT license_type FROM users WHERE user_id = ? AND license_type = "trial"', (user_id,))
        if c.fetchone():
            conn.close()
            return None, "У вас уже была пробная лицензия"
        
        # Создаем пробную лицензию на 1 МЕСЯЦ
        key = generate_key()
        expires = (datetime.now() + timedelta(days=30)).isoformat()  # 30 дней вместо 3
        
        c.execute('''UPDATE users SET 
            license_key = ?, license_type = 'trial', license_status = 'active', expires_at = ?
            WHERE user_id = ?''', (key, expires, user_id))
        
        conn.commit()
        conn.close()
        return key, None
        
    except Exception as e:
        logger.error(f"Ошибка создания лицензии: {e}")
        return None, "Ошибка создания лицензии"

def create_full_license(user_id):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        key = generate_key()
        c.execute('''UPDATE users SET 
            license_key = ?, license_type = 'full', license_status = 'active', expires_at = NULL
            WHERE user_id = ?''', (key, user_id))
        
        conn.commit()
        conn.close()
        return key
        
    except Exception as e:
        logger.error(f"Ошибка создания полной лицензии: {e}")
        return None

def create_payment_request(user_id, username):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('INSERT INTO payments (user_id, username) VALUES (?, ?)', (user_id, username))
        payment_id = c.lastrowid
        conn.commit()
        conn.close()
        return payment_id
    except Exception as e:
        logger.error(f"Ошибка создания заявки: {e}")
        return None

def save_receipt(payment_id, file_id):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('UPDATE payments SET receipt_file_id = ? WHERE id = ?', (file_id, payment_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения чека: {e}")
        return False

def approve_payment(payment_id):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM payments WHERE id = ?', (payment_id,))
        result = c.fetchone()
        if not result:
            conn.close()
            return None
        
        user_id = result[0]
        license_key = create_full_license(user_id)
        
        if license_key:
            c.execute('UPDATE payments SET status = "approved" WHERE id = ?', (payment_id,))
            conn.commit()
        
        conn.close()
        return license_key, user_id
        
    except Exception as e:
        logger.error(f"Ошибка одобрения: {e}")
        return None

def save_ea_file(file_data, filename):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('DELETE FROM ea_files')
        c.execute('INSERT INTO ea_files (filename, file_data) VALUES (?, ?)', (filename, file_data))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения EA: {e}")
        return False

def get_ea_file():
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        c.execute('SELECT file_data FROM ea_files LIMIT 1')
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка получения EA: {e}")
        return None

def get_stats():
    try:
        conn = sqlite3.connect('bot_simple.db')
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
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return {'total': 0, 'active': 0, 'trial': 0, 'full': 0}

# ===============================
# КЛАВИАТУРЫ
# ===============================

def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🆓 1 месяц БЕСПЛАТНО", callback_data="trial")],
        [InlineKeyboardButton("💰 Купить лицензию $100", callback_data="buy")],
        [InlineKeyboardButton("📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton("📖 Описание EA", callback_data="info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===============================
# ТЕКСТЫ
# ===============================

EA_INFO = """🤖 **ТОРГОВЫЙ СОВЕТНИК**
**Стратегия Богданова**

📊 **Символы:** BTCUSD, XAUUSD
⚡ **VPS оптимизирован**
🛡️ **Защита от просадок**
🔄 **Автоматическая торговля**

💰 **Рекомендуемый депозит:** от $1000

📞 **Поддержка:** @rasul_asqarov_rfx
👥 **Группа:** t.me/RFx_Group"""

# ===============================
# ОБРАБОТЧИКИ КОМАНД
# ===============================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        register_user(user.id, user.username or "Unknown")
        
        text = """🤖 **Добро пожаловать!**

🎯 **Автоматическая торговля**
📊 **Стратегия Богданова**
⚡ **VPS оптимизация**

💡 **Опции:**
🆓 Пробная лицензия - 1 МЕСЯЦ бесплатно
💰 Полная лицензия - $100 (навсегда)

📞 @rasul_asqarov_rfx
👥 t.me/RFx_Group"""
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
        
        stats = get_stats()
        text = f"""📊 **Статистика**

👥 Пользователей: {stats['total']}
✅ Активных: {stats['active']}
🆓 Пробных: {stats['trial']}
💰 Полных: {stats['full']}

💵 Доход: ${stats['full'] * LICENSE_PRICE}"""
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в stats: {e}")

# ===============================
# ОБРАБОТЧИК КНОПОК
# ===============================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
⏰ **Срок:** 1 МЕСЯЦ (30 дней)

📁 Теперь можете скачать EA"""
                
                keyboard = [[InlineKeyboardButton("📁 Скачать EA", callback_data="download")]]
                await query.message.reply_text(text, parse_mode='Markdown', 
                                             reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == "buy":
            payment_id = create_payment_request(user_id, query.from_user.username or "Unknown")
            if payment_id:
                context.user_data['payment_id'] = payment_id
                
                text = f"""💳 **ОПЛАТА ЛИЦЕНЗИИ**

💵 **Сумма:** ${LICENSE_PRICE}

💳 **РЕКВИЗИТЫ:**
🏦 **VISA:** `{VISA_CARD}`
🏦 **HUMO:** `{HUMO_CARD}`
👤 **Владелец:** {CARD_OWNER}

📝 **Инструкция:**
1. Переведите ${LICENSE_PRICE} на карту
2. Сделайте скриншот чека
3. Нажмите "Я оплатил"
4. Отправьте фото чека

📞 @rasul_asqarov_rfx"""
                
                keyboard = [[InlineKeyboardButton("✅ Я оплатил", callback_data="paid")]]
                await query.message.reply_text(text, parse_mode='Markdown',
                                             reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == "paid":
            await query.message.reply_text(f"""📸 **Отправьте чек**

Пришлите фото чека на сумму ${LICENSE_PRICE}

✅ Чек должен содержать:
• Сумму платежа
• Дату и время  
• Номер карты получателя

⏱️ Обработка: 10-30 минут""")
            
            context.user_data['waiting_receipt'] = True
        
        elif data == "status":
            license_data = get_user_license(user_id)
            
            if not license_data or not license_data[0]:
                text = """❌ **Лицензия не найдена**

Получите пробную или купите полную."""
                await query.message.reply_text(text, reply_markup=main_keyboard())
            else:
                key, license_type, status, expires = license_data
                
                # Проверяем истечение
                if expires:
                    try:
                        if datetime.now() > datetime.fromisoformat(expires):
                            status = "expired"
                    except:
                        pass
                
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
                
                await query.message.reply_text(text, parse_mode='Markdown',
                                             reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == "info":
            await query.message.reply_text(EA_INFO, parse_mode='Markdown', reply_markup=main_keyboard())
        
        elif data == "download":
            license_data = get_user_license(user_id)
            
            if not license_data or license_data[2] != 'active':
                await query.message.reply_text("❌ Нет активной лицензии!", reply_markup=main_keyboard())
                return
            
            key = license_data[0]
            
            await query.message.reply_text(f"""📁 **Скачивание EA**

🔑 **Ваш ключ:** `{key}`

⏳ Отправляю файл...""", parse_mode='Markdown')
            
            ea_data = get_ea_file()
            if ea_data:
                await query.message.reply_document(
                    document=ea_data,
                    filename="Bogdanov_Strategy_EA.ex5",
                    caption=f"🔑 Ключ: `{key}`",
                    parse_mode='Markdown'
                )
            else:
                await query.message.reply_text("❌ Файл недоступен. Обратитесь к @rasul_asqarov_rfx")
        
        elif data.startswith("approve_"):
            if not is_admin(user_id):
                return
            
            payment_id = int(data.split("_")[1])
            result = approve_payment(payment_id)
            
            if result:
                license_key, target_user_id = result
                
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"""🎉 **ПЛАТЕЖ ПОДТВЕРЖДЕН!**

✅ Полная лицензия активирована!
🔑 **Ключ:** `{license_key}`
♾️ **Срок:** Безлимитный""",
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.message.edit_text(f"✅ Платеж одобрен\n🔑 Ключ: `{license_key}`", 
                                            parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")

# ===============================
# ОБРАБОТЧИК ФОТО
# ===============================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
        if save_receipt(payment_id, file_id):
            # Отправляем админу
            try:
                keyboard = [[
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{payment_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payment_id}")
                ]]
                
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=file_id,
                    caption=f"""💳 **НОВАЯ ЗАЯВКА**

👤 @{username} (ID: {user_id})
💵 Сумма: ${LICENSE_PRICE}
🆔 Заявка: {payment_id}

💳 Реквизиты:
VISA: {VISA_CARD}
HUMO: {HUMO_CARD}""",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                await update.message.reply_text("""✅ **Чек получен!**

📸 Отправлен на проверку
⏱️ Обработка: 10-30 минут
🔔 Получите уведомление

📞 @rasul_asqarov_rfx""", reply_markup=main_keyboard())
                
                context.user_data.pop('waiting_receipt', None)
                context.user_data.pop('payment_id', None)
                
            except Exception as e:
                logger.error(f"Ошибка отправки админу: {e}")
                await update.message.reply_text("❌ Ошибка обработки. Обратитесь к @rasul_asqarov_rfx")
        else:
            await update.message.reply_text("❌ Ошибка сохранения чека")
            
    except Exception as e:
        logger.error(f"Ошибка в photo_handler: {e}")

# ===============================
# ОБРАБОТЧИК ДОКУМЕНТОВ
# ===============================

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
        
        if not update.message.document.file_name.endswith('.ex5'):
            await update.message.reply_text("❌ Нужен файл .ex5!")
            return
        
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()
        
        if save_ea_file(file_data, update.message.document.file_name):
            await update.message.reply_text(f"""✅ **Файл загружен!**

📁 {update.message.document.file_name}
📊 {len(file_data)} байт""")
        else:
            await update.message.reply_text("❌ Ошибка загрузки!")
            
    except Exception as e:
        logger.error(f"Ошибка в document_handler: {e}")
        await update.message.reply_text("❌ Ошибка загрузки файла!")

# ===============================
# ОБРАБОТЧИК ОШИБОК
# ===============================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

# ===============================
# ГЛАВНАЯ ФУНКЦИЯ
# ===============================

def main():
    if not TOKEN:
        print("❌ Не найден BOT_TOKEN!")
        print("Установите: export BOT_TOKEN='ваш_токен'")
        return
    
    # Инициализация
    init_db()
    
    # Создание приложения
    app = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    print("✅ Бот запущен!")
    print("🆓 Пробная лицензия: 1 МЕСЯЦ")
    print("💰 Полная лицензия: $100")
    print("📋 Админские команды: /stats")
    print("🚫 Платежи ТОЛЬКО через бота!")
    
    # Запуск
    app.run_polling(drop_pending_updates=True, pool_timeout=20)

if __name__ == '__main__':
    main()
