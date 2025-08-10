from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from models import db, User, MathTask, TaskAttempt, Topic, TopicLevelConfig, EvaluationSystemConfig
from datetime import datetime
import os
import json
import uuid
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError

# Создаем blueprint для административных функций
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('У вас нет прав доступа к этой странице', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def panel():
    """Главная страница администратора"""
    return redirect(url_for('admin.demo_data'))

@admin_bp.route('/demo-data')
@login_required
@admin_required
def demo_data():
    """Вкладка 1: Управление демо-данными"""
    # Собираем статистику
    total_users = User.query.count()
    total_tasks = MathTask.query.count()
    total_attempts = TaskAttempt.query.count()
    
    students_count = User.query.filter_by(role='student').count()
    teachers_count = User.query.filter_by(role='teacher').count()
    admins_count = User.query.filter_by(role='admin').count()
    topics_count = Topic.query.count()
    
    # Создаем объект stats для совместимости с шаблоном
    stats = {
        'total_users': total_users,
        'total_tasks': total_tasks,
        'total_attempts': total_attempts,
        'students': students_count,
        'teachers': teachers_count,
        'admins': admins_count,
        'total_topics': topics_count
    }
    
    return render_template('admin/demo_data.html', stats=stats, active_tab='demo-data')



@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """Вкладка 3: Настройки системы"""
    return render_template('admin/settings.html', active_tab='settings')

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Вкладка 4: Аналитика системы"""
    # Собираем статистику
    total_users = User.query.count()
    total_tasks = MathTask.query.count()
    total_attempts = TaskAttempt.query.count()
    
    # Вычисляем успешность
    successful_attempts = TaskAttempt.query.filter_by(is_correct=True).count()
    success_rate = round((successful_attempts / total_attempts * 100) if total_attempts > 0 else 0, 1)
    
    # Популярные задания (топ-5)
    popular_tasks = MathTask.query.limit(5).all()
    
    # Активные пользователи (топ-6)
    active_users = User.query.limit(6).all()
    
    return render_template('admin/analytics.html',
                         total_users=total_users,
                         total_tasks=total_tasks,
                         total_attempts=total_attempts,
                         success_rate=success_rate,
                         popular_tasks=popular_tasks,
                         active_users=active_users,
                         active_tab='analytics')

@admin_bp.route('/tasks/import', methods=['POST'])
@login_required
@admin_required
def import_tasks():
    """API для импорта заданий из JSON файла"""
    if 'import_file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    
    file = request.files['import_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({'success': False, 'message': 'Поддерживаются только файлы в формате JSON'}), 400
    
    try:
        # Создаем папку для загрузок, если её нет
        upload_folder = os.path.join(current_app.root_path, '..', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Генерируем уникальное имя файла
        filename = f"{uuid.uuid4()}.json"
        filepath = os.path.join(upload_folder, filename)
        
        # Сохраняем файл
        file.save(filepath)
        
        # Импортируем задачи
        success_count, errors = import_tasks_from_file(filepath, current_user.id)
        
        # Удаляем временный файл
        try:
            os.remove(filepath)
        except Exception as e:
            current_app.logger.error(f'Error removing temp file {filepath}: {str(e)}')
        
        if success_count > 0 or not errors:
            return jsonify({
                'success': True,
                'imported': success_count,
                'errors': errors,
                'message': f'Успешно импортировано {success_count} заданий.' + (f' Ошибок: {len(errors)}' if errors else '')
            })
        else:
            return jsonify({
                'success': False,
                'imported': 0,
                'errors': errors,
                'message': 'Не удалось импортировать ни одного задания. Проверьте формат данных.'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f'Error importing tasks: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Ошибка при импорте заданий: {str(e)}'
        }), 500

@admin_bp.route('/tasks', methods=['GET'])
@login_required
@admin_required
def tasks():
    """Вкладка 5: Управление заданиями"""
    
    # Получаем все задания с дополнительной информацией для админа
    tasks = MathTask.query.order_by(MathTask.level.desc(), MathTask.id.desc()).all()
    return render_template('admin/tasks.html', tasks=tasks, active_tab='tasks')

def import_tasks_from_file(filepath, user_id):
    """Импорт заданий из JSON файла"""
    success_count = 0
    errors = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if 'tasks' not in data:
            raise ValueError("Неверный формат файла. Ожидается объект с полем 'tasks'")
            
        for i, task_data in enumerate(data['tasks'], 1):
            try:
                # Проверяем обязательные поля
                required_fields = ['title', 'description', 'answer_type', 'correct_answer', 
                                 'level', 'topic_id', 'max_score']
                
                missing_fields = [field for field in required_fields if field not in task_data]
                if missing_fields:
                    errors.append(f'Задание {i}: Отсутствуют обязательные поля: {", ".join(missing_fields)}')
                    continue
                
                # Проверяем формат correct_answer
                correct_answer = task_data['correct_answer']
                if not isinstance(correct_answer, dict) or 'type' not in correct_answer:
                    errors.append(f'Задание {i}: Неверный формат correct_answer. Ожидается объект с полем type')
                    continue
                
                # Валидация по типу ответа
                answer_type = correct_answer.get('type')
                if answer_type == 'number':
                    if 'value' not in correct_answer or not isinstance(correct_answer['value'], (int, float)):
                        errors.append(f'Задание {i}: Для типа "number" требуется поле "value" с числовым значением')
                        continue
                elif answer_type == 'sequence':
                    if 'sequence_values' not in correct_answer or not isinstance(correct_answer['sequence_values'], list):
                        errors.append(f'Задание {i}: Для типа "sequence" требуется поле "sequence_values" со списком чисел')
                        continue
                elif answer_type == 'variables':
                    if 'variables' not in correct_answer or not isinstance(correct_answer['variables'], list):
                        errors.append(f'Задание {i}: Для типа "variables" требуется поле "variables" со списком переменных')
                        continue
                    # Проверяем структуру переменных
                    for var in correct_answer['variables']:
                        if not isinstance(var, dict) or 'name' not in var or 'value' not in var:
                            errors.append(f'Задание {i}: Каждая переменная должна содержать поля "name" и "value"')
                            break
                elif answer_type == 'interval':
                    required_interval_fields = ['start', 'end', 'start_inclusive', 'end_inclusive']
                    missing_interval_fields = [field for field in required_interval_fields if field not in correct_answer]
                    if missing_interval_fields:
                        errors.append(f'Задание {i}: Для типа "interval" отсутствуют поля: {", ".join(missing_interval_fields)}')
                        continue
                else:
                    errors.append(f'Задание {i}: Неподдерживаемый тип ответа "{answer_type}". Поддерживаются: number, sequence, variables, interval')
                    continue
                
                # Создаем новое задание
                task = MathTask(
                    title=task_data['title'],
                    description=task_data['description'],
                    answer_type=task_data['answer_type'],
                    correct_answer=task_data['correct_answer'],
                    level=task_data['level'],
                    topic_id=int(task_data['topic_id']),
                    max_score=float(task_data['max_score']),
                    explanation=task_data.get('explanation', ''),
                    created_by=user_id,
                    is_active=True
                )
                
                db.session.add(task)
                db.session.commit()
                success_count += 1
                
            except (ValueError, TypeError) as e:
                db.session.rollback()
                errors.append(f'Задание {i}: Ошибка формата данных - {str(e)}')
            except SQLAlchemyError as e:
                db.session.rollback()
                errors.append(f'Задание {i}: Ошибка базы данных - {str(e)}')
            except Exception as e:
                db.session.rollback()
                errors.append(f'Задание {i}: Неизвестная ошибка - {str(e)}')
    
    except json.JSONDecodeError:
        raise ValueError('Ошибка при чтении JSON файла')
    except Exception as e:
        raise Exception(f'Ошибка при обработке файла: {str(e)}')
    
    return success_count, errors

@admin_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_task(task_id):
    """Удаление задания"""
    task = MathTask.query.get_or_404(task_id)
    
    try:
        # Удаляем все попытки решения этого задания
        TaskAttempt.query.filter_by(task_id=task_id).delete()
        # Удаляем само задание
        db.session.delete(task)
        db.session.commit()
        flash('Задание успешно удалено', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении задания: {str(e)}', 'error')
    
    return redirect(url_for('admin.tasks'))

@admin_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_task(task_id):
    """Редактирование задания"""
    task = MathTask.query.get_or_404(task_id)
    
    if request.method == 'POST':
        try:
            # Обновляем данные задания
            task.title = request.form.get('title', task.title)
            task.description = request.form.get('description', task.description)
            task.level = request.form.get('level', task.level)
            task.topic_id = int(request.form.get('topic_id', task.topic_id))
            task.max_score = float(request.form.get('max_score', task.max_score))
            
            # Обновляем правильный ответ в зависимости от типа (унифицированный JSON формат)
            answer_type = request.form.get('answer_type', task.answer_type)
            
            if answer_type == 'number':
                # Числовой ответ: {"type": "number", "value": 75.5}
                number_value = float(request.form.get('number_value', 0))
                task.correct_answer = {
                    'type': 'number',
                    'value': number_value
                }
                
            elif answer_type == 'variables':
                # Переменные: {"type": "variables", "variables": [{"name": "x", "value": 3}, ...]}
                var_names = request.form.getlist('var_name[]')
                var_values = request.form.getlist('var_value[]')
                
                variables = []
                for name, value in zip(var_names, var_values):
                    if name.strip():  # Пропускаем пустые имена
                        variables.append({
                            'name': name.strip(),
                            'value': float(value) if value else 0
                        })
                
                task.correct_answer = {
                    'type': 'variables',
                    'variables': variables
                }
                
            elif answer_type == 'interval':
                # Интервал: {"type": "interval", "start": 2, "end": 8, "start_inclusive": true, "end_inclusive": false}
                start = float(request.form.get('interval_start', 0))
                end = float(request.form.get('interval_end', 0))
                start_inclusive = 'start_inclusive' in request.form
                end_inclusive = 'end_inclusive' in request.form
                
                task.correct_answer = {
                    'type': 'interval',
                    'start': start,
                    'end': end,
                    'start_inclusive': start_inclusive,
                    'end_inclusive': end_inclusive
                }
                
            elif answer_type == 'sequence':
                # Последовательность: {"type": "sequence", "sequence_values": [1, 2, 5, 8, 13]}
                sequence_str = request.form.get('sequence_values', '')
                values = []
                
                if sequence_str.strip():
                    try:
                        # Разбираем строку с числами через запятую
                        values = [float(x.strip()) for x in sequence_str.split(',') if x.strip()]
                    except ValueError:
                        raise ValueError('Неверный формат последовательности. Используйте числа через запятую.')
                
                task.correct_answer = {
                    'type': 'sequence',
                    'sequence_values': values
                }
            
            else:
                # Неизвестный тип ответа
                raise ValueError(f'Неподдерживаемый тип ответа: {answer_type}')
            
            task.answer_type = answer_type
            
            db.session.commit()
            flash('Задание успешно обновлено', 'success')
            return redirect(url_for('admin.tasks'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении задания: {str(e)}', 'error')
    
    # Для GET запроса показываем форму редактирования
    topics = Topic.query.all()
    return render_template('admin/edit_task.html', task=task, topics=topics)


@admin_bp.route('/tasks/export', methods=['GET', 'POST'])
@login_required
@admin_required
def export_tasks():
    """Экспорт заданий в JSON формате"""
    try:
        if request.method == 'POST':
            # Экспорт выбранных заданий
            data = request.get_json()
            task_ids = data.get('task_ids', [])
            
            if not task_ids:
                return jsonify({'success': False, 'message': 'Не выбрано ни одного задания'}), 400
                
            tasks = MathTask.query.filter(MathTask.id.in_(task_ids)).all()
        else:
            # Экспорт всех заданий
            tasks = MathTask.query.all()
        
        # Формируем данные для экспорта
        export_data = {
            'tasks': [],
            'exported_at': datetime.utcnow().isoformat(),
            'exported_by': current_user.username,
            'total_tasks': len(tasks)
        }
        
        for task in tasks:
            task_data = {
                'title': task.title,
                'description': task.description,
                'answer_type': task.answer_type,
                'correct_answer': task.correct_answer,
                'level': task.level,
                'topic_id': task.topic_id,
                'topic_name': task.topic_ref.name if task.topic_ref else 'Неизвестная тема',
                'max_score': task.max_score,
                'explanation': task.explanation or '',
                'created_at': task.created_at.isoformat() if task.created_at else None
            }
            export_data['tasks'].append(task_data)
        
        # Возвращаем JSON файл
        from flask import make_response
        import json
        
        response = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        
        if request.method == 'POST':
            filename = f'selected_tasks_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        else:
            filename = f'all_tasks_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f'Error exporting tasks: {str(e)}')
        if request.method == 'POST':
            return jsonify({'success': False, 'message': f'Ошибка при экспорте: {str(e)}'}), 500
        else:
            flash(f'Ошибка при экспорте заданий: {str(e)}', 'error')
            return redirect(url_for('admin.tasks'))


@admin_bp.route('/clear-database', methods=['POST'])
@login_required
@admin_required
def clear_database():
    """Очистка базы данных (только для админов)"""
    try:
        # Удаляем все попытки решения
        TaskAttempt.query.delete()
        
        # Удаляем все задания
        MathTask.query.delete()
        
        # Удаляем всех пользователей кроме текущего админа
        User.query.filter(User.id != current_user.id).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'База данных успешно очищена. Сохранен только ваш аккаунт администратора.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error clearing database: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Ошибка при очистке базы данных: {str(e)}'
        }), 500


# Дополнительные административные маршруты

@admin_bp.route('/create-demo-users')
@login_required
@admin_required
def create_demo_users():
    """Создание демо-пользователей"""
    try:
        # Создаем тестового студента
        if not User.query.filter_by(username='student').first():
            student = User(
                username='student',
                email='student@example.com',
                role='student',
                first_name='Тестовый',
                last_name='Студент'
            )
            student.set_password('123456')
            db.session.add(student)
        
        # Создаем тестового преподавателя
        if not User.query.filter_by(username='teacher').first():
            teacher = User(
                username='teacher',
                email='teacher@example.com',
                role='teacher',
                first_name='Тестовый',
                last_name='Преподаватель'
            )
            teacher.set_password('123456')
            db.session.add(teacher)
        
        db.session.commit()
        flash('Демо-пользователи успешно созданы!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при создании пользователей: {str(e)}', 'error')
    
    return redirect(url_for('admin.demo_data'))

@admin_bp.route('/create-olympiad-tasks')
@login_required
@admin_required
def create_olympiad_tasks():
    """Создание олимпиадных заданий"""
    try:
        from app import create_sample_tasks, create_olympiad_tasks
        
        # Принудительно создаем олимпиадные задания
        create_sample_tasks()
        create_olympiad_tasks()
        
        # Подсчитываем количество заданий
        total_tasks = MathTask.query.count()
        olympiad_tasks = MathTask.query.filter(MathTask.title.contains('Олимпиада')).count()
        
        flash(f'Задания созданы! Всего: {total_tasks}, олимпиадных: {olympiad_tasks}', 'success')
        
    except Exception as e:
        flash(f'Ошибка при создании заданий: {str(e)}', 'error')
    
    return redirect(url_for('admin.demo_data'))

@admin_bp.route('/create-sample-tasks')
@login_required
@admin_required
def create_sample_tasks():
    """Создание примеров заданий"""
    try:
        from app import create_sample_tasks
        
        # Создаем примеры заданий
        create_sample_tasks()
        
        # Подсчитываем количество заданий
        total_tasks = MathTask.query.count()
        
        flash(f'Примеры заданий созданы! Всего заданий: {total_tasks}', 'success')
        
    except Exception as e:
        flash(f'Ошибка при создании заданий: {str(e)}', 'error')
    
    return redirect(url_for('admin.demo_data'))

    # ====================================================
    # Управление пользователями
    # ====================================================

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Управление пользователями"""
    users = User.query.all()
    return render_template('admin/users.html', users=users, active_tab='users')
    
@admin_bp.route('/users/import', methods=['POST'])
@login_required
@admin_required
def import_users():
    """Импорт пользователей из JSON файла.
       Поддерживает форматы:
       1) { "users": [ {...}, ... ] }
       2) [ {...}, ... ]
    """
    try:
        # файл может прийти под разными ключами
        file = request.files.get("file") or request.files.get("import_file")
        if not file or file.filename == "":
            return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'message': 'Поддерживаются только файлы в формате JSON'}), 400

        # читаем JSON (без сохранения на диск)
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': 'Файл не является валидным JSON'}), 400

        # определяем список пользователей
        if isinstance(data, dict) and isinstance(data.get('users'), list):
            users_list = data['users']
        elif isinstance(data, list):
            users_list = data
        else:
            return jsonify({'success': False, 'message': "Неверный формат файла. Ожидается объект с полем 'users' ИЛИ массив пользователей"}), 400

        success_count = 0
        errors = []
        valid_roles = {'student', 'teacher', 'admin'}

        from werkzeug.security import generate_password_hash

        for i, user_data in enumerate(users_list, 1):
            try:
                # обязательные поля
                required = ['username', 'email', 'role']
                missing = [k for k in required if not user_data.get(k)]
                if missing:
                    errors.append(f'Пользователь {i}: отсутствуют обязательные поля: {", ".join(missing)}')
                    continue

                # роль
                role = user_data.get('role')
                if role not in valid_roles:
                    errors.append(f'Пользователь {i}: неверная роль "{role}". Допустимые: {", ".join(sorted(valid_roles))}')
                    continue

                # уникальность
                existing = User.query.filter(
                    (User.username == user_data['username']) | (User.email == user_data['email'])
                ).first()
                if existing:
                    if existing.username == user_data['username']:
                        errors.append(f'Пользователь {i}: username "{user_data["username"]}" уже существует')
                    else:
                        errors.append(f'Пользователь {i}: email "{user_data["email"]}" уже существует')
                    continue

                # создаём
                password = user_data.get('password', '123456')
                user = User(
                    username=user_data['username'],
                    email=user_data['email'],
                    password_hash=generate_password_hash(password),
                    role=role,
                    is_active=user_data.get('is_active', True),
                    first_name=user_data.get('first_name', ''),   # <-- ИМПОРТИРУЕМ
                    last_name=user_data.get('last_name', '')      # <-- ИМПОРТИРУЕМ
                )

                db.session.add(user)
                db.session.commit()   # по одному, как у тебя было (чтобы частичный импорт проходил)
                success_count += 1

            except (ValueError, TypeError) as e:
                db.session.rollback()
                errors.append(f'Пользователь {i}: ошибка формата данных — {str(e)}')
            except SQLAlchemyError as e:
                db.session.rollback()
                errors.append(f'Пользователь {i}: ошибка базы данных — {str(e)}')
            except Exception as e:
                db.session.rollback()
                errors.append(f'Пользователь {i}: неизвестная ошибка — {str(e)}')

        # ответ
        if success_count > 0 or not errors:
            return jsonify({
                'success': True,
                'imported': success_count,
                'errors': errors,
                'message': f'Успешно импортировано {success_count} пользователей.' + (f' Ошибок: {len(errors)}' if errors else '')
            })
        else:
            return jsonify({
                'success': False,
                'imported': 0,
                'errors': errors,
                'message': 'Не удалось импортировать ни одного пользователя. Проверьте формат данных.'
            }), 400

    except Exception as e:
        current_app.logger.error(f'Error importing users: {str(e)}')
        return jsonify({'success': False, 'message': f'Ошибка при импорте пользователей: {str(e)}'}), 500


@admin_bp.route('/users/export', methods=['GET', 'POST'])
@login_required
@admin_required
def export_users():
    """Экспорт пользователей в JSON формате"""
    try:
        if request.method == 'POST':
            # Получаем список ID выбранных пользователей
            selected_ids = request.json.get('selected_ids', [])
            if selected_ids:
                users = User.query.filter(User.id.in_(selected_ids)).all()
            else:
                users = User.query.all()
        else:
            # GET запрос - экспортируем всех пользователей
            users = User.query.all()

        # ==== временная диагностика ====
        if users:
            sample_user = users[0]
            current_app.logger.info("EXPORT sample user: %s", {
                'username': sample_user.username,
                'email': sample_user.email,
                'role': sample_user.role,
                'first_name': sample_user.first_name,
                'last_name': sample_user.last_name
        })
        else:
            current_app.logger.info("EXPORT: no users found")
        # ===============================
        
        # Формируем данные для экспорта
        export_data = {
            'users': [],
            'export_info': {
                'timestamp': datetime.now().isoformat(),
                'total_users': len(users),
                'exported_by': current_user.username
            }
        }
        
        for user in users:
            user_data = {
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            export_data['users'].append(user_data)
        
        if request.method == 'POST':
            return jsonify({
                "users": export_data["users"],
                "export_info": export_data["export_info"]
            })
        else:
            # GET запрос - возвращаем файл для скачивания
            from flask import make_response
            response = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename=users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            return response
            
    except Exception as e:
        current_app.logger.error(f'Error exporting users: {str(e)}')
        if request.method == 'POST':
            return jsonify({
                'success': False,
                'message': f'Ошибка при экспорте пользователей: {str(e)}'
            }), 500
        else:
            flash(f'Ошибка при экспорте пользователей: {str(e)}', 'error')
            return redirect(url_for('admin.users'))

@admin_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get_or_404(user_id)
    
    if user.role == 'admin':
        flash('Нельзя удалить администратора', 'error')
        return redirect(url_for('admin.users'))
    
    try:
        # Удаляем связанные попытки
        TaskAttempt.query.filter_by(user_id=user_id).delete()
        
        # Удаляем пользователя
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Пользователь {user.username} успешно удален', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении пользователя: {str(e)}', 'error')
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Редактирование пользователя"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            user.email = request.form.get('email', user.email)
            user.first_name = request.form.get('first_name', user.first_name)
            user.last_name = request.form.get('last_name', user.last_name)
            
            # Изменяем роль только если это не админ
            if user.role != 'admin':
                user.role = request.form.get('role', user.role)
            
            # Изменяем пароль если указан новый
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            db.session.commit()
            flash(f'Пользователь {user.username} успешно обновлен', 'success')
            return redirect(url_for('admin.users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении пользователя: {str(e)}', 'error')
    
    # Для GET запроса показываем форму редактирования
    return render_template('admin/edit_user.html',
                           user=user,
                           active_tab='users')

# =============================================================================
# УПРАВЛЕНИЕ ТЕМАМИ
# =============================================================================

@admin_bp.route('/topics')
@login_required
@admin_required
def topics():
    """Вкладка 6: Управление темами"""
    topics = Topic.query.order_by(Topic.name.asc()).all()
    return render_template('admin/topics.html', topics=topics, active_tab='topics')

@admin_bp.route('/topics/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_topic():
    """Создание новой темы"""
    if request.method == 'POST':
        try:
            code = request.form.get('code', '').strip()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            
            # Валидация
            errors = []
            if not code:
                errors.append('Код темы обязателен')
            if not name:
                errors.append('Название темы обязательно')
            
            # Проверяем уникальность кода
            if Topic.query.filter_by(code=code).first():
                errors.append('Тема с таким кодом уже существует')
            
            if errors:
                return render_template('admin/create_topic.html', errors=errors, active_tab='topics')
            
            # Создаем новую тему
            topic = Topic(
                code=code,
                name=name,
                description=description
            )
            
            db.session.add(topic)
            db.session.commit()
            
            # Создаем базовые конфигурации для всех уровней
            for level in ['low', 'medium', 'high']:
                config = TopicLevelConfig(
                    topic_id=topic.id,
                    level=level,
                    #task_count_threshold=5 if level == 'low' else (7 if level == 'medium' else 10),
                    #reference_time=300 if level == 'low' else (240 if level == 'medium' else 180),
                    task_count_threshold=10,
                    reference_time=900,  # 15 минут
                    penalty_weights=[0.7, 0.4]
                )
                db.session.add(config)
            
            db.session.commit()
            
            flash('Тема успешно создана', 'success')
            return redirect(url_for('admin.topics'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании темы: {str(e)}', 'error')
    
    return render_template('admin/create_topic.html', active_tab='topics')

@admin_bp.route('/topics/<int:topic_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_topic(topic_id):
    """Редактирование темы"""
    topic = Topic.query.get_or_404(topic_id)
    
    if request.method == 'POST':
        try:
            topic.code = request.form.get('code', topic.code)
            topic.name = request.form.get('name', topic.name)
            topic.description = request.form.get('description', topic.description)
            
            db.session.commit()
            flash('Тема успешно обновлена', 'success')
            return redirect(url_for('admin.topics'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении темы: {str(e)}', 'error')
    
    # Получаем конфигурации для всех уровней
    configs = {}
    for config in topic.level_configs:
        configs[config.level] = config
    
    return render_template('admin/edit_topic.html', topic=topic, configs=configs, active_tab='topics')

@admin_bp.route('/topics/<int:topic_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_topic(topic_id):
    """Удаление темы"""
    try:
        topic = Topic.query.get_or_404(topic_id)
        
        # Проверяем, есть ли задания, использующие эту тему
        tasks_count = MathTask.query.filter_by(topic_id=topic_id).count()
        if tasks_count > 0:
            flash(f'Нельзя удалить тему: к ней привязано {tasks_count} заданий', 'error')
            return redirect(url_for('admin.topics'))
        
        # Удаляем конфигурации уровней
        TopicLevelConfig.query.filter_by(topic_id=topic_id).delete()
        
        # Удаляем тему
        db.session.delete(topic)
        db.session.commit()
        
        flash('Тема успешно удалена', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении темы: {str(e)}', 'error')
    
    return redirect(url_for('admin.topics'))

@admin_bp.route('/topics/import', methods=['POST'])
@login_required
@admin_required
def import_topics():
    """Импорт тем из JSON файла"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Файл не выбран'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Файл не выбран'})
        
        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'message': 'Поддерживаются только JSON файлы'})
        
        # Читаем и парсим JSON
        content = file.read().decode('utf-8')
        topics_data = json.loads(content)
        
        if not isinstance(topics_data, list):
            return jsonify({'success': False, 'message': 'JSON должен содержать массив тем'})
        
        imported_count = 0
        errors = []
        
        for i, topic_data in enumerate(topics_data, 1):
            try:
                # Проверяем обязательные поля
                required_fields = ['code', 'name']
                missing_fields = [field for field in required_fields if field not in topic_data]
                if missing_fields:
                    errors.append(f'Тема {i}: Отсутствуют поля: {", ".join(missing_fields)}')
                    continue
                
                # Проверяем уникальность кода
                if Topic.query.filter_by(code=topic_data['code']).first():
                    errors.append(f'Тема {i}: Код "{topic_data["code"]}" уже существует')
                    continue
                
                # Создаем тему
                topic = Topic(
                    code=topic_data['code'],
                    name=topic_data['name'],
                    description=topic_data.get('description', '')
                )
                
                db.session.add(topic)
                db.session.flush()  # Получаем ID темы
                
                # Создаем конфигурации уровней
                level_configs = topic_data.get('level_configs', {})
                for level in ['low', 'medium', 'high']:
                    config_data = level_configs.get(level, {})
                    config = TopicLevelConfig(
                        topic_id=topic.id,
                        level=level,
                        task_count_threshold=config_data.get('task_count_threshold', 5 if level == 'low' else (7 if level == 'medium' else 10)),
                        reference_time=config_data.get('reference_time', 300 if level == 'low' else (240 if level == 'medium' else 180)),
                        penalty_weights=config_data.get('penalty_weights', [0.7, 0.4])
                    )
                    db.session.add(config)
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f'Тема {i}: {str(e)}')
                continue
        
        if imported_count > 0:
            db.session.commit()
        else:
            db.session.rollback()
        
        result_message = f'Импортировано тем: {imported_count}'
        if errors:
            result_message += f'\nОшибки: {len(errors)}'
            for error in errors[:5]:  # Показываем первые 5 ошибок
                result_message += f'\n• {error}'
            if len(errors) > 5:
                result_message += f'\n... и еще {len(errors) - 5} ошибок'
        
        return jsonify({
            'success': imported_count > 0,
            'message': result_message,
            'imported_count': imported_count,
            'errors_count': len(errors)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при импорте: {str(e)}'})

@admin_bp.route('/topics/export', methods=['GET', 'POST'])
@login_required
@admin_required
def export_topics():
    """Экспорт тем в JSON формате"""
    try:
        if request.method == 'POST':
            # Экспорт выбранных тем
            selected_ids = request.json.get('topic_ids', [])
            if not selected_ids:
                return jsonify({'success': False, 'message': 'Не выбрано ни одной темы'})
            
            topics = Topic.query.filter(Topic.id.in_(selected_ids)).all()
        else:
            # Экспорт всех тем
            topics = Topic.query.all()
        
        if not topics:
            if request.method == 'POST':
                return jsonify({'success': False, 'message': 'Темы не найдены'})
            else:
                flash('Нет тем для экспорта', 'warning')
                return redirect(url_for('admin.topics'))
        
        # Формируем данные для экспорта
        export_data = []
        for topic in topics:
            topic_data = {
                'code': topic.code,
                'name': topic.name,
                'description': topic.description or '',
                'level_configs': {}
            }
            
            # Добавляем конфигурации уровней
            for config in topic.level_configs:
                topic_data['level_configs'][config.level] = {
                    'task_count_threshold': config.task_count_threshold,
                    'reference_time': config.reference_time,
                    'penalty_weights': config.penalty_weights
                }
            
            export_data.append(topic_data)
        
        # Возвращаем JSON файл
        from flask import make_response
        import json
        
        response = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        
        if request.method == 'POST':
            filename = f'selected_topics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        else:
            filename = f'all_topics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f'Error exporting topics: {str(e)}')
        if request.method == 'POST':
            return jsonify({'success': False, 'message': f'Ошибка при экспорте: {str(e)}'}), 500
        else:
            flash(f'Ошибка при экспорте тем: {str(e)}', 'error')
            return redirect(url_for('admin.topics'))
