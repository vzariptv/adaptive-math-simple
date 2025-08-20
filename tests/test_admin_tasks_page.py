import pytest
from io import BytesIO
import json
from datetime import datetime
from flask import url_for

from extensions import db
from models import User, Topic, MathTask


class TestAdminTasksPage:
    """Test admin tasks page functionality"""

    @pytest.fixture(autouse=True)
    def setup_tasks_data(self, app, admin_user, teacher_user):
        """Setup tasks test data"""
        with app.app_context():
            # topic required for tasks
            self.topic = Topic(code="algebra", name="Алгебра")
            db.session.add(self.topic)
            db.session.flush()
            self.topic_id = self.topic.id

            # one task
            mt = MathTask(
                title="Простая задача",
                code="ALG-1",
                description="Тест",
                answer_type="number",
                correct_answer={"type": "number", "value": 42},
                topic_id=self.topic_id,
                level="low",
                max_score=1.0,
                created_by=admin_user.id,
                created_at=datetime.utcnow(),
                is_active=True,
            )
            db.session.add(mt)
            db.session.commit()
            self.task_id = mt.id

    def test_requires_login_redirect(self, client):
        """Test that tasks page requires login"""
        resp = client.get(url_for('admin.tasks'))
        assert resp.status_code in (302, 401)

    def test_forbidden_for_non_admin(self, client, teacher_user, login_teacher):
        """Test that tasks page is forbidden for non-admin users"""
        resp = client.get(url_for('admin.tasks'))
        assert resp.status_code == 403

    def test_get_tasks_page_admin(self, client, admin_user, login_admin):
        """Test that admin can access tasks page"""
        resp = client.get(url_for('admin.tasks'))
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "заданиями" in body or "tasks" in body.lower()
        assert "Создать" in body or "create" in body.lower()

    def test_preview_answer_json_ok_and_error(self, client, admin_user, login_admin):
        """Test answer JSON preview functionality"""
        # OK number type
        data_ok = {
            "answer_type": "number",
            "number_answer-value": "5",
            "title": "T",
            "topic_id": str(self.topic_id),
            "level": "low",
            "max_score": "1",
        }
        r_ok = client.post(url_for('admin.preview_answer_json'), data=data_ok)
        assert r_ok.status_code == 200
        payload = r_ok.get_json()
        assert payload.get("ok") is True
        assert payload.get("data", {}).get("type") == "number"
        # Error: invalid type
        data_bad = {"answer_type": "unknown"}
        r_bad = client.post(url_for('admin.preview_answer_json'), data=data_bad)
        assert r_bad.status_code == 400
        assert r_bad.get_json().get("ok") is False

    def test_create_task_validation_and_success(self, client, admin_user, app, login_admin):
        """Test task creation validation and success"""
        # missing -> should re-render
        r1 = client.post(url_for('admin.create_task'), data={}, follow_redirects=True)
        assert r1.status_code == 200
        # valid number task
        form = {
            "title": "Новая",
            "code": "ALG-2",
            "description": "d",
            "answer_type": "number",
            "number_answer-value": "7",
            "topic_id": str(self.topic_id),
            "level": "low",
            "max_score": "2",
            "is_active": "y",
            "submit": "1",
        }
        r2 = client.post(url_for('admin.create_task'), data=form, follow_redirects=True)
        assert r2.status_code == 200
        body = r2.get_data(as_text=True)
        assert "создано" in body or "created" in body.lower()
        with app.app_context():
            created = MathTask.query.filter_by(code="ALG-2").first()
            assert created is not None
            # Optional fields should be saved when provided
            assert created.description == "d"
            assert created.is_active is True
            assert created.level == "low"
            assert created.max_score == 2.0
            assert created.topic_id == self.topic_id
            assert created.answer_type == "number"
            assert created.correct_answer.get("value") == 7

    def test_edit_task_get_and_post(self, client, admin_user, app, login_admin):
        """Test task editing functionality"""
        # GET
        r1 = client.get(url_for('admin.edit_task', task_id=self.task_id))
        assert r1.status_code == 200
        body = r1.get_data(as_text=True)
        assert "Сохранить" in body or "save" in body.lower()
        # POST update
        form = {
            "title": "Обновлена",
            "code": "ALG-1",
            "description": "t",
            "answer_type": "number",
            "number_answer-value": "42",
            "topic_id": str(self.topic_id),
            "level": "low",
            "max_score": "3",
            "is_active": "y",
            "submit": "1",
        }
        r2 = client.post(url_for('admin.edit_task', task_id=self.task_id), data=form, follow_redirects=True)
        assert r2.status_code == 200
        body = r2.get_data(as_text=True)
        assert "обновлено" in body or "updated" in body.lower()
        # Verify optional fields updated when provided
        with app.app_context():
            updated = MathTask.query.get(self.task_id)
            assert updated.title == "Обновлена"
            assert updated.description == "t"
            assert updated.max_score == 3.0
            assert updated.is_active is True
            assert updated.code == "ALG-1"
            assert updated.correct_answer.get("value") == 42

    def test_export_tasks_all_and_selected(self, client, admin_user, app, login_admin):
        """Test task export functionality"""
        r_all = client.get(url_for('admin.export_tasks'))
        assert r_all.status_code == 200
        assert r_all.headers.get("Content-Type") == "application/json; charset=utf-8"
        data_all = json.loads(r_all.get_data(as_text=True))
        assert isinstance(data_all, list)
        assert len(data_all) >= 1
        # selected via POST
        with app.app_context():
            ids = [t.id for t in MathTask.query.all()]
        r_sel = client.post(
            url_for('admin.export_tasks'),
            data=json.dumps({"task_ids": ids[:1]}),
            content_type="application/json",
        )
        assert r_sel.status_code == 200
        data_sel = json.loads(r_sel.get_data(as_text=True))
        assert len(data_sel) == 1

    def test_import_tasks_validation_and_success(self, client, admin_user, app, login_admin):
        """Test task import validation and success"""
        # bad ext
        r_bad = client.post(
            url_for('admin.import_tasks'),
            data={"file": (BytesIO(b"[]"), "tasks.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r_bad.status_code == 200
        # correct
        payload = [
            {
                "title": "Квадратные",
                "description": "desc",
                "answer_type": "number",
                "correct_answer": {"type": "number", "value": 1},
                "topic_code": "algebra",
                "level": "low",
                "max_score": 1.0,
                "is_active": True,
            }
        ]
        r_ok = client.post(
            url_for('admin.import_tasks'),
            data={"file": (BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), "tasks.json")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r_ok.status_code == 200
        with app.app_context():
            assert MathTask.query.filter_by(title="Квадратные").first() is not None
