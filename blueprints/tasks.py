from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import MathTask, TaskAttempt, User, db
from datetime import datetime
import json

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
    task = MathTask.query.get_or_404(task_id)
    
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
    task = MathTask.query.get_or_404(task_id)
    
    if current_user.role != 'student':
        flash('Только студенты могут решать задания', 'error')
        return redirect(url_for('tasks.view_task', task_id=task_id))
    
    user_answer = request.form.get('answer', '').strip()
    
    if not user_answer:
        return render_template('shared/solve_task_error.html',
                             task=task,
                             error='Пожалуйста, введите ответ')
    
    try:
        # Проверяем правильность ответа
        correct_answer = task.correct_answer.get('value', '') if isinstance(task.correct_answer, dict) else str(task.correct_answer)
        is_correct = user_answer.lower().strip() == correct_answer.lower().strip()
        
        # Вычисляем баллы
        score = task.max_score if is_correct else 0
        
        # Подсчитываем номер попытки
        attempt_number = TaskAttempt.query.filter_by(
            user_id=current_user.id,
            task_id=task_id
        ).count() + 1
        
        # Сохраняем попытку
        attempt = TaskAttempt(
            user_id=current_user.id,
            task_id=task_id,
            user_answer={'value': user_answer, 'type': 'text'},
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
                             correct_answer=correct_answer)
        
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
        topic = request.form.get('topic', '').strip()
        difficulty_level = request.form.get('difficulty_level', '1')
        max_score = request.form.get('max_score', '1')
        correct_answer = request.form.get('correct_answer', '').strip()
        explanation = request.form.get('explanation', '').strip()
        
        # Валидация
        errors = []
        if not title:
            errors.append('Название задания обязательно')
        if not description:
            errors.append('Описание задания обязательно')
        if not topic:
            errors.append('Тема задания обязательна')
        if not correct_answer:
            errors.append('Правильный ответ обязателен')
        
        try:
            difficulty_level = float(difficulty_level)
            max_score = float(max_score)
            if difficulty_level < 1 or difficulty_level > 5:
                errors.append('Уровень сложности должен быть от 1 до 5')
            if max_score <= 0:
                errors.append('Максимальный балл должен быть больше 0')
        except ValueError:
            errors.append('Неверный формат числовых значений')
        
        if errors:
            return render_template('teacher/create_task.html', errors=errors)
        
        try:
            # Создаем новое задание
            task = MathTask(
                title=title,
                description=description,
                topic=topic,
                difficulty_level=difficulty_level,
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
            return render_template('teacher/create_task.html', 
                                 errors=[f'Ошибка при создании задания: {str(e)}'])
    
    # GET запрос - показываем форму создания
    return render_template('teacher/create_task.html')
