from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Модель пользователя (студенты и преподаватели)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'student' или 'teacher'
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Связи
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False)
    task_attempts = db.relationship('TaskAttempt', backref='user', lazy='dynamic')
    created_tasks = db.relationship('MathTask', backref='creator', lazy='dynamic')
    
    def set_password(self, password):
        """Установить хэш пароля (совместимый метод)"""
        # Используем pbkdf2 для максимальной совместимости
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Проверить пароль"""
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        """Получить полное имя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>'

class StudentProfile(db.Model):
    """Профиль студента для адаптивного алгоритма"""
    __tablename__ = 'student_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Многокритериальные показатели (0-1)
    knowledge_level = db.Column(db.Float, default=0.5)      # Уровень знаний
    learning_speed = db.Column(db.Float, default=0.5)       # Скорость обучения
    motivation_level = db.Column(db.Float, default=0.7)     # Мотивация
    attention_span = db.Column(db.Float, default=0.6)       # Концентрация
    preferred_difficulty = db.Column(db.Float, default=0.5) # Предпочитаемая сложность
    
    # Интегральный показатель эффективности
    efficiency_score = db.Column(db.Float, default=0.5)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<StudentProfile user_id={self.user_id}>'

class MathTask(db.Model):
    """Олимпиадные математические задания"""
    __tablename__ = 'math_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Структура ответа
    answer_type = db.Column(db.String(50), nullable=False)  # 'single', 'system', 'coordinates', etc.
    correct_answer = db.Column(db.JSON, nullable=False)     # JSON с правильным ответом
    answer_schema = db.Column(db.JSON)                      # JSON схема полей для ввода
    
    explanation = db.Column(db.Text)
    difficulty_level = db.Column(db.Float, nullable=False)  # 0-1
    topic = db.Column(db.String(100), nullable=False)       # Алгебра, Геометрия и т.д.
    max_score = db.Column(db.Float, default=1.0)           # Максимальный балл
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Связи
    attempts = db.relationship('TaskAttempt', backref='task', lazy='dynamic')
    
    def __repr__(self):
        return f'<MathTask {self.title}>'

class TaskAttempt(db.Model):
    """Попытки решения заданий"""
    __tablename__ = 'task_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('math_tasks.id'), nullable=False)
    
    # Ответ пользователя и результаты
    user_answer = db.Column(db.JSON)                        # JSON с ответом пользователя
    is_correct = db.Column(db.Boolean, nullable=False)      # Полностью правильно
    partial_score = db.Column(db.Float, default=0)          # Частичный балл (0-1)
    component_scores = db.Column(db.JSON)                   # Баллы по компонентам
    
    # Метаданные попытки
    time_spent = db.Column(db.Integer)                      # Время в секундах
    hints_used = db.Column(db.Integer, default=0)
    attempt_number = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskAttempt user_id={self.user_id} task_id={self.task_id}>'
