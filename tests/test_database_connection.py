import pytest
from app import create_app
from extensions import db
from models import User

def test_database_connection(app):
    """Test that the database connection works"""
    with app.app_context():
        # Create a test user
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            role='student'
        )
        user.set_password('testpass')
        
        # Add to database
        db.session.add(user)
        db.session.commit()
        
        # Query the user
        queried_user = User.query.filter_by(username='testuser').first()
        
        # Verify the user was saved and retrieved
        assert queried_user is not None
        assert queried_user.email == 'test@example.com'
        assert queried_user.check_password('testpass')
        
        # Clean up
        db.session.delete(queried_user)
        db.session.commit()

def test_app_config(app):
    """Test that the app is configured for testing"""
    assert app.config['TESTING'] is True
    assert app.config['WTF_CSRF_ENABLED'] is False
    # Check that the database URI uses SQLite
    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:')
