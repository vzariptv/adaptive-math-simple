import pytest
from io import BytesIO
import json
from datetime import datetime
from flask import url_for

from extensions import db
from models import Topic, TopicLevelConfig


class TestAdminTopicsPage:
    @pytest.fixture(autouse=True)
    def setup_topics(self, app):
        """Setup test topics for each test"""
        with app.app_context():
            # Create test topic
            self.topic = Topic(
                code="algebra", 
                name="Алгебра", 
                description="desc", 
                created_at=datetime.utcnow()
            )
            db.session.add(self.topic)
            db.session.flush()
            # Store ID to avoid DetachedInstanceError outside the session
            self.topic_id = self.topic.id
            
            # Add level configs
            for lvl in ("low", "medium", "high"):
                config = TopicLevelConfig(
                    topic_id=self.topic_id, 
                    level=lvl, 
                    task_count_threshold=10, 
                    reference_time=900, 
                    penalty_weights=[0.7, 0.4]
                )
                db.session.add(config)
            db.session.commit()

    def test_requires_login_redirect(self, client):
        """Test that unauthenticated users are redirected"""
        # Remove auto-login fixture for this test
        resp = client.get(url_for('admin.topics'))
        assert resp.status_code in (302, 401)

    def test_forbidden_for_non_admin(self, client, teacher_user, login_teacher):
        """Test that topics page is forbidden for non-admin users"""
        resp = client.get(url_for('admin.topics'))
        assert resp.status_code == 403

    def test_get_topics_page_admin(self, client, admin_user, login_admin):
        """Test that admin can access topics page"""
        resp = client.get(url_for('admin.topics'))
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "темами" in body or "topics" in body.lower()
        assert "Создать" in body or "create" in body.lower()

    def test_create_topic_validation_and_success(self, client, admin_user, app, login_admin):
        """Test topic creation validation and success"""
        # Test missing required fields
        resp = client.post(url_for('admin.create_topic'), data={}, follow_redirects=True)
        assert resp.status_code == 200
        
        # Test valid creation
        data = {
            "code": "geometry",
            "name": "Геометрия",
            "description": "about",
            "submit": "1",
        }
        resp2 = client.post(url_for('admin.create_topic'), data=data, follow_redirects=True)
        assert resp2.status_code == 200
        
        # Verify topic was created with default level configs
        with app.app_context():
            tp = Topic.query.filter_by(code="geometry").first()
            assert tp is not None
            # Optional field 'description' should be saved when provided
            assert tp.description == "about"
            cfgs = TopicLevelConfig.query.filter_by(topic_id=tp.id).all()
            assert len(cfgs) == 3

    def test_edit_topic_page_get_and_post(self, client, admin_user, app, login_admin):
        """Test topic editing GET and POST"""
        # GET edit page
        r1 = client.get(url_for('admin.edit_topic', topic_id=self.topic_id))
        assert r1.status_code == 200
        body = r1.get_data(as_text=True)
        assert "Сохранить" in body or "save" in body.lower()
        
        # POST valid update
        form_data = {
            "code": "algebra",
            "name": "Алгебра обновлённая",
            "description": "d",
            # configs field list: three entries low/medium/high
            "configs-0-level": "low",
            "configs-0-task_count_threshold": "10",
            "configs-0-reference_time": "900",
            "configs-0-penalty_weights": "0.7, 0.4",
            "configs-1-level": "medium",
            "configs-1-task_count_threshold": "10",
            "configs-1-reference_time": "900",
            "configs-1-penalty_weights": "0.7, 0.4",
            "configs-2-level": "high",
            "configs-2-task_count_threshold": "10",
            "configs-2-reference_time": "900",
            "configs-2-penalty_weights": "0.7, 0.4",
            "submit": "1",
        }
        r2 = client.post(url_for('admin.edit_topic', topic_id=self.topic_id), data=form_data, follow_redirects=True)
        assert r2.status_code == 200
        body = r2.get_data(as_text=True)
        assert "обновлена" in body or "updated" in body.lower()
        # Verify optional 'description' updated when provided
        with app.app_context():
            updated = Topic.query.get(self.topic_id)
            assert updated.name == "Алгебра обновлённая"
            assert (updated.description or "") == "d"

    def test_delete_topic_success(self, client, admin_user, app, login_admin):
        """Test topic deletion"""
        # Create separate topic without tasks
        with app.app_context():
            t = Topic(code="prob", name="Вероятности")
            db.session.add(t)
            db.session.commit()
            t_ok_id = t.id
        
        # Delete topic
        resp = client.post(url_for('admin.delete_topic', topic_id=t_ok_id), data={"submit": "1"}, follow_redirects=True)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "удалена" in body or "deleted" in body.lower()

    def test_export_topics_get_and_post_selection(self, client, admin_user, app, login_admin):
        """Test topic export functionality"""
        # GET all topics export
        r1 = client.get(url_for('admin.export_topics'))
        assert r1.status_code == 200
        assert r1.headers.get("Content-Type") == "application/json; charset=utf-8"
        data_all = json.loads(r1.get_data(as_text=True))
        assert isinstance(data_all, list)
        assert len(data_all) >= 1
        
        # POST selected topics export
        with app.app_context():
            ids = [t.id for t in Topic.query.all()]
        r2 = client.post(
            url_for('admin.export_topics'),
            data=json.dumps({"topic_ids": ids[:1]}),
            content_type="application/json",
        )
        assert r2.status_code == 200
        sel = json.loads(r2.get_data(as_text=True))
        assert len(sel) == 1

    def test_import_topics_validation_and_success(self, client, admin_user, app, login_admin):
        """Test topic import validation and success"""
        # Test wrong file extension
        r_bad_ext = client.post(
            url_for('admin.import_topics'),
            data={"file": (BytesIO(b"[]"), "topics.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r_bad_ext.status_code == 200
        
        # Test correct JSON import
        payload = [
            {
                "code": "trig",
                "name": "Тригонометрия",
                "description": "new",
                "level_configs": {
                    "low": {"task_count_threshold": 5, "reference_time": 600, "penalty_weights": [0.5]},
                    "medium": {"task_count_threshold": 5, "reference_time": 600, "penalty_weights": [0.5]},
                    "high": {"task_count_threshold": 5, "reference_time": 600, "penalty_weights": [0.5]},
                },
            }
        ]
        r_ok = client.post(
            url_for('admin.import_topics'),
            data={"file": (BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")), "topics.json")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert r_ok.status_code == 200
        with app.app_context():
            assert Topic.query.filter_by(code="trig").first() is not None
