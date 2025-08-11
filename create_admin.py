#!/usr/bin/env python3
"""
Скрипт для создания администратора
"""
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User

load_dotenv()

def main():
    app = create_app()
    
    with app.app_context():
        # Проверяем, есть ли уже администратор
        existing_admin = User.query.filter_by(role='admin').first()
        if existing_admin:
            print(f"Администратор уже существует: {existing_admin.username}")
            return
        
        # Создаем администратора
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123").strip()
        
        admin = User(
            username=admin_email.split("@")[0],
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            role="admin",
            is_active=True,
            first_name="Admin",
            last_name="User"
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"✅ Администратор создан:")
        print(f"   Email: {admin.email}")
        print(f"   Username: {admin.username}")
        print(f"   Password: {admin_password}")

if __name__ == "__main__":
    main()
