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

def create_default_admin():
    """Создаем дефолтного администратора"""
    try:
        # Проверяем, есть ли уже администратор
        admin = User.query.filter_by(role='admin').first()
        if admin:
            print("Администратор уже существует")
            return
        
        # Создаем администратора
        admin = User(
            username='CalmAndManage',
            email='admin@mathsystem.local',
            role='admin',
            first_name='Система',
            last_name='Администратор'
        )
        admin.set_password('KeepMathAlive')
        
        db.session.add(admin)
        db.session.commit()
        print("Администратор успешно создан: CalmAndManage")
        
    except Exception as e:
        print(f"Ошибка при создании администратора: {e}")
        db.session.rollback()

# Функции создания демо-данных удалены - используйте импорт заданий через админку

# Инициализация базы данных для продакшена
def init_db():
    """Инициализация базы данных"""
    with app.app_context():
        try:
            # Создаем таблицы
            db.create_all()
            print("Database tables created successfully!")
            
            # Создаем администратора
            create_default_admin()
            
        except Exception as e:
            print(f"Error initializing database: {e}")

# Регистрация blueprints
from blueprints.main import main_bp
from blueprints.auth import auth_bp
from blueprints.tasks import tasks_bp
from blueprints.admin import admin_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(tasks_bp, url_prefix='/tasks')
app.register_blueprint(admin_bp, url_prefix='/admin')

# Маршрут для принудительного создания администратора
@app.route('/create-admin')
def create_admin_route():
    """Принудительное создание администратора (для отладки)"""
    try:
        with app.app_context():
            # Проверяем, есть ли уже администратор
            existing_admin = User.query.filter_by(username='CalmAndManage').first()
            if existing_admin:
                return f'''
                <h1>Администратор уже существует</h1>
                <p>Логин: {existing_admin.username}</p>
                <p>Email: {existing_admin.email}</p>
                <p>Роль: {existing_admin.role}</p>
                <p><a href="/auth/login">Войти в систему</a></p>
                '''
            
            # Создаем администратора
            admin = User(
                username='CalmAndManage',
                email='admin@mathsystem.local',
                role='admin',
                first_name='Система',
                last_name='Администратор'
            )
            admin.set_password('KeepMathAlive')
            
            db.session.add(admin)
            db.session.commit()
            
            return '''
            <h1>Администратор создан!</h1>
            <p><strong>Логин:</strong> CalmAndManage</p>
            <p><strong>Пароль:</strong> KeepMathAlive</p>
            <p><a href="/auth/login">Войти в систему</a></p>
            '''
            
    except Exception as e:
        db.session.rollback()
        return f'''
        <h1>Ошибка при создании администратора</h1>
        <p>{str(e)}</p>
        <p><a href="/">На главную</a></p>
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
    # Для разработки
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8083)),
        debug=True
    )
