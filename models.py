from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

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

# Модель StudentProfile удалена согласно новой архитектуре
# Заменена на Topic-based систему оценки

class Topic(db.Model):
    """Справочник тем обучения"""
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Например: 'quadratic_equations'
    name = db.Column(db.String(100), nullable=False)              # Название темы: 'Квадратные уравнения'
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    tasks = db.relationship('MathTask', backref='topic_ref', lazy='dynamic')
    level_configs = db.relationship('TopicLevelConfig', backref='topic', lazy='dynamic')
    
    def __repr__(self):
        return f'<Topic {self.name}>'

class MathTask(db.Model):
    """Олимпиадные математические задания"""
    __tablename__ = 'math_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Структура ответа
    answer_type = db.Column(db.String(50), nullable=False)  # 'number', 'variables', 'interval', 'sequence'
    correct_answer = db.Column(db.JSON, nullable=False)     # JSON с правильным ответом
    answer_schema = db.Column(db.JSON)                      # JSON схема полей для ввода
    
    explanation = db.Column(db.Text)
    
    # Новая архитектура: тема и уровень
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'
    
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

class TopicLevelConfig(db.Model):
    """Конфигурация параметров для каждой темы и уровня сложности"""
    __tablename__ = 'topic_level_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'
    
    task_count_threshold = db.Column(db.Integer, nullable=False)         # Пороговое число задач за период
    reference_time = db.Column(db.Integer, nullable=False)              # Эталонное время (сек)
    penalty_weights = db.Column(db.JSON, nullable=False)                # Штрафы за попытки [0.7, 0.4] для 2-й и 3-й попытки
    
    __table_args__ = (db.UniqueConstraint('topic_id', 'level', name='_topic_level_uc'),)
    
    def __repr__(self):
        return f'<TopicLevelConfig {self.topic.name if hasattr(self, "topic") else self.topic_id} {self.level}>'

class StudentEvaluationLog(db.Model):
    """Журнал результатов оценки студентов"""
    __tablename__ = 'student_evaluation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'
    
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    
    # Рассчитанные метрики
    accuracy = db.Column(db.Float)
    avg_time = db.Column(db.Float)
    progress = db.Column(db.Float)
    motivation = db.Column(db.Float)
    total_score = db.Column(db.Float)
    
    level_change = db.Column(db.String(10))  # 'up', 'down', 'stay', 'mastered'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    user = db.relationship('User', backref='evaluation_logs')
    topic = db.relationship('Topic', backref='evaluation_logs')
    
    def __repr__(self):
        return f'<StudentEvaluationLog user_id={self.user_id} topic_id={self.topic_id} {self.level}>'

class StudentTopicProgress(db.Model):
    """Текущий прогресс студента по теме"""
    __tablename__ = 'student_topic_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    
    current_level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'
    is_mastered = db.Column(db.Boolean, default=False)
    last_evaluated_at = db.Column(db.DateTime)
    
    # Связи
    user = db.relationship('User', backref='topic_progress')
    topic = db.relationship('Topic', backref='student_progress')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'topic_id'),)
    
    def __repr__(self):
        return f'<StudentTopicProgress user_id={self.user_id} topic_id={self.topic_id} {self.current_level}>'

class EvaluationSystemConfig(db.Model):
    """Глобальная конфигурация системы оценки"""
    __tablename__ = 'evaluation_system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Параметры периода оценки
    evaluation_period_days = db.Column(db.Integer, default=7)
    weekend_bonus_multiplier = db.Column(db.Float, default=1.5)
    
    # Веса для итоговой формулы
    weight_accuracy = db.Column(db.Float, default=0.3)
    weight_time = db.Column(db.Float, default=0.2)
    weight_progress = db.Column(db.Float, default=0.3)
    weight_motivation = db.Column(db.Float, default=0.2)
    
    # Пороговые значения для переходов между уровнями
    min_threshold_low = db.Column(db.Float, default=0.3)
    max_threshold_low = db.Column(db.Float, default=0.7)
    min_threshold_medium = db.Column(db.Float, default=0.4)
    max_threshold_medium = db.Column(db.Float, default=0.8)
    # Последний уровень (high) не требует min_threshold / max_threshold
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EvaluationSystemConfig id={self.id}>'
