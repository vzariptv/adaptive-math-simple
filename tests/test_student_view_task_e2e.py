import json
import pytest
from flask import url_for

from extensions import db
from models import Topic, MathTask, TaskAttempt


def _make_topic(app, code="algebra", name="Алгебра"):
    with app.app_context():
        t = Topic(code=code, name=name)
        db.session.add(t)
        db.session.commit()
        tid = t.id
        db.session.expunge(t)
        return tid


def _make_task(app, admin_user, topic_id, answer_type, correct_answer, title="Test Task"):
    with app.app_context():
        task = MathTask(
            title=title,
            code=None,
            description="desc",
            answer_type=answer_type,
            correct_answer=correct_answer,
            answer_schema=None,
            explanation=None,
            topic_id=topic_id,
            level="low",
            max_score=1.0,
            created_by=admin_user.id,
            is_active=True,
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task


@pytest.mark.usefixtures("login_student")
class TestStudentSubmit:
    def test_number_submit_correct(self, app, client, admin_user):
        topic_id = _make_topic(app)
        task = _make_task(app, admin_user, topic_id, "number", {"type": "number", "value": 42.0})

        # GET page
        resp = client.get(f"/student/tasks/{task.id}")
        assert resp.status_code == 200

        # POST correct answer
        resp = client.post(f"/student/tasks/{task.id}", data={"answer": "42"}, follow_redirects=False)
        assert resp.status_code in (302, 303)

        # Check attempt persisted
        with app.app_context():
            attempts = TaskAttempt.query.filter_by(task_id=task.id).all()
            assert len(attempts) == 1
            a = attempts[0]
            assert a.user_answer == {"type": "number", "value": 42.0}
            assert a.is_correct is True
            assert a.attempt_number == 1

    def test_variables_legacy_mapping_submit(self, app, client, admin_user):
        topic_id = _make_topic(app, code="vars", name="Переменные")
        # correct_answer canonical in DB
        correct = {"type": "variables", "variables": [{"name": "x", "value": 1.0}, {"name": "y", "value": 2.5}]}
        task = _make_task(app, admin_user, topic_id, "variables", correct)

        # Legacy template renders per key fields; our view supports it
        resp = client.post(f"/student/tasks/{task.id}", data={"x": "1", "y": "2,5"}, follow_redirects=False)
        assert resp.status_code in (302, 303)
        with app.app_context():
            attempts = TaskAttempt.query.filter_by(task_id=task.id).all()
            assert len(attempts) == 1
            a = attempts[0]
            assert a.user_answer == correct
            assert a.is_correct is True

    def test_interval_submit(self, app, client, admin_user):
        topic_id = _make_topic(app, code="interval", name="Интервалы")
        correct = {
            "type": "interval",
            "start": None,
            "end": 10.5,
            "start_inclusive": True,
            "end_inclusive": False,
        }
        task = _make_task(app, admin_user, topic_id, "interval", correct)

        form = {
            "start_infinity": "on",
            "end": "10,5",
            "start_inclusive": "on",
            # end_inclusive omitted => False
        }
        resp = client.post(f"/student/tasks/{task.id}", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        with app.app_context():
            a = TaskAttempt.query.filter_by(task_id=task.id).one()
            assert a.user_answer == correct
            assert a.is_correct is True

    def test_number_incorrect_then_blocked_after_three(self, app, client, admin_user):
        topic_id = _make_topic(app, code="algebra2", name="Алгебра 2")
        task = _make_task(app, admin_user, topic_id, "number", {"type": "number", "value": 42.0})

        # 3 incorrect submissions
        for wrong in ("0", "1", "2"):
            resp = client.post(f"/student/tasks/{task.id}", data={"answer": wrong}, follow_redirects=False)
            assert resp.status_code in (302, 303)

        with app.app_context():
            attempts = TaskAttempt.query.filter_by(task_id=task.id).order_by(TaskAttempt.id.asc()).all()
            assert len(attempts) == 3
            assert all(a.is_correct is False for a in attempts)

        # 4th POST should be blocked (no new attempt created)
        resp = client.post(f"/student/tasks/{task.id}", data={"answer": "3"}, follow_redirects=False)
        assert resp.status_code in (302, 303)
        with app.app_context():
            attempts = TaskAttempt.query.filter_by(task_id=task.id).all()
            assert len(attempts) == 3

        # GET should redirect to tasks (blocked view)
        resp = client.get(f"/student/tasks/{task.id}", follow_redirects=False)
        assert resp.status_code in (302, 303)
        # We don't rely on exact query string, only path
        assert "/student/tasks" in resp.headers.get("Location", "")

    def test_sequence_textarea_submit(self, app, client, admin_user):
        topic_id = _make_topic(app, code="seq", name="Последовательности")
        correct = {"type": "sequence", "sequence_values": [1.0, 2.0, 3.0, 4.5]}
        task = _make_task(app, admin_user, topic_id, "sequence", correct)

        form = {"sequence_input": "1, 2; 3, 4.5"}
        resp = client.post(f"/student/tasks/{task.id}", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        with app.app_context():
            a = TaskAttempt.query.filter_by(task_id=task.id).one()
            assert a.user_answer == correct
            assert a.is_correct is True
