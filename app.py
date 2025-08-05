from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, get_flashed_messages
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, StudentProfile, MathTask, TaskAttempt
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
# Настройка базы данных с поддержкой PostgreSQL для продакшена
database_url = os.environ.get('DATABASE_URL', 'sqlite:///math_learning.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Инициализация базы данных для продакшена
def init_db():
    """Инициализация базы данных"""
    try:
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")
            # Создаем тестовые задания для демонстрации
            create_sample_tasks()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Вызываем инициализацию при импорте модуля
init_db()

def get_base_styles():
    """Базовые CSS стили для всех страниц"""
    return '''
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                line-height: 1.6;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                margin-bottom: 20px;
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.2em;
                font-weight: 300;
            }
            .form-group {
                margin-bottom: 20px;
            }
            input[type="text"], input[type="email"], input[type="password"], select {
                width: 100%;
                padding: 12px 15px;
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.3s ease;
                box-sizing: border-box;
            }
            input[type="text"]:focus, input[type="email"]:focus, input[type="password"]:focus, select:focus {
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
            }
            .btn {
                display: inline-block;
                background: linear-gradient(135deg, #3498db, #2980b9);
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px 5px;
                border: none;
                cursor: pointer;
                font-size: 16px;
                font-weight: 500;
                transition: all 0.3s ease;
                text-align: center;
                min-width: 120px;
            }
            .btn:hover {
                background: linear-gradient(135deg, #2980b9, #1f5f8b);
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3);
            }
            .btn-success {
                background: linear-gradient(135deg, #27ae60, #229954);
            }
            .btn-success:hover {
                background: linear-gradient(135deg, #229954, #1e8449);
                box-shadow: 0 5px 15px rgba(39, 174, 96, 0.3);
            }
            .status {
                background: linear-gradient(135deg, #d4edda, #c3e6cb);
                color: #155724;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
                font-weight: 500;
                border-left: 4px solid #28a745;
            }
            .error {
                background: linear-gradient(135deg, #f8d7da, #f1aeb5);
                color: #721c24;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: center;
                font-weight: 500;
                border-left: 4px solid #dc3545;
            }
            .nav-links {
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e1e8ed;
            }
            .nav-links a {
                color: #3498db;
                text-decoration: none;
                margin: 0 15px;
                font-weight: 500;
            }
            .nav-links a:hover {
                color: #2980b9;
                text-decoration: underline;
            }
            .form-title {
                text-align: center;
                margin-bottom: 30px;
                color: #2c3e50;
                font-size: 1.8em;
                font-weight: 400;
            }
            .welcome-text {
                text-align: center;
                margin-top: 30px;
                color: #7f8c8d;
                font-style: italic;
            }
        </style>
    '''

@app.route('/')
def home():
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Система адаптивного обучения математике</title>
        {get_base_styles()}
    </head>
    <body>
        <div class="container">
            <h1>🎓 Система адаптивного обучения математике</h1>
            
            <div class="status">
                ✅ Приложение работает стабильно и красиво!
            </div>
            
            <div style="text-align: center;">
                <a href="/register" class="btn">📝 Регистрация</a>
                <a href="/login" class="btn">🔐 Вход</a>
            </div>
            
            <div class="welcome-text">
                Версия 2.2 - стабильная версия с улучшенным дизайном
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role', 'student')
            first_name = request.form.get('first_name', '')
            last_name = request.form.get('last_name', '')
            
            # Проверяем, что пользователь не существует
            if User.query.filter_by(username=username).first():
                return f'''
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Ошибка регистрации</title>
                    {get_base_styles()}
                </head>
                <body>
                    <div class="container">
                        <div class="form-title">⚠️ Ошибка регистрации</div>
                        
                        <div class="error">
                            Пользователь с таким именем уже существует!
                        </div>
                        
                        <div style="text-align: center;">
                            <a href="/register" class="btn">← Попробовать снова</a>
                            <a href="/login" class="btn">Уже есть аккаунт? Войти</a>
                        </div>
                    </div>
                </body>
                </html>
                '''
            
            if User.query.filter_by(email=email).first():
                return f'''
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Ошибка регистрации</title>
                    {get_base_styles()}
                </head>
                <body>
                    <div class="container">
                        <div class="form-title">⚠️ Ошибка регистрации</div>
                        
                        <div class="error">
                            Пользователь с таким email уже существует!
                        </div>
                        
                        <div style="text-align: center;">
                            <a href="/register" class="btn">← Попробовать снова</a>
                            <a href="/login" class="btn">Уже есть аккаунт? Войти</a>
                        </div>
                    </div>
                </body>
                </html>
                '''
            
            # Создаем нового пользователя
            user = User(
                username=username,
                email=email,
                role=role,
                first_name=first_name,
                last_name=last_name
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Создаем профиль для студента
            if role == 'student':
                profile = StudentProfile(user_id=user.id)
                db.session.add(profile)
                db.session.commit()
            
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Успешная регистрация</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="form-title">✅ Успешная регистрация!</div>
                    
                    <div class="status">
                        🎉 Поздравляем! Ваш аккаунт успешно создан.
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <p style="color: #6c757d;">Теперь вы можете войти в систему с вашими данными.</p>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="/login" class="btn btn-success">🔐 Войти в систему</a>
                        <a href="/" class="btn">← На главную</a>
                    </div>
                </div>
            </body>
            </html>
            '''
            
        except Exception as e:
            db.session.rollback()
            return f'<h1>Ошибка</h1><p>Ошибка при регистрации: {str(e)}</p><a href="/register">Назад</a>'
    
    # GET запрос - показываем форму регистрации
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Регистрация - Система адаптивного обучения</title>
        {get_base_styles()}
    </head>
    <body>
        <div class="container">
            <div class="form-title">📝 Регистрация нового пользователя</div>
            
            <form method="POST">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Имя пользователя" required>
                </div>
                
                <div class="form-group">
                    <input type="email" name="email" placeholder="Email" required>
                </div>
                
                <div class="form-group">
                    <input type="password" name="password" placeholder="Пароль" required>
                </div>
                
                <div class="form-group">
                    <input type="text" name="first_name" placeholder="Имя (необязательно)">
                </div>
                
                <div class="form-group">
                    <input type="text" name="last_name" placeholder="Фамилия (необязательно)">
                </div>
                
                <div class="form-group">
                    <select name="role">
                        <option value="student">👨‍🎓 Студент</option>
                        <option value="teacher">👨‍🏫 Преподаватель</option>
                    </select>
                </div>
                
                <div style="text-align: center;">
                    <button type="submit" class="btn btn-success">Зарегистрироваться</button>
                </div>
            </form>
            
            <div class="nav-links">
                <a href="/">← Главная</a>
                <a href="/login">Уже есть аккаунт? Войти</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('dashboard'))
            else:
                return f'''
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Ошибка входа</title>
                    {get_base_styles()}
                </head>
                <body>
                    <div class="container">
                        <div class="form-title">⚠️ Ошибка входа</div>
                        
                        <div class="error">
                            Неверное имя пользователя или пароль!
                        </div>
                        
                        <div style="text-align: center;">
                            <a href="/login" class="btn">← Попробовать снова</a>
                            <a href="/register" class="btn">Нет аккаунта? Регистрация</a>
                        </div>
                    </div>
                </body>
                </html>
                '''
                
        except Exception as e:
            db.session.rollback()
            return f'<h1>Ошибка</h1><p>Ошибка при входе: {str(e)}</p><a href="/login">Назад</a>'
    
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход - Система адаптивного обучения</title>
        {get_base_styles()}
    </head>
    <body>
        <div class="container">
            <div class="form-title">🔐 Вход в систему</div>
            
            <form method="POST">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Имя пользователя" required>
                </div>
                
                <div class="form-group">
                    <input type="password" name="password" placeholder="Пароль" required>
                </div>
                
                <div style="text-align: center;">
                    <button type="submit" class="btn btn-success">Войти в систему</button>
                </div>
            </form>
            
            <div class="nav-links">
                <a href="/">← Главная</a>
                <a href="/register">Нет аккаунта? Регистрация</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_name = current_user.get_full_name() if hasattr(current_user, 'get_full_name') else current_user.username
        
        if current_user.role == 'student':
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Панель студента - Система адаптивного обучения</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <h1>🎓 Панель студента</h1>
                    
                    <div class="status">
                        🚀 Добро пожаловать, {user_name}!
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #495057; margin-top: 0;">📊 Ваша статистика:</h3>
                        <p><strong>Роль:</strong> {current_user.role.title()}</p>
                        <p><strong>Последний вход:</strong> {current_user.last_login.strftime('%d.%m.%Y %H:%M') if current_user.last_login else 'Первый вход'}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <h3 style="color: #495057;">📚 Математические задания</h3>
                        <a href="/tasks" class="btn btn-success">📈 Посмотреть задания</a>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="/logout" class="btn">🚪 Выйти из системы</a>
                    </div>
                </div>
            </body>
            </html>
            '''
        else:
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Панель преподавателя - Система адаптивного обучения</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <h1>👨‍🏫 Панель преподавателя</h1>
                    
                    <div class="status">
                        🎆 Добро пожаловать, {user_name}!
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #495057; margin-top: 0;">📊 Информация о профиле:</h3>
                        <p><strong>Роль:</strong> {current_user.role.title()}</p>
                        <p><strong>Последний вход:</strong> {current_user.last_login.strftime('%d.%m.%Y %H:%M') if current_user.last_login else 'Первый вход'}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <h3 style="color: #495057;">🛠️ Инструменты преподавателя</h3>
                        <a href="/tasks" class="btn">📚 Посмотреть задания</a>
                        <a href="/create-task" class="btn btn-success">➕ Создать задание</a>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="/logout" class="btn">🚪 Выйти из системы</a>
                    </div>
                </div>
            </body>
            </html>
            '''
    except Exception as e:
        return f'<h1>Ошибка панели управления</h1><p>Ошибка: {str(e)}</p><p><a href="/logout">Выйти</a></p>'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/tasks')
@login_required
def tasks_list():
    """Список всех доступных задач"""
    try:
        # Получаем все активные задачи
        tasks = MathTask.query.filter_by(is_active=True).order_by(MathTask.created_at.desc()).all()
        
        # Для студентов показываем их попытки
        user_attempts = {}
        if current_user.role == 'student':
            attempts = TaskAttempt.query.filter_by(user_id=current_user.id).all()
            for attempt in attempts:
                if attempt.task_id not in user_attempts:
                    user_attempts[attempt.task_id] = []
                user_attempts[attempt.task_id].append(attempt)
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Математические задания</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>📚 Математические задания</h1>
                
                <div style="text-align: center; margin-bottom: 30px;">
                    <a href="/dashboard" class="btn">← Назад в панель</a>
                    {('<a href="/create-task" class="btn btn-success">➕ Создать задание</a>' if current_user.role == 'teacher' else '')}
                </div>
                
                {''.join([f'''
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #3498db;">
                    <h3 style="color: #2c3e50; margin-top: 0;">{task.title}</h3>
                    <p style="color: #6c757d;"><strong>Тема:</strong> {task.topic}</p>
                    <p style="color: #6c757d;"><strong>Сложность:</strong> {task.difficulty_level}/5</p>
                    <p style="color: #6c757d;"><strong>Максимальный балл:</strong> {task.max_score}</p>
                    
                    {(f'<p style="color: #28a745;"><strong>Ваши попытки:</strong> {len(user_attempts.get(task.id, []))}</p>' if current_user.role == 'student' and task.id in user_attempts else '')}
                    
                    <div style="text-align: right; margin-top: 15px;">
                        <a href="/task/{task.id}" class="btn btn-success">{'📝 Решать' if current_user.role == 'student' else '👁️ Посмотреть'}</a>
                    </div>
                </div>
                ''' for task in tasks])}
                
                {('<div style="text-align: center; color: #6c757d; margin: 40px 0;"><p>Пока нет доступных заданий.</p></div>' if not tasks else '')}
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'<h1>Ошибка</h1><p>Ошибка при загрузке заданий: {str(e)}</p><p><a href="/dashboard">← Назад</a></p>'

@app.route('/task/<int:task_id>')
@login_required
def view_task(task_id):
    """Просмотр конкретной задачи"""
    try:
        task = MathTask.query.get_or_404(task_id)
        
        # Получаем попытки пользователя для этой задачи
        user_attempts = []
        if current_user.role == 'student':
            user_attempts = TaskAttempt.query.filter_by(
                user_id=current_user.id, 
                task_id=task_id
            ).order_by(TaskAttempt.created_at.desc()).all()
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{task.title}</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>📝 {task.title}</h1>
                
                <div style="text-align: center; margin-bottom: 30px;">
                    <a href="/tasks" class="btn">← Назад к заданиям</a>
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">📋 Условие задачи:</h3>
                    <p style="white-space: pre-wrap; line-height: 1.6;">{task.description}</p>
                </div>
                
                <div style="background: #e3f2fd; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <p><strong>📊 Тема:</strong> {task.topic}</p>
                    <p><strong>⭐ Сложность:</strong> {task.difficulty_level}/5</p>
                    <p><strong>🎯 Максимальный балл:</strong> {task.max_score}</p>
                    <p><strong>📅 Создано:</strong> {task.created_at.strftime('%d.%m.%Y %H:%M')}</p>
                </div>
                
                {(f'''
                <div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">📈 Ваши попытки: {len(user_attempts)}</h3>
                    {(''.join([f'<p><strong>Попытка {i+1}:</strong> Балл {attempt.partial_score}/{task.max_score} ({attempt.created_at.strftime("%d.%m.%Y %H:%M")})</p>' for i, attempt in enumerate(user_attempts[:3])]) if user_attempts else '<p>Попыток пока нет</p>')}
                </div>
                ''' if current_user.role == 'student' else '')}
                
                {(f'''
                <form method="POST" action="/solve-task/{task_id}">
                    <div style="background: white; padding: 20px; border-radius: 10px; margin: 20px 0; border: 2px solid #3498db;">
                        <h3 style="color: #2c3e50; margin-top: 0;">✏️ Ваш ответ:</h3>
                        <div class="form-group">
                            <textarea name="answer" placeholder="Введите ваш ответ здесь..." 
                                style="width: 100%; height: 120px; padding: 15px; border: 2px solid #e1e8ed; border-radius: 8px; font-size: 16px; resize: vertical;" 
                                required></textarea>
                        </div>
                        <div style="text-align: center;">
                            <button type="submit" class="btn btn-success">🚀 Отправить решение</button>
                        </div>
                    </div>
                </form>
                ''' if current_user.role == 'student' else '')}
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'<h1>Ошибка</h1><p>Ошибка при загрузке задачи: {str(e)}</p><p><a href="/tasks">← Назад</a></p>'

@app.route('/solve-task/<int:task_id>', methods=['POST'])
@login_required
def solve_task(task_id):
    """Обработка решения задачи студентом"""
    if current_user.role != 'student':
        return redirect(url_for('tasks_list'))
    
    try:
        task = MathTask.query.get_or_404(task_id)
        user_answer = request.form.get('answer', '').strip()
        
        if not user_answer:
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Ошибка</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="form-title">⚠️ Ошибка</div>
                    <div class="error">Пожалуйста, введите ответ!</div>
                    <div style="text-align: center;">
                        <a href="/task/{task_id}" class="btn">← Назад к задаче</a>
                    </div>
                </div>
            </body>
            </html>
            '''
        
        # Подсчет номера попытки
        attempt_number = TaskAttempt.query.filter_by(
            user_id=current_user.id, 
            task_id=task_id
        ).count() + 1
        
        # Простая проверка ответа (пока что текстовое сравнение)
        # В будущем здесь будет более сложная логика
        is_correct = False
        partial_score = 0.0
        
        # Попробуем сравнить с правильным ответом
        try:
            if isinstance(task.correct_answer, dict):
                # Если ответ в JSON формате, пока просто сравниваем как строку
                correct_str = str(task.correct_answer.get('value', ''))
                is_correct = user_answer.lower().strip() == correct_str.lower().strip()
            else:
                # Простое текстовое сравнение
                is_correct = user_answer.lower().strip() == str(task.correct_answer).lower().strip()
            
            if is_correct:
                partial_score = task.max_score
        except:
            # Если не удалось сравнить, считаем неправильным
            is_correct = False
            partial_score = 0.0
        
        # Сохраняем попытку
        attempt = TaskAttempt(
            user_id=current_user.id,
            task_id=task_id,
            user_answer={'text': user_answer},
            is_correct=is_correct,
            partial_score=partial_score,
            attempt_number=attempt_number
        )
        
        db.session.add(attempt)
        db.session.commit()
        
        # Показываем результат
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Результат решения</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <div class="form-title">📊 Результат решения</div>
                
                <div class="{'status' if is_correct else 'error'}">
                    {'🎉 Правильно! Отличная работа!' if is_correct else '❌ Ответ неверный. Попробуйте еще раз!'}
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">📝 Ваш ответ:</h3>
                    <p style="background: white; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">{user_answer}</p>
                    
                    <h3 style="color: #495057;">📊 Результат:</h3>
                    <p><strong>Балл:</strong> {partial_score}/{task.max_score}</p>
                    <p><strong>Попытка №:</strong> {attempt_number}</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="/task/{task_id}" class="btn">🔄 Попробовать еще раз</a>
                    <a href="/tasks" class="btn btn-success">📚 К другим заданиям</a>
                </div>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        db.session.rollback()
        return f'<h1>Ошибка</h1><p>Ошибка при сохранении решения: {str(e)}</p><p><a href="/task/{task_id}">← Назад</a></p>'

@app.route('/create-task', methods=['GET', 'POST'])
@login_required
def create_task():
    """Создание новой задачи (только для преподавателей)"""
    if current_user.role != 'teacher':
        return redirect(url_for('tasks_list'))
    
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            topic = request.form.get('topic', '').strip()
            difficulty_level = float(request.form.get('difficulty_level', 1))
            max_score = float(request.form.get('max_score', 1))
            correct_answer = request.form.get('correct_answer', '').strip()
            explanation = request.form.get('explanation', '').strip()
            
            if not all([title, description, topic, correct_answer]):
                return f'''
                <!DOCTYPE html>
                <html lang="ru">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Ошибка</title>
                    {get_base_styles()}
                </head>
                <body>
                    <div class="container">
                        <div class="form-title">⚠️ Ошибка</div>
                        <div class="error">Пожалуйста, заполните все обязательные поля!</div>
                        <div style="text-align: center;">
                            <a href="/create-task" class="btn">← Назад</a>
                        </div>
                    </div>
                </body>
                </html>
                '''
            
            # Создаем новую задачу
            task = MathTask(
                title=title,
                description=description,
                topic=topic,
                difficulty_level=difficulty_level,
                max_score=max_score,
                correct_answer={'value': correct_answer, 'type': 'text'},
                explanation=explanation if explanation else None,
                answer_type='text',
                created_by=current_user.id
            )
            
            db.session.add(task)
            db.session.commit()
            
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Успешно создано</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="form-title">✅ Задание создано!</div>
                    
                    <div class="status">
                        🎉 Задание "{title}" успешно создано и доступно для студентов!
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="/tasks" class="btn btn-success">📚 Посмотреть все задания</a>
                        <a href="/create-task" class="btn">➕ Создать еще одно</a>
                    </div>
                </div>
            </body>
            </html>
            '''
            
        except Exception as e:
            db.session.rollback()
            return f'<h1>Ошибка</h1><p>Ошибка при создании задания: {str(e)}</p><p><a href="/create-task">← Назад</a></p>'
    
    # GET запрос - показываем форму создания
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Создание задания</title>
        {get_base_styles()}
    </head>
    <body>
        <div class="container">
            <div class="form-title">➕ Создание нового задания</div>
            
            <form method="POST">
                <div class="form-group">
                    <input type="text" name="title" placeholder="Название задания" required>
                </div>
                
                <div class="form-group">
                    <textarea name="description" placeholder="Описание задачи (условие)" 
                        style="width: 100%; height: 150px; padding: 15px; border: 2px solid #e1e8ed; border-radius: 8px; font-size: 16px; resize: vertical;" 
                        required></textarea>
                </div>
                
                <div class="form-group">
                    <input type="text" name="topic" placeholder="Тема (например: Алгебра, Геометрия)" required>
                </div>
                
                <div class="form-group">
                    <select name="difficulty_level">
                        <option value="1">⚫ Очень легко (1/5)</option>
                        <option value="2">🟢 Легко (2/5)</option>
                        <option value="3" selected>🟡 Средне (3/5)</option>
                        <option value="4">🟠 Сложно (4/5)</option>
                        <option value="5">🔴 Очень сложно (5/5)</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <input type="number" name="max_score" placeholder="Максимальный балл" min="0.1" max="10" step="0.1" value="1" required>
                </div>
                
                <div class="form-group">
                    <input type="text" name="correct_answer" placeholder="Правильный ответ" required>
                </div>
                
                <div class="form-group">
                    <textarea name="explanation" placeholder="Объяснение решения (необязательно)" 
                        style="width: 100%; height: 100px; padding: 15px; border: 2px solid #e1e8ed; border-radius: 8px; font-size: 16px; resize: vertical;"></textarea>
                </div>
                
                <div style="text-align: center;">
                    <button type="submit" class="btn btn-success">✅ Создать задание</button>
                </div>
            </form>
            
            <div class="nav-links">
                <a href="/tasks">← К списку заданий</a>
                <a href="/dashboard">Панель управления</a>
            </div>
        </div>
    </body>
    </html>
    '''

def create_sample_tasks():
    """Создаем несколько тестовых задач для демонстрации"""
    try:
        # Проверяем, есть ли уже задачи
        if MathTask.query.count() > 0:
            return
        
        # Находим первого преподавателя или создаем системного
        teacher = User.query.filter_by(role='teacher').first()
        if not teacher:
            # Создаем системного преподавателя
            teacher = User(
                username='system_teacher',
                email='system@example.com',
                role='teacher',
                first_name='Система',
                last_name='Обучения'
            )
            teacher.set_password('system123')
            db.session.add(teacher)
            db.session.commit()
        
        # Создаем тестовые задачи
        sample_tasks = [
            {
                'title': 'Простое уравнение',
                'description': 'Решите уравнение:\n\n2x + 5 = 13\n\nНайдите значение x.',
                'topic': 'Алгебра',
                'difficulty_level': 2.0,
                'max_score': 1.0,
                'correct_answer': {'value': '4', 'type': 'text'},
                'explanation': '2x + 5 = 13\n2x = 13 - 5\n2x = 8\nx = 4'
            },
            {
                'title': 'Площадь прямоугольника',
                'description': 'Прямоугольник имеет длину 8 см и ширину 5 см.\n\nНайдите площадь прямоугольника в квадратных сантиметрах.',
                'topic': 'Геометрия',
                'difficulty_level': 1.0,
                'max_score': 1.0,
                'correct_answer': {'value': '40', 'type': 'text'},
                'explanation': 'Площадь = длина × ширина\nПлощадь = 8 × 5 = 40 см²'
            },
            {
                'title': 'Квадратное уравнение',
                'description': 'Решите квадратное уравнение:\n\nx² - 5x + 6 = 0\n\nНайдите все корни уравнения. Ответ запишите через запятую.',
                'topic': 'Алгебра',
                'difficulty_level': 3.0,
                'max_score': 2.0,
                'correct_answer': {'value': '2,3', 'type': 'text'},
                'explanation': 'x² - 5x + 6 = 0\nИспользуем формулу квадратного уравнения или разложение на множители:\n(x-2)(x-3) = 0\nx = 2 или x = 3'
            }
        ]
        
        for task_data in sample_tasks:
            task = MathTask(
                title=task_data['title'],
                description=task_data['description'],
                topic=task_data['topic'],
                difficulty_level=task_data['difficulty_level'],
                max_score=task_data['max_score'],
                correct_answer=task_data['correct_answer'],
                explanation=task_data['explanation'],
                answer_type='text',
                created_by=teacher.id
            )
            db.session.add(task)
        
        db.session.commit()
        print(f"Создано {len(sample_tasks)} тестовых заданий!")
        
    except Exception as e:
        print(f"Ошибка при создании тестовых заданий: {e}")
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы базы данных
        db.create_all()
        # Создаем тестовые задания для демонстрации
        create_sample_tasks()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
