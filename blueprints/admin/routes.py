from __future__ import annotations
import json
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash
import secrets

from flask import (
    render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
)
from flask_login import login_required, current_user

from extensions import db
from sqlalchemy import func
from models import User, Topic, MathTask, TopicLevelConfig, TaskAttempt
from . import admin_bp
from .forms import CreateUserForm, EditUserForm, CreateTopicForm, EditTopicForm, TaskForm, ImportFileForm, ConfirmDeleteForm, LevelConfigForm, LEVEL_CHOICES, AttemptFilterForm, CreateAttemptForm, EditAttemptForm




# ---------- utils ----------
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
            # 403 — достаточно, редирект не нужен
            from flask import abort
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def _parse_json(text: str, field_name: str):
    """Безопасный парсер JSON из текстового поля формы."""
    try:
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"{field_name}: некорректный JSON ({e})")

def _serialize_topic(topic: Topic) -> dict:
    data = {
        "code": topic.code,
        "name": topic.name,
        "description": topic.description or "",
        "level_configs": {}
    }
    for cfg in topic.level_configs:
        data["level_configs"][cfg.level] = {
            "task_count_threshold": cfg.task_count_threshold,
            "reference_time": cfg.reference_time,
            "penalty_weights": cfg.penalty_weights,
        }
    return data

def _serialize_task(task: MathTask) -> dict:
    return {
        "title": task.title,
        "description": task.description or "",
        "code": task.code,
        "answer_type": task.answer_type,
        "correct_answer": task.correct_answer,
        "answer_schema": task.answer_schema,
        "explanation": task.explanation or "",
        "topic_code": task.topic_ref.code if task.topic_ref else None,
        "topic_id": task.topic_id,
        "level": task.level,
        "max_score": task.max_score,
        "is_active": task.is_active,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }

def _set_user_password(user, password: str):
    """Поддержка как метода set_password у модели, так и прямой записи хеша."""
    if hasattr(user, "set_password") and callable(user.set_password):
        user.set_password(password)
    elif hasattr(user, "password_hash"):
        user.password_hash = generate_password_hash(password)
    else:
        raise RuntimeError("Модель User не поддерживает установку пароля (нет set_password/password_hash)")

# -----------------------------------------------------------------------------
# Helper: flash all form errors recursively (for FieldList/FormField too)

def _flash_form_errors(form):
    """Собирает ошибки валидации рекурсивно (включая FieldList/FormField)
    и показывает их как одно понятное сообщение с метками полей."""
    messages = []

    def walk(frm, path=""):
        for name, field in getattr(frm, "_fields", {}).items():
            label_text = getattr(getattr(field, "label", None), "text", name)
            current = f"{path}{label_text}"

            # Собственные ошибки поля
            for err in getattr(field, "errors", []) or []:
                messages.append(f"«{current}»: {err}")

            # FieldList (массив подформ/полей)
            entries = getattr(field, "entries", None)
            if entries:
                for idx, entry in enumerate(entries):
                    if hasattr(entry, "form") and entry.form is not None:
                        walk(entry.form, f"{current}[{idx}] → ")
                    else:
                        for err in getattr(entry, "errors", []) or []:
                            messages.append(f"«{current}[{idx}]»: {err}")

            # FormField (вложенная форма)
            sub = getattr(field, "form", None)
            if sub is not None:
                walk(sub, f"{current} → ")

    walk(form)
    if messages:
        flash("Проверьте поля: " + "; ".join(messages), "warning")

# ---- scoring helpers ---------------------------------------------------------

def _compute_partial_score(task: MathTask, attempt_number: int, is_correct: bool) -> float:
    """Возвращает partial_score по политике:
    - если попытка неуспешная -> 0.0
    - 1-я успешная попытка -> 1.0
    - 2-я -> penalty_weights[0]
    - 3-я -> penalty_weights[1]
    - дальше -> 0.0, если веса не заданы
    """
    if not is_correct:
        return 0.0
    if attempt_number <= 1:
        return 1.0
    cfg = TopicLevelConfig.query.filter_by(topic_id=task.topic_id, level=task.level).first()
    weights = []
    if cfg and isinstance(cfg.penalty_weights, (list, tuple)):
        weights = list(cfg.penalty_weights)
    idx = max(0, attempt_number - 2)  # 2-я попытка -> index 0
    try:
        return float(weights[idx]) if idx < len(weights) else 0.0
    except Exception:
        return 0.0

# =============================================================================
#                 API: penalty_weights for a task
# =============================================================================

@admin_bp.route('/api/tasks/<int:task_id>/weights', methods=['GET'])
@login_required
def api_task_weights(task_id: int):
    """Возвращает JSON с penalty_weights и level/topic для выбранной задачи.
    Поддерживаем форматы хранения penalty_weights: list/tuple, JSON-строка, CSV-строка.
    """
    task = MathTask.query.get_or_404(task_id)
    cfg = TopicLevelConfig.query.filter_by(topic_id=task.topic_id, level=task.level).first()

    def _is_number(x):
        try:
            float(x)
            return True
        except Exception:
            return False

    def _normalize_weights(raw):
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            out = []
            for x in raw:
                try:
                    out.append(float(x))
                except Exception:
                    continue
            return out
        if isinstance(raw, str):
            s = raw.strip()
            if s:
                try:
                    data = json.loads(s)
                    if isinstance(data, (list, tuple)):
                        return [float(x) for x in data if _is_number(x)]
                except Exception:
                    pass
                parts = [p.strip() for p in s.split(',') if p.strip()]
                out = []
                for p in parts:
                    try:
                        out.append(float(p))
                    except Exception:
                        continue
                return out
        return []

    raw = cfg.penalty_weights if cfg else []
    weights = _normalize_weights(raw)
    return jsonify({
        'task_id': task.id,
        'topic_id': task.topic_id,
        'level': task.level,
        'penalty_weights': weights
    })

# ---------- панель ----------
@admin_bp.route("/")
@login_required
@admin_required
def panel():
    # Можно вести на /admin/topics как на самую полезную вкладку
    return redirect(url_for("admin.topics"))

# =============================================================================
#                               Т Е М Ы
# =============================================================================
@admin_bp.route("/topics")
@login_required
@admin_required
def topics():
    topics = Topic.query.order_by(Topic.name.asc()).all()

    # один запрос для подсчёта заданий по темам (опционально, но полезно)
    rows = (db.session.query(Topic.id, func.count(MathTask.id))
            .outerjoin(MathTask, MathTask.topic_id == Topic.id)
            .group_by(Topic.id).all())
    task_counts = dict(rows)

    # ВАЖНО: создаём экземпляры форм и передаём в шаблон
    import_form = ImportFileForm()
    delete_form = ConfirmDeleteForm()

    return render_template(
        "admin/topics.html",
        topics=topics,
        task_counts=task_counts,
        import_form=import_form,
        delete_form=delete_form,
        active_tab="topics",
    )

@admin_bp.route("/topics/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_topic():
    form = CreateTopicForm()
    if form.validate_on_submit():
        topic = Topic(
            code=form.code.data.strip(),
            name=form.name.data.strip(),
            description=form.description.data.strip() or None
        )
        db.session.add(topic)
        db.session.flush()

        # базовые конфиги уровней
        for level, _label in LEVEL_CHOICES:
            db.session.add(TopicLevelConfig(
                topic_id=topic.id,
                level=level,
                task_count_threshold=10,
                reference_time=900,
                penalty_weights=[0.7, 0.4],
            ))
        db.session.commit()
        flash("Тема успешно создана", "success")
        return redirect(url_for("admin.topics"))
    return render_template("admin/create_topic.html", form=form, active_tab="topics")

@admin_bp.route("/topics/<int:topic_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)

    # Собираем словарь конфигов по уровням, чтобы было легко обращаться
    existing_cfgs = {cfg.level: cfg for cfg in (topic.level_configs or [])}

    # Гарантируем наличие трёх уровней (если в БД чего-то нет — подставим временные дефолты для формы)
    def cfg_or_defaults(level):
        cfg = existing_cfgs.get(level)
        if cfg:
            return {
                "level": cfg.level,
                "task_count_threshold": cfg.task_count_threshold or 10,
                "reference_time": cfg.reference_time or 900,
                "penalty_weights": ", ".join(str(x) for x in (cfg.penalty_weights or [0.7, 0.4])),
            }
        # дефолт
        return {
            "level": level,
            "task_count_threshold": 10,
            "reference_time": 900,
            "penalty_weights": "0.7, 0.4",
        }

    levels = ["low", "medium", "high"]

    if request.method == "POST":
        form = EditTopicForm(obj=topic, instance=topic)
        if form.validate_on_submit():
            topic.code = form.code.data.strip()
            topic.name = form.name.data.strip()
            topic.description = (form.description.data or "").strip() or None

            # подформы конфигов
            for sub in form.configs.entries:
                sf = sub.form
                level = (sf.level.data or "").strip()
                if level not in levels:
                    continue
                cfg = existing_cfgs.get(level)
                if not cfg:
                    cfg = TopicLevelConfig(topic_id=topic.id, level=level)
                    db.session.add(cfg)

                cfg.task_count_threshold = sf.task_count_threshold.data
                cfg.reference_time = sf.reference_time.data
                # берём распарсенный список из валидатора
                cfg.penalty_weights = getattr(sf, "_weights", None) or [0.7, 0.4]
            
            db.session.commit()
            flash("Тема обновлена", "success")
            return redirect(url_for("admin.topics"))
        else:
            # форма с ошибками — отрендерим как есть
            return render_template("admin/edit_topic.html", form=form, topic=topic, active_tab="topics")
    # GET — заполняем форму текущими данными
    form_data = {
        "code": topic.code,
        "name": topic.name,
        "description": topic.description or "",
        "configs": [cfg_or_defaults(lvl) for lvl in levels],
    }
    form = EditTopicForm(instance=topic, data=form_data)

    return render_template("admin/edit_topic.html", form=form, topic=topic, active_tab="topics")

@admin_bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        flash("Неверный запрос", "error")
        return redirect(url_for("admin.topics"))

    # запрещаем удалять, если есть связанные задания
    if topic.tasks.count() > 0:
        flash("Нельзя удалить: есть связанные задания", "error")
        return redirect(url_for("admin.topics"))

    try:
        # каскадно удаляем level_configs (если не настроен CASCADE — удалим вручную)
        for cfg in topic.level_configs:
            db.session.delete(cfg)
        db.session.delete(topic)
        db.session.commit()
        flash("Тема удалена", "success")
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f"Ошибка при удалении темы: {e}", "error")

    return redirect(url_for("admin.topics"))

@admin_bp.route("/topics/import", methods=["POST"])
@login_required
@admin_required
def import_topics():
    form = ImportFileForm()
    if not form.validate_on_submit():
        flash("Файл не выбран", "error")
        return redirect(url_for("admin.topics"))

    f = form.file.data
    if not f.filename.endswith(".json"):
        flash("Поддерживаются только .json", "error")
        return redirect(url_for("admin.topics"))

    try:
        items = json.loads(f.read().decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("JSON должен содержать массив тем")

        created = 0
        updated = 0
        skipped = 0
        skipped_codes = []  # для информативного сообщения

        for i, item in enumerate(items, 1):
            code = (item.get("code") or "").strip()
            name = (item.get("name") or "").strip()
            if not code or not name:
                raise ValueError(f"Элемент {i}: поля 'code' и 'name' обязательны")

            if Topic.query.filter_by(code=code).first():
                # пропустим дубликаты, но не падаем полностью
                skipped += 1
                skipped_codes.append(code)
                continue

            topic = Topic(code=code, name=name, description=item.get("description"))
            db.session.add(topic)
            db.session.flush()

            # level_configs
            level_cfgs = item.get("level_configs") or {}
            for level, defaults in [("low", {}), ("medium", {}), ("high", {})]:
                cfg = level_cfgs.get(level, {})
                db.session.add(TopicLevelConfig(
                    topic_id=topic.id,
                    level=level,
                    task_count_threshold=int(cfg.get("task_count_threshold", 10)),
                    reference_time=int(cfg.get("reference_time", 900)),
                    penalty_weights=cfg.get("penalty_weights", [0.7, 0.4]),
                ))
            created += 1

        db.session.commit()
        
        parts = []
        parts.append(f"Создано: {created}")
        if updated:
            parts.append(f"Обновлено: {updated}")
        if skipped:
            # покажем первые 5 кодов, чтобы не раздувать сообщение
            sample = ", ".join(skipped_codes[:5])
            more = f" и ещё {skipped - 5}" if skipped > 5 else ""
            parts.append(f"Пропущено (дубликаты): {skipped} [{sample}{more}]")

        msg = "; ".join(parts)

        # Если вообще ничего не создали/обновили — это скорее информсообщение
        category = "info" if (created == 0 and updated == 0) else "success"
        flash(f"Импорт тем завершён. {msg}", category)

    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f"Ошибка импорта: {e}", "error")

    return redirect(url_for("admin.topics"))

@admin_bp.route("/topics/export", methods=["GET", "POST"])
@login_required
@admin_required
def export_topics():
    """GET — экспорт всех; POST — экспорт выбранных (topic_ids в JSON)."""
    try:
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            ids = payload.get("topic_ids") or []
            if not ids:
                return jsonify({"success": False, "message": "Не выбрано ни одной темы"}), 400
            topics = Topic.query.filter(Topic.id.in_(ids)).all()
        else:
            topics = Topic.query.all()

        export_data = [_serialize_topic(t) for t in topics]
        resp = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        fname = ("selected_topics_export_" if request.method == "POST" else "all_topics_export_") \
                + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
        return resp
    except Exception as e:
        current_app.logger.error(f"Error exporting topics: {e}")
        if request.method == "POST":
            return jsonify({"success": False, "message": f"Ошибка при экспорте: {e}"}), 500
        flash(f"Ошибка при экспорте тем: {e}", "error")
        return redirect(url_for("admin.topics"))

# =============================================================================
#                               З А Д А Н И Я
# =============================================================================

@admin_bp.route("/tasks", methods=["GET"])
@login_required
@admin_required
def tasks():
    topic_id = request.args.get('topic_id', type=int)

    query = MathTask.query
    if topic_id:
        query = query.filter_by(topic_id=topic_id)
    
    items = query.order_by(MathTask.level.desc(), MathTask.id.desc()).all()

    # Для фильтра и форм
    topics = Topic.query.order_by(Topic.name).all()
    import_form = ImportFileForm()
    delete_form = ConfirmDeleteForm()
    
    return render_template(
        "admin/tasks.html", 
        tasks=items,
        topics=topics,
        import_form=import_form,
        delete_form=delete_form,
        active_tab="tasks"
    )

# ----------- Preview answer JSON from form data -----------
@admin_bp.route("/tasks/preview_answer_json", methods=["POST"])
@login_required
@admin_required
def preview_answer_json():
    # Формируем форму из текущего POST без строгой валидации
    form = TaskForm()
    # choices для SelectField, чтобы форма корректно инициализировалась
    form.topic_id.choices = [(t.id, f"{t.name} ({t.code})") for t in Topic.query.order_by(Topic.name).all()]
    try:
        data = form.build_answer_json()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"ok": False, "error": str(e)}), 400

@admin_bp.route("/tasks/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_task():
    form = TaskForm()
    form.topic_id.choices = [(t.id, f"{t.name} ({t.code})") for t in Topic.query.order_by(Topic.name).all()]
    
    # Принудительно создаём переменную, если нет
    try:
        if not form.variables_answer.form.variables.entries:
            form.variables_answer.form.variables.append_entry()
    except Exception:
        pass

    # Серверная обработка добавления/удаления переменных до валидации
    if request.method == "POST":
        if form.handle_variable_actions(request.form):
            # структура FieldList изменилась — просто перерисуем форму без validate_on_submit
            return render_template("admin/create_task.html", form=form, active_tab="tasks")
    
    if request.method == "POST":
        if form.validate_on_submit():
            try:
                task = MathTask(
                    title=form.title.data.strip(),
                    code=(form.code.data.strip() if form.code.data else None),
                    description=form.description.data.strip() if form.description.data else "",
                    answer_type=form.answer_type.data,
                    correct_answer=form._answer_data,  # уже готовый dict
                    answer_schema=getattr(form, "_answer_schema_obj", None),
                    explanation=form.explanation.data.strip() if form.explanation.data else "",
                    topic_id=form.topic_id.data,
                    level=form.level.data,
                    max_score=float(form.max_score.data or 1.0),
                    is_active=bool(form.is_active.data),
                    created_by=current_user.id,
                    created_at=datetime.utcnow()
                )
                db.session.add(task)
                db.session.commit()
                flash("Задание успешно создано", "success")
                return redirect(url_for("admin.tasks"))
            except Exception as e:
                current_app.logger.exception(e)
                db.session.rollback()
                flash(f"Ошибка при создании задания: {e}", "error")
        else:
            # Явно покажем ошибки валидации, чтобы было понятно, почему не создалось
            current_app.logger.warning("Create task validation errors: %s", form.errors)
            _flash_form_errors(form)
        # В любом случае при POST без редиректа — отрисовываем форму с ошибками ниже
        return render_template("admin/create_task.html", form=form, active_tab="tasks")

    # GET
    return render_template("admin/create_task.html", form=form, active_tab="tasks")

@admin_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_task(task_id):
    task = MathTask.query.get_or_404(task_id)
    form = TaskForm(obj=task)
    form.topic_id.choices = [(t.id, f"{t.name} ({t.code})") for t in Topic.query.order_by(Topic.name).all()]
    delete_form = ConfirmDeleteForm()

    # Гарантируем, что есть хотя бы одна строка переменных для рендера
    try:
        if not form.variables_answer.form.variables.entries:
            form.variables_answer.form.variables.append_entry()
    except Exception:
        pass

    # POST: сначала структурные изменения, затем валидация и сохранение
    if request.method == "POST":
        if form.handle_variable_actions(request.form):
            return render_template(
                "admin/edit_task.html",
                form=form,
                task=task,
                delete_form=delete_form,
                active_tab="tasks",
            )

        if form.validate_on_submit():
            task.code = (form.code.data.strip() if form.code.data else None)
            task.title = form.title.data.strip()
            task.description = (form.description.data or "").strip()
            task.answer_type = form.answer_type.data
            task.correct_answer = form._answer_data  # готовый dict из валидации
            task.answer_schema = getattr(form, "_answer_schema_obj", None)
            task.explanation = (form.explanation.data or "").strip()
            task.topic_id = form.topic_id.data
            task.level = form.level.data
            task.max_score = float(form.max_score.data or 1.0)
            task.is_active = bool(form.is_active.data)
            db.session.commit()
            flash("Задание обновлено", "success")
            return redirect(url_for("admin.tasks"))
        else:
            current_app.logger.warning("Edit task validation errors: %s", form.errors)
            _flash_form_errors(form)
            return render_template(
                "admin/edit_task.html",
                form=form,
                task=task,
                delete_form=delete_form,
                active_tab="tasks",
            )

    # GET: заполняем подформы из сохранённого ответа
    try:
        form.answer_type.data = task.answer_type
        form.populate_answer_forms(task.correct_answer)
    except Exception as e:
        current_app.logger.exception(e)

    # Схема ответа (если есть) в текстовое поле для режима JSON
    try:
        if task.answer_schema:
            form.answer_schema.data = json.dumps(task.answer_schema, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Текстовый JSON ответа (для опытного режима)
    try:
        if task.correct_answer:
            form.correct_answer_json.data = json.dumps(task.correct_answer, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return render_template(
        "admin/edit_task.html",
        form=form,
        task=task,
        delete_form=delete_form,
        active_tab="tasks",
    )
    
@admin_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_task(task_id):
    task = MathTask.query.get_or_404(task_id)
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        flash("Неверный запрос", "error")
        return redirect(url_for("admin.tasks"))

    try:
        db.session.delete(task)
        db.session.commit()
        flash("Задание удалено", "success")
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f"Ошибка удаления: {e}", "error")
    return redirect(url_for("admin.tasks"))

@admin_bp.route("/tasks/import", methods=["POST"])
@login_required
@admin_required
def import_tasks():
    form = ImportFileForm()
    if not form.validate_on_submit():
        flash("Файл не выбран", "error")
        return redirect(url_for("admin.tasks"))

    f = form.file.data
    if not f.filename.endswith(".json"):
        flash("Поддерживаются только .json", "error")
        return redirect(url_for("admin.tasks"))

    try:
        items = json.loads(f.read().decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("JSON должен содержать массив заданий")

        created = 0
        for i, item in enumerate(items, 1):
            title = (item.get("title") or "").strip()
            answer_type = item.get("answer_type")
            correct_answer = item.get("correct_answer")
            topic_code = item.get("topic_code")
            topic_id = item.get("topic_id")

            if not title or not answer_type or not correct_answer:
                raise ValueError(f"Задание {i}: title, answer_type и correct_answer — обязательны")

            # ищем тему (code предпочтительно)
            topic = None
            if topic_code:
                topic = Topic.query.filter_by(code=topic_code).first()
            if not topic and topic_id:
                topic = Topic.query.get(topic_id)
            if not topic:
                raise ValueError(f"Задание {i}: тема не найдена (topic_code/topic_id)")

            # минимальная валидация correct_answer
            if not isinstance(correct_answer, dict) or "type" not in correct_answer:
                raise ValueError(f"Задание {i}: correct_answer должен быть объектом с полем type")
            ca_type = correct_answer.get("type")
            if ca_type == "number" and not isinstance(correct_answer.get("value"), (int, float)):
                raise ValueError(f"Задание {i}: для типа number требуется числовой value")
            if ca_type == "sequence" and not isinstance(correct_answer.get("sequence_values"), list):
                raise ValueError(f"Задание {i}: для типа sequence нужен список sequence_values")
            if ca_type == "variables" and not isinstance(correct_answer.get("variables"), list):
                raise ValueError(f"Задание {i}: для типа variables нужен список variables")
            if ca_type == "interval":
                if "start" not in correct_answer or "end" not in correct_answer:
                    raise ValueError(f"Задание {i}: для типа interval нужны start/end")

            # опциональный внешний код; проверим уникальность, если задан
            code = (item.get("code") or "").strip() or None
            if code and MathTask.query.filter_by(code=code).first():
                raise ValueError(f"Задание {i}: код '{code}' уже используется")

            task = MathTask(
                title=title,
                code=code,
                description=item.get("description") or "",
                answer_type=answer_type,
                correct_answer=correct_answer,
                answer_schema=item.get("answer_schema"),
                explanation=item.get("explanation"),
                topic_id=topic.id,
                level=item.get("level") or "medium",
                max_score=float(item.get("max_score", 1.0)),
                created_by=current_user.id,
                is_active=bool(item.get("is_active", True)),
            )
            db.session.add(task)
            created += 1

        db.session.commit()
        flash(f"Импортировано заданий: {created}", "success")
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f"Ошибка импорта: {e}", "error")

    return redirect(url_for("admin.tasks"))

@admin_bp.route("/tasks/export", methods=["GET", "POST"])
@login_required
@admin_required
def export_tasks():
    try:
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            ids = payload.get("task_ids") or []
            if not ids:
                return jsonify({"success": False, "message": "Не выбрано ни одного задания"}), 400
            tasks = MathTask.query.filter(MathTask.id.in_(ids)).all()
        else:
            tasks = MathTask.query.all()

        export = {
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": getattr(current_user, "username", "admin"),
            "total_tasks": len(tasks),
            "tasks": [_serialize_task(t) for t in tasks],
        }
        resp = make_response(json.dumps(export, ensure_ascii=False, indent=2))
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        fname = ("selected_tasks_export_" if request.method == "POST" else "all_tasks_export_") \
                + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
        return resp
    except Exception as e:
        current_app.logger.exception(e)
        if request.method == "POST":
            return jsonify({"success": False, "message": f"Ошибка экспорта: {e}"}), 500
        flash(f"Ошибка экспорта: {e}", "error")
        return redirect(url_for("admin.tasks"))

# =============================================================================
#                               П О Л Ь З О В А Т Е Л И
# =============================================================================

@admin_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def users():
    items = User.query.order_by(User.created_at.desc().nullslast(), User.id.desc()).all()

    # словарь {user_id: count}
    attempt_counts = dict(
        db.session.query(TaskAttempt.user_id, func.count(TaskAttempt.id))
                  .group_by(TaskAttempt.user_id).all()
    )

    return render_template(
        "admin/users.html",
        users=items,
        attempt_counts=attempt_counts,
        import_form=ImportFileForm(),
        delete_form=ConfirmDeleteForm(),
        active_tab="users",
    )


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        u = User(
            username=form.username.data.strip(),
            email=(form.email.data or "").strip() or None,
            role=form.role.data,
            is_active=bool(form.is_active.data),
        )
        _set_user_password(u, form.password.data)
        db.session.add(u)
        db.session.commit()
        flash("Пользователь создан", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/create_user.html", form=form, active_tab="users")

@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    u = User.query.get_or_404(user_id)
    form = EditUserForm(obj=u, instance=u)
    if form.validate_on_submit():
        # Проверим уникальность (исключая текущего)
        u.username = form.username.data.strip()
        u.email = form.email.data.strip() if form.email.data else None
        u.role = form.role.data
        u.is_active = bool(form.is_active.data)
        if form.password.data:
            _set_user_password(u, form.password.data)
        db.session.commit()
        flash("Пользователь обновлён", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/edit_user.html", form=form, user=u, active_tab="users")


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        flash("Неверный запрос удаления.", "danger")
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)

    # защита: не удаляем себя
    if current_user.id == user.id:
        flash("Нельзя удалить свою учётную запись.", "warning")
        return redirect(url_for("admin.users"))

    delete_attempts = (request.form.get("delete_attempts") == "1")

    # есть ли попытки?
    has_attempts = db.session.query(
        db.session.query(TaskAttempt.id).filter_by(user_id=user.id).exists()
    ).scalar()

    if has_attempts and not delete_attempts:
        flash("У пользователя есть попытки. Отметьте «Также удалить попытки» в модалке и повторите удаление.", "warning")
        return redirect(url_for("admin.users"))

    try:
        if delete_attempts:
            # сначала удаляем попытки, затем пользователя
            TaskAttempt.query.filter_by(user_id=user.id).delete(synchronize_session=False)

        db.session.delete(user)
        db.session.commit()
        flash(("Пользователь и его попытки удалены." if delete_attempts else "Пользователь удалён."), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка удаления: {e}", "danger")

    return redirect(url_for("admin.users"))

@admin_bp.route("/users/import", methods=["POST"])
@login_required
@admin_required
def import_users():
    form = ImportFileForm()
    if not form.validate_on_submit():
        flash("Файл не выбран", "error")
        return redirect(url_for("admin.users"))

    f = form.file.data
    if not f.filename.endswith(".json"):
        flash("Поддерживаются только .json", "error")
        return redirect(url_for("admin.users"))

    try:
        items = json.loads(f.read().decode("utf-8"))
        if not isinstance(items, list):
            raise ValueError("JSON должен содержать массив пользователей")

        created, skipped = 0, 0
        for i, item in enumerate(items, 1):
            username = (item.get("username") or "").strip()
            role = item.get("role") or "student"
            email = (item.get("email") or "").strip() or None
            password = item.get("password")  # можно не передавать — сгенерируем

            if not username:
                raise ValueError(f"Элемент {i}: поле 'username' обязательно")
            if role not in {"student", "teacher", "admin"}:
                raise ValueError(f"Элемент {i}: недопустимая роль '{role}'")

            if User.query.filter_by(username=username).first() or (email and User.query.filter_by(email=email).first()):
                skipped += 1
                continue

            u = User(
                username=username,
                email=email,
                role=role,
                is_active=bool(item.get("is_active", True)),
            )
            _set_user_password(u, password or secrets.token_urlsafe(8))
            db.session.add(u)
            created += 1

        db.session.commit()
        flash(f"Импортировано пользователей: {created}. Пропущено (дубликаты): {skipped}", "success")
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f"Ошибка импорта: {e}", "error")

    return redirect(url_for("admin.users"))

@admin_bp.route("/users/export", methods=["GET", "POST"])
@login_required
@admin_required
def export_users():
    """GET — экспорт всех; POST — экспорт выбранных (user_ids в JSON). Пароли не экспортируем."""
    try:
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            ids = payload.get("user_ids") or []
            if not ids:
                return jsonify({"success": False, "message": "Не выбрано ни одного пользователя"}), 400
            users = User.query.filter(User.id.in_(ids)).all()
        else:
            users = User.query.all()

        export_data = [{
            "id": u.id,
            "username": u.username,
            "email": getattr(u, "email", None),
            "role": getattr(u, "role", None),
            "is_active": getattr(u, "is_active", True),
            "created_at": getattr(u, "created_at", None).isoformat() if getattr(u, "created_at", None) else None,
        } for u in users]

        resp = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        fname = ("selected_users_export_" if request.method == "POST" else "all_users_export_") \
                + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
        return resp
    except Exception as e:
        current_app.logger.exception(e)
        if request.method == "POST":
            return jsonify({"success": False, "message": f"Ошибка экспорта: {e}"}), 500
        flash(f"Ошибка экспорта: {e}", "error")
        return redirect(url_for("admin.users"))


# =============================================================================
#                             Ж У Р Н А Л   П О П Ы Т О К
# =============================================================================

@admin_bp.route("/attempts", methods=["GET"])  # список с фильтрами + пагинация
@login_required
def attempts():
    # Доступ: админ — полный, преподаватель — только просмотр
    can_manage = (getattr(current_user, "role", None) == "admin")

    form = AttemptFilterForm(request.args)

    # choices для фильтров
    students = User.query.order_by(User.username.asc()).all()
    tasks_q = MathTask.query.order_by(MathTask.title.asc())
    topics = Topic.query.order_by(Topic.name.asc()).all()
    form.student_id.choices = [(0, 'Все')] + [(u.id, u.username) for u in students]
    form.task_id.choices    = [(0, 'Все')] + [(t.id, t.title) for t in tasks_q]
    form.topic_id.choices   = [(0, 'Все')] + [(t.id, t.name) for t in topics]

    q = (TaskAttempt.query
         .join(User, TaskAttempt.user_id == User.id)
         .join(MathTask, TaskAttempt.task_id == MathTask.id))

    # Фильтры
    if form.student_id.data and int(form.student_id.data) != 0:
        q = q.filter(TaskAttempt.user_id == int(form.student_id.data))
    if form.task_id.data and int(form.task_id.data) != 0:
        q = q.filter(TaskAttempt.task_id == int(form.task_id.data))
    if form.topic_id.data and int(form.topic_id.data) != 0:
        q = q.filter(MathTask.topic_id == int(form.topic_id.data))
    if form.date_from.data:
        q = q.filter(TaskAttempt.created_at >= datetime.combine(form.date_from.data, datetime.min.time()))
    if form.date_to.data:
        q = q.filter(TaskAttempt.created_at < datetime.combine(form.date_to.data, datetime.min.time()) + timedelta(days=1))

    # Сортировка: новые сверху
    q = q.order_by(TaskAttempt.created_at.desc(), TaskAttempt.id.desc())

    # Паджинация
    try:
        per_page = int(request.args.get('per_page', form.per_page.data or 20))
    except Exception:
        per_page = 20
    page = max(int(request.args.get('page', 1)), 1)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'admin/attempts.html',
        form=form,
        pagination=pagination,
        attempts=pagination.items,
        can_manage=can_manage,
        active_tab='attempts'
    )

@admin_bp.route('/attempts/create', methods=['GET', 'POST'])
@login_required
def create_attempt():
    if getattr(current_user, 'role', None) != 'admin':
        from flask import abort
        abort(403)
    form = CreateAttemptForm()
    # Заполняем choices
    form.user_id.choices = [(u.id, u.username) for u in User.query.order_by(User.username.asc()).all()]
    form.task_id.choices = [(t.id, t.title) for t in MathTask.query.order_by(MathTask.title.asc()).all()]

    # Предзаполнение задачи из query (?task_id=...) и подстановка правильного ответа, если поле пустое
    preselect_task_id = request.args.get('task_id', type=int)
    if preselect_task_id and not form.task_id.data:
        form.task_id.data = preselect_task_id

    if form.task_id.data and not form.user_answer.data:
        try:
            task_obj = MathTask.query.get(form.task_id.data)
            if task_obj and getattr(task_obj, 'correct_answer', None) is not None:
                ca = task_obj.correct_answer
                if isinstance(ca, str):
                    try:
                        ca = json.loads(ca)
                    except Exception:
                        pass
                form.user_answer.data = json.dumps(ca, ensure_ascii=False, indent=2) if not isinstance(ca, str) else ca
        except Exception:
            pass

    # Нажатие кнопки «Подставить ответ задачи» — просто подставляем и рендерим форму без создания записи
    if request.method == 'POST' and 'prefill_from_task' in request.form:
        task_obj = MathTask.query.get(form.task_id.data) if form.task_id.data else None
        if task_obj and getattr(task_obj, 'correct_answer', None) is not None:
            ca = task_obj.correct_answer
            try:
                if isinstance(ca, str):
                    try:
                        ca = json.loads(ca)
                    except Exception:
                        pass
                form.user_answer.data = json.dumps(ca, ensure_ascii=False, indent=2) if not isinstance(ca, str) else ca
                flash('Ответ задачи подставлен. Проверьте и сохраните.', 'info')
            except Exception as e:
                flash(f'Не удалось подставить ответ: {e}', 'warning')
        else:
            flash('У выбранной задачи отсутствует правильный ответ.', 'warning')
        return render_template('admin/create_attempt.html', form=form, active_tab='attempts')

    if form.validate_on_submit():
        # Автонумерация, если не задан attempt_number
        attempt_number = form.attempt_number.data
        if not attempt_number:
            last = (TaskAttempt.query
                    .filter_by(user_id=form.user_id.data, task_id=form.task_id.data)
                    .order_by(TaskAttempt.attempt_number.desc())
                    .first())
            attempt_number = (last.attempt_number + 1) if last and last.attempt_number else 1

        # user_answer: допускаем JSON-строку, иначе сохраняем как есть
        ua_raw = (form.user_answer.data or '').strip()
        ua_val = None
        if ua_raw:
            try:
                ua_val = json.loads(ua_raw)
            except Exception:
                ua_val = ua_raw

        # Получим объект задачи для расчёта
        task_obj_for_scoring = MathTask.query.get(form.task_id.data)

        # partial_score по политике (0..1) с учётом успешности и номера попытки
        computed_partial = _compute_partial_score(
            task_obj_for_scoring, int(attempt_number), bool(form.is_correct.data)
        ) if task_obj_for_scoring else 0.0

        # component_scores: пока наследуем максимум балла задачи (числом)
        component_scores_value = None
        if task_obj_for_scoring is not None:
            try:
                component_scores_value = float(task_obj_for_scoring.max_score or 0)
            except Exception:
                component_scores_value = 0.0

        att = TaskAttempt(
            user_id=form.user_id.data,
            task_id=form.task_id.data,
            attempt_number=int(attempt_number),
            is_correct=bool(form.is_correct.data),
            partial_score=computed_partial,
            component_scores=component_scores_value,
            time_spent=int(form.time_spent.data or 0),
            hints_used=int(form.hints_used.data or 0),
            created_at=form.created_at.data or datetime.utcnow(),
            user_answer=ua_val,
        )
        db.session.add(att)
        db.session.commit()
        flash('Попытка добавлена', 'success')
        return redirect(url_for('admin.attempts'))

    return render_template('admin/create_attempt.html', form=form, active_tab='attempts')


# =============================================================================
#                             Edit Attempt
# =============================================================================
@admin_bp.route('/attempts/<int:attempt_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_attempt(attempt_id):
    if getattr(current_user, 'role', None) not in ('admin', 'teacher'):
        from flask import abort
        abort(403)

    att = TaskAttempt.query.get_or_404(attempt_id)

    form = EditAttemptForm(obj=att)
    form.user_id.choices = [(u.id, u.username) for u in User.query.order_by(User.username.asc()).all()]
    form.task_id.choices = [(t.id, t.title) for t in MathTask.query.order_by(MathTask.title.asc()).all()]

    can_edit = (getattr(current_user, 'role', None) == 'admin')

    if form.validate_on_submit():
        if not can_edit:
            flash('Недостаточно прав', 'warning')
            return redirect(url_for('admin.attempts'))

        ua_raw = (form.user_answer.data or '').strip()
        ua_val = None
        if ua_raw:
            try:
                ua_val = json.loads(ua_raw)
            except Exception:
                ua_val = ua_raw

        attempt_number = form.attempt_number.data
        if not attempt_number:
            last = (TaskAttempt.query
                    .filter_by(user_id=form.user_id.data, task_id=form.task_id.data)
                    .order_by(TaskAttempt.attempt_number.desc())
                    .first())
            attempt_number = (last.attempt_number + 1) if last and last.attempt_number else 1

        att.user_id = form.user_id.data
        att.task_id = form.task_id.data
        att.attempt_number = int(attempt_number)
        att.is_correct = bool(form.is_correct.data)
        att.partial_score = float(form.partial_score.data or 0.0)
        att.time_spent = int(form.time_spent.data or 0)
        att.hints_used = int(form.hints_used.data or 0)
        att.created_at = form.created_at.data or att.created_at
        att.user_answer = ua_val

        db.session.commit()
        flash('Изменения сохранены', 'success')
        return redirect(url_for('admin.attempts'))

    if isinstance(att.user_answer, (dict, list)) and not form.is_submitted():
        form.user_answer.data = json.dumps(att.user_answer, ensure_ascii=False, indent=2)

    return render_template('admin/edit_attempt.html', form=form, attempt=att, can_edit=can_edit, active_tab='attempts')

@admin_bp.route('/attempts/<int:attempt_id>/delete', methods=['POST'])
@login_required
def delete_attempt(attempt_id):
    if getattr(current_user, 'role', None) != 'admin':
        from flask import abort
        abort(403)
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        flash('Неверный запрос', 'warning')
        return redirect(url_for('admin.attempts'))
    att = TaskAttempt.query.get_or_404(attempt_id)
    db.session.delete(att)
    db.session.commit()
    flash('Попытка удалена', 'success')
    return redirect(url_for('admin.attempts'))

@admin_bp.route('/attempts/export', methods=['GET'])
@login_required
def export_attempts():
    form = AttemptFilterForm(request.args)
    q = TaskAttempt.query
    # Применяем те же правила фильтрации, что и на списке (0 == «Все»)
    if form.student_id.data and str(form.student_id.data).isdigit() and int(form.student_id.data) != 0:
        q = q.filter(TaskAttempt.user_id == int(form.student_id.data))
    if form.task_id.data and str(form.task_id.data).isdigit() and int(form.task_id.data) != 0:
        q = q.filter(TaskAttempt.task_id == int(form.task_id.data))
    if form.topic_id.data and str(form.topic_id.data).digits() if False else str(form.topic_id.data).isdigit() and int(form.topic_id.data) != 0:
        q = q.join(MathTask).filter(MathTask.topic_id == int(form.topic_id.data))
    if form.date_from.data:
        q = q.filter(TaskAttempt.created_at >= datetime.combine(form.date_from.data, datetime.min.time()))
    if form.date_to.data:
        q = q.filter(TaskAttempt.created_at < datetime.combine(form.date_to.data, datetime.min.time()) + timedelta(days=1))

    data = []
    for a in q.order_by(TaskAttempt.created_at.desc(), TaskAttempt.id.desc()).all():
        data.append({
            'id': a.id,
            'user_id': a.user_id,
            'username': a.user.username if a.user else None,
            'task_id': a.task_id,
            'task_code': a.task.code if a.task else None,
            'attempt_number': a.attempt_number,
            'is_correct': a.is_correct,
            'partial_score': a.partial_score,
            'time_spent': a.time_spent,
            'hints_used': a.hints_used,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'user_answer': a.user_answer,
        })
    resp = make_response(json.dumps(data, ensure_ascii=False, indent=2))
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    fname = "attempts_export_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".json"
    resp.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp

@admin_bp.route('/attempts/import', methods=['POST'])
@login_required
def import_attempts():
    if getattr(current_user, 'role', None) != 'admin':
        from flask import abort
        abort(403)

    form = ImportFileForm()
    if not form.validate_on_submit():
        flash('Файл не выбран', 'warning')
        return redirect(url_for('admin.attempts'))

    f = form.file.data
    if not f.filename.endswith('.json'):
        flash('Поддерживаются только .json', 'danger')
        return redirect(url_for('admin.attempts'))

    # ---- helpers ------------------------------------------------------------
    def _parse_created_at(val):
        if not val:
            return None
        # Допускаем ISO8601 или 'YYYY-MM-DD HH:MM:SS'
        try:
            return datetime.fromisoformat(val)
        except Exception:
            pass
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt)
            except Exception:
                continue
        return None

    def _normalize_answer(val):
        """Приводит ответ к пригодному для сохранения виду:
        - если строка — пытаемся распарсить JSON, иначе возвращаем исходную строку
        - если пустая строка/None — возвращаем None
        - dict/list/числа/булевы — возвращаем как есть
        """
        if val is None:
            return None
        if isinstance(val, (dict, list, int, float, bool)):
            return val
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return None
            try:
                return json.loads(s)
            except Exception:
                return s
        return val

    try:
        payload = json.loads(f.read().decode('utf-8'))
        if not isinstance(payload, list):
            raise ValueError('JSON должен содержать массив попыток')

        created = 0
        errors = 0
        for i, item in enumerate(payload, start=1):
            # === Схема: ожидаем task_code и username (импорт по внешним ключам) ===
            task = None
            code = (item.get('task_code') or '').strip()
            if code:
                task = MathTask.query.filter_by(code=code).first()
            if not task and item.get('task_id'):
                # fallback для старых файлов
                try:
                    task = MathTask.query.get(int(item['task_id']))
                except Exception:
                    task = None
            if not task:
                errors += 1
                flash(f'Строка {i}: задача не найдена (task_code/task_id)', 'danger')
                continue

            user = None
            username = (item.get('username') or '').strip()
            if username:
                user = User.query.filter_by(username=username).first()
            if not user and item.get('user_id'):
                # fallback для старых файлов
                try:
                    user = User.query.get(int(item['user_id']))
                except Exception:
                    user = None
            if not user:
                errors += 1
                flash(f'Строка {i}: студент не найден (username/user_id)', 'danger')
                continue

            # Номер попытки: если отсутствует — следующий по паре (user, task)
            attempt_number = item.get('attempt_number')
            if not attempt_number:
                last = (TaskAttempt.query
                        .filter_by(user_id=user.id, task_id=task.id)
                        .order_by(TaskAttempt.attempt_number.desc())
                        .first())
                attempt_number = (last.attempt_number + 1) if last and last.attempt_number else 1

            # Время создания: допускаем ISO или простой формат; иначе now
            created_at = _parse_created_at(item.get('created_at')) or datetime.utcnow()

            # Ответ пользователя: допускаем JSON-строку; если нет — подставляем correct_answer задачи
            ua = _normalize_answer(item.get('user_answer'))
            if ua is None:
                ua = _normalize_answer(getattr(task, 'correct_answer', None))

            is_correct = bool(item.get('is_correct', False))

            # === Расчёт баллов по единой политике ===
            computed_partial = _compute_partial_score(task, int(attempt_number), is_correct)
            try:
                component_scores_value = float(getattr(task, 'max_score', 0) or 0)
            except Exception:
                component_scores_value = 0.0

            att = TaskAttempt(
                user_id=user.id,
                task_id=task.id,
                attempt_number=int(attempt_number),
                is_correct=is_correct,
                partial_score=computed_partial,
                component_scores=component_scores_value,
                time_spent=int(item.get('time_spent') or 0),
                hints_used=int(item.get('hints_used') or 0),
                created_at=created_at,
                user_answer=ua,
            )
            db.session.add(att)
            created += 1

        db.session.commit()
        if errors:
            flash(f'Импортировано попыток: {created}. Ошибок: {errors}', 'warning')
        else:
            flash(f'Импортировано попыток: {created}', 'success')
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        flash(f'Ошибка импорта: {e}', 'danger')
    return redirect(url_for('admin.attempts'))


# ---------------------------------------------------------------------------
# Bulk delete attempts
@admin_bp.route('/attempts/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_attempts():
    # Только админ может удалять массово
    if getattr(current_user, 'role', None) != 'admin':
        from flask import abort
        abort(403)

    try:
        ids = request.form.getlist('ids')
        # допускаем как ['1','2'] так и просто одну строку
        if not ids:
            return make_response('No ids', 400)
        # Приведём к int и отфильтруем нечисловые
        try:
            id_list = [int(x) for x in ids]
        except Exception:
            return make_response('Bad ids', 400)
        if not id_list:
            return make_response('No valid ids', 400)

        # Удаляем пачкой
        TaskAttempt.query.filter(TaskAttempt.id.in_(id_list)).delete(synchronize_session=False)
        db.session.commit()
        # Пустой ответ, как ожидает JS (resp.ok => reload)
        return ('', 204)
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return make_response(f'Error: {e}', 500)
