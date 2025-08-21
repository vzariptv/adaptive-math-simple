from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, case
from datetime import datetime, date, time, timedelta

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
                                     func.sum(case((TaskAttempt.is_correct == True, 1), else_=0)).label('solved_attempts'))
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
        # поддержим запятую как разделитель дробной части
        s = s.replace(',', '.') if s else s
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
    """Build student answer JSON mirroring admin TaskForm.build_answer_json()."""
    at = task.answer_type

    # helper to coerce numeric inputs (supports comma)
    def _num(v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            v = v.replace(',', '.')
        try:
            return float(v)
        except Exception:
            return None

    if at == 'number':
        val = _num(form.get('answer'))
        return {"type": "number", "value": val}

    if at == 'variables':
        # Build canonical list of {name, value}
        variables = []
        # 1) Preferred: dynamic rows name_i/value_i or WTForms-style variables_answer-variables-i-name
        indices = set()
        for key in form.keys():
            if key.startswith('name_'):
                try:
                    indices.add(int(key.split('_', 1)[1]))
                except Exception:
                    pass
            elif '-variables-' in key and key.endswith('-name'):
                try:
                    idx = int(key.split('-')[-2])
                    indices.add(idx)
                except Exception:
                    pass
        if indices:
            for i in sorted(indices):
                name = (form.get(f'name_{i}') or form.get(f'variables_answer-variables-{i}-name') or '').strip()
                val_raw = form.get(f'value_{i}') or form.get(f'variables_answer-variables-{i}-value')
                val = _num(val_raw)
                if name:
                    variables.append({"name": name, "value": val})
        else:
            # 2) Back-compat:
            # 2a) If correct_answer is canonical dict with list of variables, use their names as field names
            ca = task.correct_answer
            if isinstance(ca, dict) and ca.get('type') == 'variables' and isinstance(ca.get('variables'), list):
                for item in ca['variables']:
                    name = str(item.get('name')) if item and 'name' in item else None
                    if name:
                        v = _num(form.get(name))
                        variables.append({"name": name, "value": v})
            # 2b) Or if it's a plain mapping like {x: 1, y: 2}, fields are named by key
            elif isinstance(ca, dict):
                for k in ca.keys():
                    v = _num(form.get(k))
                    if k:
                        variables.append({"name": str(k), "value": v})
        return {"type": "variables", "variables": variables}

    if at == 'interval':
        # Field names from shared template
        start_inf = bool(form.get('start_infinity'))
        end_inf = bool(form.get('end_infinity'))
        start = None if start_inf else _num(form.get('start'))
        end = None if end_inf else _num(form.get('end'))
        start_inclusive = bool(form.get('start_inclusive'))
        end_inclusive = bool(form.get('end_inclusive'))
        return {
            "type": "interval",
            "start": start,
            "end": end,
            "start_inclusive": start_inclusive,
            "end_inclusive": end_inclusive,
        }

    if at == 'sequence':
        nums = []
        raw = form.get('sequence_input')
        if raw is not None:
            parts = [p.strip() for p in (raw or '').replace(';', ',').split(',') if p.strip()]
            for p in parts:
                n = _num(p)
                if n is not None:
                    nums.append(n)
        else:
            # Back-compat: fields item_0..item_N based on correct_answer length
            length = 0
            if isinstance(task.correct_answer, list):
                length = len(task.correct_answer)
            i = 0
            # if length unknown, read until missing
            if length == 0:
                while True:
                    key = f'item_{i}'
                    if key not in form:
                        break
                    n = _num(form.get(key))
                    if n is not None:
                        nums.append(n)
                    i += 1
            else:
                for i in range(length):
                    n = _num(form.get(f'item_{i}'))
                    if n is not None:
                        nums.append(n)
        return {"type": "sequence", "sequence_values": nums}

    # Fallback — try generic single field
    return _normalize_answer(form.get('answer'))


def _answers_equal(expected, given):
    # Точное сравнение по структуре, но допускаем случай: expected = {k: v}, given = v
    if isinstance(expected, dict) and len(expected) == 1 and not isinstance(given, dict):
        # завернём scalar в dict по тому же ключу
        only_key = next(iter(expected.keys()))
        given_wrapped = {only_key: given}
        return expected == given_wrapped
    # И обратный случай: expected scalar, given single-key dict
    if not isinstance(expected, dict) and isinstance(given, dict) and len(given) == 1:
        only_key = next(iter(given.keys()))
        return expected == given[only_key]
    return expected == given


def _canonical_expected(task: MathTask):
    """Return expected answer in canonical admin JSON for given task.answer_type.
    Keeps backward compatibility with legacy scalar/list/dict formats in DB.
    """
    at = task.answer_type
    ca = task.correct_answer

    if at == 'number':
        if isinstance(ca, dict) and ca.get('type') == 'number':
            return ca
        return {"type": "number", "value": _normalize_value(ca)}

    if at == 'variables':
        if isinstance(ca, dict) and ca.get('type') == 'variables':
            return ca
        if isinstance(ca, dict):
            vars_list = []
            for k, v in ca.items():
                vars_list.append({"name": str(k), "value": _normalize_value(v)})
            return {"type": "variables", "variables": vars_list}
        return {"type": "variables", "variables": []}

    if at == 'interval':
        if isinstance(ca, dict) and ca.get('type') == 'interval':
            return ca
        # No solid legacy mapping -> default empty interval structure
        return {
            "type": "interval",
            "start": None,
            "end": None,
            "start_inclusive": False,
            "end_inclusive": False,
        }

    if at == 'sequence':
        if isinstance(ca, dict) and ca.get('type') == 'sequence':
            return ca
        if isinstance(ca, list):
            return {"type": "sequence", "sequence_values": [_normalize_value(x) for x in ca]}
        return {"type": "sequence", "sequence_values": []}

    return ca


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
        expected = _normalize_answer(_canonical_expected(task))
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


# ---------- Profile stats (weekly JSON) ----------
@student_bp.route('/profile/stats.json', methods=['GET'])
@login_required
def profile_stats():
    """Return weekly stats for current and previous week (Mon..Sun) for the current user.
    Aggregates per topic: attempts, solved, solved_tasks_count, success_rate.
    """
    if current_user.role != 'student':
        return jsonify({"error": "forbidden"}), 403

    # Helper to compute week boundaries (Mon..Sun) for a given anchor date
    def week_range(anchor: date):
        # Monday = 0
        start = anchor - timedelta(days=anchor.weekday())  # Monday
        end = start + timedelta(days=6)                     # Sunday (label only)
        start_dt = datetime.combine(start, time.min)
        # Exclusive end: next Monday 00:00 to avoid microsecond issues in SQLite
        end_exclusive_dt = datetime.combine(end + timedelta(days=1), time.min)
        return start, end, start_dt, end_exclusive_dt

    today = datetime.utcnow().date()
    curr_w_start, curr_w_end, curr_start_dt, curr_end_excl_dt = week_range(today)
    prev_anchor = today - timedelta(days=7)
    prev_w_start, prev_w_end, prev_start_dt, prev_end_excl_dt = week_range(prev_anchor)

    def aggregate_week(start_dt: datetime, end_excl_dt: datetime):
        # Pull attempts joined with tasks within range for current user
        q = (db.session.query(TaskAttempt.id,
                              TaskAttempt.is_correct,
                              MathTask.topic_id,
                              MathTask.id.label('task_id'))
             .join(MathTask, MathTask.id == TaskAttempt.task_id)
             .filter(TaskAttempt.user_id == current_user.id,
                     TaskAttempt.created_at >= start_dt,
                     TaskAttempt.created_at < end_excl_dt))
        rows = q.all()

        by_topic = {}
        solved_tasks_sets = {}
        for rid, is_correct, topic_id, task_id in rows:
            info = by_topic.setdefault(topic_id, {"attempts": 0, "solved": 0})
            info["attempts"] += 1
            if bool(is_correct):
                info["solved"] += 1
                solved_set = solved_tasks_sets.setdefault(topic_id, set())
                solved_set.add(task_id)

        topic_ids = list(by_topic.keys())
        names = {}
        if topic_ids:
            for t in Topic.query.filter(Topic.id.in_(topic_ids)).all():
                names[t.id] = t.name

        result_list = []
        totals_attempts = 0
        totals_solved = 0
        totals_solved_tasks = 0

        for tid, agg in by_topic.items():
            solved_tasks_cnt = len(solved_tasks_sets.get(tid, set()))
            attempts = int(agg["attempts"])
            solved = int(agg["solved"])
            sr = (solved / attempts) if attempts > 0 else 0.0
            result_list.append({
                "topic_id": int(tid),
                "topic_name": names.get(tid, str(tid)),
                "attempts": attempts,
                "solved": solved,
                "solved_tasks_count": int(solved_tasks_cnt),
                "success_rate": sr,
            })
            totals_attempts += attempts
            totals_solved += solved
            totals_solved_tasks += solved_tasks_cnt

        # Sort topics by name for stable order
        result_list.sort(key=lambda x: x["topic_name"].lower())

        totals = {
            "attempts": int(totals_attempts),
            "solved": int(totals_solved),
            "solved_tasks_count": int(totals_solved_tasks),
            "success_rate": (totals_solved / totals_attempts) if totals_attempts > 0 else 0.0,
        }
        # Top-5 by solved_tasks_count
        top5 = sorted(result_list, key=lambda x: (-x["solved_tasks_count"], x["topic_name"].lower()))[:5]
        return result_list, totals, top5

    prev_list, prev_totals, prev_top5 = aggregate_week(prev_start_dt, prev_end_excl_dt)
    curr_list, curr_totals, curr_top5 = aggregate_week(curr_start_dt, curr_end_excl_dt)

    payload = {
        "weeks": {
            "prev": {"start": prev_w_start.isoformat(), "end": prev_w_end.isoformat()},
            "curr": {"start": curr_w_start.isoformat(), "end": curr_w_end.isoformat()},
        },
        "by_topic": {
            "prev": prev_list,
            "curr": curr_list,
        },
        "totals": {
            "prev": prev_totals,
            "curr": curr_totals,
        },
        "top5_by_solved_tasks": {
            "prev": prev_top5,
            "curr": curr_top5,
        }
    }

    # Optional debug info
    if request.args.get('debug') in ('1', 'true', 'yes'):
        # Return UTC datetime boundaries used for filtering and quick counts
        def fmt_dt(dt):
            try:
                return dt.isoformat() + 'Z'
            except Exception:
                return str(dt)
        # Counts in raw table (no grouping)
        prev_cnt = (db.session.query(func.count(TaskAttempt.id))
                    .filter(TaskAttempt.user_id == current_user.id,
                            TaskAttempt.created_at >= prev_start_dt,
                            TaskAttempt.created_at < prev_end_excl_dt)
                    ).scalar() or 0
        curr_cnt = (db.session.query(func.count(TaskAttempt.id))
                    .filter(TaskAttempt.user_id == current_user.id,
                            TaskAttempt.created_at >= curr_start_dt,
                            TaskAttempt.created_at < curr_end_excl_dt)
                    ).scalar() or 0
        # Max timestamps for quick sanity
        prev_max = (db.session.query(func.max(TaskAttempt.created_at))
                    .filter(TaskAttempt.user_id == current_user.id,
                            TaskAttempt.created_at >= prev_start_dt,
                            TaskAttempt.created_at < prev_end_excl_dt)
                    ).scalar()
        curr_max = (db.session.query(func.max(TaskAttempt.created_at))
                    .filter(TaskAttempt.user_id == current_user.id,
                            TaskAttempt.created_at >= curr_start_dt,
                            TaskAttempt.created_at < curr_end_excl_dt)
                    ).scalar()
        payload["_debug"] = {
            "boundaries_utc": {
                "prev": {"start": fmt_dt(prev_start_dt), "end_exclusive": fmt_dt(prev_end_excl_dt)},
                "curr": {"start": fmt_dt(curr_start_dt), "end_exclusive": fmt_dt(curr_end_excl_dt)},
            },
            "raw_attempt_counts": {"prev": int(prev_cnt), "curr": int(curr_cnt)},
            "last_attempt_ts": {
                "prev": fmt_dt(prev_max) if prev_max else None,
                "curr": fmt_dt(curr_max) if curr_max else None,
            }
        }

    return jsonify(payload)
