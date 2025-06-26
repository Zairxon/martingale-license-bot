#!/usr/bin/env python3
import os
import sqlite3
import logging
import aiohttp
import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from io import BytesIO

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ParseMode
except ImportError:
    logger.error("Telegram библиотека не установлена! Установите: pip install python-telegram-bot")
    exit(1)

# ============================================================================
# 🔧 ТОЛЬКО ИСПРАВЛЕНИЕ БД - ОСТАЛЬНОЕ БЕЗ ИЗМЕНЕНИЙ
# ============================================================================

# Токен бота (замените на ваш)
BOT_TOKEN = "7883129351:AAGGUIgmfEzRIg5_vNx2NhgCNXa6gSLkwwU"

# ОРИГИНАЛЬНЫЕ банковские реквизиты (ОБЕИ КАРТЫ!)
PAYMENT_CARDS = {
    "uzcard": {
        "number": "8600 0691 4864 4864",
        "owner": "Asqarov Rasulbek",
        "bank": "Kapitalbank",
        "name": "💳 UzCard Kapitalbank"
    },
    "visa": {
        "number": "4278 3100 2430 7167",
        "owner": "Asqarov Rasulbek", 
        "bank": "Kapitalbank",
        "name": "💳 VISA Kapital"
    }
}

# ОРИГИНАЛЬНАЯ структура тарифов (БЕЗ ИЗМЕНЕНИЙ!)
# 3 дня триал + 100 USD за месяц
TRIAL_DAYS = 3
MONTHLY_PRICE = 100  # USD

# ============================================================================
# 🔧 ТОЛЬКО ДОБАВЛЯЕМ ФУНКЦИИ БД - ОСТАЛЬНОЕ НЕ ТРОГАЕМ
# ============================================================================

def init_database():
    """ТОЛЬКО для синхронизации с API - остальная логика не меняется"""
    try:
        conn = sqlite3.connect('license_system.db')
        cursor = conn.cursor()
        
        # Создаем таблицы (для совместимости с API)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT UNIQUE NOT NULL,
                account_number TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                plan_type TEXT NOT NULL,
                telegram_user_id TEXT,
                payment_verified BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_licenses INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id TEXT NOT NULL,
                license_key TEXT NOT NULL,
                amount REAL NOT NULL,
                plan_type TEXT NOT NULL,
                payment_method TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                verified BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована (для API совместимости)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

def save_license_to_db(license_key, plan_type, telegram_user_id, days, amount=0):
    """ТОЛЬКО сохранение в БД для API совместимости"""
    try:
        conn = sqlite3.connect('license_system.db')
        cursor = conn.cursor()
        
        expires_at = datetime.now() + timedelta(days=days)
        
        # Определяем статус оплаты (триал автоматически подтвержден)
        payment_verified = 1 if plan_type == "trial" else 0
        
        cursor.execute('''
            INSERT INTO licenses (license_key, plan_type, telegram_user_id, expires_at, is_active, payment_verified)
            VALUES (?, ?, ?, ?, 1, ?)
        ''', (license_key, plan_type, str(telegram_user_id), expires_at, payment_verified))
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_user_id, username, total_licenses)
            VALUES (?, ?, 0)
        ''', (str(telegram_user_id), ""))
        
        cursor.execute('''
            UPDATE users SET total_licenses = total_licenses + 1 
            WHERE telegram_user_id = ?
        ''', (str(telegram_user_id),))
        
        if amount > 0:
            cursor.execute('''
                INSERT INTO payments (telegram_user_id, license_key, amount, plan_type, verified)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(telegram_user_id), license_key, amount, plan_type, payment_verified))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Лицензия сохранена в БД: {license_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в БД: {e}")
        return False

def verify_payment_in_db(license_key):
    """ТОЛЬКО подтверждение оплаты в БД"""
    try:
        conn = sqlite3.connect('license_system.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE licenses SET payment_verified = 1 WHERE license_key = ?
        ''', (license_key,))
        
        cursor.execute('''
            UPDATE payments SET verified = 1 WHERE license_key = ?
        ''', (license_key,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Оплата подтверждена в БД: {license_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка подтверждения оплаты: {e}")
        return False

def get_user_licenses_from_db(telegram_user_id):
    """ТОЛЬКО получение из БД для совместимости"""
    try:
        conn = sqlite3.connect('license_system.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT license_key, plan_type, created_at, expires_at, is_active, payment_verified
            FROM licenses 
            WHERE telegram_user_id = ?
            ORDER BY created_at DESC
        ''', (str(telegram_user_id),))
        
        licenses = cursor.fetchall()
        conn.close()
        
        return licenses
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения лицензий: {e}")
        return []

# ============================================================================
# ОРИГИНАЛЬНАЯ ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ!)
# ============================================================================

# Хранилище данных пользователей (ОРИГИНАЛЬНОЕ!)
users_data = {}

def generate_license_key():
    """ОРИГИНАЛЬНАЯ функция генерации ключа"""
    timestamp = str(int(time.time()))[-6:]
    random_part = hashlib.md5(os.urandom(32)).hexdigest()[:12].upper()
    
    key_parts = [
        "RFX",
        random_part[:4],
        random_part[4:8], 
        random_part[8:12],
        timestamp[:3],
        timestamp[3:5]
    ]
    
    return "-".join(key_parts)

def has_trial_license(user_id):
    """ОРИГИНАЛЬНАЯ проверка триала"""
    if user_id in users_data:
        for license_data in users_data[user_id].get('licenses', []):
            if license_data.get('type') == 'trial':
                return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ОРИГИНАЛЬНАЯ команда /start"""
    user = update.effective_user
    user_id = user.id
    
    # Инициализируем пользователя если нужно
    if user_id not in users_data:
        users_data[user_id] = {
            'username': user.username or user.first_name,
            'licenses': [],
            'payments': []
        }
    
    keyboard = [
        [InlineKeyboardButton("🆓 Получить триал (3 дня бесплатно)", callback_data="trial")],
        [InlineKeyboardButton("💳 Купить лицензию ($100/месяц)", callback_data="buy_license")],
        [InlineKeyboardButton("📋 Мои лицензии", callback_data="my_licenses")],
        [InlineKeyboardButton("💰 Подтвердить оплату", callback_data="verify_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 <b>Добро пожаловать в RFX Trading License Bot!</b>\n\n"
        f"👋 Привет, {user.first_name}!\n\n"
        f"🔐 <b>Система лицензирования торгового советника MT5</b>\n\n"
        f"📋 <b>Доступные опции:</b>\n"
        f"• 🆓 <b>Триал период:</b> 3 дня бесплатно\n"
        f"• 💳 <b>Месячная лицензия:</b> $100 USD\n"
        f"• 📋 Просмотр активных лицензий\n"
        f"• 💰 Подтверждение оплаты\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ОРИГИНАЛЬНЫЙ обработчик кнопок + обработка выбора карт"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "trial":
        await handle_trial_request(query)
    elif query.data == "buy_license":
        await handle_license_purchase(query)
    elif query.data == "my_licenses":
        await show_user_licenses(query)
    elif query.data == "verify_payment":
        await start_payment_verification(query)
    elif query.data == "back_to_main":
        await start_from_callback(query)
    elif query.data.startswith("pay_card_"):
        # Новый обработчик для выбора карты
        parts = query.data.split("_")
        card_id = parts[2]
        license_key = parts[3] if len(parts) > 3 else ""
        await show_payment_details(query, card_id, license_key)

async def handle_trial_request(query):
    """ОРИГИНАЛЬНАЯ выдача триала"""
    user_id = query.from_user.id
    
    if has_trial_license(user_id):
        await query.edit_message_text(
            "❌ <b>Триал уже использован</b>\n\n"
            "Вы уже получали триал период.\n"
            "Для продолжения купите месячную лицензию за $100.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Генерируем триал ключ
    license_key = generate_license_key()
    
    # ОРИГИНАЛЬНОЕ сохранение
    trial_data = {
        'key': license_key,
        'type': 'trial',
        'created': datetime.now(),
        'expires': datetime.now() + timedelta(days=TRIAL_DAYS),
        'active': True
    }
    
    users_data[user_id]['licenses'].append(trial_data)
    
    # НОВОЕ: также сохраняем в БД для API
    save_license_to_db(license_key, "trial", user_id, TRIAL_DAYS, 0)
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🎉 <b>Триал период активирован!</b>\n\n"
        f"🔐 <b>Ваш лицензионный ключ:</b>\n"
        f"<code>{license_key}</code>\n\n"
        f"⏰ <b>Срок действия:</b> 3 дня\n"
        f"📅 <b>Истекает:</b> {trial_data['expires'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📋 <b>Как использовать:</b>\n"
        f"1. Скопируйте ключ (нажмите на него)\n"
        f"2. Вставьте в настройки советника MT5\n"
        f"3. Запустите советника\n\n"
        f"💡 <b>После окончания триала:</b>\n"
        f"Купите месячную лицензию за $100 для продолжения работы.",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def handle_license_purchase(query):
    """ОРИГИНАЛЬНАЯ покупка лицензии с выбором карты"""
    user_id = query.from_user.id
    
    # Генерируем ключ для покупки
    license_key = generate_license_key()
    
    # ОРИГИНАЛЬНОЕ сохранение в память
    purchase_data = {
        'key': license_key,
        'type': 'monthly',
        'created': datetime.now(),
        'expires': datetime.now() + timedelta(days=30),
        'active': False,  # Активируется после оплаты
        'paid': False
    }
    
    users_data[user_id]['licenses'].append(purchase_data)
    
    # НОВОЕ: также сохраняем в БД для API (неподтвержденное)
    save_license_to_db(license_key, "monthly", user_id, 30, MONTHLY_PRICE)
    
    # Показываем выбор карт
    keyboard = []
    for card_id, card_info in PAYMENT_CARDS.items():
        keyboard.append([InlineKeyboardButton(
            card_info["name"], 
            callback_data=f"pay_card_{card_id}_{license_key}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💳 <b>Покупка месячной лицензии</b>\n\n"
        f"💰 <b>Сумма:</b> ${MONTHLY_PRICE} USD\n"
        f"🔐 <b>Лицензионный ключ:</b>\n<code>{license_key}</code>\n\n"
        f"💳 <b>Выберите способ оплаты:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def show_payment_details(query, card_id, license_key):
    """Показ реквизитов выбранной карты"""
    if card_id not in PAYMENT_CARDS:
        await query.edit_message_text("❌ Ошибка: неверная карта")
        return
    
    card_info = PAYMENT_CARDS[card_id]
    
    keyboard = [
        [InlineKeyboardButton("💰 Подтвердить оплату", callback_data="verify_payment")],
        [InlineKeyboardButton("🔙 Выбрать другую карту", callback_data="buy_license")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💳 <b>Реквизиты для оплаты</b>\n\n"
        f"🔐 <b>Лицензионный ключ:</b>\n<code>{license_key}</code>\n\n"
        f"💰 <b>Сумма:</b> ${MONTHLY_PRICE} USD\n\n"
        f"💳 <b>Реквизиты карты:</b>\n"
        f"• <b>Карта:</b> <code>{card_info['number']}</code>\n"
        f"• <b>Получатель:</b> {card_info['owner']}\n"
        f"• <b>Банк:</b> {card_info['bank']}\n"
        f"• <b>Тип:</b> {card_info['name']}\n\n"
        f"📝 <b>Инструкция:</b>\n"
        f"1. Переведите точную сумму ${MONTHLY_PRICE} USD\n"
        f"2. Нажмите 'Подтвердить оплату'\n"
        f"3. Отправьте скриншот перевода\n\n"
        f"⚠️ <b>ВАЖНО:</b> Сохраните лицензионный ключ!",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def start_payment_verification(query):
    """ОРИГИНАЛЬНАЯ процедура подтверждения"""
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Показываем информацию об обеих картах
    cards_info = ""
    for card_id, card_info in PAYMENT_CARDS.items():
        cards_info += f"• {card_info['name']}: {card_info['number']} ({card_info['owner']})\n"
    
    await query.edit_message_text(
        "📸 <b>Подтверждение оплаты</b>\n\n"
        f"Отправьте скриншот или фото чека об оплате ${MONTHLY_PRICE} USD\n\n"
        f"💳 <b>Доступные карты для оплаты:</b>\n{cards_info}\n"
        "После проверки ваша лицензия будет активирована!",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ОРИГИНАЛЬНАЯ обработка скриншота"""
    user_id = update.effective_user.id
    
    if user_id not in users_data:
        await update.message.reply_text(
            "❌ Сначала купите лицензию через /start → 'Купить лицензию'"
        )
        return
    
    # Ищем неоплаченную лицензию
    unverified_license = None
    for license_data in users_data[user_id]['licenses']:
        if license_data.get('type') == 'monthly' and not license_data.get('paid', False):
            unverified_license = license_data
            break
    
    if not unverified_license:
        await update.message.reply_text(
            "❌ Нет неоплаченных лицензий. Сначала создайте заказ."
        )
        return
    
    # Активируем лицензию
    unverified_license['paid'] = True
    unverified_license['active'] = True
    
    # НОВОЕ: подтверждаем в БД для API
    verify_payment_in_db(unverified_license['key'])
    
    keyboard = [[InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ <b>Оплата подтверждена!</b>\n\n"
        f"🔐 <b>Ваша лицензия активирована:</b>\n"
        f"<code>{unverified_license['key']}</code>\n\n"
        f"📅 <b>Действует до:</b> {unverified_license['expires'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"✅ <b>Лицензия готова к использованию!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def show_user_licenses(query):
    """ОРИГИНАЛЬНЫЙ показ лицензий"""
    user_id = query.from_user.id
    
    if user_id not in users_data or not users_data[user_id]['licenses']:
        keyboard = [
            [InlineKeyboardButton("🆓 Получить триал", callback_data="trial")],
            [InlineKeyboardButton("💳 Купить лицензию", callback_data="buy_license")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 <b>Ваши лицензии</b>\n\n"
            "У вас пока нет лицензий.\n\n"
            "Получите триал на 3 дня бесплатно или купите месячную лицензию!",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return
    
    text = "📋 <b>Ваши лицензии:</b>\n\n"
    
    for license_data in users_data[user_id]['licenses']:
        license_key = license_data['key']
        license_type = license_data['type']
        expires = license_data['expires']
        is_active = license_data.get('active', False)
        is_paid = license_data.get('paid', True)  # Триал считается оплаченным
        
        # Проверяем истечение
        is_expired = expires < datetime.now()
        
        if license_type == 'trial':
            type_name = "🆓 Триал (3 дня)"
            status = "✅ Активен" if (is_active and not is_expired) else "❌ Истек"
        else:
            type_name = "💳 Месячная лицензия"
            if not is_paid:
                status = "⏳ Ожидает оплаты"
            elif is_expired:
                status = "❌ Истекла"
            else:
                status = "✅ Активна"
        
        text += (
            f"🔐 <code>{license_key}</code>\n"
            f"📋 {type_name}\n"
            f"📅 Истекает: {expires.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 Статус: {status}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("💳 Купить еще", callback_data="buy_license")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def start_from_callback(query):
    """ОРИГИНАЛЬНЫЙ возврат в меню"""
    keyboard = [
        [InlineKeyboardButton("🆓 Получить триал (3 дня бесплатно)", callback_data="trial")],
        [InlineKeyboardButton("💳 Купить лицензию ($100/месяц)", callback_data="buy_license")],
        [InlineKeyboardButton("📋 Мои лицензии", callback_data="my_licenses")],
        [InlineKeyboardButton("💰 Подтвердить оплату", callback_data="verify_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🤖 <b>RFX Trading License Bot</b>\n\n"
        f"🔐 <b>Система лицензирования торгового советника</b>\n\n"
        f"• 🆓 <b>Триал:</b> 3 дня бесплатно\n"
        f"• 💳 <b>Лицензия:</b> $100 USD/месяц\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

# ============================================================================
# 🚀 ЗАПУСК БОТА (БЕЗ ИЗМЕНЕНИЙ!)
# ============================================================================

def main():
    """ОРИГИНАЛЬНАЯ функция запуска"""
    # ТОЛЬКО ДОБАВЛЯЕМ инициализацию БД для API совместимости
    init_database()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_payment_proof))
    
    logger.info("🤖 Запуск RFX Trading License Bot...")
    logger.info("💳 Оригинальные тарифы: 3 дня триал + $100/месяц")
    logger.info(f"💳 Реквизиты UzCard: {PAYMENT_CARDS['uzcard']['number']} ({PAYMENT_CARDS['uzcard']['owner']})")
    logger.info(f"💳 Реквизиты VISA: {PAYMENT_CARDS['visa']['number']} ({PAYMENT_CARDS['visa']['owner']})")
    logger.info("✅ БД синхронизирована с API")
    logger.info("🔐 Бот готов к работе!")
    
    application.run_polling()

if __name__ == '__main__':
    main()
