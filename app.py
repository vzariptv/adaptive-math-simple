from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, StudentProfile
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///math_learning.db')
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

@app.route('/')
def home():
    return '''
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
            .feature {
                background: #ecf0f1;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #3498db;
            }
            .status {
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                text-align: center;
                margin: 20px 0;
            }
            .nav-buttons {
                text-align: center;
                margin: 20px 0;
            }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                margin: 5px;
                background-color: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                border: none;
                cursor: pointer;
            }
            .btn:hover {
                background-color: #2980b9;
            }
            .btn-secondary {
                background-color: #95a5a6;
            }
            .btn-secondary:hover {
                background-color: #7f8c8d;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧮 Система адаптивного обучения математике</h1>
            
            <div class="status">
                ✅ Приложение с базой данных успешно запущено!
            </div>
            
            <div class="nav-buttons">
                <a href="/register" class="btn">📝 Регистрация</a>
                <a href="/login" class="btn btn-secondary">🔑 Вход</a>
            </div>
            
            <p>Добро пожаловать в систему адаптивного обучения математике для олимпиадных задач.</p>
            
            <div class="feature">
                <h3>🆕 Новые возможности:</h3>
                <ul>
                    <li>✅ База данных SQLite</li>
                    <li>✅ Регистрация пользователей</li>
                    <li>✅ Роли: студенты и преподаватели</li>
                    <li>✅ Система аутентификации</li>
                    <li>🔄 Олимпиадные задания (в разработке)</li>
                </ul>
            </div>
            
            <div class="feature">
                <h3>🎯 Поддерживаемые типы задач:</h3>
                <ul>
                    <li>Алгебраические уравнения и системы</li>
                    <li>Геометрические задачи с координатами</li>
                    <li>Комбинаторные задачи</li>
                    <li>Задачи на функции</li>
                    <li>Интервалы и множества решений</li>
                </ul>
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
    
    # GET запрос - показываем форму регистрации
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Регистрация - Система адаптивного обучения</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
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
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #34495e;
            }
            input, select {
                width: 100%;
                padding: 10px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }
            input:focus, select:focus {
                border-color: #3498db;
                outline: none;
            }
            .btn {
                width: 100%;
                padding: 12px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            .btn:hover {
                background-color: #2980b9;
            }
            .back-link {
                text-align: center;
                margin-top: 20px;
            }
            .back-link a {
                color: #3498db;
                text-decoration: none;
            }
            .alert {
                padding: 10px;
                margin-bottom: 20px;
                border-radius: 5px;
            }
            .alert-success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .alert-error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📝 Регистрация</h1>
            
            <form method="POST">
                <div class="form-group">
                    <label for="username">Имя пользователя *</label>
                    <input type="text" id="username" name="username" required>
                </div>
                
                <div class="form-group">
                    <label for="email">Email *</label>
                    <input type="email" id="email" name="email" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Пароль *</label>
                    <input type="password" id="password" name="password" required>
                </div>
                
                <div class="form-group">
                    <label for="role">Роль *</label>
                    <select id="role" name="role" required>
                        <option value="student">Студент</option>
                        <option value="teacher">Преподаватель</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="first_name">Имя</label>
                    <input type="text" id="first_name" name="first_name">
                </div>
                
                <div class="form-group">
                    <label for="last_name">Фамилия</label>
                    <input type="text" id="last_name" name="last_name">
                </div>
                
                <button type="submit" class="btn">Зарегистрироваться</button>
            </form>
            
            <div class="back-link">
                <a href="/">← Вернуться на главную</a> | 
                <a href="/login">Уже есть аккаунт? Войти</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = db.session.execute(db.text('SELECT CURRENT_TIMESTAMP')).scalar()
            db.session.commit()
            flash(f'Добро пожаловать, {user.get_full_name()}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль!', 'error')
    
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход - Система адаптивного обучения</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 500px;
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
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #34495e;
            }
            input {
                width: 100%;
                padding: 10px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }
            input:focus {
                border-color: #3498db;
                outline: none;
            }
            .btn {
                width: 100%;
                padding: 12px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            .btn:hover {
                background-color: #2980b9;
            }
            .back-link {
                text-align: center;
                margin-top: 20px;
            }
            .back-link a {
                color: #3498db;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔑 Вход в систему</h1>
            
            <form method="POST">
                <div class="form-group">
                    <label for="username">Имя пользователя</label>
                    <input type="text" id="username" name="username" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Пароль</label>
                    <input type="password" id="password" name="password" required>
                </div>
                
                <button type="submit" class="btn">Войти</button>
            </form>
            
            <div class="back-link">
                <a href="/">← Вернуться на главную</a> | 
                <a href="/register">Нет аккаунта? Зарегистрироваться</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'student':
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Панель студента</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #2c3e50;
                    margin-bottom: 20px;
                }}
                .welcome {{
                    background: #d4edda;
                    color: #155724;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .feature {{
                    background: #ecf0f1;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                    border-left: 4px solid #3498db;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    margin: 5px;
                    background-color: #e74c3c;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                }}
                .btn:hover {{
                    background-color: #c0392b;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎓 Панель студента</h1>
                
                <div class="welcome">
                    Добро пожаловать, {current_user.get_full_name()}! (Роль: {current_user.role})
                </div>
                
                <div class="feature">
                    <h3>📊 Ваш профиль обучения:</h3>
                    <p>Система адаптивного обучения создала для вас персональный профиль.</p>
                    <p><strong>Email:</strong> {current_user.email}</p>
                    <p><strong>Дата регистрации:</strong> {current_user.created_at.strftime('%d.%m.%Y')}</p>
                </div>
                
                <div class="feature">
                    <h3>🎯 Следующие шаги:</h3>
                    <ul>
                        <li>Олимпиадные задания (в разработке)</li>
                        <li>Адаптивный алгоритм (в разработке)</li>
                        <li>Статистика прогресса (в разработке)</li>
                    </ul>
                </div>
                
                <p>
                    <a href="/logout" class="btn">Выйти</a>
                </p>
            </div>
        </body>
        </html>
        '''
    else:  # teacher
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Панель преподавателя</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #2c3e50;
                    margin-bottom: 20px;
                }}
                .welcome {{
                    background: #d1ecf1;
                    color: #0c5460;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .feature {{
                    background: #ecf0f1;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                    border-left: 4px solid #17a2b8;
                }}
                .btn {{
                    display: inline-block;
                    padding: 10px 20px;
                    margin: 5px;
                    background-color: #e74c3c;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                }}
                .btn:hover {{
                    background-color: #c0392b;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>👨‍🏫 Панель преподавателя</h1>
                
                <div class="welcome">
                    Добро пожаловать, {current_user.get_full_name()}! (Роль: {current_user.role})
                </div>
                
                <div class="feature">
                    <h3>📋 Ваши возможности:</h3>
                    <ul>
                        <li>Создание олимпиадных заданий</li>
                        <li>Просмотр статистики студентов</li>
                        <li>Аналитика эффективности обучения</li>
                        <li>Рекомендации по улучшению процесса</li>
                    </ul>
                </div>
                
                <div class="feature">
                    <h3>🎯 Следующие шаги:</h3>
                    <ul>
                        <li>Интерфейс создания заданий (в разработке)</li>
                        <li>Панель аналитики (в разработке)</li>
                        <li>Система рекомендаций (в разработке)</li>
                    </ul>
                </div>
                
                <p>
                    <a href="/logout" class="btn">Выйти</a>
                </p>
            </div>
        </body>
        </html>
        '''

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
        print("База данных инициализирована!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
