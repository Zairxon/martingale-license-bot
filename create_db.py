import sqlite3

# Создаем базу данных
conn = sqlite3.connect('bot_secure.db')
c = conn.cursor()

# Создаем таблицы
c.execute('''CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    license_key TEXT UNIQUE,
    license_type TEXT DEFAULT 'none',
    license_status TEXT DEFAULT 'inactive',
    expires_at TEXT,
    bound_account TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    trial_used INTEGER DEFAULT 0,
    key_generated INTEGER DEFAULT 0
)''')

c.execute('''CREATE TABLE license_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT,
    account_number TEXT,
    ip_address TEXT,
    last_check TEXT DEFAULT CURRENT_TIMESTAMP,
    check_count INTEGER DEFAULT 1,
    UNIQUE(license_key, account_number)
)''')

c.execute('''CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    amount INTEGER DEFAULT 100,
    status TEXT DEFAULT 'pending',
    receipt_file_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')

c.execute('''CREATE TABLE ea_files (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    file_data BLOB
)''')

c.execute('''CREATE TABLE api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT,
    account_number TEXT,
    action TEXT,
    result TEXT,
    ip_address TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
conn.close()
print("База данных создана!")
