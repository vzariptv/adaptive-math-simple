import pytest
import tempfile
import os
from app import create_app
from extensions import db
from models import User


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file in the system temp directory
    import tempfile
    import os
    
    # Create a temporary directory for the test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    # Absolute path requires four slashes in SQLite URL
    db_uri = f'sqlite:////{db_path}'
    
    # Set environment variable before creating the app
    os.environ['DATABASE_URL'] = db_uri
    
    try:
        # Create the app with test config
        app = create_app()
        
        # Override the database URI
        app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            SECRET_KEY='test-secret-key',
            SERVER_NAME='localhost.localdomain',
            SQLALCHEMY_DATABASE_URI=db_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False
        )
        
        # Safety: ensure we are pointing at the temp DB, not the main DB
        def _assert_uses_temp_db():
            active_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            try:
                # Access engine URL database path safely
                active_db_file = db.engine.url.database if db.engine else ''
            except Exception:
                active_db_file = ''
            # Must contain our temp_dir and match our intended db_path
            if not (str(active_uri).startswith('sqlite:') and temp_dir in str(active_uri)):
                raise RuntimeError(
                    f"Test DB URI mismatch. Expected temp dir {temp_dir}, got URI {active_uri}"
                )
            if active_db_file and temp_dir not in active_db_file:
                raise RuntimeError(
                    f"Test engine DB path mismatch. Expected under {temp_dir}, got {active_db_file}"
                )
        
        # Set up the database and yield the app
        with app.app_context():
            _assert_uses_temp_db()
            db.create_all()
            yield app
            db.session.remove()
            db.session.close()
            _assert_uses_temp_db()
            db.drop_all()
    finally:
        # Clean up the temporary directory and its contents
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            # Clean up environment variable
            if 'DATABASE_URL' in os.environ:
                del os.environ['DATABASE_URL']
        except Exception as e:
            print(f"Error during cleanup: {e}")


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    """Create an admin user for testing."""
    with app.app_context():
        admin = User(
            username='admin',
            email='admin@test.com',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
        db.session.expunge(admin)
        admin.id = admin_id
        return admin


@pytest.fixture
def student_user(app):
    """Create a student user for testing."""
    with app.app_context():
        student = User(
            username='student',
            email='student@test.com',
            first_name='Student',
            last_name='User',
            role='student',
            is_active=True
        )
        student.set_password('student123')
        db.session.add(student)
        db.session.commit()
        student_id = student.id
        db.session.expunge(student)
        student.id = student_id
        return student


@pytest.fixture
def teacher_user(app):
    """Create a teacher user for testing."""
    with app.app_context():
        teacher = User(
            username='teacher',
            email='teacher@test.com',
            first_name='Teacher',
            last_name='User',
            role='teacher',
            is_active=True
        )
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id
        db.session.expunge(teacher)
        teacher.id = teacher_id
        return teacher


@pytest.fixture
def login_admin(client, admin_user):
    """Log in as admin for tests that need authentication."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True


@pytest.fixture
def login_student(client, student_user):
    """Log in as student user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(student_user.id)
        sess['_fresh'] = True


@pytest.fixture
def login_teacher(client, teacher_user):
    """Log in as teacher user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(teacher_user.id)
        sess['_fresh'] = True


