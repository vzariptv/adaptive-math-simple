from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, get_flashed_messages
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, StudentProfile
import os
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
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

# Вызываем инициализацию при импорте модуля
init_db()

@app.route('/')
def home():
    # Получаем flash-сообщения для главной страницы (например, о выходе из системы)
    messages = []
    flashed_messages = get_flashed_messages(with_categories=True)
    for category, message in flashed_messages:
        if category == 'info' and 'вышли' in message:
            color = '#d1ecf1'
            text_color = '#0c5460'
            messages.append(f'<div style="background: {color}; color: {text_color}; padding: 15px; margin: 20px 0; border-radius: 5px; text-align: center;">{message}</div>')
    
    messages_html = ''.join(messages)
    
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Система адаптивного обучения математике</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                text-align: center;
                margin-bottom: 30px;
            }
            .btn {
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px;
                border: none;
                cursor: pointer;
            }
            .btn:hover {
                background: #2980b9;
            }
            .status {
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 Система адаптивного обучения математике v2.0</h1>
            
            {messages_html}
            
            <div class="status">
                ✅ Приложение с базой данных успешно запущено!
            </div>
            
            <div style="text-align: center;">
                <a href="/register" class="btn">📝 Регистрация</a>
                <a href="/login" class="btn">🔐 Вход</a>
            </div>
            
            <p style="text-align: center; margin-top: 30px; color: #7f8c8d;">
                Версия 2.0 - с базой данных и регистрацией пользователей
            </p>
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
                flash('Пользователь с таким именем уже существует!', 'error')
                return redirect(url_for('register'))
            
            if User.query.filter_by(email=email).first():
                flash('Пользователь с таким email уже существует!', 'error')
                return redirect(url_for('register'))
            
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
            
            flash('Регистрация успешна! Теперь вы можете войти в систему.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            flash(f'Ошибка при регистрации: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    # GET запрос - показываем форму регистрации
    # Получаем только релевантные flash-сообщения для страницы входа
    messages = []
    flashed_messages = get_flashed_messages(with_categories=True)
    for category, message in flashed_messages:
        # Показываем только ошибки входа, не приветствия и не сообщения о выходе
        if category == 'error' or (category == 'success' and 'Добро пожаловать' not in message and 'вышли' not in message):
            color = '#d4edda' if category == 'success' else '#f8d7da'
            text_color = '#155724' if category == 'success' else '#721c24'
            messages.append(f'<div style="background: {color}; color: {text_color}; padding: 10px; margin: 10px 0; border-radius: 5px;">{message}</div>')
    
    messages_html = ''.join(messages)
    
    return f'''
    <h1>📝 Регистрация</h1>
    {messages_html}
    <form method="POST">
        <p><input type="text" name="username" placeholder="Имя пользователя" required></p>
        <p><input type="email" name="email" placeholder="Email" required></p>
        <p><input type="password" name="password" placeholder="Пароль" required></p>
        <p><input type="text" name="first_name" placeholder="Имя"></p>
        <p><input type="text" name="last_name" placeholder="Фамилия"></p>
        <p>
            <select name="role">
                <option value="student">Студент</option>
                <option value="teacher">Преподаватель</option>
            </select>
        </p>
        <p><button type="submit">Зарегистрироваться</button></p>
    </form>
    <p><a href="/">← Главная</a> | <a href="/login">Войти</a></p>
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
                # Упрощенное обновление времени последнего входа
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash(f'Добро пожаловать, {user.get_full_name()}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Неверное имя пользователя или пароль!', 'error')
                
        except Exception as e:
            db.session.rollback()
            print(f"Login error: {str(e)}")
            flash(f'Ошибка при входе: {str(e)}', 'error')
            return redirect(url_for('login'))
    
    # Получаем только релевантные flash-сообщения для страницы входа
    messages = []
    flashed_messages = get_flashed_messages(with_categories=True)
    for category, message in flashed_messages:
        # Показываем только ошибки входа, не приветствия и не сообщения о выходе
        if category == 'error' or (category == 'success' and 'Добро пожаловать' not in message and 'вышли' not in message):
            color = '#d4edda' if category == 'success' else '#f8d7da'
            text_color = '#155724' if category == 'success' else '#721c24'
            messages.append(f'<div style="background: {color}; color: {text_color}; padding: 10px; margin: 10px 0; border-radius: 5px;">{message}</div>')
    
    messages_html = ''.join(messages)
    
    return f'''
    <h1>🔐 Вход в систему</h1>
    {messages_html}
    <form method="POST">
        <p><input type="text" name="username" placeholder="Имя пользователя" required></p>
        <p><input type="password" name="password" placeholder="Пароль" required></p>
        <p><button type="submit">Войти</button></p>
    </form>
    <p><a href="/">← Главная</a> | <a href="/register">Регистрация</a></p>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_name = current_user.get_full_name() if hasattr(current_user, 'get_full_name') else current_user.username
        
        if current_user.role == 'student':
            return f'''
            <h1>🎓 Панель студента</h1>
            <p>Добро пожаловать, {user_name}!</p>
            <p>Роль: {current_user.role}</p>
            <p>Функциональность в разработке...</p>
            <p><a href="/logout">Выйти</a></p>
            '''
        else:
            return f'''
            <h1>👨‍🏫 Панель преподавателя</h1>
            <p>Добро пожаловать, {user_name}!</p>
            <p>Роль: {current_user.role}</p>
            <p>Функциональность в разработке...</p>
            <p><a href="/logout">Выйти</a></p>
            '''
    except Exception as e:
        return f'<h1>Ошибка панели управления</h1><p>Ошибка: {str(e)}</p><p><a href="/logout">Выйти</a></p>'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'info')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы базы данных
        db.create_all()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
