#!/usr/bin/env python3
"""
Утилита для очистки базы данных
Удаляет все данные из таблиц, но сохраняет структуру
"""

from app import app
from models import db, User, MathTask, TaskAttempt

def clear_database():
    """Очищает все данные из базы данных"""
    with app.app_context():
        try:
            print("🗑️  Начинаем очистку базы данных...")
            
            # Удаляем все данные в правильном порядке (учитывая внешние ключи)
            print("   Удаляем попытки решения заданий...")
            TaskAttempt.query.delete()
            
            print("   Удаляем задания...")
            MathTask.query.delete()
            
            print("   Удаляем пользователей...")
            User.query.delete()
            
            # Сохраняем изменения
            db.session.commit()
            
            print("✅ База данных успешно очищена!")
            print("   Все таблицы пусты, но структура сохранена.")
            
        except Exception as e:
            print(f"❌ Ошибка при очистке базы данных: {e}")
            db.session.rollback()

def recreate_admin():
    """Создает администратора после очистки"""
    with app.app_context():
        try:
            print("👤 Создаем администратора...")
            
            admin = User(
                username='CalmAndManage',
                email='admin@mathsystem.local',
                role='admin'
            )
            admin.set_password('KeepMathAlive')
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Администратор создан!")
            print("   Логин: CalmAndManage")
            print("   Пароль: KeepMathAlive")
            
        except Exception as e:
            print(f"❌ Ошибка при создании администратора: {e}")
            db.session.rollback()

if __name__ == "__main__":
    print("=" * 50)
    print("🧹 ОЧИСТКА БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    response = input("Вы уверены, что хотите очистить ВСЮ базу данных? (yes/no): ")
    
    if response.lower() in ['yes', 'y', 'да', 'д']:
        clear_database()
        
        create_admin = input("Создать администратора? (yes/no): ")
        if create_admin.lower() in ['yes', 'y', 'да', 'д']:
            recreate_admin()
    else:
        print("❌ Операция отменена.")
    
    print("=" * 50)
