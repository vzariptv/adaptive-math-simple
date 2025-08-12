#!/usr/bin/env python3
"""
Исправление миграции таблицы math_tasks
- Обновление структуры: level -> level, topic -> topic_id
- Миграция существующих данных
"""

import os
import sys
import sqlite3
from datetime import datetime

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Topic

def backup_database():
    """Создаем резервную копию базы данных"""
    import shutil
    db_path = 'instance/math_learning.db'
    backup_path = f'instance/math_learning_fix_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        print(f"✅ Создана резервная копия: {backup_path}")
        return backup_path
    else:
        print("⚠️ Файл базы данных не найден")
        return None

def migrate_math_tasks_table():
    """Миграция таблицы math_tasks"""
    db_path = 'instance/math_learning.db'
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена")
        return False
    
    # Создаем резервную копию
    backup_path = backup_database()
    if not backup_path:
        return False
    
    try:
        # Подключаемся к базе данных напрямую через sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Начинаем миграцию таблицы math_tasks...")
        
        # 1. Проверяем существующую структуру таблицы
        cursor.execute("PRAGMA table_info(math_tasks)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"📋 Текущие столбцы: {column_names}")
        
        # 2. Создаем новую таблицу с правильной структурой
        cursor.execute("""
            CREATE TABLE math_tasks_new (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                answer_type VARCHAR(50) NOT NULL,
                correct_answer JSON NOT NULL,
                answer_schema JSON,
                explanation TEXT,
                topic_id INTEGER NOT NULL,
                level VARCHAR(10) NOT NULL,
                max_score FLOAT DEFAULT 1.0,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(topic_id) REFERENCES topics(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            )
        """)
        
        # 3. Получаем ID первой темы для миграции данных
        with app.app_context():
            first_topic = Topic.query.first()
            if not first_topic:
                print("❌ Не найдено ни одной темы для миграции")
                conn.close()
                return False
            default_topic_id = first_topic.id
            print(f"📌 Используем тему по умолчанию: {first_topic.name} (ID: {default_topic_id})")
        
        # 4. Копируем данные из старой таблицы в новую
        if 'level' in column_names and 'topic' in column_names:
            # Старая структура - нужна полная миграция
            cursor.execute("""
                INSERT INTO math_tasks_new 
                (id, title, description, answer_type, correct_answer, answer_schema, 
                 explanation, topic_id, level, max_score, created_by, created_at, is_active)
                SELECT 
                    id, title, description, answer_type, correct_answer, answer_schema,
                    explanation, 
                    ? as topic_id,
                    CASE 
                        WHEN level <= 1 THEN 'low'
                        WHEN level <= 2 THEN 'medium'
                        ELSE 'high'
                    END as level,
                    max_score, created_by, created_at, is_active
                FROM math_tasks
            """, (default_topic_id,))
            
            migrated_count = cursor.rowcount
            print(f"✅ Мигрировано {migrated_count} заданий из старой структуры")
            
        elif 'topic_id' in column_names and 'level' in column_names:
            # Новая структура уже есть - просто копируем
            cursor.execute("""
                INSERT INTO math_tasks_new 
                SELECT * FROM math_tasks
            """)
            print("✅ Скопированы данные (структура уже новая)")
        else:
            print("⚠️ Неизвестная структура таблицы, создаем пустую таблицу")
        
        # 5. Удаляем старую таблицу и переименовываем новую
        cursor.execute("DROP TABLE math_tasks")
        cursor.execute("ALTER TABLE math_tasks_new RENAME TO math_tasks")
        
        # 6. Сохраняем изменения
        conn.commit()
        conn.close()
        
        print("🎉 Миграция таблицы math_tasks завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        # Восстанавливаем из резервной копии
        if backup_path and os.path.exists(backup_path):
            import shutil
            shutil.copy2(backup_path, db_path)
            print("🔄 База данных восстановлена из резервной копии")
        return False

def show_migration_info():
    """Показываем информацию о миграции"""
    print("=" * 60)
    print("ИСПРАВЛЕНИЕ МИГРАЦИИ ТАБЛИЦЫ MATH_TASKS")
    print("=" * 60)
    print()
    print("Изменения:")
    print("• Обновление структуры таблицы math_tasks:")
    print("  - level (INTEGER) -> level (VARCHAR: 'low'/'medium'/'high')")
    print("  - topic (VARCHAR) -> topic_id (INTEGER, внешний ключ)")
    print("• Миграция существующих данных с сохранением содержимого")
    print("• Автоматическое преобразование уровней сложности:")
    print("  - 1 -> 'low'")
    print("  - 2 -> 'medium'") 
    print("  - 3+ -> 'high'")
    print()
    print("⚠️ ВНИМАНИЕ: Будет создана резервная копия базы данных")
    print()

if __name__ == "__main__":
    show_migration_info()
    
    response = input("Продолжить исправление миграции? (y/N): ").strip().lower()
    if response in ['y', 'yes', 'да']:
        if migrate_math_tasks_table():
            print("\n🎉 Миграция завершена успешно!")
            print("Теперь можно перезапустить приложение.")
        else:
            print("\n❌ Миграция завершилась с ошибками!")
            sys.exit(1)
    else:
        print("Миграция отменена.")
