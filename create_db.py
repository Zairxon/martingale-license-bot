#!/usr/bin/env python3
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta

# ============================================================================
# 🔧 ИСПРАВЛЕНО: ЕДИНАЯ СХЕМА БД ДЛЯ БОТА И API
# ============================================================================

DATABASE_PATH = 'license_system.db'

def create_database():
    """Создание единой базы данных для бота и API"""
    print("🔧 Создание единой базы данных...")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # ============================================================================
        # 📋 ТАБЛИЦА ЛИЦЕНЗИЙ (ОСНОВНАЯ)
        # ============================================================================
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
        
        # ============================================================================
        # 👥 ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
        # ============================================================================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_licenses INTEGER DEFAULT 0
            )
        ''')
        
        # ============================================================================
        # 💰 ТАБЛИЦА ПЛАТЕЖЕЙ
        # ============================================================================
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
        
        # ============================================================================
        # 📊 СОЗДАНИЕ ИНДЕКСОВ ДЛЯ БЫСТРОГО ПОИСКА
        # ============================================================================
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_license_key ON licenses(license_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_number ON licenses(account_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_telegram_user_id ON licenses(telegram_user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON licenses(expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_verified ON licenses(payment_verified)')
        
        conn.commit()
        print("✅ База данных создана успешно!")
        
        # ============================================================================
        # 📋 ИНФОРМАЦИЯ О ТАБЛИЦАХ
        # ============================================================================
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 Созданные таблицы: {[table[0] for table in tables]}")
        
        cursor.execute("SELECT COUNT(*) FROM licenses")
        license_count = cursor.fetchone()[0]
        print(f"🔐 Лицензий в базе: {license_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка создания базы данных: {e}")
        return False
    
    return True

def generate_test_license():
    """Генерация тестового лицензионного ключа"""
    timestamp = str(int(time.time()))[-6:]
    random_part = hashlib.md5(b"test_license_key").hexdigest()[:12].upper()
    
    # Формат: RFX-XXXX-XXXX-XXXX-XXX-XX
    key_parts = [
        "RFX",
        random_part[:4],
        random_part[4:8], 
        random_part[8:12],
        timestamp[:3],
        timestamp[3:5]
    ]
    
    return "-".join(key_parts)

def add_test_data():
    """Добавление тестовых данных"""
    print("🧪 Добавление тестовых данных...")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Тестовая лицензия
        test_license = generate_test_license()
        expires_at = datetime.now() + timedelta(days=30)
        
        cursor.execute('''
            INSERT OR IGNORE INTO licenses 
            (license_key, plan_type, expires_at, is_active, payment_verified, telegram_user_id)
            VALUES (?, ?, ?, 1, 1, ?)
        ''', (test_license, "1_month", expires_at, "12345"))
        
        # Тестовый пользователь
        cursor.execute('''
            INSERT OR IGNORE INTO users 
            (telegram_user_id, username, total_licenses)
            VALUES (?, ?, 1)
        ''', ("12345", "test_user"))
        
        # Тестовый платеж
        cursor.execute('''
            INSERT OR IGNORE INTO payments 
            (telegram_user_id, license_key, amount, plan_type, verified)
            VALUES (?, ?, 30.0, ?, 1)
        ''', ("12345", test_license, "1_month"))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Тестовые данные добавлены!")
        print(f"🔐 Тестовый ключ: {test_license}")
        print(f"📅 Действует до: {expires_at.strftime('%d.%m.%Y %H:%M')}")
        
        return test_license
        
    except Exception as e:
        print(f"❌ Ошибка добавления тестовых данных: {e}")
        return None

def verify_database():
    """Проверка целостности базы данных"""
    print("🔍 Проверка базы данных...")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Проверяем таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        
        required_tables = ['licenses', 'users', 'payments']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ Отсутствующие таблицы: {missing_tables}")
            return False
        
        # Проверяем структуру таблицы licenses
        cursor.execute("PRAGMA table_info(licenses)")
        columns = [column[1] for column in cursor.fetchall()]
        
        required_columns = [
            'id', 'license_key', 'account_number', 'created_at', 
            'expires_at', 'is_active', 'plan_type', 'telegram_user_id', 
            'payment_verified'
        ]
        
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            print(f"❌ Отсутствующие колонки в licenses: {missing_columns}")
            return False
        
        # Статистика
        cursor.execute("SELECT COUNT(*) FROM licenses")
        total_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE payment_verified = 1")
        verified_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        print(f"✅ База данных корректна!")
        print(f"📊 Статистика:")
        print(f"   • Всего лицензий: {total_licenses}")
        print(f"   • Подтвержденных: {verified_licenses}")
        print(f"   • Пользователей: {total_users}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка проверки базы данных: {e}")
        return False

def main():
    """Основная функция"""
    print("🚀 Инициализация системы лицензирования RFX Trading")
    print("=" * 60)
    
    # Создаем базу данных
    if create_database():
        print("✅ База данных создана")
    else:
        print("❌ Ошибка создания базы данных")
        return
    
    # Проверяем базу данных
    if verify_database():
        print("✅ База данных проверена")
    else:
        print("❌ Ошибка проверки базы данных")
        return
    
    # Добавляем тестовые данные
    test_license = add_test_data()
    
    print("=" * 60)
    print("🎉 Система лицензирования готова к работе!")
    print("📋 Следующие шаги:")
    print("   1. Запустите Telegram бота: python telegram_bot_FIXED.py")
    print("   2. Запустите API сервер: python main_FIXED.py")
    print("   3. Используйте тестовый ключ в MT5 советнике")
    
    if test_license:
        print(f"🔐 Тестовый ключ: {test_license}")
    
    print("=" * 60)

if __name__ == '__main__':
    main()
