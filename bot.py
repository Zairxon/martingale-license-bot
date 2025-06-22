import logging
import sqlite3
import asyncio
import uuid
import datetime
import hashlib
import base64
import os
from typing import Optional
from dataclasses import dataclass
import io

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Конфигурация
BOT_TOKEN = "7946468786:AAGGeUgN6liN462JMcTG31aWCRKk4n7BB1M"
ADMIN_ID = 295698267  # @Zair_Khudayberganov
LICENSE_PRICE = 100  # Цена лицензии в USD
TRIAL_DAYS = 3  # Дни испытательного периода
FULL_LICENSE_DAYS = 30  # Дни полной лицензии

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
5. Получите полную лицензию на 30 дней
"""

# Описание советника
EA_DESCRIPTION = """
🤖 **MartingaleVPS Enhanced v1.60**

**Описание:**
Профессиональный торговый советник для автоматической торговли по стратегии Мартингейл, специально оптимизированный для работы на VPS серверах с криптовалютами и драгоценными металлами.

**Поддерживаемые символы:**
• 🟡 **BTCUSD** - Bitcoin (основной)
• 🥇 **XAUUSD** - Золото (дополнительный)

❌ **Внимание:** Работает ТОЛЬКО с указанными символами!

**Основные возможности:**
• ✅ VPS-оптимизированная архитектура
• ✅ Автоматическое определение тренда
• ✅ Интеллектуальное управление рисками
• ✅ Защита от пропущенных сделок
• ✅ Система удвоения лотов (мартингейл)
• ✅ Глобальный Take Profit
• ✅ Аварийная остановка при достижении лимитов

**Торговые параметры:**

📊 **Для XAUUSD (золото):**
• Take Profit: 10,000 пунктов
• Stop Distance: 3,000 пунктов  
• Настройки по умолчанию (не изменять)

📊 **Для BTCUSD (биткоин):**
• Take Profit: 100,000 пунктов
• Stop Distance: 30,000 пунктов
• Обязательно настроить правильно!

**Управление лотами:**

💰 **Баланс $100-999:**
• Рекомендуется: 0.01 лот
• Максимум: 0.10 лот (риск высокий)

💰 **Баланс $1000+:**
• Рекомендуется: 0.10 лот  
• Максимум: 1.00 лот (риск очень высокий)

**Безопасность:**
• 🔒 Проверка лицензии каждые 10 минут
• 🔒 Привязка к конкретному торговому счету
• 🔒 Защита от копирования и повторного использования
• 🔒 Автоматическая остановка при истечении лицензии

**Рекомендуемые настройки:**
• Таймфрейм: M1-M15
• Минимальный депозит: $100
• Рекомендуемый депозит: $1000+
• VPS сервер для круглосуточной работы

**Что включено:**
• Техническая поддержка 24/7
• Обновления включены в лицензию
• Детальные инструкции по установке
• Настройка для каждого символа
"""

@dataclass
class User:
    user_id: int
    username: str
    license_key: Optional[str]
    license_expiry: Optional[datetime.datetime]
    license_type: str  # 'trial' или 'full'
    payment_pending: bool
    account_number: Optional[str]  # Привязанный торговый счет
    trial_used: bool  # Использовался ли пробный период
    downloads_count: int  # Количество скачиваний
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
                license_type TEXT DEFAULT 'trial',
                payment_pending BOOLEAN DEFAULT FALSE,
                account_number TEXT,
                trial_used BOOLEAN DEFAULT FALSE,
                downloads_count INTEGER DEFAULT 0,
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
        
        # Таблица скачиваний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_hash TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица для хранения файла EA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ea_files (
                id INTEGER PRIMARY KEY,
                filename TEXT,
                file_data BLOB,
                version TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица лицензионных проверок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS license_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT,
                account_number TEXT,
                check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                ip_hash TEXT
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
                license_type=row[4] or 'trial',
                payment_pending=bool(row[5]),
                account_number=row[6],
                trial_used=bool(row[7]),
                downloads_count=row[8] or 0,
                created_at=datetime.datetime.fromisoformat(row[9])
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
    
    def generate_license_key(self, license_type: str = 'trial') -> str:
        """Генерация уникального ключа лицензии"""
        prefix = "TRIAL" if license_type == 'trial' else "FULL"
        return f"MEA-{prefix}-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
    
    def create_trial_license(self, user_id: int):
        """Создать пробную лицензию"""
        if self.is_trial_used(user_id):
            return False, "Пробный период уже использован"
        
        license_key = self.generate_license_key('trial')
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=TRIAL_DAYS)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET 
                license_key = ?, 
                license_expiry = ?, 
                license_type = 'trial',
                trial_used = TRUE
            WHERE user_id = ?
        """, (license_key, expiry_date.isoformat(), user_id))
        
        conn.commit()
        conn.close()
        
        return True, license_key
    
    def is_trial_used(self, user_id: int) -> bool:
        """Проверить, использовался ли пробный период"""
        user = self.get_user(user_id)
        return user.trial_used if user else False
    
    def create_payment_request(self, user_id: int, screenshot_file_id: str):
        """Создать запрос на оплату"""
        license_key = self.generate_license_key('full')
        
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
        """Подтвердить платеж и активировать полную лицензию"""
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=FULL_LICENSE_DAYS)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Обновляем пользователя
        cursor.execute("""
            UPDATE users SET 
                license_key = ?, 
                license_expiry = ?, 
                license_type = 'full',
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
    
    def increment_download_count(self, user_id: int):
        """Увеличить счетчик скачиваний"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET downloads_count = downloads_count + 1 WHERE user_id = ?
        """, (user_id,))
        
        cursor.execute("""
            INSERT INTO downloads (user_id) VALUES (?)
        """, (user_id,))
        
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
    
    def get_stats(self):
        """Получить статистику"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE trial_used = TRUE")
        trial_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE license_type = 'full' AND license_expiry > ?", 
                      (datetime.datetime.now().isoformat(),))
        active_full_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(downloads_count) FROM users")
        total_downloads = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'confirmed'")
        confirmed_payments = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_users': total_users,
            'trial_users': trial_users,
            'active_licenses': active_full_licenses,
            'total_downloads': total_downloads,
            'confirmed_payments': confirmed_payments
        }

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
    
    # Проверяем статус лицензии
    has_active_license = False
    if db_user.license_key and db_user.license_expiry:
        has_active_license = db_user.license_expiry > datetime.datetime.now()
    
    # Формируем клавиатуру в зависимости от статуса
    keyboard = []
    
    if not db_user.trial_used:
        keyboard.append([InlineKeyboardButton("🆓 Получить 3 дня БЕСПЛАТНО", callback_data="get_trial")])
    
    if not has_active_license:
        keyboard.append([InlineKeyboardButton("💰 Купить полную лицензию ($100)", callback_data="buy_license")])
    
    keyboard.extend([
        [InlineKeyboardButton("📊 Мой статус", callback_data="check_status")],
        [InlineKeyboardButton("📖 Описание советника", callback_data="show_description")],
        [InlineKeyboardButton("❓ Инструкция", callback_data="show_instructions")]
    ])
    
    if has_active_license:
        keyboard.append([InlineKeyboardButton("⬇️ Скачать EA файл", callback_data="download_ea")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🤖 **Добро пожаловать в MartingaleEA License Bot!**

Привет, {user.first_name}! 👋

Этот бот предназначен для лицензирования торгового советника **MartingaleVPS Enhanced v1.60**.

🎁 **СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ:**
• 3 дня БЕСПЛАТНОГО использования
• Полная функциональность
• Без ограничений

💼 **Полная лицензия:**
• 30 дней использования
• Техническая поддержка 24/7
• Обновления и улучшения
• Стоимость: $100 USD

Выберите действие:
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "get_trial":
        await handle_get_trial(query)
    elif data == "buy_license":
        await handle_buy_license(query)
    elif data == "check_status":
        await handle_check_status(query)
    elif data == "show_description":
        await handle_show_description(query)
    elif data == "show_instructions":
        await handle_show_instructions(query)
    elif data == "download_ea":
        await handle_download_ea(query)
    elif data == "back_to_menu":
        await start_from_callback(query)
    elif data.startswith("confirm_payment_"):
        payment_info = data.replace("confirm_payment_", "")
        await handle_confirm_payment(query, payment_info)
    elif data.startswith("reject_payment_"):
        payment_info = data.replace("reject_payment_", "")
        await handle_reject_payment(query, payment_info)

async def handle_get_trial(query):
    """Получение пробной лицензии"""
    user_id = query.from_user.id
    
    success, result = db.create_trial_license(user_id)
    
    if not success:
        await query.edit_message_text(
            f"❌ **{result}**\n\n"
            f"Каждый пользователь может получить пробный период только один раз.\n"
            f"Для дальнейшего использования приобретите полную лицензию.",
            parse_mode='Markdown'
        )
        return
    
    license_key = result
    keyboard = [
        [InlineKeyboardButton("⬇️ Скачать EA файл", callback_data="download_ea")],
        [InlineKeyboardButton("📖 Инструкция по установке", callback_data="show_instructions")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    trial_text = f"""
🎉 **ПРОБНАЯ ЛИЦЕНЗИЯ АКТИВИРОВАНА!**

✅ **Ваш пробный ключ:** `{license_key}`
⏰ **Действует:** 3 дня (72 часа)
🎯 **Тип:** Полная функциональность

**📋 Что дальше:**
1. Скачайте EA файл (кнопка ниже)
2. Прочитайте инструкцию по установке
3. Установите в MetaTrader 5
4. Введите ключ: `{license_key}`
5. Начинайте торговать!

**⚠️ Важно:**
• Лицензия привязывается к торговому счету
• Один ключ = один счет
• После истечения нужно купить полную лицензию

💰 **Полная лицензия: $100 за 30 дней**
"""
    
    await query.edit_message_text(trial_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_buy_license(query):
    """Обработка покупки лицензии"""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    # Проверяем, есть ли уже активная полная лицензия
    if user.license_type == 'full' and user.license_expiry:
        if user.license_expiry > datetime.datetime.now():
            await query.edit_message_text(
                f"✅ **У вас уже есть активная полная лицензия!**\n\n"
                f"🔑 **Ключ:** `{user.license_key}`\n"
                f"⏰ **Действует до:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Для продления обратитесь в поддержку после истечения.",
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
        status_text = """
❌ **Лицензия не найдена**

Вы еще не получили лицензию.

**Доступные опции:**
• 🆓 Получить 3 дня бесплатно
• 💰 Купить полную лицензию ($100)
"""
    elif user.license_expiry and user.license_expiry > datetime.datetime.now():
        days_left = (user.license_expiry - datetime.datetime.now()).days
        hours_left = (user.license_expiry - datetime.datetime.now()).seconds // 3600
        
        license_emoji = "🆓" if user.license_type == 'trial' else "💎"
        license_name = "Пробная" if user.license_type == 'trial' else "Полная"
        
        status_text = f"""
✅ **Лицензия активна!**

{license_emoji} **Тип:** {license_name}
🔑 **Ключ:** `{user.license_key}`
⏰ **Действует до:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}
📅 **Осталось:** {days_left} дн. {hours_left} ч.
📊 **Скачиваний:** {user.downloads_count}
"""
    else:
        license_name = "Пробная" if user.license_type == 'trial' else "Полная"
        status_text = f"""
❌ **Лицензия истекла**

🔑 **Ключ:** `{user.license_key}`
📝 **Тип:** {license_name}
⏰ **Истекла:** {user.license_expiry.strftime('%d.%m.%Y %H:%M')}

Для продления приобретите новую лицензию.
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_show_description(query):
    """Показать описание советника"""
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(EA_DESCRIPTION, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_show_instructions(query):
    """Показать инструкцию по установке"""
    instructions = """
📖 **ИНСТРУКЦИЯ ПО УСТАНОВКЕ И НАСТРОЙКЕ**

**1. СИСТЕМНЫЕ ТРЕБОВАНИЯ:**
• MetaTrader 5 (последняя версия)
• Стабильное интернет-соединение
• Разрешенная автоторговля
• Минимальный депозит: $100

**2. УСТАНОВКА EA:**
• Скачайте файл EA из бота
• Скопируйте в папку: `MetaTrader 5/MQL5/Experts/`
• Перезапустите MetaTrader 5
• EA появится в навигаторе

**3. ПОДДЕРЖИВАЕМЫЕ СИМВОЛЫ:**
🟢 **BTCUSD** - основной символ
🟢 **XAUUSD** - золото (дополнительный)

❌ **Другие символы не поддерживаются!**

**4. НАСТРОЙКИ ПО СИМВОЛАМ:**

📊 **Для XAUUSD:**
• TakeProfitPips: `10000` (не изменять)
• BuyStopPips: `3000` (не изменять)
• Используйте настройки по умолчанию

📊 **Для BTCUSD:**
• TakeProfitPips: `100000` (добавлен ноль)
• BuyStopPips: `30000` (добавлен ноль)
• Обязательно измените эти параметры!

**5. УПРАВЛЕНИЕ ЛОТАМИ:**

💰 **Баланс $100-999:**
• ✅ Рекомендуется: `0.01` лот
• ⚠️ Рискованно: `0.10` лот
• ❌ Не рекомендуется: больше 0.10

💰 **Баланс $1000+:**
• ✅ Рекомендуется: `0.10` лот
• ⚠️ Рискованно: `1.00` лот
• ❌ Крайне рискованно: больше 1.00

**6. АКТИВАЦИЯ ЛИЦЕНЗИИ:**
• Перетащите EA на график
• В поле "LicenseKey" введите ваш ключ
• Установите правильные настройки для символа
• Разрешите автоторговлю (галочка)
• Нажмите OK

**7. ПРОВЕРКА РАБОТЫ:**
• В журнале должно появиться: "✅ Лицензия активна"
• Статус: "ТОРГУЕТ" в правом углу графика
• Появятся уровни сессии на графике

**⚠️ КРИТИЧЕСКИ ВАЖНО:**

🔒 **Лицензирование:**
• Один ключ = один торговый счет MT5
• При смене счета ключ блокируется
• Проверка лицензии каждые 10 минут онлайн

📈 **Риск-менеджмент:**
• НЕ используйте весь депозит сразу
• Начинайте с минимальных лотов
• Следите за просадкой (не более 30%)
• При серии убытков - остановите советника

🔧 **Технические требования:**
• VPS рекомендуется для 24/7 работы
• Пинг к брокеру не более 50ms
• Стабильное интернет-соединение

**8. ПОИСК И УСТРАНЕНИЕ НЕИСПРАВНОСТЕЙ:**

❌ **"Неверная лицензия":**
• Проверьте правильность ключа
• Убедитесь в наличии интернета
• Перезапустите EA

❌ **"Символ не поддерживается":**
• Используйте только BTCUSD или XAUUSD
• Проверьте точное написание символа

❌ **"Нет сигнала":**
• Дождитесь формирования тренда
• Проверьте рыночное время
• Убедитесь в наличии ликвидности

**🆘 ТЕХНИЧЕСКАЯ ПОДДЕРЖКА:**
• Telegram: @Zair_Khudayberganov
• Время ответа: до 24 часов
• Приложите: скриншот настроек + ваш ключ
• Опишите проблему детально

**💡 СОВЕТЫ ДЛЯ УСПЕШНОЙ ТОРГОВЛИ:**
• Торгуйте в активные сессии (Лондон, Нью-Йорк)
• Избегайте торговли во время новостей
• Регулярно проверяйте работу советника
• Ведите учет результатов
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(instructions, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_download_ea(query):
    """Скачивание EA файла"""
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    # Проверяем наличие активной лицензии
    if not user.license_key or not user.license_expiry:
        await query.edit_message_text(
            "❌ **Доступ запрещен**\n\n"
            "Для скачивания нужна активная лицензия.\n"
            "Получите пробную или купите полную лицензию."
        )
        return
    
    if user.license_expiry <= datetime.datetime.now():
        await query.edit_message_text(
            "❌ **Лицензия истекла**\n\n"
            "Ваша лицензия истекла. Для скачивания обновите лицензию."
        )
        return
    
    # Заглушка для файла (в реальности здесь будет загрузка из БД)
    await query.edit_message_text(
        """
⬇️ **СКАЧИВАНИЕ EA ФАЙЛА**

📁 **Файл:** MartingaleVPS_Enhanced_v1.60.ex5
📏 **Размер:** ~45 KB
🔒 **Защищено лицензией**

🔗 **Ссылка на скачивание:**
`https://temp-download-link.com/ea-file-{}`

⏰ **Ссылка действительна 10 минут**

📋 **После скачивания:**
1. Поместите файл в папку MetaTrader 5/MQL5/Experts/
2. Перезапустите MetaTrader 5
3. Установите на график и введите ключ: `{}`

**⚠️ Внимание:** Каждое скачивание фиксируется в системе.
""".format(user.license_key[:8], user.license_key),
        parse_mode='Markdown'
    )
    
    # Увеличиваем счетчик скачиваний
    db.increment_download_count(user_id)
    
    # Здесь в реальности нужно отправить файл
    # await query.message.reply_document(document=InputFile(ea_file_data, filename="MartingaleVPS_Enhanced_v1.60.ex5"))

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
            f"🎫 **Номер заявки:** {license_key}\n\n"
            f"⏰ Проверка обычно занимает до 24 часов.\n"
            f"После подтверждения вы получите полную лицензию на 30 дней.",
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

✅ Ваша ПОЛНАЯ лицензия активирована!

💎 **Ваш ключ:** `{license_key}`
⏰ **Действует до:** {(datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%d.%m.%Y %H:%M')}
🎯 **Тип:** Полная лицензия (30 дней)

**📋 Что дальше:**
1. Скачайте обновленный EA файл
2. Используйте новый ключ: `{license_key}`
3. Полная техническая поддержка включена

💼 Приятной и прибыльной торговли!
"""
        
        keyboard = [
            [InlineKeyboardButton("⬇️ Скачать EA файл", callback_data="download_ea")],
            [InlineKeyboardButton("📖 Инструкция", callback_data="show_instructions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.bot.send_message(
            chat_id=user_id,
            text=user_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Обновляем сообщение админа
        await query.edit_message_caption(
            caption=f"✅ **ПЛАТЕЖ ПОДТВЕРЖДЕН**\n\n{query.message.caption}",
            parse_mode='Markdown'
        )
        
        await query.answer("✅ Платеж подтвержден! Пользователь получил полную лицензию.")
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения платежа: {e}")
        await query.answer("❌ Ошибка при подтверждении платежа!")

async def handle_reject_payment(query, payment_info):
    """Отклонение платежа администратором"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ У вас нет прав на это действие!")
        return
    
    try:
        parts = payment_info.split('_')
        user_id = int(parts[0])
        
        # Уведомляем пользователя об отклонении
        await query.bot.send_message(
            chat_id=user_id,
            text="""
❌ **Платеж отклонен**

К сожалению, ваш платеж не может быть подтвержден.

**Возможные причины:**
• Неполная информация в чеке
• Неверная сумма
• Технические проблемы

**Что делать:**
• Проверьте правильность перевода
• Отправьте новый скриншот
• Обратитесь в поддержку: @Zair_Khudayberganov
""",
            parse_mode='Markdown'
        )
        
        # Обновляем сообщение админа
        await query.edit_message_caption(
            caption=f"❌ **ПЛАТЕЖ ОТКЛОНЕН**\n\n{query.message.caption}",
            parse_mode='Markdown'
        )
        
        await query.answer("❌ Платеж отклонен. Пользователь уведомлен.")
        
    except Exception as e:
        logger.error(f"Ошибка отклонения платежа: {e}")
        await query.answer("❌ Ошибка при отклонении платежа!")

async def start_from_callback(query):
    """Возврат в главное меню из callback"""
    user = query.from_user
    db_user = db.get_user(user.id)
    
    # Проверяем статус лицензии
    has_active_license = False
    if db_user.license_key and db_user.license_expiry:
        has_active_license = db_user.license_expiry > datetime.datetime.now()
    
    # Формируем клавиатуру
    keyboard = []
    
    if not db_user.trial_used:
        keyboard.append([InlineKeyboardButton("🆓 Получить 3 дня БЕСПЛАТНО", callback_data="get_trial")])
    
    if not has_active_license or db_user.license_type == 'trial':
        keyboard.append([InlineKeyboardButton("💰 Купить полную лицензию ($100)", callback_data="buy_license")])
    
    keyboard.extend([
        [InlineKeyboardButton("📊 Мой статус", callback_data="check_status")],
        [InlineKeyboardButton("📖 Описание советника", callback_data="show_description")],
        [InlineKeyboardButton("❓ Инструкция", callback_data="show_instructions")]
    ])
    
    if has_active_license:
        keyboard.append([InlineKeyboardButton("⬇️ Скачать EA файл", callback_data="download_ea")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🤖 **MartingaleEA License Bot**

Добро пожаловать обратно, {user.first_name}! 👋

Выберите действие:
"""
    
    await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# Команды для администратора
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика для администратора"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    stats = db.get_stats()
    
    stats_text = f"""
📊 **СТАТИСТИКА БОТА**

👥 **Пользователи:**
• Всего зарегистрировано: {stats['total_users']}
• Использовали пробный период: {stats['trial_users']}
• Активных полных лицензий: {stats['active_licenses']}

💰 **Платежи:**
• Подтвержденных платежей: {stats['confirmed_payments']}
• Общая выручка: ${stats['confirmed_payments'] * LICENSE_PRICE}

📁 **Скачивания:**
• Всего скачиваний: {stats['total_downloads']}

⏰ **Время:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    
    # Запускаем бота
    print("🤖 MartingaleEA License Bot запущен!")
    print(f"📊 Админ: @Zair_Khudayberganov (ID: {ADMIN_ID})")
    application.run_polling()

if __name__ == '__main__':
    main()
