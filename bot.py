import logging
import sqlite3
import asyncio
import uuid
import datetime
from typing import Optional
import os
from dataclasses import dataclass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Конфигурация
BOT_TOKEN = "7946468786:AAGGeUgN6liN462JMcTG31aWCRKk4n7BB1M"  # Замените на токен вашего бота
ADMIN_ID = 295698267  # Замените на ваш Telegram ID
LICENSE_PRICE = 100  # Цена лицензии в USD

# Банковские реквизиты
BANK_DETAILS = """
💳 **РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:**

🏦 **Банк:** Kapital Bank Uzbekistan
🔢 **МФО:** 01158
💰 **Счет:** 22618 840 092855351 001
💳 **Номер карты:** 4278 3200 2190 9386

💵 **Сумма:** $100 USD
⏰ **Срок действия:** 30 дней

📋 **Инструкция:**
1. Переведите $100 на указанные реквизиты
2. Сделайте скриншот чека об оплате
3. Отправьте скриншот в этот бот
4. Ожидайте подтверждения (обычно в течение 24 часов)
"""

@dataclass
class User:
    user_id: int
    username: str
    license_key: Optional[str]
    license_expiry: Optional[datetime.datetime]
    payment_pending: bool
    created_at: datetime.datetime

class DatabaseManager:
    def __init__(self, db_path: str = "licenses.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                license_key TEXT UNIQUE,
                license_expiry TIMESTAMP,
                payment_pending BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                license_key TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                screenshot_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                user_id=row[0],
                username=row[1],
                license_key=row[2],
                license_expiry=datetime.datetime.fromisoformat(row[3]) if row[3] else None,
                payment_pending=bool(row[4]),
                created_at=datetime.datetime.fromisoformat(row[5])
            )
        return None
    
    def create_user(self, user_id: int, username: str) -> User:
        """Создать нового пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
        """, (user_id, username, datetime.datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return self.get_user(user_id)
    
    def generate_license_key(self) -> str:
        """Генерация уникального ключа лицензии"""
        return f"MEA-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
    
    def create_payment_request(self, user_id: int, screenshot_file_id: str):
        """Создать запрос на оплату"""
        license_key = self.generate_license_key()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Обновляем пользователя
        cursor.execute("""
            UPDATE users SET payment_pending = TRUE WHERE user_id = ?
        """, (user_id,))
        
        # Создаем запись о платеже
        cursor.execute("""
            INSERT INTO payments (user_id, license_key, amount, screenshot_file_id)
            VALUES (?, ?, ?, ?)
        """, (user_id, license_key, LICENSE_PRICE, screenshot_file_id))
        
        conn.commit()
        conn.close()
        
        return license_key
    
    def confirm_payment(self, user_id: int, license_key: str):
        """Подтвердить платеж и активировать лицензию"""
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=30)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Обновляем пользователя
        cursor.execute("""
            UPDATE users SET 
                license_key = ?, 
                license_expiry = ?, 
                payment_pending = FALSE 
            WHERE user_id = ?
        """, (license_key, expiry_date.isoformat(), user_id))
        
        # Обновляем платеж
        cursor.execute("""
            UPDATE payments SET 
                status = 'confirmed', 
                confirmed_at = ? 
            WHERE user_id = ? AND license_key = ?
        """, (datetime.datetime.now().isoformat(), user_id, license_key))
        
        conn.commit()
        conn.close()
    
    def get_pending_payments(self):
        """Получить все ожидающие платежи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.*, u.username FROM payments p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending'
            ORDER BY p.created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        return rows

# Инициализация
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = DatabaseManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        db_user = db.create_user(user.id, user.username or user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("💰 Купить лицензию ($100)", callback_data="buy_license")],
        [InlineKeyboardButton("📊 Проверить статус", callback_data="check_status")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🤖 **Добро пожаловать в MartingaleEA License Bot!**

Привет, {user.first_name}! 👋

Этот бот предназначен для покупки лицензий на торгового советника **MartingaleVPS Enhanced v1.60**.

💼 **Что вы получаете:**
• Лицензия на 30 дней
• Уникальный ключ активации
• Техническая поддержка
• Обновления советника

💰 **Стоимость:** $100 USD за месяц

Выберите действие:
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "buy_license":
        await handle_buy_license(query)
    elif data == "check_status":
        await handle_check_status(query)
    elif data == "help":
        await handle_help(query)
    elif data.startswith("confirm_payment_"):
        payment_id = data.split("_")[-1]
        await handle_confirm_payment(query, payment_id)

async def handle_buy_license(query):
    """Обработка покупки лицензии"""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    # Проверяем, есть ли уже активная лицензия
    if user.license_key and user.license_expiry:
        if user.license_expiry > datetime.datetime.now():
            await query.edit_message_text(
                f"✅ **У вас уже есть активная лицензия!**\n\n"
                f"🔑 **Ключ:** `{user.license_key}`\n"
                f"⏰ **Действует до:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Для продления обратитесь в поддержку.",
                parse_mode='Markdown'
            )
            return
    
    # Проверяем, есть ли ожидающий платеж
    if user.payment_pending:
        await query.edit_message_text(
            "⏳ **У вас есть ожидающий платеж!**\n\n"
            "Пожалуйста, дождитесь подтверждения или отправьте новый скриншот об оплате."
        )
        return
    
    # Показываем реквизиты для оплаты
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        BANK_DETAILS + "\n\n**После оплаты отправьте скриншот чека в этот чат!**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_check_status(query):
    """Проверка статуса лицензии"""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    if not user.license_key:
        status_text = "❌ **Лицензия не найдена**\n\nВы еще не приобрели лицензию."
    elif user.license_expiry and user.license_expiry > datetime.datetime.now():
        days_left = (user.license_expiry - datetime.datetime.now()).days
        status_text = f"""
✅ **Лицензия активна!**

🔑 **Ключ:** `{user.license_key}`
⏰ **Действует до:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}
📅 **Осталось дней:** {days_left}
"""
    else:
        status_text = f"""
❌ **Лицензия истекла**

🔑 **Ключ:** `{user.license_key}`
⏰ **Истекла:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}

Для продления приобретите новую лицензию.
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_help(query):
    """Справка"""
    help_text = """
❓ **Справка по использованию бота**

**Команды:**
• `/start` - Главное меню
• `/buy` - Купить лицензию
• `/status` - Проверить статус лицензии

**Как купить лицензию:**
1. Нажмите "Купить лицензию"
2. Переведите $100 на указанные реквизиты
3. Отправьте скриншот чека в бот
4. Дождитесь подтверждения (до 24 часов)
5. Получите уникальный ключ активации

**Поддержка:**
Если у вас есть вопросы, напишите администратору: @your_support_username

**Важно:**
• Лицензия действует 30 дней
• Один ключ = один терминал
• Продление происходит через новую покупку
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншотов об оплате"""
    user = update.effective_user
    
    if update.message.photo:
        # Получаем файл с максимальным разрешением
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Создаем запрос на оплату
        license_key = db.create_payment_request(user.id, file_id)
        
        # Уведомляем пользователя
        await update.message.reply_text(
            f"✅ **Скриншот получен!**\n\n"
            f"🔄 **Статус:** Ожидает проверки\n"
            f"🎫 **Ваш номер:** {license_key}\n\n"
            f"⏰ Проверка обычно занимает до 24 часов.\n"
            f"После подтверждения вы получите уникальный ключ активации.",
            parse_mode='Markdown'
        )
        
        # Уведомляем администратора
        await notify_admin_about_payment(context, user, license_key, file_id)
    
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте изображение (скриншот) чека об оплате."
        )

async def notify_admin_about_payment(context, user, license_key, file_id):
    """Уведомление администратора о новом платеже"""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_payment_{user.id}_{license_key}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_payment_{user.id}_{license_key}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = f"""
🔔 **НОВЫЙ ПЛАТЕЖ!**

👤 **Пользователь:** {user.first_name} (@{user.username or 'без username'})
🆔 **ID:** `{user.id}`
🎫 **Номер заявки:** `{license_key}`
💰 **Сумма:** $100 USD
⏰ **Время:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

Проверьте скриншот и подтвердите платеж:
"""
    
    try:
        # Отправляем фото
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=admin_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

async def handle_confirm_payment(query, payment_info):
    """Подтверждение платежа администратором"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ У вас нет прав на это действие!")
        return
    
    try:
        # Парсим информацию о платеже
        parts = payment_info.split('_')
        user_id = int(parts[0])
        license_key = '_'.join(parts[1:])
        
        # Подтверждаем платеж в базе данных
        db.confirm_payment(user_id, license_key)
        
        # Уведомляем пользователя
        user_text = f"""
🎉 **ПЛАТЕЖ ПОДТВЕРЖДЕН!**

✅ Ваша лицензия активирована!

🔑 **Ваш уникальный ключ:** `{license_key}`
⏰ **Действует до:** {(datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%d.%m.%Y %H:%M')}

**Инструкция по активации:**
1. Скопируйте ключ: `{license_key}`
2. Вставьте его в настройки советника
3. Перезапустите советника

💼 Приятной торговли!
"""
        
        await query.bot.send_message(
            chat_id=user_id,
            text=user_text,
            parse_mode='Markdown'
        )
        
        # Обновляем сообщение админа
        await query.edit_message_caption(
            caption=f"✅ **ПЛАТЕЖ ПОДТВЕРЖДЕН**\n\n{query.message.caption}",
            parse_mode='Markdown'
        )
        
        await query.answer("✅ Платеж подтвержден! Пользователь уведомлен.")
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения платежа: {e}")
        await query.answer("❌ Ошибка при подтверждении платежа!")

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    
    # Запускаем бота
    print("🤖 Бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()