#!/usr/bin/env python3
import os
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
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
except ImportError:
    print("❌ Ошибка: установите python-telegram-bot")
    print("pip install python-telegram-bot aiohttp")
    exit(1)

# ===============================
# КОНФИГУРАЦИЯ
# ===============================
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 295698267
API_BASE_URL = "https://web-production-969a6.up.railway.app"  # Ваш Railway URL

# Банковские реквизиты
VISA_CARD = "4278 3100 2430 7167"
HUMO_CARD = "9860 1001 2541 9018"
CARD_OWNER = "Asqarov Rasulbek"

print("🚀 Запуск бота с API интеграцией...")
print(f"👨‍💼 Admin ID: {ADMIN_ID}")
print(f"🌐 API URL: {API_BASE_URL}")

# ===============================
# API ФУНКЦИИ
# ===============================
async def api_request(endpoint, method="GET", data=None):
    """Выполняет HTTP запрос к API"""
    try:
        url = f"{API_BASE_URL}/{endpoint.lstrip('/')}"
        
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API ошибка: {response.status}")
                        return {"error": f"API ошибка: {response.status}"}
            
            elif method == "POST":
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API ошибка: {response.status}")
                        return {"error": f"API ошибка: {response.status}"}
    
    except Exception as e:
        logger.error(f"Ошибка API запроса: {e}")
        return {"error": f"Сетевая ошибка: {e}"}

async def check_api_health():
    """Проверяет здоровье API"""
    result = await api_request("/health")
    return result.get("status") == "healthy"

async def check_license_api(license_key, account_number):
    """Проверяет лицензию через API"""
    endpoint = f"/check_license/{license_key}/{account_number}"
    return await api_request(endpoint)

# ===============================
# ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (временное)
# ===============================
# Хранилище для данных пользователей (в памяти)
users_data = {}
payments_data = {}
ea_file_data = None

def get_user_data(user_id):
    """Получает данные пользователя"""
    if user_id not in users_data:
        users_data[user_id] = {
            'license_key': None,
            'license_type': 'none',
            'license_status': 'inactive',
            'trial_used': False,
            'payment_id': None
        }
    return users_data[user_id]

def generate_user_key(user_id):
    """Генерирует постоянный ключ для пользователя (упрощенная версия)"""
    import hashlib
    secret_data = f"{user_id}_RFX_SECRET_2025_PERMANENT"
    hash_key = hashlib.sha256(secret_data.encode()).hexdigest()[:16].upper()
    key = f"RFX-{hash_key[:4]}-{hash_key[4:8]}-{hash_key[8:12]}-{hash_key[12:16]}"
    return key

def create_trial_license(user_id):
    """Создает пробную лицензию"""
    user_data = get_user_data(user_id)
    
    if user_data['trial_used']:
        return None, "Вы уже использовали пробный период"
    
    user_data['license_key'] = generate_user_key(user_id)
    user_data['license_type'] = 'trial'
    user_data['license_status'] = 'active'
    user_data['trial_used'] = True
    user_data['expires_at'] = (datetime.now() + timedelta(days=3)).isoformat()
    
    return user_data['license_key'], None

def create_payment_request(user_id):
    """Создает заявку на оплату"""
    import time
    payment_id = int(time.time())
    payments_data[payment_id] = {
        'user_id': user_id,
        'amount': 100,
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    return payment_id

def approve_payment(payment_id):
    """Одобряет платеж"""
    if payment_id not in payments_data:
        return None
    
    payment = payments_data[payment_id]
    user_id = payment['user_id']
    user_data = get_user_data(user_id)
    
    # Создаем или продлеваем лицензию
    if not user_data['license_key']:
        user_data['license_key'] = generate_user_key(user_id)
    
    user_data['license_type'] = 'monthly'
    user_data['license_status'] = 'active'
    user_data['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
    
    payment['status'] = 'approved'
    
    return user_data['license_key'], user_id, user_data['expires_at']

# ===============================
# УТИЛИТЫ
# ===============================
def is_admin(user_id):
    return int(user_id) == ADMIN_ID

def format_datetime(dt_string):
    try:
        dt = datetime.fromisoformat(dt_string)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return "Неизвестно"

def check_license_expired(expires_at):
    if not expires_at:
        return False
    try:
        expires_dt = datetime.fromisoformat(expires_at)
        return datetime.now() > expires_dt
    except:
        return True

# ===============================
# КЛАВИАТУРЫ
# ===============================
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🆓 3 дня БЕСПЛАТНО + EA файл", callback_data="trial")],
        [InlineKeyboardButton("💰 Купить месяц - 100 USD", callback_data="buy")],
        [InlineKeyboardButton("📊 Мой статус", callback_data="status")],
        [InlineKeyboardButton("📖 Описание EA", callback_data="info")],
        [InlineKeyboardButton("🔍 Тест API", callback_data="test_api")]
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

🎯 Как начать:
🆓 Пробный период: 3 дня + EA файл бесплатно
📈 Тестируйте на демо или реальном счете
💰 Месячная подписка: 100 USD (после тестирования)

🔐 Система защиты:
• Уникальный ключ для каждого пользователя
• Привязка ключа к торговому счету
• Защита от перепродажи лицензий
• Встроенная проверка лицензий через API

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""

WELCOME_TEXT = f"""🤖 Добро пожаловать в RFX Trading!

🎯 Автоматическая торговля
📊 Стратегия Богданова
⚡ VPS оптимизация
🔐 Защищенная лицензионная система
🌐 API интеграция с Railway

💡 Варианты:
🆓 Пробный период - 3 дня бесплатно + EA файл
💰 Месячная подписка - 100 USD

🎯 Логика работы:
1. Берете пробную лицензию на 3 дня
2. Скачиваете и тестируете EA
3. Если понравится - покупаете подписку
4. Ключ привязывается к вашему торговому счету

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""

# ===============================
# ОБРАБОТЧИКИ КОМАНД
# ===============================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(WELCOME_TEXT, reply_markup=main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
        
        # Проверяем API
        api_healthy = await check_api_health()
        api_status = "✅ Работает" if api_healthy else "❌ Недоступен"
        
        # Статистика из локального хранилища
        total_users = len(users_data)
        active_licenses = sum(1 for u in users_data.values() 
                            if u['license_status'] == 'active' and not check_license_expired(u.get('expires_at')))
        trial_licenses = sum(1 for u in users_data.values() if u['license_type'] == 'trial')
        monthly_licenses = sum(1 for u in users_data.values() if u['license_type'] == 'monthly')
        
        ea_status = "✅ Загружен" if ea_file_data else "❌ Не загружен"
        
        text = f"""📊 Статистика бота
🌐 API статус: {api_status}
🔗 API URL: {API_BASE_URL}

👥 Всего пользователей: {total_users}
✅ Активных лицензий: {active_licenses}
🆓 Пробных: {trial_licenses}
💰 Месячных: {monthly_licenses}
💵 Доход: {len([p for p in payments_data.values() if p['status'] == 'approved']) * 100} USD
📁 EA файл: {ea_status}

🔐 СИСТЕМА ЗАЩИТЫ:
• Постоянные ключи пользователей
• API проверка лицензий
• Привязка к торговому счету
• Защита от перепродажи

💡 Для загрузки EA файла отправьте .ex5 файл боту"""
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Ошибка в stats: {e}")

async def test_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для тестирования API проверки лицензий"""
    try:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Использование: /test_license <ключ> <номер_счета>")
            return
        
        license_key = context.args[0]
        account_number = context.args[1]
        
        await update.message.reply_text("🔍 Проверяю лицензию через API...")
        
        result = await check_license_api(license_key, account_number)
        
        if result.get("valid"):
            text = f"""✅ Лицензия действительна!
🔑 Ключ: {license_key}
💼 Счет: {account_number}
📊 Результат: {result}"""
        else:
            text = f"""❌ Лицензия недействительна!
🔑 Ключ: {license_key}
💼 Счет: {account_number}
❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"""
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Ошибка в test_license_command: {e}")

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

🔑 Ваш ПОСТОЯННЫЙ ключ: `{key}`
⏰ Срок: 3 дня
📁 Можете СРАЗУ скачать и тестировать EA!

🔐 ВАЖНО:
• Ключ будет привязан к вашему торговому счету
• Один ключ = один торговый счет
• После тестирования тот же ключ продлевается

🎯 Как тестировать:
1. Скачайте EA файл
2. Установите на MT4/MT5  
3. Введите ключ в настройки EA
4. Тестируйте 3 дня
5. Если понравится - купите подписку

💰 После тестирования: месячная подписка 100 USD"""
                
                keyboard = [[InlineKeyboardButton("📁 Скачать EA для тестирования", callback_data="download")]]
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "buy":
            payment_id = create_payment_request(user_id)
            context.user_data['payment_id'] = payment_id
            
            user_data = get_user_data(user_id)
            user_key = user_data['license_key'] or generate_user_key(user_id)
            
            text = f"""💳 ОПЛАТА ЛИЦЕНЗИИ

💵 Сумма: 100 USD (1 месяц)
🔑 Ваш ключ: `{user_key}`

💳 РЕКВИЗИТЫ:
🏦 VISA: `{VISA_CARD}`
🏦 HUMO: `{HUMO_CARD}`
👤 Владелец: {CARD_OWNER}

📝 Инструкция:
1. Переведите 100 USD на любую карту
2. Сделайте скриншот чека
3. Нажмите "Я оплатил"
4. Отправьте фото чека

🔐 После оплаты тот же ключ будет продлен на месяц!
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
                
            await query.message.reply_text("""📸 Отправьте чек об оплате

Пришлите фото чека как обычное сообщение.
✅ Чек должен содержать:
• Сумму платежа 100 USD
• Дату и время перевода
• Номер карты получателя

⏱️ Время обработки: 10-30 минут
🔔 Вы получите уведомление о результате
🔐 Ваш ключ будет продлен автоматически""")
            
            context.user_data['waiting_receipt'] = True
        
        elif data == "status":
            user_data = get_user_data(user_id)
            
            if not user_data['license_key']:
                text = """❌ Лицензия не найдена

Вы можете:
🆓 Получить пробную лицензию на 3 дня + EA файл
💰 Купить месячную подписку за 100 USD"""
                await query.message.reply_text(text, reply_markup=main_keyboard())
            else:
                # Проверяем истечение
                is_expired = check_license_expired(user_data.get('expires_at'))
                status = "expired" if is_expired else user_data['license_status']
                
                status_emoji = "✅" if status == "active" else "❌"
                type_emoji = "🆓" if user_data['license_type'] == "trial" else "💰"
                
                text = f"""{status_emoji} Статус лицензии

🔑 Ваш ПОСТОЯННЫЙ ключ: `{user_data['license_key']}`
{type_emoji} Тип: {user_data['license_type'].title()}
📊 Статус: {status.title()}"""
                
                if user_data.get('expires_at'):
                    if status == "active":
                        text += f"\n⏰ Действует до: {format_datetime(user_data['expires_at'])}"
                    else:
                        text += f"\n❌ Истекла: {format_datetime(user_data['expires_at'])}"
                
                text += f"\n\n🔐 ЗАЩИТА: Ключ уникален и привязывается к торговому счету"
                text += f"\n🌐 API проверка через Railway"
                
                keyboard = []
                if status == "active":
                    download_text = "📁 Скачать EA для тестирования" if user_data['license_type'] == "trial" else "📁 Скачать EA"
                    keyboard.append([InlineKeyboardButton(download_text, callback_data="download")])
                if user_data['license_type'] == "trial" or status == "expired":
                    keyboard.append([InlineKeyboardButton("💰 Купить подписку", callback_data="buy")])
                
                await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "info":
            await query.message.reply_text(EA_INFO, reply_markup=main_keyboard())
        
        elif data == "back":
            await query.message.reply_text(WELCOME_TEXT, reply_markup=main_keyboard())
        
        elif data == "test_api":
            await query.message.reply_text("🔍 Тестирую API...")
            
            # Проверяем здоровье API
            is_healthy = await check_api_health()
            
            if is_healthy:
                # Тестируем проверку лицензии
                test_result = await check_license_api("RFX-TEST-TEST-TEST", "12345")
                
                text = f"""✅ API работает!
🌐 URL: {API_BASE_URL}
💚 Статус: Здоров
🔍 Тест проверки: {test_result.get('valid', False)}
📊 Ответ API: {test_result}"""
            else:
                text = f"""❌ API недоступен!
🌐 URL: {API_BASE_URL}
💔 Статус: Ошибка
⚠️ Проверьте Railway deployment"""
            
            await query.message.reply_text(text, reply_markup=main_keyboard())
        
        elif data == "download":
            user_data = get_user_data(user_id)
            
            if not user_data['license_key']:
                await query.message.reply_text("❌ У вас нет лицензии!", reply_markup=main_keyboard())
                return
            
            # Проверяем не истекла ли лицензия
            if check_license_expired(user_data.get('expires_at')):
                if user_data['license_type'] == "trial":
                    await query.message.reply_text("""❌ Пробный период истек!
🎯 Понравился советник? 
💰 Купите месячную подписку за 100 USD""", reply_markup=main_keyboard())
                else:
                    await query.message.reply_text("""❌ Подписка истекла!
💰 Продлите подписку за 100 USD""", reply_markup=main_keyboard())
                return
            
            # Проверяем наличие файла
            if not ea_file_data:
                await query.message.reply_text("""❌ EA файл не найден!
🔧 Возможные причины:
• Админ еще не загрузил файл
• Файл поврежден
📞 Обратитесь к @rasul_asqarov_rfx""", reply_markup=main_keyboard())
                return
            
            try:
                # Отправляем файл
                file_obj = BytesIO(ea_file_data['data'])
                file_obj.name = ea_file_data['filename']
                
                if user_data['license_type'] == "trial":
                    caption_text = f"""🤖 EA для тестирования загружен!

🔑 Ваш ПОСТОЯННЫЙ ключ: `{user_data['license_key']}`
📊 Стратегия: Богданова
⏰ Срок тестирования: 3 дня

🎯 Инструкция:
1. Установите EA на MT4/MT5
2. В настройках EA введите ключ: {user_data['license_key']}
3. EA автоматически привяжется к вашему счету
4. Тестируйте 3 дня

🔐 ВАЖНО: Ключ привяжется к первому торговому счету!
💰 Понравилось? Купите подписку за 100 USD!

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""
                else:
                    caption_text = f"""🤖 Торговый советник загружен!

🔑 Ваш ПОСТОЯННЫЙ ключ: `{user_data['license_key']}`
📊 Стратегия: Богданова
⚡ Оптимизирован для VPS

🎯 Инструкция:
1. Установите EA на MT4/MT5
2. В настройках EA введите ключ: {user_data['license_key']}
3. EA работает месяц до истечения лицензии

🔐 ЗАЩИТА: Ключ привязан к вашему торговому счету
🌐 API проверка через Railway

📞 Поддержка: @rasul_asqarov_rfx
👥 Группа: t.me/RFx_Group"""
                
                await query.message.reply_document(
                    document=file_obj,
                    filename=ea_file_data['filename'],
                    caption=caption_text,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Ошибка отправки файла: {e}")
                await query.message.reply_text("""❌ Ошибка при отправке файла!
🔧 Попробуйте:
• Обновить Telegram
• Перезапустить приложение
• Попробовать позже
📞 Если проблема остается: @rasul_asqarov_rfx""", reply_markup=main_keyboard())
        
        elif data.startswith("approve_"):
            if not is_admin(user_id):
                return
            
            payment_id = int(data.split("_")[1])
            result = approve_payment(payment_id)
            
            if result:
                license_key, target_user_id, expires = result
                
                # Уведомляем пользователя
                try:
                    keyboard = [[InlineKeyboardButton("📁 Скачать EA", callback_data="download")]]
                    
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"""🎉 ПЛАТЕЖ ПОДТВЕРЖДЕН!

✅ Месячная лицензия активирована!
🔑 Ваш ключ: `{license_key}`
⏰ Действует до: {format_datetime(expires)}
🔐 Ключ остается тот же - он ПОСТОЯННЫЙ!
📁 Теперь можете скачать EA!""",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление: {e}")
                
                await query.message.edit_text(f"""✅ Платеж одобрен!

🔑 Ключ: `{license_key}`
👤 Пользователь уведомлен
⏰ Лицензия до: {format_datetime(expires)}
🔐 Постоянный ключ продлен""", parse_mode='Markdown')
        
        elif data.startswith("reject_"):
            if not is_admin(user_id):
                return
            
            payment_id = int(data.split("_")[1])
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
        
        user_data = get_user_data(user_id)
        user_key = user_data['license_key'] or generate_user_key(user_id)
        
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
🔑 Ключ пользователя: {user_key}
💵 Сумма: 100 USD (1 месяц)
🆔 Заявка №{payment_id}

💳 Реквизиты для проверки:
VISA: {VISA_CARD}
HUMO: {HUMO_CARD}
Владелец: {CARD_OWNER}

🔐 ВАЖНО: При одобрении тот же ключ будет продлен!""",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            await update.message.reply_text("""✅ Чек получен и отправлен на проверку!

⏱️ Время обработки: 10-30 минут
🔔 Вы получите уведомление о результате
🔐 Ваш постоянный ключ будет продлен
📞 Вопросы: @rasul_asqarov_rfx""", reply_markup=main_keyboard())
            
            context.user_data.pop('waiting_receipt', None)
            context.user_data.pop('payment_id', None)
            
        except Exception as e:
            logger.error(f"Ошибка отправки админу: {e}")
            await update.message.reply_text("❌ Ошибка обработки. Обратитесь к @rasul_asqarov_rfx")
            
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
        
        document = update.message.document
        
        if not document.file_name.lower().endswith('.ex5'):
            await update.message.reply_text("❌ Можно загружать только файлы .ex5!")
            return
        
        if document.file_size > 20 * 1024 * 1024:
            await update.message.reply_text("❌ Файл слишком большой! Максимум 20MB.")
            return
        
        await update.message.reply_text("⏳ Загружаю файл...")
        
        try:
            file = await document.get_file()
            file_data = await file.download_as_bytearray()
            
            if not file_data:
                await update.message.reply_text("❌ Не удалось скачать файл!")
                return
            
            # Сохраняем в глобальную переменную
            global ea_file_data
            ea_file_data = {
                'filename': document.file_name,
                'data': file_data
            }
            
            await update.message.reply_text(f"""✅ EA файл успешно загружен и готов к раздаче!

📁 Имя файла: {document.file_name}
📊 Размер: {len(file_data):,} байт
🎯 Теперь пользователи смогут скачивать этот файл!
🔐 Файл защищен системой лицензирования
🌐 Интеграция с API на Railway

Проверьте: /stats""")
            
            logger.info(f"Админ {update.effective_user.id} загрузил файл {document.file_name}")
            
        except Exception as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            await update.message.reply_text("❌ Ошибка при скачивании файла с серверов Telegram!")
            
    except Exception as e:
        logger.error(f"Ошибка в document_handler: {e}")

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
    
    print("🔄 Инициализация бота с API интеграцией...")
    
    # Создание приложения
    app_bot = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков
    app_bot.add_handler(CommandHandler("start", start_command))
    app_bot.add_handler(CommandHandler("stats", stats_command))
    app_bot.add_handler(CommandHandler("test_license", test_license_command))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app_bot.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    
    # Обработчик ошибок
    app_bot.add_error_handler(error_handler)
    
    print("✅ Бот успешно запущен!")
    print("=" * 60)
    print("🔧 КОНФИГУРАЦИЯ:")
    print(f"🌐 API URL: {API_BASE_URL}")
    print(f"👨‍💼 Админ ID: {ADMIN_ID}")
    print(f"💰 Цена за месяц: 100 USD")
    print("=" * 60)
    print("🔐 СИСТЕМА ЗАЩИТЫ:")
    print("• Постоянные ключи пользователей")
    print("• API проверка через Railway")
    print("• Привязка ключей к торговым счетам")
    print("• Защита от перепродажи")
    print("=" * 60)
    print("📋 ДОСТУПНЫЕ КОМАНДЫ:")
    print("/start - Главное меню")
    print("/stats - Статистика (только админ)")
    print("/test_license <ключ> <счет> - Тест API (только админ)")
    print("=" * 60)
    print("⚡ Бот готов к работе с API!")
    
    try:
        app_bot.run_polling(
            drop_pending_updates=True,
            pool_timeout=60,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30
        )
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        print("❌ Не удалось запустить бота!")

if __name__ == '__main__':
    main()
