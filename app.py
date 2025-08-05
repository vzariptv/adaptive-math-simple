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
    try:
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")
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
                        <h3 style="color: #6c757d;">🛠️ Функционал в разработке</h3>
                        <p style="color: #6c757d; font-style: italic;">Скоро здесь появятся математические задания и адаптивные алгоритмы!</p>
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
                        <h3 style="color: #6c757d;">🛠️ Инструменты преподавателя</h3>
                        <p style="color: #6c757d; font-style: italic;">Скоро здесь появятся создание заданий, аналитика и управление студентами!</p>
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

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы базы данных
        db.create_all()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
