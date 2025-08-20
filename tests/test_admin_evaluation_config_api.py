import json
import pytest
from flask import url_for

from extensions import db
from models import User, EvaluationSystemConfig


class TestAdminEvaluationConfigApi:
    """Test admin evaluation config API endpoints"""

    def test_requires_login(self, client):
        """Test that evaluation config API requires login"""
        resp = client.get(url_for('admin.api_evaluation_config'))
        assert resp.status_code in (302, 401, 403)

    def test_forbidden_for_non_admin(self, client, teacher_user, login_teacher):
        """Test that evaluation config API is forbidden for non-admin users"""
        resp = client.get(url_for('admin.api_evaluation_config'))
        assert resp.status_code == 403

    def test_get_defaults_ok(self, client, admin_user, login_admin):
        """Test getting default evaluation config values"""
        resp = client.get(url_for('admin.api_evaluation_config'))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        payload = data.get("data") or {}
        # At least keys should be present
        for key in (
            "evaluation_period_days",
            "engagement_weight_alpha",
            "weight_accuracy",
            "weight_time",
            "weight_progress",
            "weight_motivation",
            "min_threshold_low",
            "max_threshold_low",
            "min_threshold_medium",
            "max_threshold_medium",
        ):
            assert key in payload

    def test_post_update_and_persist(self, client, admin_user, app, login_admin):
        """Test updating and persisting evaluation config"""
        body = {
            "evaluation_period_days": 14,
            "engagement_weight_alpha": 0.75,
            "weight_accuracy": 0.4,
            "weight_time": 0.1,
            "weight_progress": 0.3,
            "weight_motivation": 0.2,
            "min_threshold_low": 0.25,
            "max_threshold_low": 0.65,
            "min_threshold_medium": 0.45,
            "max_threshold_medium": 0.85,
        }
        resp = client.post(
            url_for('admin.api_evaluation_config'),
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        saved = data.get("data") or {}
        assert saved.get("evaluation_period_days") == 14
        assert abs(saved.get("engagement_weight_alpha") - 0.75) < 0.001
        assert abs(saved.get("weight_accuracy") - 0.4) < 0.001
        assert abs(saved.get("weight_time") - 0.1) < 0.001
        assert abs(saved.get("weight_progress") - 0.3) < 0.001
        assert abs(saved.get("weight_motivation") - 0.2) < 0.001
        assert abs(saved.get("min_threshold_low") - 0.25) < 0.001
        assert abs(saved.get("max_threshold_low") - 0.65) < 0.001
        assert abs(saved.get("min_threshold_medium") - 0.45) < 0.001
        assert abs(saved.get("max_threshold_medium") - 0.85) < 0.001

        # GET again should return the same latest values
        resp2 = client.get(url_for('admin.api_evaluation_config'))
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2.get("ok") is True
        saved2 = data2.get("data") or {}
        assert saved2.get("evaluation_period_days") == 14
        assert abs(saved2.get("engagement_weight_alpha") - 0.75) < 0.001

        # Check DB directly
        with app.app_context():
            row = EvaluationSystemConfig.query.order_by(EvaluationSystemConfig.id.desc()).first()
            assert row is not None
            assert row.evaluation_period_days == 14

    def test_post_clamps_and_swaps_thresholds(self, client, admin_user, login_admin):
        """Test that config values are clamped and thresholds are swapped when needed"""
        body = {
            # Out-of-range values should be clamped to [0,1]
            "engagement_weight_alpha": 1.5,
            "weight_accuracy": -0.2,
            "weight_time": 2,
            # medium thresholds intentionally reversed (min > max) to check swap
            "min_threshold_medium": 0.9,
            "max_threshold_medium": 0.3,
            # low thresholds normal
            "min_threshold_low": 0.1,
            "max_threshold_low": 0.2,
        }
        resp = client.post(
            url_for('admin.api_evaluation_config'),
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        saved = data.get("data") or {}
        # clamps
        assert saved.get("engagement_weight_alpha") >= 0.0
        assert saved.get("engagement_weight_alpha") <= 1.0
        assert saved.get("weight_accuracy") >= 0.0
        assert saved.get("weight_accuracy") <= 1.0
        assert saved.get("weight_time") >= 0.0
        assert saved.get("weight_time") <= 1.0
        # swap for medium band
        assert saved.get("min_threshold_medium") <= saved.get("max_threshold_medium")
        # specific expected after clamp+swap
        assert abs(saved.get("min_threshold_medium") - 0.3) < 0.001
        assert abs(saved.get("max_threshold_medium") - 0.9) < 0.001
