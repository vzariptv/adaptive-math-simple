import json
import pytest
from datetime import datetime, timedelta
from flask import url_for

from extensions import db
from models import User, Topic, MathTask, TaskAttempt, EvaluationSystemConfig


class TestAdminEvaluationPage:
    """Test admin evaluation page functionality"""

    @pytest.fixture(autouse=True)
    def setup_evaluation_data(self, app, admin_user, teacher_user, student_user):
        """Setup evaluation test data"""
        with app.app_context():
            # Seed config
            cfg = EvaluationSystemConfig(
                evaluation_period_days=7,
                weight_accuracy=0.3,
                weight_time=0.2,
                weight_progress=0.3,
                weight_motivation=0.2,
            )
            db.session.add(cfg)

            # Topic + task
            self.topic = Topic(code="algebra", name="Алгебра")
            db.session.add(self.topic)
            db.session.flush()
            self.topic_id = self.topic.id

            self.task = MathTask(
                title="Простая задача",
                code="ALG-1",
                description="Тест",
                answer_type="number",
                correct_answer={"type": "number", "value": 42},
                topic_id=self.topic.id,
                level="low",
                max_score=1.0,
                created_by=admin_user.id,
                created_at=datetime.utcnow(),
                is_active=True,
            )
            db.session.add(self.task)
            db.session.flush()

            # One correct attempt within period
            base = datetime.utcnow() - timedelta(days=1)
            att = TaskAttempt(
                user_id=student_user.id,
                task_id=self.task.id,
                user_answer={"type": "number", "value": 42},
                is_correct=True,
                partial_score=1.0,
                component_scores=None,
                time_spent=120,
                hints_used=0,
                attempt_number=1,
                created_at=base,
            )
            db.session.add(att)
            db.session.commit()
            self.student_id = student_user.id

    def test_requires_login_redirect(self, client):
        """Test that evaluation page requires login"""
        resp = client.get(url_for('admin.evaluation_page'))
        assert resp.status_code in (302, 401)

    def test_forbidden_for_non_admin(self, client, teacher_user, login_teacher):
        """Test that evaluation page is forbidden for non-admin users"""
        resp = client.get(url_for('admin.evaluation_page'))
        # admin_required aborts with 403
        assert resp.status_code == 403

    def test_get_page_as_admin_ok(self, client, admin_user, login_admin):
        """Test that admin can access evaluation page"""
        resp = client.get(url_for('admin.evaluation_page'))
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "оценивания" in body or "evaluation" in body.lower()

    def test_preview_validation_errors(self, client, admin_user, login_admin):
        """Test evaluation preview validation errors"""
        # Missing user_ids and topic_id
        resp = client.post(
            url_for('admin.evaluation_preview'),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        payload = resp.get_json()
        assert payload.get("ok") is False
        errors = payload.get("errors", [])
        error_text = " ".join(errors).lower()
        assert "студента" in error_text or "user" in error_text
        assert "тему" in error_text or "topic" in error_text

    def test_preview_success(self, client, admin_user, login_admin):
        """Test successful evaluation preview"""
        body = {
            "user_ids": [self.student_id],
            "topic_id": self.topic_id,
            # let backend choose default period based on config
        }
        resp = client.post(
            url_for('admin.evaluation_preview'),
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload.get("ok") is True
        assert "results" in payload
        assert "meta" in payload
        assert payload["meta"].get("user_count", 0) >= 1
