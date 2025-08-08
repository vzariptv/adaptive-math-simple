#!/usr/bin/env python3
"""
Миграция для установки last_login для существующих пользователей
"""

from app import app
from models import User, db

def migrate_last_login():
    """Установить last_login для всех пользователей, у которых оно равно None"""
    with app.app_context():
        # Найти всех пользователей с last_login = None
        users_without_last_login = User.query.filter(User.last_login.is_(None)).all()
        
        print(f"Найдено пользователей без last_login: {len(users_without_last_login)}")
        
        for user in users_without_last_login:
            # Устанавливаем last_login равным времени создания пользователя
            user.last_login = user.created_at
            print(f"Обновлен пользователь {user.username}: last_login = {user.last_login}")
        
        # Сохраняем изменения
        db.session.commit()
        print("Миграция завершена успешно!")

if __name__ == '__main__':
    migrate_last_login()
