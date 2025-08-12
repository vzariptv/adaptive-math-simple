#!/usr/bin/env python3
"""
Миграция базы данных к новой архитектуре адаптивного механизма
- Удаление таблицы student_profiles
- Обновление структуры math_tasks (level -> level, topic -> topic_id)
- Создание новых таблиц: topics, topic_level_configs, student_evaluation_logs, 
  student_topic_progress, evaluation_system_config
"""

import os
import sys
from datetime import datetime

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Topic, TopicLevelConfig, EvaluationSystemConfig

def backup_database():
    """Создаем резервную копию базы данных"""
    import shutil
    db_path = 'instance/math_learning.db'
    backup_path = f'instance/math_learning_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        print(f"✅ Создана резервная копия: {backup_path}")
    else:
        print("⚠️ Файл базы данных не найден")

def migrate_database():
    """Выполняем миграцию базы данных"""
    with app.app_context():
        print("🔄 Начинаем миграцию базы данных...")
        
        # 1. Создаем резервную копию
        backup_database()
        
        # 2. Удаляем старую таблицу student_profiles если существует
        try:
            db.engine.execute("DROP TABLE IF EXISTS student_profiles")
            print("✅ Удалена таблица student_profiles")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении student_profiles: {e}")
        
        # 3. Создаем новые таблицы
        try:
            db.create_all()
            print("✅ Созданы новые таблицы")
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            return False
            
        # 4. Создаем базовую конфигурацию системы оценки
        try:
            config = EvaluationSystemConfig.query.first()
            if not config:
                config = EvaluationSystemConfig()
                db.session.add(config)
                db.session.commit()
                print("✅ Создана базовая конфигурация системы оценки")
            else:
                print("ℹ️ Конфигурация системы оценки уже существует")
        except Exception as e:
            print(f"❌ Ошибка при создании конфигурации: {e}")
            return False
            
        # 5. Создаем базовые темы для демонстрации
        try:
            create_demo_topics()
        except Exception as e:
            print(f"❌ Ошибка при создании демо-тем: {e}")
            return False
            
        print("🎉 Миграция завершена успешно!")
        return True

def create_demo_topics():
    """Создаем демонстрационные темы"""
    demo_topics = [
        {
            'code': 'quadratic_equations',
            'name': 'Квадратные уравнения',
            'description': 'Решение квадратных уравнений различными методами'
        },
        {
            'code': 'linear_systems',
            'name': 'Системы линейных уравнений',
            'description': 'Решение систем линейных уравнений'
        },
        {
            'code': 'geometry_triangles',
            'name': 'Геометрия треугольников',
            'description': 'Свойства и задачи на треугольники'
        }
    ]
    
    for topic_data in demo_topics:
        existing_topic = Topic.query.filter_by(code=topic_data['code']).first()
        if not existing_topic:
            topic = Topic(**topic_data)
            db.session.add(topic)
            
            # Создаем конфигурации для каждого уровня
            for level in ['low', 'medium', 'high']:
                config = TopicLevelConfig(
                    topic=topic,
                    level=level,
                    task_count_threshold=5 if level == 'low' else (7 if level == 'medium' else 10),
                    reference_time=300 if level == 'low' else (240 if level == 'medium' else 180),  # секунды
                    penalty_weights=[0.7, 0.4]  # штрафы за 2-ю и 3-ю попытки
                )
                db.session.add(config)
    
    db.session.commit()
    print("✅ Созданы демонстрационные темы и их конфигурации")

def show_migration_info():
    """Показываем информацию о миграции"""
    print("=" * 60)
    print("МИГРАЦИЯ К НОВОЙ АРХИТЕКТУРЕ АДАПТИВНОГО МЕХАНИЗМА")
    print("=" * 60)
    print()
    print("Изменения:")
    print("• Удаление модели StudentProfile")
    print("• Обновление MathTask: level -> level, topic -> topic_id")
    print("• Добавление новых моделей:")
    print("  - Topic (справочник тем)")
    print("  - TopicLevelConfig (параметры для каждой темы/уровня)")
    print("  - StudentEvaluationLog (журнал оценок)")
    print("  - StudentTopicProgress (текущий прогресс)")
    print("  - EvaluationSystemConfig (глобальные настройки)")
    print()
    print("⚠️ ВНИМАНИЕ: Будет создана резервная копия базы данных")
    print()

if __name__ == "__main__":
    show_migration_info()
    
    response = input("Продолжить миграцию? (y/N): ").strip().lower()
    if response in ['y', 'yes', 'да']:
        if migrate_database():
            print("\n🎉 Миграция завершена успешно!")
            print("Теперь можно запустить приложение и проверить работоспособность.")
        else:
            print("\n❌ Миграция завершилась с ошибками!")
            sys.exit(1)
    else:
        print("Миграция отменена.")
