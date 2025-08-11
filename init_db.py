#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных и создания администратора
"""
import os
import sqlite3
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

def create_database():
    """Создает базу данных и таблицы"""
    # Подключаемся к базе данных (создастся автоматически если не существует)
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Создаем таблицу пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'student',
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Создаем таблицу задач
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS math_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            correct_answer TEXT NOT NULL,
            difficulty_level INTEGER DEFAULT 1,
            topic VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES user (id)
        )
    ''')
    
    # Создаем таблицу попыток решения
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            user_answer TEXT,
            is_correct BOOLEAN,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user (id),
            FOREIGN KEY (task_id) REFERENCES math_task (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана успешно")

def create_admin():
    """Создает администратора"""
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли уже администратор
    cursor.execute("SELECT * FROM user WHERE role = 'admin'")
    existing_admin = cursor.fetchone()
    
    if existing_admin:
        print(f"ℹ️  Администратор уже существует")
        conn.close()
        return
    
    # Получаем данные администратора из переменных окружения
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123").strip()
    admin_username = admin_email.split("@")[0]
    
    # Создаем хеш пароля
    password_hash = generate_password_hash(admin_password)
    
    # Вставляем администратора
    cursor.execute('''
        INSERT INTO user (username, email, password_hash, role, first_name, last_name, is_active)
        VALUES (?, ?, ?, 'admin', 'Admin', 'User', 1)
    ''', (admin_username, admin_email, password_hash))
    
    conn.commit()
    conn.close()
    
    print("✅ Администратор создан успешно:")
    print(f"   Email: {admin_email}")
    print(f"   Username: {admin_username}")
    print(f"   Password: {admin_password}")

def main():
    print("🚀 Инициализация базы данных...")
    create_database()
    create_admin()
    print("✅ Инициализация завершена!")

if __name__ == "__main__":
    main()
