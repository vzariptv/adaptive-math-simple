from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import User, MathTask, TaskAttempt

# Создаем blueprint для основных страниц
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    """Главная страница"""
    return render_template('shared/home.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Панель управления (дашборд) для всех ролей"""
    
    if current_user.role == 'student':
        # Статистика для студента
        total_attempts = TaskAttempt.query.filter_by(user_id=current_user.id).count()
        successful_attempts = TaskAttempt.query.filter_by(user_id=current_user.id, is_correct=True).count()
        success_rate = round((successful_attempts / total_attempts * 100) if total_attempts > 0 else 0, 1)
        
        # Последние попытки
        recent_attempts = TaskAttempt.query.filter_by(user_id=current_user.id)\
                                          .order_by(TaskAttempt.created_at.desc())\
                                          .limit(5).all()
        
        return render_template('student/dashboard.html',
                             total_attempts=total_attempts,
                             successful_attempts=successful_attempts,
                             success_rate=success_rate,
                             recent_attempts=recent_attempts)
    
    elif current_user.role == 'teacher':
        # Статистика для преподавателя
        created_tasks = MathTask.query.filter_by(created_by=current_user.id).count()
        total_students = User.query.filter_by(role='student').count()
        
        # Последние созданные задания
        recent_tasks = MathTask.query.filter_by(created_by=current_user.id)\
                                    .order_by(MathTask.created_at.desc())\
                                    .limit(5).all()
        
        return render_template('teacher/dashboard.html',
                             created_tasks=created_tasks,
                             total_students=total_students,
                             recent_tasks=recent_tasks)
    
    elif current_user.role == 'admin':
        # Статистика для администратора
        total_users = User.query.count()
        total_tasks = MathTask.query.count()
        total_attempts = TaskAttempt.query.count()
        
        return render_template('admin/dashboard.html',
                             total_users=total_users,
                             total_tasks=total_tasks,
                             total_attempts=total_attempts)
    
    else:
        # Неизвестная роль
        return redirect(url_for('auth.logout'))
