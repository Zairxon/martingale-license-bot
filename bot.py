#!/usr/bin/env python3
import os
import sqlite3
import secrets
import string
import logging
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
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
MONTHLY_PRICE = 100  # 100$ за месяц
TRIAL_DAYS = 3       # 3 дня пробный период

# Банковские реквизиты
VISA_CARD = "4278 3100 2430 7167"
HUMO_CARD = "9860 1001 2541 9018"
CARD_OWNER = "Asqarov Rasulbek"

print("🚀 Запуск бота...")
print(f"👨‍💼 Admin ID: {ADMIN_ID}")
print(f"💰 Цена за месяц: {MONTHLY_PRICE} USD")
print(f"🆓 Пробный период: {TRIAL_DAYS} дня")
print(f"💳 VISA: {VISA_CARD}")
print(f"💳 HUMO: {HUMO_CARD}")

# ===============================
# БАЗА ДАННЫХ
# ===============================
def init_db():
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        # Таблица пользователей (обновленная схема)
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            license_key TEXT,
            license_type TEXT DEFAULT 'none',
            license_status TEXT DEFAULT 'inactive',
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            trial_used INTEGER DEFAULT 0
        )''')
        
        # Добавляем колонку trial_used если её нет
        try:
            c.execute('ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Таблица платежей
        c.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            amount INTEGER DEFAULT 100,
            license_months INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Добавляем колонку license_months если её нет
        try:
            c.execute('ALTER TABLE payments ADD COLUMN license_months INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass
        
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
        logger.error(f"Ошибка БД: {e}")

# ===============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================
def generate_key():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def check_license_expired(expires_at):
    """Проверяет истекла ли лицензия"""
    if not expires_at:
        return False
    try:
        return datetime.now() > datetime.fromisoformat(expires_at)
    except:
        return True

def format_datetime(dt_string):
    """Форматирует дату для отображения"""
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return "Неизвестно"

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
        c.execute('SELECT license_key, license_type, license_status, expires_at, trial_used FROM users WHERE user_id = ?', (user_id,))
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
        
        # Проверяем использовался ли пробный период
        c.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        if result and result[0] == 1:
            conn.close()
            return None, "Вы уже использовали пробный период"
        
        # Создаем пробную лицензию на 3 дня
        key = generate_key()
        expires = (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()
        
        c.execute('''UPDATE users SET 
            license_key = ?, license_type = 'trial', license_status = 'active', 
            expires_at = ?, trial_used = 1
            WHERE user_id = ?''', (key, expires, user_id))
        
        conn.commit()
        conn.close()
        return key, None
        
    except Exception as e:
        logger.error(f"Ошибка создания пробной лицензии: {e}")
        return None, "Ошибка создания лицензии"

def create_monthly_license(user_id, months=1):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        key = generate_key()
        expires = (datetime.now() + timedelta(days=30 * months)).isoformat()
        
        c.execute('''UPDATE users SET 
            license_key = ?, license_type = 'monthly', license_status = 'active', expires_at = ?
            WHERE user_id = ?''', (key, expires, user_id))
        
        conn.commit()
        conn.close()
        return key
        
    except Exception as e:
        logger.error(f"Ошибка создания месячной лицензии: {e}")
        return None

def extend_license(user_id, months=1):
    """Продлевает существующую лицензию"""
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        
        # Получаем текущую лицензию
        c.execute('SELECT expires_at FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        if result and result[0]:
            # Продлеваем от текущей даты истечения
            current_expires = datetime.fromisoformat(result[0])
            if current_expires > datetime.now():
                new_expires = current_expires + timedelta(days=30 * months)
            else:
                new_expires = datetime.now() + timedelta(days=30 * months)
        else:
            # Создаем новую лицензию
            new_expires = datetime.now() + timedelta(days=30 * months)
        
        key = generate_key()
        c.execute('''UPDATE users SET 
            license_key = ?, license_type = 'monthly', license_status = 'active', expires_at = ?
            WHERE user_id = ?''', (key, new_expires.isoformat(), user_id))
        
        conn.commit()
        conn.close()
        return key, new_expires
        
    except Exception as e:
        logger.error(f"Ошибка продления лицензии: {e}")
        return None, None

def create_payment_request(user_id, username, months=1):
    try:
        conn = sqlite3.connect('bot_simple.db')
        c = conn.cursor()
        amount = MONTHLY_PRICE * months
        c.execute('INSERT INTO payments (user_id, username, amount, license_months) VALUES (?, ?, ?, ?)', 
                 (user_id, username, amount, months))
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
        
        c.execute('SELECT user_id, license_months FROM payments WHERE id = ?', (payment_id,))
        result = c.fetchone()
        if not result:
            conn.close()
            return None
        
        user_id, months = result
        license_key, new_expires = extend_license(user_id, months)
        
        if license_key:
            c.execute('UPDATE payments SET status = "approved" WHERE id = ?', (payment_id,))
            conn.commit()
        
        conn.close()
        return license_key, user_id, new_expires
        
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
        
        # Активные лицензии (не истекшие)
        c.execute('''SELECT COUNT(*) FROM users 
                    WHERE license_status = "active" 
                    AND (expires_at IS NULL OR expires_at > datetime('now'))''')
        active = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM users WHERE license_type = "trial"')
        trial = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM users WHERE license_type = "monthly"')
        monthly = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM payments WHERE status = "approved"')
        approved_payments = c.fetchone()[0]
        
        conn.close()
        return {
            'total': total_users, 
            'active': active, 
            'trial': trial, 
            'monthly': monthly,
            'revenue': approved_payments * MONTHLY_PRICE
        }
        
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return {'total': 0, 'active': 0, 'trial': 0, 'monthly': 0, 'revenue': 0}

# ===============================
# КЛАВИАТУРЫ
# ===============================
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🆓 3 дня БЕСПЛАТНО", callback_data="trial")],
        [InlineKeyboardButton("💰 1 месяц - 100 USD", callback_data="buy_1")],
        [InlineKeyboardButton("💎 3 месяца - 270 USD", callback_data="buy_3")],
        [InlineKeyboardButton("🔥 6 месяцев - 500 USD", callback_data="buy_6")],
        [InlineKeyboardButton("📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton("📖 Описание EA", callback_data="info")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_buy_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 1 месяц - 100 USD", callback_data="buy_1")],
        [InlineKeyboardButton("💎 3 месяца - 270 USD (-10%)", callback_data="buy_3")],
        [InlineKeyboardButton("🔥 6 месяцев - 500 USD (-17%)", callback_data="buy_6")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ===============================
# ТЕКСТЫ
# ===============================
EA_INFO = """🤖 ТОРГОВЫЙ СОВЕТНИК
Стратегия Богданова

📊 Символы: BTCUSD, XAUUSD
⚡ VPS оптимизирован
🛡️ Защита от просадок
🔄 Автоматическая торговля
💰 Рекомендуемый депозит: от 1000 USD

🆓 Пробный период: 3 дня
💰 Месячная подписка: 100 USD
💎 Скидки при покупке на несколько месяцев

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""

WELCOME_TEXT = """🤖 Добро пожаловать в RFX Trading!

🎯 Автоматическая торговля
📊 Стратегия Богданова
⚡ VPS оптимизация

💡 Варианты подписки:
🆓 Пробный период - 3 дня бесплатно
💰 Месячная подписка - 100 USD
💎 Скидки при покупке на несколько месяцев

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""

# ===============================
# ОБРАБОТЧИКИ КОМАНД
# ===============================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        register_user(user.id, user.username or "Unknown")
        
        await update.message.reply_text(WELCOME_TEXT, reply_markup=main_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
        
        stats = get_stats()
        text = f"""📊 Статистика бота

👥 Всего пользователей: {stats['total']}
✅ Активных лицензий: {stats['active']}
🆓 Пробных: {stats['trial']}
💰 Месячных: {stats['monthly']}
💵 Доход: {stats['revenue']} USD

⚡ Цена за месяц: {MONTHLY_PRICE} USD
🆓 Пробный период: {TRIAL_DAYS} дня"""
        
        await update.message.reply_text(text)
        
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
                text = f"""🎉 Пробная лицензия активирована!

🔑 Ваш ключ: `{key}`
⏰ Срок: {TRIAL_DAYS} дня
📁 Теперь можете скачать EA

После окончания пробного периода вы можете купить месячную подписку."""
                
                keyboard = [[InlineKeyboardButton("📁 Скачать EA", callback_data="download")]]
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("buy_"):
            months = int(data.split("_")[1])
            prices = {1: 100, 3: 270, 6: 500}  # Скидки для длительных подписок
            amount = prices.get(months, MONTHLY_PRICE * months)
            
            payment_id = create_payment_request(user_id, query.from_user.username or "Unknown", months)
            if payment_id:
                context.user_data['payment_id'] = payment_id
                
                months_text = "месяц" if months == 1 else f"{months} месяца" if months < 5 else f"{months} месяцев"
                savings = ""
                if months > 1:
                    regular_price = MONTHLY_PRICE * months
                    savings = f"\n💰 Экономия: {regular_price - amount} USD"
                
                text = f"""💳 ОПЛАТА ЛИЦЕНЗИИ

📦 Пакет: {months_text}
💵 Сумма: {amount} USD{savings}

💳 РЕКВИЗИТЫ:
🏦 VISA: `{VISA_CARD}`
🏦 HUMO: `{HUMO_CARD}`
👤 Владелец: {CARD_OWNER}

📝 Инструкция:
1. Переведите {amount} USD на любую карту
2. Сделайте скриншот чека
3. Нажмите "Я оплатил"
4. Отправьте фото чека

📞 Поддержка: @rasul_asqarov_rfx"""
                
                keyboard = [
                    [InlineKeyboardButton("✅ Я оплатил", callback_data="paid")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
                ]
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "paid":
            payment_id = context.user_data.get('payment_id')
            if not payment_id:
                await query.message.reply_text("❌ Ошибка: заявка не найдена!", reply_markup=main_keyboard())
                return
                
            await query.message.reply_text(f"""📸 Отправьте чек об оплате

Пришлите фото чека как обычное сообщение.

✅ Чек должен содержать:
• Сумму платежа в USD
• Дату и время перевода
• Номер карты получателя

⏱️ Время обработки: 10-30 минут
🔔 Вы получите уведомление о результате""")
            
            context.user_data['waiting_receipt'] = True
        
        elif data == "status":
            license_data = get_user_license(user_id)
            
            if not license_data or not license_data[0]:
                text = """❌ Лицензия не найдена

Вы можете:
🆓 Получить пробную лицензию на 3 дня
💰 Купить месячную подписку"""
                await query.message.reply_text(text, reply_markup=main_keyboard())
            else:
                key, license_type, status, expires, trial_used = license_data
                
                # Проверяем истечение
                if expires and check_license_expired(expires):
                    status = "expired"
                
                status_emoji = "✅" if status == "active" else "❌"
                type_emoji = "🆓" if license_type == "trial" else "💰"
                
                text = f"""{status_emoji} Статус лицензии

🔑 Ключ: `{key}`
{type_emoji} Тип: {license_type.title()}
📊 Статус: {status.title()}"""
                
                if expires:
                    if status == "active":
                        text += f"\n⏰ Действует до: {format_datetime(expires)}"
                    else:
                        text += f"\n❌ Истекла: {format_datetime(expires)}"
                
                keyboard = []
                if status == "active":
                    keyboard.append([InlineKeyboardButton("📁 Скачать EA", callback_data="download")])
                if license_type == "trial" or status == "expired":
                    keyboard.append([InlineKeyboardButton("💰 Купить подписку", callback_data="buy_options")])
                
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "buy_options":
            text = """💰 Выберите пакет подписки:

💰 1 месяц - 100 USD
💎 3 месяца - 270 USD (скидка 10%)
🔥 6 месяцев - 500 USD (скидка 17%)

Чем больше пакет - тем больше экономия!"""
            await query.message.reply_text(text, reply_markup=get_buy_keyboard())
        
        elif data == "info":
            await query.message.reply_text(EA_INFO, reply_markup=main_keyboard())
        
        elif data == "back":
            await query.message.reply_text(WELCOME_TEXT, reply_markup=main_keyboard())
        
        elif data == "download":
            license_data = get_user_license(user_id)
            
            if not license_data or license_data[2] != 'active':
                await query.message.reply_text("❌ Нет активной лицензии!", reply_markup=main_keyboard())
                return
            
            # Проверяем не истекла ли лицензия
            if license_data[3] and check_license_expired(license_data[3]):
                await query.message.reply_text("❌ Лицензия истекла! Продлите подписку.", reply_markup=main_keyboard())
                return
            
            key = license_data[0]
            
            await query.message.reply_text(f"""📁 Подготовка файла EA...

🔑 Ваш ключ: `{key}`
⏳ Отправляю файл...""", parse_mode='Markdown')
            
            ea_data = get_ea_file()
            if ea_data:
                await query.message.reply_document(
                    document=ea_data,
                    filename="Bogdanov_Strategy_EA.ex5",
                    caption=f"""🤖 Торговый советник загружен!

🔑 Лицензионный ключ: `{key}`
📊 Стратегия: Богданова
⚡ Оптимизирован для VPS

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group""",
                    parse_mode='Markdown'
                )
            else:
                await query.message.reply_text("❌ Файл временно недоступен. Обратитесь к @rasul_asqarov_rfx")
        
        elif data.startswith("approve_"):
            if not is_admin(user_id):
                return
            
            payment_id = int(data.split("_")[1])
            result = approve_payment(payment_id)
            
            if result:
                license_key, target_user_id, expires = result
                
                # Уведомляем пользователя
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"""🎉 ПЛАТЕЖ ПОДТВЕРЖДЕН!

✅ Месячная лицензия активирована!
🔑 Ключ: `{license_key}`
⏰ Действует до: {format_datetime(expires.isoformat())}

📁 Теперь можете скачать EA!""",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю: {e}")
                
                await query.message.edit_text(f"""✅ Платеж одобрен!

🔑 Ключ: `{license_key}`
👤 Пользователь уведомлен
⏰ Лицензия до: {format_datetime(expires.isoformat())}""", parse_mode='Markdown')
        
        elif data.startswith("reject_"):
            if not is_admin(user_id):
                return
            
            payment_id = int(data.split("_")[1])
            # Здесь можно добавить логику отклонения платежа
            await query.message.edit_text("❌ Платеж отклонен")
        
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")
        await query.message.reply_text("❌ Произошла ошибка. Попробуйте позже.", reply_markup=main_keyboard())

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
            # Получаем данные о платеже
            try:
                conn = sqlite3.connect('bot_simple.db')
                c = conn.cursor()
                c.execute('SELECT amount, license_months FROM payments WHERE id = ?', (payment_id,))
                payment_data = c.fetchone()
                conn.close()
                
                amount, months = payment_data if payment_data else (MONTHLY_PRICE, 1)
                months_text = "месяц" if months == 1 else f"{months} месяца" if months < 5 else f"{months} месяцев"
            except:
                amount, months, months_text = MONTHLY_PRICE, 1, "месяц"
            
            # Отправляем админу
            try:
                keyboard = [[
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{payment_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payment_id}")
                ]]
                
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=file_id,
                    caption=f"""💳 НОВАЯ ЗАЯВКА НА ОПЛАТУ

👤 Пользователь: @{username} (ID: {user_id})
📦 Пакет: {months_text}
💵 Сумма: {amount} USD
🆔 Заявка №{payment_id}

💳 Реквизиты для проверки:
VISA: {VISA_CARD}
HUMO: {HUMO_CARD}
Владелец: {CARD_OWNER}""",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                await update.message.reply_text("""✅ Чек получен и отправлен на проверку!

⏱️ Время обработки: 10-30 минут
🔔 Вы получите уведомление о результате
📞 Вопросы: @rasul_asqarov_rfx""", reply_markup=main_keyboard())
                
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
            await update.message.reply_text("❌ Можно загружать только файлы .ex5!")
            return
        
        file = await update.message.document.get_file()
        file_data = await file.download_as_bytearray()
        
        if save_ea_file(file_data, update.message.document.file_name):
            await update.message.reply_text(f"""✅ EA файл успешно загружен!

📁 Имя файла: {update.message.document.file_name}
📊 Размер: {len(file_data):,} байт
🔄 Файл заменен и готов к раздаче""")
        else:
            await update.message.reply_text("❌ Ошибка при загрузке файла!")
            
    except Exception as e:
        logger.error(f"Ошибка в document_handler: {e}")
        await update.message.reply_text("❌ Произошла ошибка при загрузке!")

# ===============================
# ОБРАБОТЧИК ОШИБОК
# ===============================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка в боте: {context.error}")

# ===============================
# ГЛАВНАЯ ФУНКЦИЯ
# ===============================
def main():
    if not TOKEN:
        print("❌ Не найден BOT_TOKEN!")
        print("Установите переменную окружения:")
        print("export BOT_TOKEN='ваш_токен_бота'")
        return
    
    print("🔄 Инициализация...")
    
    # Инициализация базы данных
    init_db()
    
    # Создание приложения с обновленными настройками
    app = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    print("✅ Бот успешно запущен!")
    print("=" * 50)
    print("🔧 КОНФИГУРАЦИЯ:")
    print(f"🆓 Пробный период: {TRIAL_DAYS} дня")
    print(f"💰 Цена за месяц: {MONTHLY_PRICE} USD")
    print(f"💎 Скидки: 3 мес. = 270$, 6 мес. = 500$")
    print(f"👨‍💼 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    print("📋 ДОСТУПНЫЕ КОМАНДЫ:")
    print("/start - Главное меню")
    print("/stats - Статистика (только админ)")
    print("=" * 50)
    print("⚡ Бот готов к работе!")
    
    # Запуск с оптимизированными настройками
    try:
        app.run_polling(
            drop_pending_updates=True,
            pool_timeout=60,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30
        )
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        print("❌ Не удалось запустить бота!")
        print("Проверьте:")
        print("1. Правильность токена")
        print("2. Интернет соединение") 
        print("3. Что нет других экземпляров бота")

if __name__ == '__main__':
    main()
