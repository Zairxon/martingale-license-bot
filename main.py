#!/usr/bin/env python3
from flask import Flask, jsonify, request
import sqlite3
import logging
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# 🔧 ИСПРАВЛЕНО: ЕДИНАЯ БАЗА ДАННЫХ С TELEGRAM БОТОМ
# ============================================================================

DATABASE_PATH = 'license_system.db'

def init_database():
    """ПОЛНАЯ инициализация базы данных со всеми индексами"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        logger.info("🔧 Создание таблиц базы данных...")
        
        # Создаем таблицы (те же что в telegram боте)
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
        
        # Создаем индексы для быстрого поиска
        logger.info("📊 Создание индексов...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_license_key ON licenses(license_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_number ON licenses(account_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_telegram_user_id ON licenses(telegram_user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON licenses(expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payment_verified ON licenses(payment_verified)')
        
        conn.commit()
        
        # Проверяем структуру
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        logger.info(f"📋 Созданные таблицы: {tables}")
        
        cursor.execute("SELECT COUNT(*) FROM licenses")
        license_count = cursor.fetchone()[0]
        logger.info(f"🔐 Лицензий в базе: {license_count}")
        
        conn.close()
        logger.info("✅ База данных API полностью инициализирована")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД API: {e}")
        raise

def get_db_connection():
    """Получение соединения с базой данных"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# 🔐 API ENDPOINTS
# ============================================================================

@app.route('/', methods=['GET'])
def home():
    """Главная страница API"""
    return jsonify({
        "service": "RFX Trading License API",
        "version": "2.0",
        "status": "active",
        "description": "License verification system for MT5 Expert Advisor",
        "endpoints": {
            "check_license": "/check_license/<license_key>/<account_number>",
            "health": "/health",
            "stats": "/stats"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка состояния сервиса"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM licenses")
        total_licenses = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "total_licenses": total_licenses,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Статистика системы"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM licenses")
        total_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE is_active = 1 AND payment_verified = 1")
        active_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE payment_verified = 0")
        pending_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE expires_at < datetime('now')")
        expired_licenses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT telegram_user_id) FROM licenses")
        total_users = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "total_licenses": total_licenses,
            "active_licenses": active_licenses,
            "pending_payments": pending_payments,
            "expired_licenses": expired_licenses,
            "total_users": total_users,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

@app.route('/check_license/<license_key>/<account_number>', methods=['GET'])
def check_license(license_key, account_number):
    """
    🔐 ОСНОВНАЯ ФУНКЦИЯ: Проверка лицензионного ключа
    """
    logger.info(f"🔍 Проверка лицензии: {license_key} для счета: {account_number}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ищем лицензию в базе данных
        cursor.execute('''
            SELECT license_key, account_number, expires_at, is_active, payment_verified, plan_type
            FROM licenses 
            WHERE license_key = ?
        ''', (license_key,))
        
        license_data = cursor.fetchone()
        
        if not license_data:
            logger.warning(f"❌ Ключ не найден: {license_key}")
            conn.close()
            return jsonify({
                "valid": False,
                "reason": "key_not_found",
                "message": "License key not found in database",
                "license_key": license_key
            }), 404
        
        # Извлекаем данные лицензии
        db_license_key = license_data['license_key']
        db_account_number = license_data['account_number']
        expires_at = license_data['expires_at']
        is_active = license_data['is_active']
        payment_verified = license_data['payment_verified']
        plan_type = license_data['plan_type']
        
        logger.info(f"🔍 Найдена лицензия: {db_license_key}")
        logger.info(f"🔍 Привязанный счет: {db_account_number}")
        logger.info(f"🔍 Оплата подтверждена: {payment_verified}")
        logger.info(f"🔍 Активна: {is_active}")
        logger.info(f"🔍 Истекает: {expires_at}")
        
        # Проверяем подтверждение оплаты
        if not payment_verified:
            logger.warning(f"❌ Оплата не подтверждена: {license_key}")
            conn.close()
            return jsonify({
                "valid": False,
                "reason": "payment_not_verified",
                "message": "Payment not verified",
                "license_key": license_key
            }), 402  # Payment Required
        
        # Проверяем активность
        if not is_active:
            logger.warning(f"❌ Лицензия неактивна: {license_key}")
            conn.close()
            return jsonify({
                "valid": False,
                "reason": "license_inactive",
                "message": "License is inactive",
                "license_key": license_key
            }), 403
        
        # Проверяем срок действия
        try:
            expires_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if expires_date < datetime.now():
                logger.warning(f"❌ Лицензия истекла: {license_key} (истекла: {expires_date})")
                conn.close()
                return jsonify({
                    "valid": False,
                    "reason": "expired",
                    "message": "License has expired",
                    "license_key": license_key,
                    "expired_at": expires_at
                }), 410  # Gone
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга даты: {e}")
        
        # Проверяем привязку к торговому счету
        if db_account_number and db_account_number != account_number:
            logger.warning(f"❌ Неверный торговый счет: {account_number} (ожидается: {db_account_number})")
            conn.close()
            return jsonify({
                "valid": False,
                "reason": "wrong_account",
                "message": "License is bound to different account",
                "license_key": license_key,
                "bound_account": db_account_number,
                "requested_account": account_number
            }), 403
        
        # Если счет не привязан, привязываем его
        if not db_account_number:
            logger.info(f"🔗 Привязываем лицензию {license_key} к счету {account_number}")
            cursor.execute('''
                UPDATE licenses 
                SET account_number = ? 
                WHERE license_key = ?
            ''', (account_number, license_key))
            conn.commit()
            
        conn.close()
        
        # ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ
        logger.info(f"✅ Лицензия действительна: {license_key} для счета: {account_number}")
        
        return jsonify({
            "valid": True,
            "message": "License is valid",
            "license_key": license_key,
            "account_number": account_number,
            "plan_type": plan_type,
            "expires_at": expires_at,
            "verified_at": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка проверки лицензии: {e}")
        return jsonify({
            "valid": False,
            "reason": "server_error",
            "message": "Internal server error",
            "error": str(e)
        }), 500

@app.route('/check_license/<license_key>', methods=['GET'])
def check_license_simple(license_key):
    """Упрощенная проверка лицензии без торгового счета"""
    return check_license(license_key, "")

# ============================================================================
# 🔧 ДОПОЛНИТЕЛЬНЫЕ API ENDPOINTS ДЛЯ АДМИНИСТРИРОВАНИЯ
# ============================================================================

@app.route('/admin/licenses', methods=['GET'])
def admin_get_licenses():
    """Админ: Получить все лицензии"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT license_key, account_number, created_at, expires_at, 
                   is_active, payment_verified, plan_type, telegram_user_id
            FROM licenses 
            ORDER BY created_at DESC
            LIMIT 100
        ''')
        
        licenses = []
        for row in cursor.fetchall():
            licenses.append({
                "license_key": row['license_key'],
                "account_number": row['account_number'],
                "created_at": row['created_at'],
                "expires_at": row['expires_at'],
                "is_active": bool(row['is_active']),
                "payment_verified": bool(row['payment_verified']),
                "plan_type": row['plan_type'],
                "telegram_user_id": row['telegram_user_id']
            })
        
        conn.close()
        
        return jsonify({
            "total": len(licenses),
            "licenses": licenses
        })
        
    except Exception as e:
        logger.error(f"Admin licenses error: {e}")
        return jsonify({"error": "Failed to get licenses"}), 500

@app.route('/admin/verify_payment/<license_key>', methods=['POST'])
def admin_verify_payment(license_key):
    """Админ: Подтвердить оплату лицензии"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем существование лицензии
        cursor.execute('SELECT id FROM licenses WHERE license_key = ?', (license_key,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "License not found"}), 404
        
        # Подтверждаем оплату
        cursor.execute('''
            UPDATE licenses 
            SET payment_verified = 1 
            WHERE license_key = ?
        ''', (license_key,))
        
        cursor.execute('''
            UPDATE payments 
            SET verified = 1 
            WHERE license_key = ?
        ''', (license_key,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Админ подтвердил оплату: {license_key}")
        
        return jsonify({
            "success": True,
            "message": "Payment verified successfully",
            "license_key": license_key
        })
        
    except Exception as e:
        logger.error(f"Admin verify payment error: {e}")
        return jsonify({"error": "Failed to verify payment"}), 500

# ============================================================================
# 🚀 ЗАПУСК СЕРВЕРА
# ============================================================================

if __name__ == '__main__':
    # Инициализируем базу данных при запуске
    init_database()
    
    logger.info("🚀 Запуск RFX Trading License API Server")
    logger.info("✅ База данных инициализирована")
    logger.info("🔐 API готов к работе!")
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
