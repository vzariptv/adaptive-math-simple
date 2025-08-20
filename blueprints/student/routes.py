from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, case

from extensions import db
from models import Topic, MathTask, TaskAttempt, StudentTopicProgress, TopicLevelConfig
from .forms import UpdateProfileForm, ChangePasswordForm


student_bp = Blueprint('student', __name__, url_prefix='/student')


# ---------- Tasks page ----------
@student_bp.route('/tasks', methods=['GET'])
@login_required
def tasks():
    if current_user.role != 'student':
        # Ограничим доступ только студентам
        return redirect(url_for('main.dashboard'))

    # Все темы для селекта
    topics = Topic.query.order_by(Topic.name.asc()).all()

    topic_id = request.args.get('topic_id', type=int)
    status = request.args.get('status', default='all')  # 'all' | 'solved' | 'pending'
    page = request.args.get('page', default=1, type=int)
    per_page = 20
    selected_topic = None
    target_level = None
    tasks_data = []

    if topic_id:
        selected_topic = db.session.get(Topic, topic_id)
        if selected_topic:
            # Определяем уровень студента по теме (или 'low')
            progress = StudentTopicProgress.query.filter_by(user_id=current_user.id, topic_id=topic_id).first()
            target_level = progress.current_level if progress else 'low'

            # Список задач для уровня
            q = (MathTask.query
                 .filter_by(topic_id=topic_id, level=target_level, is_active=True)
                 .order_by(MathTask.created_at.desc()))
            tasks_list = q.all()

            # Подсчет попыток/статуса по каждой задаче
            # Сразу вытащим агрегаты по всем задачам выбранного уровня
            attempts = (db.session.query(
                            TaskAttempt.task_id,
                            func.count(TaskAttempt.id).label('cnt'),
                            func.sum(case((TaskAttempt.is_correct == False, 1), else_=0)).label('incorrect_cnt'),
                            func.max(func.cast(TaskAttempt.is_correct, db.Integer)).label('solved')
                        )
                        .filter(TaskAttempt.user_id == current_user.id,
                                TaskAttempt.task_id.in_([t.id for t in tasks_list]))
                        .group_by(TaskAttempt.task_id)
                        .all())
            attempts_map = {a.task_id: {
                'cnt': int(a.cnt),
                'incorrect_cnt': int(a.incorrect_cnt or 0),
                'solved': bool(a.solved)
            } for a in attempts}

            for t in tasks_list:
                agg = attempts_map.get(t.id, {'cnt': 0, 'solved': False})
                incorrect_cnt = int(agg.get('incorrect_cnt', 0))
                blocked = (incorrect_cnt >= 3) and (not bool(agg['solved']))
                item = {
                    'task': t,
                    'attempts': int(agg['cnt']),
                    'attempts_str': f"{min(int(agg['cnt']), 3)}/3",
                    'is_solved': bool(agg['solved']),
                    'incorrect_cnt': incorrect_cnt,
                    'is_blocked': blocked,
                }
                tasks_data.append(item)

            # Фильтрация по статусу
            if status == 'solved':
                tasks_data = [it for it in tasks_data if it['is_solved']]
            elif status == 'pending':
                tasks_data = [it for it in tasks_data if not it['is_solved']]

            # Сортировка: решенные в начале, затем по числу попыток (desc), затем по дате создания (desc)
            tasks_data.sort(key=lambda it: (
                0 if it['is_solved'] else 1,
                -int(it['attempts']),
                -int(it['task'].created_at.timestamp()) if hasattr(it['task'].created_at, 'timestamp') else 0
            ))

            # Пагинация на уровне python-списка
            total = len(tasks_data)
            total_pages = max((total + per_page - 1) // per_page, 1)
            page = max(1, min(page, total_pages))
            start = (page - 1) * per_page
            end = start + per_page
            tasks_data = tasks_data[start:end]
        
    return render_template(
        'student/tasks.html',
        topics=topics,
        selected_topic=selected_topic,
        target_level=target_level,
        tasks_data=tasks_data,
        status=status,
        page=page,
        per_page=per_page,
        total_pages=locals().get('total_pages', 1),
        total=locals().get('total', 0),
    )


# ---------- Profile page ----------
@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role != 'student':
        return redirect(url_for('main.dashboard'))

    profile_form = UpdateProfileForm()
    password_form = ChangePasswordForm()

    # Prefill on GET
    if request.method == 'GET':
        profile_form.first_name.data = current_user.first_name or ''
        profile_form.last_name.data = current_user.last_name or ''
        profile_form.email.data = current_user.email or ''

    # Handle profile update
    if request.method == 'POST' and 'submit_profile' in request.form and profile_form.validate_on_submit():
        # Простая валидация уникальности e-mail: если меняется, проверим
        if profile_form.email.data != current_user.email:
            if db.session.query(func.count()).select_from(type(current_user)).filter_by(email=profile_form.email.data).scalar():
                flash('Этот email уже используется', 'error')
                return redirect(url_for('student.profile'))
        current_user.first_name = profile_form.first_name.data or None
        current_user.last_name = profile_form.last_name.data or None
        current_user.email = profile_form.email.data
        db.session.commit()
        flash('Профиль обновлен', 'success')
        return redirect(url_for('student.profile'))

    # Handle password change
    if request.method == 'POST' and 'submit_password' in request.form and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data):
            flash('Неверный текущий пароль', 'error')
            return redirect(url_for('student.profile'))
        current_user.set_password(password_form.new_password.data)
        db.session.commit()
        flash('Пароль обновлен', 'success')
        return redirect(url_for('student.profile'))

    # Темы, где есть хотя бы одна попытка
    # total_limit берем из конфигурации уровня (если есть)
    studied_topics = []

    # Соберем по темам агрегаты попыток пользователя
    attempts_agg = (db.session.query(MathTask.topic_id,
                                     func.count(func.distinct(TaskAttempt.task_id)).label('tasks_attempted'),
                                     func.sum(func.case((TaskAttempt.is_correct == True, 1), else_=0)).label('solved_attempts'))
                    .join(MathTask, MathTask.id == TaskAttempt.task_id)
                    .filter(TaskAttempt.user_id == current_user.id)
                    .group_by(MathTask.topic_id)
                    .all())
    agg_map = {row.topic_id: {'tasks_attempted': int(row.tasks_attempted), 'solved_attempts': int(row.solved_attempts or 0)} for row in attempts_agg}

    topic_ids = list(agg_map.keys())
    if topic_ids:
        topics = Topic.query.filter(Topic.id.in_(topic_ids)).all()
        progress_rows = StudentTopicProgress.query.filter(StudentTopicProgress.user_id == current_user.id,
                                                          StudentTopicProgress.topic_id.in_(topic_ids)).all()
        progress_map = {p.topic_id: p for p in progress_rows}

        for t in topics:
            prog = progress_map.get(t.id)
            level = prog.current_level if prog else 'low'
            # Попробуем достать порог (предельное кол-во задач) из TopicLevelConfig
            conf = TopicLevelConfig.query.filter_by(topic_id=t.id, level=level).first()
            total_limit = conf.task_count_threshold if conf else 10

            # Считаем решенные задачи (по уникальным task_id, где была успешная попытка)
            solved_tasks_count = (db.session.query(func.count(func.distinct(TaskAttempt.task_id)))
                                  .join(MathTask, MathTask.id == TaskAttempt.task_id)
                                  .filter(TaskAttempt.user_id == current_user.id,
                                          MathTask.topic_id == t.id,
                                          TaskAttempt.is_correct == True)
                                  .scalar() or 0)

            studied_topics.append({
                'topic': t,
                'limit_total': total_limit,
                'solved_total': int(solved_tasks_count),
                'current_level': level,
            })

    return render_template('student/profile.html',
                           profile_form=profile_form,
                           password_form=password_form,
                           studied_topics=studied_topics)


# ---------- Single task view & submit ----------
def _normalize_value(val):
    if isinstance(val, str):
        s = val.strip()
        # попробуем к числу
        try:
            if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                return int(s)
            return float(s)
        except Exception:
            return s
    return val


def _normalize_answer(raw):
    if isinstance(raw, dict):
        return {k: _normalize_value(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_normalize_value(x) for x in raw]
    return _normalize_value(raw)


def _extract_user_answer(task: MathTask, form):
    # Простое сопоставление по типу
    if task.answer_type == 'number':
        return _normalize_value(form.get('answer'))
    # variables: ключи фиксированы по correct_answer
    if task.answer_type == 'variables' and isinstance(task.correct_answer, dict):
        out = {}
        for k in task.correct_answer.keys():
            out[k] = _normalize_value(form.get(k))
        return out
    # sequence: ожидаем поля item_0..item_N или используем answer_schema.length
    if task.answer_type == 'sequence':
        items = []
        # попытаемся считать по длине правильного ответа
        length = 0
        if isinstance(task.correct_answer, list):
            length = len(task.correct_answer)
        for i in range(length):
            items.append(_normalize_value(form.get(f'item_{i}')))
        return items
    # interval и прочие: пробуем собрать как словарь известных ключей correct_answer
    if isinstance(task.correct_answer, dict):
        return {k: _normalize_value(form.get(k)) for k in task.correct_answer.keys()}
    return _normalize_value(form.get('answer'))


def _answers_equal(expected, given):
    # Порядок сохраняем (форма контролирует структуру), пробелы уже тримим, типы приводим
    return expected == given


def _user_task_stats(user_id: int, task_id: int):
    q = (db.session.query(
            func.count(TaskAttempt.id).label('cnt'),
            func.sum(case((TaskAttempt.is_correct == False, 1), else_=0)).label('incorrect_cnt'),
            func.max(func.cast(TaskAttempt.is_correct, db.Integer)).label('solved')
        )
        .filter(TaskAttempt.user_id == user_id, TaskAttempt.task_id == task_id)
    )
    row = q.one()
    cnt = int(row.cnt or 0)
    incorrect = int(row.incorrect_cnt or 0)
    solved = bool(row.solved)
    blocked = (incorrect >= 3) and (not solved)
    return cnt, incorrect, solved, blocked


@student_bp.route('/tasks/<int:task_id>', methods=['GET', 'POST'])
@login_required
def view_task(task_id: int):
    if current_user.role != 'student':
        return redirect(url_for('main.dashboard'))

    task = db.session.get(MathTask, task_id)
    if not task or not task.is_active:
        flash('Задача не найдена или недоступна', 'error')
        return redirect(url_for('student.tasks'))

    # Определим уровень/тему для связанной логики и следующей задачи
    topic_id = task.topic_id
    level = task.level

    # Статистика пользователя по этой задаче
    total_cnt, incorrect_cnt, solved, blocked = _user_task_stats(current_user.id, task.id)

    if request.method == 'POST':
        # Запрет если уже решено или заблокировано
        if solved or blocked:
            flash('Отправка ответа недоступна для этой задачи', 'warning')
            return redirect(url_for('student.view_task', task_id=task.id))

        user_answer = _extract_user_answer(task, request.form)
        expected = _normalize_answer(task.correct_answer)
        given = _normalize_answer(user_answer)

        # Определяем попытку
        attempt_number = total_cnt + 1
        is_correct = _answers_equal(expected, given)

        # Записываем попытку
        db.session.add(TaskAttempt(
            user_id=current_user.id,
            task_id=task.id,
            user_answer=given,
            is_correct=is_correct,
            partial_score=0,
            attempt_number=attempt_number,
        ))
        db.session.commit()

        # Пересчитаем состояние после записи
        total_cnt, incorrect_cnt, solved, blocked = _user_task_stats(current_user.id, task.id)

        # Flash результат
        if is_correct:
            # вычислим скор (для отображения), используя TopicLevelConfig.penalty_weights
            score = 1.0
            if attempt_number == 1:
                score = 1.0
            elif attempt_number in (2, 3):
                conf = TopicLevelConfig.query.filter_by(topic_id=topic_id, level=level).first()
                if conf and isinstance(conf.penalty_weights, list):
                    idx = attempt_number - 2  # 0 для 2-й, 1 для 3-й
                    if 0 <= idx < len(conf.penalty_weights):
                        try:
                            w = float(conf.penalty_weights[idx])
                            score = max(0.0, min(1.0, w))
                        except Exception:
                            score = 0.0
                else:
                    score = 0.0
            flash(f'Верно! Набрано баллов: {score:.2f}', 'success')
        else:
            flash('Неверно. Попробуйте еще раз.', 'error')

        return redirect(url_for('student.view_task', task_id=task.id))

    # Подсказка доступна, если есть хотя бы одна неуспешная попытка
    hint_available = incorrect_cnt >= 1

    # Подберем «следующую» задачу: случайная активная той же темы/уровня, не текущая, исключая решенные и заблокированные
    next_task = None
    if solved:
        subq_attempts = (db.session.query(
            TaskAttempt.task_id,
            func.sum(case((TaskAttempt.is_correct == False, 1), else_=0)).label('incorrect_cnt'),
            func.max(func.cast(TaskAttempt.is_correct, db.Integer)).label('solved')
        )
        .filter(TaskAttempt.user_id == current_user.id)
        .group_by(TaskAttempt.task_id)
        ).subquery()

        candidates = (MathTask.query
                      .filter_by(topic_id=topic_id, level=level, is_active=True)
                      .filter(MathTask.id != task.id)
                      .outerjoin(subq_attempts, MathTask.id == subq_attempts.c.task_id)
                      .filter(~( (func.coalesce(subq_attempts.c.solved, 0) == 1) |
                                ((func.coalesce(subq_attempts.c.incorrect_cnt, 0) >= 3) & (func.coalesce(subq_attempts.c.solved, 0) == 0)) ))
                      .order_by(func.random())
                      .first())
        next_task = candidates

    # Если задача заблокирована и не решена — запретим просмотр карточки
    if blocked and not solved and request.method == 'GET':
        flash('Задача заблокирована после 3 неудачных попыток', 'warning')
        return redirect(url_for('student.tasks', topic_id=task.topic_id))

    # История попыток для отображения
    user_attempts = (TaskAttempt.query
                     .filter_by(user_id=current_user.id, task_id=task.id)
                     .order_by(TaskAttempt.created_at.desc())
                     .limit(20)
                     .all())

    return render_template('student/task_view.html',
                           task=task,
                           solved=solved,
                           blocked=blocked,
                           total_attempts=total_cnt,
                           incorrect_attempts=incorrect_cnt,
                           hint_available=hint_available,
                           user_attempts=user_attempts,
                           next_task=next_task)
