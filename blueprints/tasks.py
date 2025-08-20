from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import MathTask, TaskAttempt, Topic, User, db
from datetime import datetime
import json


def parse_student_answer(form_data, answer_type):
    """
    Парсит ответ студента в зависимости от типа задачи
    Возвращает словарь с данными ответа или None если ответ пустой
    """
    try:
        if answer_type == 'number':
            value = form_data.get('number_answer', '').strip()
            if not value:
                return None
            return {
                'type': 'number',
                'value': float(value)
            }
            
        elif answer_type == 'variables':
            variables = []
            # Ищем все поля с переменными
            for key in form_data.keys():
                if key.startswith('var_value_'):
                    var_name = key.replace('var_value_', '')
                    var_value = form_data.get(key, '').strip()
                    if var_value:
                        variables.append({
                            'name': var_name,
                            'value': float(var_value)
                        })
            
            if not variables:
                return None
            return {
                'type': 'variables',
                'variables': variables
            }
            
        elif answer_type == 'interval':
            start = form_data.get('interval_start', '').strip()
            end = form_data.get('interval_end', '').strip()
            
            if not start or not end:
                return None
                
            return {
                'type': 'interval',
                'start': float(start),
                'end': float(end),
                'start_inclusive': 'start_inclusive' in form_data,
                'end_inclusive': 'end_inclusive' in form_data
            }
            
        elif answer_type == 'sequence':
            sequence_str = form_data.get('sequence_values', '').strip()
            if not sequence_str:
                return None
                
            # Парсим последовательность чисел
            values = []
            for val in sequence_str.split(','):
                val = val.strip()
                if val:
                    values.append(float(val))
                    
            if not values:
                return None
                
            return {
                'type': 'sequence',
                'sequence_values': values
            }
            
        else:
            return None
            
    except (ValueError, TypeError):
        return None


def check_answer_correctness(user_answer, correct_answer, max_score):
    """
    Проверяет правильность ответа студента
    Возвращает (is_correct, score)
    """
    try:
        if not user_answer or not correct_answer:
            return False, 0
            
        answer_type = user_answer.get('type')
        
        if answer_type == 'number':
            user_value = user_answer.get('value')
            correct_value = correct_answer.get('value')
            # Сравниваем с небольшой погрешностью для чисел с плавающей точкой
            is_correct = abs(user_value - correct_value) < 1e-6
            
        elif answer_type == 'variables':
            user_vars = {var['name']: var['value'] for var in user_answer.get('variables', [])}
            correct_vars = {var['name']: var['value'] for var in correct_answer.get('variables', [])}
            
            # Проверяем, что все переменные совпадают
            is_correct = True
            for name, correct_val in correct_vars.items():
                user_val = user_vars.get(name)
                if user_val is None or abs(user_val - correct_val) >= 1e-6:
                    is_correct = False
                    break
                    
        elif answer_type == 'interval':
            user_start = user_answer.get('start')
            user_end = user_answer.get('end')
            user_start_inc = user_answer.get('start_inclusive', True)
            user_end_inc = user_answer.get('end_inclusive', False)
            
            correct_start = correct_answer.get('start')
            correct_end = correct_answer.get('end')
            correct_start_inc = correct_answer.get('start_inclusive', True)
            correct_end_inc = correct_answer.get('end_inclusive', False)
            
            is_correct = (
                abs(user_start - correct_start) < 1e-6 and
                abs(user_end - correct_end) < 1e-6 and
                user_start_inc == correct_start_inc and
                user_end_inc == correct_end_inc
            )
            
        elif answer_type == 'sequence':
            user_values = user_answer.get('sequence_values', [])
            correct_values = correct_answer.get('sequence_values', [])
            
            # Проверяем, что последовательности одинаковой длины
            if len(user_values) != len(correct_values):
                is_correct = False
            else:
                # Проверяем каждый элемент
                is_correct = True
                for i, (user_val, correct_val) in enumerate(zip(user_values, correct_values)):
                    if abs(user_val - correct_val) >= 1e-6:
                        is_correct = False
                        break
        else:
            is_correct = False
            
        score = max_score if is_correct else 0
        return is_correct, score
        
    except (ValueError, TypeError, KeyError):
        return False, 0

# Создаем blueprint для работы с заданиями
tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('/')
@login_required
def list_tasks():
    """Список всех заданий"""
    tasks = MathTask.query.filter_by(is_active=True).order_by(MathTask.created_at.desc()).all()
    return render_template('shared/tasks_list.html', tasks=tasks)

@tasks_bp.route('/<int:task_id>')
@login_required
def view_task(task_id):
    """Просмотр конкретного задания"""
    task = db.session.get(MathTask, task_id)
    if task is None:
        from flask import abort
        abort(404)
    
    # Получаем статистику попыток для текущего пользователя
    user_attempts = TaskAttempt.query.filter_by(
        user_id=current_user.id, 
        task_id=task_id
    ).order_by(TaskAttempt.created_at.desc()).all()
    
    # Общая статистика по заданию
    total_attempts = TaskAttempt.query.filter_by(task_id=task_id).count()
    successful_attempts = TaskAttempt.query.filter_by(task_id=task_id, is_correct=True).count()
    success_rate = round((successful_attempts / total_attempts * 100) if total_attempts > 0 else 0, 1)
    
    return render_template('shared/view_task.html',
                         task=task,
                         user_attempts=user_attempts,
                         total_attempts=total_attempts,
                         success_rate=success_rate)

@tasks_bp.route('/<int:task_id>/solve', methods=['POST'])
@login_required
def solve_task(task_id):
    """Отправка решения задания"""
    task = db.session.get(MathTask, task_id)
    if task is None:
        from flask import abort
        abort(404)
    
    if current_user.role != 'student':
        flash('Только студенты могут решать задания', 'error')
        return redirect(url_for('tasks.view_task', task_id=task_id))
    
    try:
        # Получаем тип ответа из формы
        answer_type = request.form.get('answer_type', 'number')
        
        # Парсим ответ студента в зависимости от типа
        user_answer_data = parse_student_answer(request.form, answer_type)
        
        if not user_answer_data:
            return render_template('shared/solve_task_error.html',
                                 task=task,
                                 error='Пожалуйста, введите ответ')
        
        # Проверяем правильность ответа
        is_correct, score = check_answer_correctness(user_answer_data, task.correct_answer, task.max_score)
        
        # Подсчитываем номер попытки
        attempt_number = TaskAttempt.query.filter_by(
            user_id=current_user.id,
            task_id=task_id
        ).count() + 1
        
        # Сохраняем попытку
        attempt = TaskAttempt(
            user_id=current_user.id,
            task_id=task_id,
            user_answer=user_answer_data,
            is_correct=is_correct,
            partial_score=score,
            attempt_number=attempt_number,
            created_at=datetime.utcnow()
        )
        
        db.session.add(attempt)
        db.session.commit()
        
        return render_template('shared/solve_task_result.html',
                             task=task,
                             attempt=attempt,
                             is_correct=is_correct,
                             score=score,
                             correct_answer=task.correct_answer)
        
    except Exception as e:
        db.session.rollback()
        return render_template('shared/solve_task_error.html',
                             task=task,
                             error=f'Ошибка при сохранении ответа: {str(e)}')

@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """Создание нового задания (только для преподавателей и админов)"""
    if current_user.role not in ['teacher', 'admin']:
        flash('У вас нет прав для создания заданий', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        topic_id = request.form.get('topic_id', '')
        level = request.form.get('level', 'low')
        max_score = request.form.get('max_score', '1')
        correct_answer = request.form.get('correct_answer', '').strip()
        explanation = request.form.get('explanation', '').strip()
        
        # Валидация
        errors = []
        if not title:
            errors.append('Название задания обязательно')
        if not description:
            errors.append('Описание задания обязательно')
        if not topic_id:
            errors.append('Тема задания обязательна')
        if not correct_answer:
            errors.append('Правильный ответ обязателен')
        
        try:
            topic_id = int(topic_id)
            max_score = float(max_score)
            if level not in ['low', 'medium', 'high']:
                errors.append('Уровень сложности должен быть low, medium или high')
            if max_score <= 0:
                errors.append('Максимальный балл должен быть больше 0')
            # Проверяем существование темы
            topic = db.session.get(Topic, topic_id)
            if not topic:
                errors.append('Выбранная тема не существует')
        except ValueError:
            errors.append('Неверный формат числовых значений')
        
        if errors:
            topics = Topic.query.all()
            return render_template('teacher/create_task.html', errors=errors, topics=topics)
        
        try:
            # Создаем новое задание
            task = MathTask(
                title=title,
                description=description,
                topic_id=topic_id,
                level=level,
                max_score=max_score,
                correct_answer={'value': correct_answer, 'type': 'text'},
                explanation=explanation,
                answer_type='text',
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(task)
            db.session.commit()
            
            return render_template('teacher/create_task_success.html', task=task)
            
        except Exception as e:
            db.session.rollback()
            topics = Topic.query.all()
            return render_template('teacher/create_task.html', 
                                 errors=[f'Ошибка при создании задания: {str(e)}'], topics=topics)
    
    # GET запрос - показываем форму создания
    topics = Topic.query.all()
    return render_template('teacher/create_task.html', topics=topics)
