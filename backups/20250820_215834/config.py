# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    # Build a robust default to instance/math_learning.db using an absolute path
    _base_dir = os.path.abspath(os.path.dirname(__file__))
    _instance_dir = os.path.join(_base_dir, "instance")
    _default_db_path = os.path.join(_instance_dir, "math_learning.db")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        # For absolute paths, sqlite URI should have 4 slashes: sqlite:////<abs_path>
        f"sqlite:////{_default_db_path}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False   # True в проде (HTTPS)
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_HEADERS = ["X-CSRFToken"]  # твой фронт шлёт именно так
