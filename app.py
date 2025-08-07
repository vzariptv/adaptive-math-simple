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
            # Создаем дефолтного администратора
            create_default_admin()
            # Создаем тестовые задания для демонстрации
            create_sample_tasks()
            # Создаем олимпиадные задания
            create_olympiad_tasks()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Вызываем инициализацию при импорте модуля
init_db()

def get_base_styles():
    """Ссылка на внешний CSS-файл"""
    return '<link rel="stylesheet" type="text/css" href="/static/css/style.css">'

@app.route('/')
def home():
    try:
        messages = get_flashed_messages()
        return render_template('shared/home.html', messages=messages)
    except Exception as e:
        return f'<h1>Ошибка</h1><p>Ошибка при загрузке главной страницы: {str(e)}</p>'

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
                return render_template('auth/register.html', error='Пользователь с таким именем уже существует!')
            
            if User.query.filter_by(email=email).first():
                return render_template('auth/register.html', error='Пользователь с таким email уже существует!')
            
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
            
            return render_template('auth/register_success.html')
            
        except Exception as e:
            db.session.rollback()
            return render_template('auth/register.html', error=f'Ошибка при регистрации: {str(e)}')
    
    # GET запрос - показываем форму регистрации
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            return render_template('auth/login.html', error='Неверное имя пользователя или пароль.')
    
    return render_template('auth/login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_name = current_user.get_full_name() if hasattr(current_user, 'get_full_name') else current_user.username
        
        if current_user.role == 'student':
            return render_template('student/dashboard.html', user_name=user_name)
        elif current_user.role == 'admin':
            return render_template('admin/dashboard.html', user_name=user_name)
        else:  # teacher
            return render_template('teacher/dashboard.html', user_name=user_name)
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
        
        return render_template('shared/tasks_list.html', tasks=tasks, user_attempts=user_attempts)
        
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
        
        return render_template('shared/view_task.html', task=task, user_attempts=user_attempts)
        
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
            return render_template('shared/solve_task_error.html', 
                                 error_message='Пожалуйста, введите ответ!', 
                                 task_id=task_id)
        
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
        return render_template('shared/solve_task_result.html',
                             task=task,
                             user_answer=user_answer,
                             is_correct=is_correct,
                             partial_score=partial_score,
                             attempt_number=attempt_number)
        
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
                return render_template('teacher/create_task.html', 
                                     error='Пожалуйста, заполните все обязательные поля!')
            
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
            
            return render_template('teacher/create_task_success.html', task_title=title)
            
        except Exception as e:
            db.session.rollback()
            return f'<h1>Ошибка</h1><p>Ошибка при создании задания: {str(e)}</p><p><a href="/create-task">← Назад</a></p>'
    
    # GET запрос - показываем форму создания
    return render_template('teacher/create_task.html')

def create_default_admin():
    """Создаем дефолтного администратора"""
    try:
        # Проверяем, существует ли админ
        existing_admin = User.query.filter_by(username='CalmAndManage').first()
        if existing_admin:
            print("Администратор уже существует")
            return
            
        # Создаем администратора
        admin = User(
            username='CalmAndManage',
            email='admin@mathsystem.local',
            role='admin'
        )
        admin.set_password('KeepMathAlive')
        
        db.session.add(admin)
        db.session.commit()
        print("Администратор успешно создан: CalmAndManage")
        
    except Exception as e:
        print(f"Ошибка при создании администратора: {e}")
        db.session.rollback()

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

def create_olympiad_tasks():
    """Создаем олимпиадные задания для демонстрации"""
    try:
        # Находим системного преподавателя
        teacher = User.query.filter_by(username='system_teacher').first()
        if not teacher:
            teacher = User.query.filter_by(role='teacher').first()
        
        if not teacher:
            print("Не найден преподаватель для создания олимпиадных задач")
            return
        
        # Проверяем, есть ли уже олимпиадные задачи
        existing_olympiad = MathTask.query.filter(MathTask.title.contains('Олимпиада')).first()
        if existing_olympiad:
            print("Олимпиадные задачи уже существуют")
            return
        
        # Создаем олимпиадные задачи
        olympiad_tasks = [
            {
                'title': 'Олимпиада: Числовая последовательность',
                'description': '''Дана последовательность чисел: 2, 6, 12, 20, 30, ...

Каждое число в последовательности можно записать в виде n(n+1), где n — натуральное число.

Вопрос: Какое число стоит на 10-м месте в этой последовательности?

Подсказка: 
- 1-е число: 1×2 = 2
- 2-е число: 2×3 = 6  
- 3-е число: 3×4 = 12
- и так далее...''',
                'topic': 'Числовые последовательности',
                'difficulty_level': 4.0,
                'max_score': 3.0,
                'correct_answer': {'value': '110', 'type': 'text'},
                'explanation': '''Решение:
Последовательность имеет вид: n(n+1), где n = 1, 2, 3, ...

Для 10-го места: n = 10
10-е число = 10 × (10+1) = 10 × 11 = 110

Ответ: 110'''
            },
            {
                'title': 'Олимпиада: Геометрическая задача',
                'description': '''В треугольнике ABC проведены медианы AM, BN и CK.

Известно, что площадь треугольника ABC равна 36 см².

Вопрос: Чему равна площадь треугольника, образованного пересечением медиан (треугольник в центре)?

Справка: Медиана — это отрезок, соединяющий вершину треугольника с серединой противоположной стороны. Все три медианы пересекаются в одной точке — центроиде.''',
                'topic': 'Планиметрия',
                'difficulty_level': 5.0,
                'max_score': 4.0,
                'correct_answer': {'value': '4', 'type': 'text'},
                'explanation': '''Решение:
Медианы треугольника пересекаются в центроиде и делят треугольник на 6 равных по площади треугольников.

Центральный треугольник, образованный пересечением медиан, имеет площадь равную 1/9 от площади исходного треугольника.

Площадь центрального треугольника = 36 ÷ 9 = 4 см²

Ответ: 4'''
            },
            {
                'title': 'Олимпиада: Логическая задача с числами',
                'description': '''У Маши есть несколько монет достоинством 5 рублей и 10 рублей.

Всего у неё 17 монет на сумму 125 рублей.

Вопрос: Сколько у Маши монет достоинством 5 рублей?

Подумайте логически: если обозначить количество 5-рублевых монет как x, а 10-рублевых как y, то можно составить систему уравнений.''',
                'topic': 'Системы уравнений',
                'difficulty_level': 4.0,
                'max_score': 3.0,
                'correct_answer': {'value': '9', 'type': 'text'},
                'explanation': '''Решение:
Пусть x — количество 5-рублевых монет, y — количество 10-рублевых монет.

Составим систему уравнений:
x + y = 17 (общее количество монет)
5x + 10y = 125 (общая сумма)

Из первого уравнения: y = 17 - x
Подставим во второе: 5x + 10(17 - x) = 125
5x + 170 - 10x = 125
-5x = 125 - 170
-5x = -45
x = 9

Проверка: y = 17 - 9 = 8
9×5 + 8×10 = 45 + 80 = 125 ✓

Ответ: 9'''
            },
            {
                'title': 'Олимпиада: Задача на проценты',
                'description': '''В магазине цену товара сначала увеличили на 20%, а затем уменьшили на 20%.

Вопрос: На сколько процентов изменилась первоначальная цена товара?

Варианты ответов:
A) Не изменилась (0%)
B) Уменьшилась на 4%
C) Увеличилась на 4%
D) Уменьшилась на 2%

Введите букву правильного ответа (A, B, C или D).''',
                'topic': 'Проценты',
                'difficulty_level': 3.0,
                'max_score': 2.0,
                'correct_answer': {'value': 'B', 'type': 'text'},
                'explanation': '''Решение:
Пусть первоначальная цена = 100 рублей

После увеличения на 20%: 100 + 20% = 100 × 1.2 = 120 рублей
После уменьшения на 20%: 120 - 20% = 120 × 0.8 = 96 рублей

Итоговая цена: 96 рублей
Изменение: 96 - 100 = -4 рубля
В процентах: -4/100 × 100% = -4%

Цена уменьшилась на 4%

Ответ: B'''
            },
            {
                'title': 'Олимпиада: Комбинаторная задача',
                'description': '''На полке стоят 5 различных книг: по математике, физике, химии, биологии и истории.

Вопрос: Сколькими способами можно расставить эти книги так, чтобы книга по математике стояла рядом с книгой по физике?

Подсказка: Можно рассматривать книги по математике и физике как один "блок", но помните, что внутри блока книги тоже можно переставлять.''',
                'topic': 'Комбинаторика',
                'difficulty_level': 4.0,
                'max_score': 3.0,
                'correct_answer': {'value': '48', 'type': 'text'},
                'explanation': '''Решение:
Рассмотрим книги по математике и физике как один "блок".

Тогда у нас есть 4 объекта для расстановки:
- "блок" (математика + физика)
- химия
- биология  
- история

Эти 4 объекта можно расставить 4! = 24 способами.

Внутри "блока" математику и физику можно переставить 2! = 2 способами.

Общее количество способов: 24 × 2 = 48

Ответ: 48'''
            },
            {
                'title': 'Олимпиада: Задача на движение',
                'description': '''Два велосипедиста выехали одновременно навстречу друг другу из городов A и B.

Скорость первого велосипедиста 15 км/ч, второго — 20 км/ч.
Они встретились через 2 часа после начала движения.

Вопрос: Чему равно расстояние между городами A и B?

Подсказка: За время до встречи каждый велосипедист проехал определенное расстояние, а сумма этих расстояний равна расстоянию между городами.''',
                'topic': 'Задачи на движение',
                'difficulty_level': 3.0,
                'max_score': 2.0,
                'correct_answer': {'value': '70', 'type': 'text'},
                'explanation': '''Решение:
За 2 часа первый велосипедист проехал: 15 × 2 = 30 км
За 2 часа второй велосипедист проехал: 20 × 2 = 40 км

Расстояние между городами = 30 + 40 = 70 км

Альтернативное решение:
Скорость сближения = 15 + 20 = 35 км/ч
Расстояние = скорость × время = 35 × 2 = 70 км

Ответ: 70'''
            }
        ]
        
        for task_data in olympiad_tasks:
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
        print(f"Создано {len(olympiad_tasks)} олимпиадных заданий!")
        
    except Exception as e:
        print(f"Ошибка при создании олимпиадных заданий: {e}")
        db.session.rollback()

@app.route('/admin')
@login_required
def admin_panel():
    """Главная страница администратора"""
    # Проверяем, что пользователь - администратор
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    # Получаем статистику
    total_users = User.query.count()
    students_count = User.query.filter_by(role='student').count()
    teachers_count = User.query.filter_by(role='teacher').count()
    admins_count = User.query.filter_by(role='admin').count()
    total_tasks = MathTask.query.count()
    total_attempts = TaskAttempt.query.count()
    
    # По умолчанию открываем первую вкладку
    return redirect(url_for('admin_demo_data'))

@app.route('/admin/demo-data')
@login_required
def admin_demo_data():
    """Вкладка 1: Управление демо-данными"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    # Статистика
    stats = {
        'total_users': User.query.count(),
        'students': User.query.filter_by(role='student').count(),
        'teachers': User.query.filter_by(role='teacher').count(),
        'admins': User.query.filter_by(role='admin').count(),
        'total_tasks': MathTask.query.count(),
        'total_attempts': TaskAttempt.query.count()
    }
    
    return render_template('admin/demo_data.html', stats=stats, active_tab='demo-data')

@app.route('/admin/create-demo-users')
@login_required
def admin_create_demo_users():
    """Создание тестовых пользователей"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    try:
        created_users = []
        
        # Создаем тестового студента
        student = User.query.filter_by(username='student').first()
        if not student:
            student = User(
                username='student',
                email='student@test.com',
                role='student'
            )
            student.set_password('123456')
            db.session.add(student)
            created_users.append('Студент (student/123456)')
        
        # Создаем тестового преподавателя
        teacher = User.query.filter_by(username='teacher').first()
        if not teacher:
            teacher = User(
                username='teacher',
                email='teacher@test.com',
                role='teacher'
            )
            teacher.set_password('123456')
            db.session.add(teacher)
            created_users.append('Преподаватель (teacher/123456)')
        
        db.session.commit()
        
        if created_users:
            users_list = '<br>'.join([f'• {user}' for user in created_users])
            message = f'Успешно созданы:<br>{users_list}'
        else:
            message = 'Все тестовые пользователи уже существуют'
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Тестовые пользователи</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <div class="form-title">👥 Тестовые пользователи</div>
                
                <div class="status">
                    {message}
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">🔑 Данные для входа:</h3>
                    <p><strong>Студент:</strong> student / 123456</p>
                    <p><strong>Преподаватель:</strong> teacher / 123456</p>
                    <p><strong>Администратор:</strong> CalmAndManage / KeepMathAlive</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="/admin/demo-data" class="btn btn-success">← Назад к демо-данным</a>
                    <a href="/admin/users" class="btn">👥 Управление пользователями</a>
                </div>
            </div>
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
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <div class="form-title">⚠️ Ошибка</div>
                <div class="error">Ошибка при создании пользователей: {str(e)}</div>
                <div style="text-align: center;">
                    <a href="/admin/demo-data" class="btn">← Назад</a>
                </div>
            </div>
        </body>
        </html>
        '''

@app.route('/admin/create-olympiad-tasks')
def admin_create_olympiad_tasks():
    """Админский маршрут для создания олимпиадных заданий"""
    try:
        # Принудительно создаем олимпиадные задания
        create_sample_tasks()
        create_olympiad_tasks()
        
        # Подсчитываем количество заданий
        total_tasks = MathTask.query.count()
        olympiad_tasks = MathTask.query.filter(MathTask.title.contains('Олимпиада')).count()
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Задания созданы</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <div class="form-title">✅ Задания успешно созданы!</div>
                
                <div class="status">
                    🎉 В базе данных теперь {total_tasks} заданий, включая {olympiad_tasks} олимпиадных!
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="color: #495057; margin-top: 0;">📊 Статистика:</h3>
                    <p><strong>Общее количество заданий:</strong> {total_tasks}</p>
                    <p><strong>Олимпиадных заданий:</strong> {olympiad_tasks}</p>
                    <p><strong>Простых заданий:</strong> {total_tasks - olympiad_tasks}</p>
                </div>
                
                <div style="text-align: center;">
                    <a href="/tasks" class="btn btn-success">📚 Посмотреть все задания</a>
                    <a href="/dashboard" class="btn">🏠 На главную</a>
                </div>
            </div>
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
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <div class="form-title">⚠️ Ошибка</div>
                <div class="error">Ошибка при создании заданий: {str(e)}</div>
                <div style="text-align: center;">
                    <a href="/dashboard" class="btn">← На главную</a>
                </div>
            </div>
        </body>
        </html>
        '''

@app.route('/admin/users')
@login_required
def admin_users():
    """Вкладка 2: Управление пользователями"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    # Получаем всех пользователей
    users = User.query.order_by(User.role, User.username).all()
    
    users_html = ''
    for user in users:
        role_emoji = {'admin': '🔧', 'teacher': '👨‍🏫', 'student': '🎓'}
        emoji = role_emoji.get(user.role, '👤')
        delete_button = '' if user.role == 'admin' else f'<a href="/admin/delete-user/{user.id}" class="btn-small btn-delete" onclick="return confirm(\'Удалить пользователя {user.username}?\')">🗑️ Удалить</a>'
        users_html += f'''
        <tr>
            <td>{emoji} {user.username}</td>
            <td>{user.email}</td>
            <td><span class="role-badge role-{user.role}">{user.role}</span></td>
            <td>
                <a href="/admin/edit-user/{user.id}" class="btn-small btn-edit">✏️ Редактировать</a>
                {delete_button}
            </td>
        </tr>
        '''
    
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Панель администратора</title>
        {get_base_styles()}
        <style>
            .admin-tabs {{
                display: flex;
                background: #f8f9fa;
                border-radius: 10px 10px 0 0;
                margin: 20px 0 0 0;
                overflow: hidden;
            }}
            .admin-tab {{
                flex: 1;
                padding: 15px 20px;
                text-align: center;
                background: #e9ecef;
                color: #495057;
                text-decoration: none;
                border-right: 1px solid #dee2e6;
                transition: all 0.3s ease;
            }}
            .admin-tab:hover {{
                background: #dee2e6;
            }}
            .admin-tab.active {{
                background: #007bff;
                color: white;
            }}
            .admin-content {{
                background: white;
                border-radius: 0 0 10px 10px;
                padding: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .users-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            .users-table th, .users-table td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #dee2e6;
            }}
            .users-table th {{
                background: #f8f9fa;
                font-weight: bold;
            }}
            .role-badge {{
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }}
            .role-admin {{ background: #dc3545; color: white; }}
            .role-teacher {{ background: #28a745; color: white; }}
            .role-student {{ background: #007bff; color: white; }}
            .btn-small {{
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 12px;
                display: inline-block;
            }}
            .btn-edit {{ background: #ffc107; color: #212529; }}
            .btn-delete {{ background: #dc3545; color: white; }}
            .btn-small:hover {{
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="form-title">🔧 Панель администратора</div>
            
            <div class="admin-tabs">
                <a href="/admin/demo-data" class="admin-tab">🎯 Демо-данные</a>
                <a href="/admin/users" class="admin-tab active">👥 Пользователи</a>
                <a href="/admin/settings" class="admin-tab">⚙️ Настройки</a>
                <a href="/admin/analytics" class="admin-tab">📊 Аналитика</a>
                <a href="/admin/tasks" class="admin-tab">📝 Задания</a>
            </div>
            
            <div class="admin-content">
                <h2>👥 Управление пользователями</h2>
                
                <div style="margin: 20px 0;">
                    <a href="/admin/add-user" class="btn btn-success">➕ Добавить пользователя</a>
                </div>
                
                <table class="users-table">
                    <thead>
                        <tr>
                            <th>Пользователь</th>
                            <th>Email</th>
                            <th>Роль</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users_html}
                    </tbody>
                </table>
            </div>
            
            <div class="nav-links">
                <a href="/dashboard">← На главную</a>
                <a href="/logout">Выход</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/settings')
@login_required
def admin_settings():
    """Вкладка 3: Настройки (пока пустая)"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Панель администратора</title>
        {get_base_styles()}
        <style>
            .admin-tabs {{
                display: flex;
                background: #f8f9fa;
                border-radius: 10px 10px 0 0;
                margin: 20px 0 0 0;
                overflow: hidden;
            }}
            .admin-tab {{
                flex: 1;
                padding: 15px 20px;
                text-align: center;
                background: #e9ecef;
                color: #495057;
                text-decoration: none;
                border-right: 1px solid #dee2e6;
                transition: all 0.3s ease;
            }}
            .admin-tab:hover {{
                background: #dee2e6;
            }}
            .admin-tab.active {{
                background: #007bff;
                color: white;
            }}
            .admin-content {{
                background: white;
                border-radius: 0 0 10px 10px;
                padding: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .placeholder {{
                text-align: center;
                padding: 60px 20px;
                color: #6c757d;
                background: #f8f9fa;
                border-radius: 10px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="form-title">🔧 Панель администратора</div>
            
            <div class="admin-tabs">
                <a href="/admin/demo-data" class="admin-tab">🎯 Демо-данные</a>
                <a href="/admin/users" class="admin-tab">👥 Пользователи</a>
                <a href="/admin/settings" class="admin-tab active">⚙️ Настройки</a>
                <a href="/admin/analytics" class="admin-tab">📊 Аналитика</a>
                <a href="/admin/tasks" class="admin-tab">📝 Задания</a>
            </div>
            
            <div class="admin-content">
                <h2>⚙️ Настройки системы</h2>
                
                <div class="placeholder">
                    <h3>🚧 В разработке</h3>
                    <p>Здесь будут настройки весовых коэффициентов<br>адаптивного алгоритма обучения</p>
                </div>
            </div>
            
            <div class="nav-links">
                <a href="/dashboard">← На главную</a>
                <a href="/logout">Выход</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    """Вкладка 4: Аналитика (пока пустая)"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Панель администратора</title>
        {get_base_styles()}
        <style>
            .admin-tabs {{
                display: flex;
                background: #f8f9fa;
                border-radius: 10px 10px 0 0;
                margin: 20px 0 0 0;
                overflow: hidden;
            }}
            .admin-tab {{
                flex: 1;
                padding: 15px 20px;
                text-align: center;
                background: #e9ecef;
                color: #495057;
                text-decoration: none;
                border-right: 1px solid #dee2e6;
                transition: all 0.3s ease;
            }}
            .admin-tab:hover {{
                background: #dee2e6;
            }}
            .admin-tab.active {{
                background: #007bff;
                color: white;
            }}
            .admin-content {{
                background: white;
                border-radius: 0 0 10px 10px;
                padding: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .placeholder {{
                text-align: center;
                padding: 60px 20px;
                color: #6c757d;
                background: #f8f9fa;
                border-radius: 10px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="form-title">🔧 Панель администратора</div>
            
            <div class="admin-tabs">
                <a href="/admin/demo-data" class="admin-tab">🎯 Демо-данные</a>
                <a href="/admin/users" class="admin-tab">👥 Пользователи</a>
                <a href="/admin/settings" class="admin-tab">⚙️ Настройки</a>
                <a href="/admin/analytics" class="admin-tab active">📊 Аналитика</a>
                <a href="/admin/tasks" class="admin-tab">📝 Задания</a>
            </div>
            
            <div class="admin-content">
                <h2>📊 Аналитика системы</h2>
                
                <div class="placeholder">
                    <h3>🚧 В разработке</h3>
                    <p>Здесь будут графики и статистика:<br>• Активность студентов<br>• Сложность заданий<br>• Прогресс обучения</p>
                </div>
            </div>
            
            <div class="nav-links">
                <a href="/dashboard">← На главную</a>
                <a href="/logout">Выход</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/tasks')
@login_required
def admin_tasks():
    """Вкладка 5: Управление заданиями"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    # Перенаправляем на страницу задач с админскими правами
    return redirect(url_for('tasks_list'))

@app.route('/create-admin')
def force_create_admin():
    """Принудительное создание администратора (публичный маршрут для первого запуска)"""
    try:
        # Проверяем, существует ли админ
        existing_admin = User.query.filter_by(username='CalmAndManage').first()
        if existing_admin:
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <title>Создание администратора</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <h1>✅ Администратор уже существует</h1>
                    <p>Администратор с логином <strong>CalmAndManage</strong> уже создан в системе.</p>
                    <p><a href="/login" class="btn btn-primary">Войти в систему</a></p>
                    <p><a href="/" class="btn btn-secondary">На главную</a></p>
                </div>
            </body>
            </html>
            '''
            
        # Создаем администратора
        admin = User(
            username='CalmAndManage',
            email='admin@mathsystem.local',
            role='admin'
        )
        admin.set_password('KeepMathAlive')
        
        db.session.add(admin)
        db.session.commit()
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Администратор создан</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>🎉 Администратор успешно создан!</h1>
                <div class="success-message">
                    <h3>Данные для входа:</h3>
                    <p><strong>Логин:</strong> CalmAndManage</p>
                    <p><strong>Пароль:</strong> KeepMathAlive</p>
                </div>
                <p><a href="/login" class="btn btn-primary">Войти как администратор</a></p>
                <p><a href="/" class="btn btn-secondary">На главную</a></p>
                <div class="warning-message" style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px;">
                    <strong>⚠️ Важно:</strong> Этот маршрут создан для первоначальной настройки. 
                    После входа в систему рекомендуется сменить пароль администратора.
                </div>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Ошибка создания администратора</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>❌ Ошибка при создании администратора</h1>
                <p>Произошла ошибка: {str(e)}</p>
                <p><a href="/" class="btn btn-secondary">На главную</a></p>
            </div>
        </body>
        </html>
        '''

@app.route('/admin/delete-user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    """Удаление пользователя (только для админов)"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Защита от удаления администраторов
        if user.role == 'admin':
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <title>Ошибка удаления</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <h1>❌ Ошибка удаления</h1>
                    <p>Нельзя удалить администратора!</p>
                    <p><a href="/admin/users" class="btn btn-secondary">Назад к списку пользователей</a></p>
                </div>
            </body>
            </html>
            '''
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Пользователь удален</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>✅ Пользователь удален</h1>
                <p>Пользователь <strong>{username}</strong> успешно удален из системы.</p>
                <p><a href="/admin/users" class="btn btn-primary">Назад к списку пользователей</a></p>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Ошибка удаления</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>❌ Ошибка при удалении пользователя</h1>
                <p>Произошла ошибка: {str(e)}</p>
                <p><a href="/admin/users" class="btn btn-secondary">Назад к списку пользователей</a></p>
            </div>
        </body>
        </html>
        '''

@app.route('/admin/edit-user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    """Редактирование пользователя (только для админов)"""
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    try:
        user = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            # Обработка формы редактирования
            new_username = request.form.get('username', '').strip()
            new_email = request.form.get('email', '').strip()
            new_role = request.form.get('role', '').strip()
            new_password = request.form.get('password', '').strip()
            
            # Валидация
            if not new_username or not new_email or not new_role:
                raise ValueError("Все поля обязательны для заполнения")
            
            if new_role not in ['student', 'teacher', 'admin']:
                raise ValueError("Недопустимая роль пользователя")
            
            # Проверка уникальности имени пользователя (если изменилось)
            if new_username != user.username:
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user:
                    raise ValueError(f"Пользователь с именем '{new_username}' уже существует")
            
            # Проверка уникальности email (если изменился)
            if new_email != user.email:
                existing_email = User.query.filter_by(email=new_email).first()
                if existing_email:
                    raise ValueError(f"Пользователь с email '{new_email}' уже существует")
            
            # Обновление данных пользователя
            user.username = new_username
            user.email = new_email
            user.role = new_role
            
            # Обновление пароля (если указан)
            if new_password:
                user.set_password(new_password)
            
            db.session.commit()
            
            return f'''
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <title>Пользователь обновлен</title>
                {get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <h1>✅ Пользователь обновлен</h1>
                    <p>Данные пользователя <strong>{user.username}</strong> успешно обновлены.</p>
                    <p><a href="/admin/users" class="btn btn-primary">Назад к списку пользователей</a></p>
                </div>
            </body>
            </html>
            '''
        
        # GET запрос - показываем форму редактирования
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Редактирование пользователя</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>✏️ Редактирование пользователя</h1>
                <form method="POST">
                    <div class="form-group">
                        <label>Имя пользователя:</label>
                        <input type="text" name="username" value="{user.username}" required>
                    </div>
                    <div class="form-group">
                        <label>Email:</label>
                        <input type="email" name="email" value="{user.email}" required>
                    </div>
                    <div class="form-group">
                        <label>Роль:</label>
                        <select name="role" required>
                            <option value="student" {'selected' if user.role == 'student' else ''}>Студент</option>
                            <option value="teacher" {'selected' if user.role == 'teacher' else ''}>Преподаватель</option>
                            <option value="admin" {'selected' if user.role == 'admin' else ''}>Администратор</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Новый пароль (оставьте пустым, если не хотите менять):</label>
                        <input type="password" name="password" placeholder="Новый пароль">
                    </div>
                    <button type="submit" class="btn btn-primary">💾 Сохранить изменения</button>
                    <a href="/admin/users" class="btn btn-secondary">❌ Отмена</a>
                </form>
            </div>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Ошибка редактирования</title>
            {get_base_styles()}
        </head>
        <body>
            <div class="container">
                <h1>❌ Ошибка при редактировании пользователя</h1>
                <p>Произошла ошибка: {str(e)}</p>
                <p><a href="/admin/users" class="btn btn-secondary">Назад к списку пользователей</a></p>
            </div>
        </body>
        </html>
        '''

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
    
    app.run(host='0.0.0.0', port=5000, debug=True)
