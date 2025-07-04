from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/')
def home():
    return {
        "service": "License Bot API",
        "endpoints": [
            "/health",
            "/check_license/<key>/<account>"
        ]
    }

@app.route('/health')
def health_check():
    return {
        "status": "healthy", 
        "timestamp": "2025-06-26T07:55:50+05:00",
        "database": "connected"
    }
@app.route('/check_license/<key>/<account>')
def check_license(key, account):
        
    # Подключение к той же базе данных
    conn = sqlite3.connect('bot_secure.db')
    c = conn.cursor()
    
    # Проверка лицензии (упрощенная)
    c.execute('SELECT license_status, expires_at FROM users WHERE license_key = ?', (key,))
    result = c.fetchone()
    
    if result and result[0] == 'active':
        return jsonify({"valid": True, "status": "active"})
    else:
        return jsonify({"valid": False, "error": "invalid"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
