import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from flask import Flask, render_template
from flask_wtf.csrf import generate_csrf

from config import Config
from extensions import db, csrf, login_manager

load_dotenv()  # подтягиваем .env при старте

def create_default_admin():
    """Создаёт администратора, если его ещё нет."""
    from models import User  # Импорт внутри функции для избежания циклических импортов
    
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123").strip()
    if not admin_email or not admin_password:
        return
    if not User.query.filter_by(role="admin").first():
        admin = User(
            username=admin_email.split("@")[0],
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            role="admin",
            is_active=True,
        )
        db.session.add(admin)
        db.session.commit()

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Конфиг из класса + возможность переопределять через env
    app.config.from_object(Config)

    # Расширения
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # Блюпринты
    from blueprints.main import main_bp
    from blueprints.tasks import tasks_bp
    from blueprints.admin import admin_bp
    from blueprints.auth import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(auth_bp,  url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Jinja: csrf_token() во все шаблоны
    @app.context_processor
    def inject_csrf():
        return {"csrf_token": generate_csrf}

    # Обработчики ошибок (регистрируем на app)
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('shared/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('shared/500.html'), 500

    # CLI команды
    @app.cli.command("init-db")
    def init_db():
        """Инициализация базы данных"""
        db.create_all()
        print("DB created")
        
    @app.cli.command("create-admin")
    def create_admin():
        """Создание администратора"""
        create_default_admin()
        print("Admin created")

    # Создание таблиц на первом старте
    with app.app_context():
        db.create_all()
        print("Database tables created")

    return app

# Локальный запуск (python app.py)
if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8083)),
        debug=True
    )
