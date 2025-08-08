from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
import os

# Создаем приложение Flask
app = Flask(__name__)

# Конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///math_learning.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'

# Инициализация CSRF защиты
csrf = CSRFProtect(app)

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
            # Создаем дефолтного администратора
            create_default_admin()
            # Создаем тестовые задания для демонстрации
            create_sample_tasks()
            # Создаем олимпиадные задания
            create_olympiad_tasks()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Регистрация blueprints
from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.tasks import tasks_bp
from blueprints.admin import admin_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(admin_bp)

# Дополнительные маршруты для совместимости
@app.route('/create-admin')
def create_admin_route():
    """Маршрут для принудительного создания администратора"""
    try:
        with app.app_context():
            create_default_admin()
            return '''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Создание администратора</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                    .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; }
                    .btn { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
                </style>
            </head>
            <body>
                <h1>✅ Администратор создан</h1>
                <div class="success">
                    <p>Администратор успешно создан!</p>
                    <p><strong>Логин:</strong> CalmAndManage</p>
                    <p><strong>Пароль:</strong> KeepMathAlive</p>
                </div>
                <p><a href="/auth/login" class="btn">Войти в систему</a></p>
            </body>
            </html>
            '''
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ошибка</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>❌ Ошибка</h1>
            <div class="error">
                <p>Ошибка при создании администратора: {str(e)}</p>
            </div>
        </body>
        </html>
        '''

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('shared/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('shared/500.html'), 500

# Вызываем инициализацию при импорте модуля
init_db()

if __name__ == '__main__':
    with app.app_context():
        # Создаем таблицы базы данных
        db.create_all()
        # Создаем дефолтного администратора
        create_default_admin()
        # Создаем тестовые задания для демонстрации
        create_sample_tasks()
        # Создаем олимпиадные задания
        create_olympiad_tasks()
    
    app.run(host='0.0.0.0', port=8083, debug=True)
