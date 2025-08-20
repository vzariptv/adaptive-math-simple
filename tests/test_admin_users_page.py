import pytest
import json
from io import BytesIO
from flask import url_for
from werkzeug.security import check_password_hash

from models import User, TaskAttempt, MathTask, Topic
from extensions import db


class TestAdminUsersPage:
    """Test suite for admin users management page"""

    @pytest.fixture(autouse=True)
    def setup_users(self, app):
        """Setup test users for each test"""
        print(f"\nUsing database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        with app.app_context():
            # Create test users
            self.student1 = User(
                username="student1",
                email="student1@test.com",
                first_name="John",
                last_name="Doe",
                role="student"
            )
            self.student1.set_password("password123")
            
            self.student2 = User(
                username="student2", 
                email="student2@test.com",
                first_name="Jane",
                last_name="Smith",
                role="student"
            )
            self.student2.set_password("password456")
            
            self.teacher1 = User(
                username="teacher1",
                email="teacher1@test.com",
                first_name="Bob",
                last_name="Wilson",
                role="teacher"
            )
            self.teacher1.set_password("teachpass")
            
            db.session.add_all([self.student1, self.student2, self.teacher1])
            db.session.commit()
            
            # Store IDs to avoid detached instance errors
            self.student1_id = self.student1.id
            self.student2_id = self.student2.id
            self.teacher1_id = self.teacher1.id

    def _get_csrf_token(self, client, url):
        """Helper to get CSRF token from a form page"""
        return 'test_csrf_token'  # Simplified for testing

    def test_users_list_page_access_admin(self, client, admin_user, login_admin):
        """Test that admin can access users list page"""
        resp = client.get(url_for('admin.users'))
        assert resp.status_code == 200
        assert b'users' in resp.data or "пользователи".encode('utf-8') in resp.data

    def test_users_list_page_access_non_admin(self, client, teacher_user, login_teacher):
        """Test that non-admin users get 403 when accessing users page"""
        resp = client.get(url_for('admin.users'))
        assert resp.status_code == 403

    def test_users_list_page_unauthenticated(self, client):
        """Test that unauthenticated users are redirected"""
        resp = client.get(url_for('admin.users'))
        assert resp.status_code in (302, 401) # Redirect to login

    def test_create_user_get(self, client, admin_user, login_admin):
        """Test GET request to create user page"""
        response = client.get(url_for('admin.create_user'))
        assert response.status_code == 200
        assert b'form' in response.data
        assert b'username' in response.data
        assert b'email' in response.data

    def test_create_user_post_valid(self, client, admin_user, login_admin):
        """Test creating a new user with valid data"""
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'role': 'student',
            'password': 'newpassword123',
            'csrf_token': self._get_csrf_token(client, url_for('admin.create_user'))
        }
        
        response = client.post(url_for('admin.create_user'), data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'created' in response.data or 'создан'.encode('utf-8') in response.data
        
        # Verify user was created in database
        new_user = User.query.filter_by(username='newuser').first()
        assert new_user is not None
        assert new_user.email == 'newuser@test.com'
        assert new_user.role == 'student'
        assert check_password_hash(new_user.password_hash, 'newpassword123')

    def test_create_user_post_duplicate_username(self, client, admin_user, login_admin):
        """Test creating user with duplicate username fails"""
        data = {
            'username': 'student1',  # Already exists
            'email': 'different@test.com',
            'first_name': 'Different',
            'last_name': 'User',
            'role': 'student',
            'password': 'password123',
            'csrf_token': self._get_csrf_token(client, url_for('admin.create_user'))
        }
        
        response = client.post(url_for('admin.create_user'), data=data)
        assert response.status_code == 200  # Form redisplayed with errors
        # WTForms validator message from CreateUserForm.validate_username
        assert 'Логин уже занят'.encode('utf-8') in response.data

    def test_create_user_post_duplicate_email(self, client, admin_user, login_admin):
        """Test creating user with duplicate email fails"""
        data = {
            'username': 'differentuser',
            'email': 'student1@test.com',  # Already exists
            'first_name': 'Different',
            'last_name': 'User',
            'role': 'student',
            'password': 'password123',
            'csrf_token': self._get_csrf_token(client, url_for('admin.create_user'))
        }
        
        response = client.post(url_for('admin.create_user'), data=data)
        assert response.status_code == 200  # Form redisplayed with errors
        # WTForms validator message from CreateUserForm.validate_email
        assert 'Email уже используется'.encode('utf-8') in response.data

    def test_edit_user_get(self, client, admin_user, login_admin, app):
        """Test GET request to edit user page"""
        with app.app_context():
            student = User.query.get(self.student1_id)
            response = client.get(url_for('admin.edit_user', user_id=student.id))
            assert response.status_code == 200
            assert student.username.encode() in response.data
            assert student.email.encode() in response.data

    def test_edit_user_post_valid(self, client, admin_user, login_admin, app):
        """Test editing user with valid data"""
        with app.app_context():
            student = User.query.get(self.student1_id)
            data = {
                'username': 'student1_updated',
                'email': 'student1_updated@test.com',
                'first_name': 'John_Updated',
                'last_name': 'Doe_Updated',
                'role': 'teacher',
                'csrf_token': self._get_csrf_token(client, url_for('admin.edit_user', user_id=student.id))
            }
        
            response = client.post(url_for('admin.edit_user', user_id=student.id), data=data, follow_redirects=True)
            assert response.status_code == 200
            assert b'updated' in response.data or 'обновлён'.encode('utf-8') in response.data
            
            # Verify user was updated
            updated_user = User.query.get(self.student1_id)
            assert updated_user.username == 'student1_updated'
            assert updated_user.email == 'student1_updated@test.com'
            assert updated_user.first_name == 'John_Updated'
            assert updated_user.last_name == 'Doe_Updated'
            assert updated_user.role == 'teacher'

    def test_edit_user_change_password(self, client, admin_user, login_admin, app):
        """Test changing user password"""
        with app.app_context():
            student = User.query.get(self.student1_id)
            data = {
                'username': student.username,
                'email': student.email,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'role': student.role,
                'new_password': 'newpassword456',
                'csrf_token': self._get_csrf_token(client, url_for('admin.edit_user', user_id=student.id))
            }
        
            response = client.post(url_for('admin.edit_user', user_id=student.id), 
                             data=data, follow_redirects=True)
            assert response.status_code == 200
        
            # Verify password was changed
            updated_user = User.query.get(self.student1_id)
            assert check_password_hash(updated_user.password_hash, 'newpassword456')

    def test_edit_user_nonexistent(self, client, admin_user, login_admin):
        """Test editing non-existent user returns 404"""
        response = client.get(url_for('admin.edit_user', user_id=99999))
        assert response.status_code == 404

    def test_delete_user_valid(self, client, admin_user, login_admin, app):
        """Test deleting user without attempts"""
        with app.app_context():
            student = User.query.get(self.student1_id)
            data = {
                'csrf_token': self._get_csrf_token(client, url_for('admin.users')),
                'delete_attempts': '0'
            }
            
            response = client.post(url_for('admin.delete_user', user_id=student.id), 
                                 data=data, follow_redirects=True)
        assert response.status_code == 200
        
        # Verify user was deleted
        deleted_user = User.query.get(self.student1.id)
        assert deleted_user is None

    def test_delete_user_with_attempts_no_cascade(self, client, admin_user, login_admin, app):
        """Test deleting user with attempts fails without cascade option"""
        with app.app_context():
            # Create a topic and task for attempts
            topic = Topic(code="TEST", name="Test Topic")
            db.session.add(topic)
            db.session.flush()
            
            task = MathTask(
                title="Test Task",
                description="A test math task",
                topic_id=topic.id,
                level="low",
                answer_type="number",
                correct_answer="42",
                created_by=admin_user.id
            )
            db.session.add(task)
            db.session.flush()
            
            # Create attempt for student1
            student = User.query.get(self.student1_id)
            attempt = TaskAttempt(
                user_id=student.id,
                task_id=task.id,
                is_correct=True,
                attempt_number=1
            )
            db.session.add(attempt)
            db.session.commit()
        
        data = {
            'csrf_token': self._get_csrf_token(client, url_for('admin.users')),
            'delete_attempts': '0'  # Don't delete attempts
        }
        
        with app.app_context():
            student = User.query.get(self.student1_id)
            response = client.post(url_for('admin.delete_user', user_id=student.id), 
                                 data=data, follow_redirects=True)
            assert response.status_code == 200
            # Expect warning flash about existing attempts
            assert 'попытки'.encode('utf-8') in response.data
                
            # Verify user was NOT deleted due to foreign key constraint
            user_still_exists = User.query.get(self.student1_id)
            assert user_still_exists is not None

    def test_delete_user_with_attempts_cascade(self, client, admin_user, login_admin, app):
        """Test deleting user with attempts succeeds with cascade option"""
        with app.app_context():
            # Create a topic and task for attempts
            topic = Topic(code="TEST2", name="Test Topic 2")
            db.session.add(topic)
            db.session.flush()
            
            task = MathTask(
                title="Test Task 2",
                description="A test math task for cascade deletion",
                topic_id=topic.id,
                level="low",
                answer_type="number",
                correct_answer="42",
                created_by=admin_user.id
            )
            db.session.add(task)
            db.session.flush()
            
            # Create attempt for student2
            student2 = User.query.get(self.student2_id)
            attempt = TaskAttempt(
                user_id=student2.id,
                task_id=task.id,
                is_correct=True,
                attempt_number=1
            )
            db.session.add(attempt)
            db.session.commit()
        
        data = {
            'csrf_token': self._get_csrf_token(client, url_for('admin.users')),
            'delete_attempts': '1'  # Delete attempts too
        }
        
        with app.app_context():
            student2 = User.query.get(self.student2_id)
            response = client.post(url_for('admin.delete_user', user_id=student2.id), 
                                 data=data, follow_redirects=True)
            assert response.status_code == 200
            # Expect success flash about deletion (with attempts)
            assert 'удален'.encode('utf-8') in response.data or 'удалён'.encode('utf-8') in response.data
            
            # Verify user was deleted
            deleted_user = User.query.get(self.student2_id)
            assert deleted_user is None
            
            remaining_attempts = TaskAttempt.query.filter_by(user_id=self.student2_id).count()
            assert remaining_attempts == 0

    def test_delete_self_forbidden(self, client, admin_user, login_admin):
        """Test admin cannot delete their own account"""
        data = {
            'csrf_token': self._get_csrf_token(client, url_for('admin.users')),
            'delete_attempts': '0'
        }
        
        response = client.post(url_for('admin.delete_user', user_id=admin_user.id), 
                             data=data, follow_redirects=True)
        assert response.status_code == 200
        assert b'own' in response.data or 'свою'.encode('utf-8') in response.data
        
        # Verify admin user still exists
        admin_still_exists = User.query.get(admin_user.id)
        assert admin_still_exists is not None

    def test_delete_user_nonexistent(self, client, admin_user, login_admin):
        """Test deleting non-existent user returns 404"""
        data = {
            'csrf_token': self._get_csrf_token(client, url_for('admin.users')),
            'delete_attempts': '0'
        }
        
        response = client.post(url_for('admin.delete_user', user_id=99999), data=data)
        assert response.status_code == 404

    def test_import_users_valid_json(self, client, admin_user, login_admin):
        """Test importing users from valid JSON file"""
        users_data = [
            {
                "username": "imported1",
                "email": "imported1@test.com",
                "first_name": "Imported",
                "last_name": "User1",
                "role": "student"
            },
            {
                "username": "imported2",
                "email": "imported2@test.com",
                "first_name": "Imported",
                "last_name": "User2",
                "role": "teacher"
            }
        ]
        
        file_data = BytesIO(json.dumps(users_data).encode('utf-8'))
        data = {
            'file': (file_data, 'users.json'),
            'csrf_token': self._get_csrf_token(client, url_for('admin.users'))
        }
        
        response = client.post(url_for('admin.import_users'), 
                             data=data, follow_redirects=True)
        assert response.status_code == 200
        # Expect success flash about import
        assert 'Импортировано'.encode('utf-8') in response.data or 'импорт'.encode('utf-8') in response.data
        
        # Verify users were created
        imported1 = User.query.filter_by(username='imported1').first()
        imported2 = User.query.filter_by(username='imported2').first()
        assert imported1 is not None
        assert imported2 is not None
        assert imported1.role == 'student'
        assert imported2.role == 'teacher'

    def test_import_users_invalid_json(self, client, admin_user, login_admin):
        """Test importing invalid JSON file fails"""
        file_data = BytesIO(b'invalid json content')
        data = {
            'file': (file_data, 'invalid.json'),
            'csrf_token': self._get_csrf_token(client, url_for('admin.users'))
        }
        
        response = client.post(url_for('admin.import_users'), 
                             data=data, follow_redirects=True)
        assert response.status_code == 200
        # Expect error flash text
        assert 'Ошибка импорта'.encode('utf-8') in response.data or 'ошибк'.encode('utf-8') in response.data

    def test_import_users_wrong_file_type(self, client, admin_user, login_admin):
        """Test importing non-JSON file fails"""
        file_data = BytesIO(b'some text content')
        data = {
            'file': (file_data, 'users.txt'),
            'csrf_token': self._get_csrf_token(client, url_for('admin.users'))
        }
        
        response = client.post(url_for('admin.import_users'), 
                             data=data, follow_redirects=True)
        assert response.status_code == 200
        assert 'json'.encode('utf-8') in response.data.lower()

    def test_export_users_all(self, client, admin_user, login_admin):
        """Test exporting all users"""
        response = client.get(url_for('admin.export_users'))
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/json; charset=utf-8'
        assert 'attachment' in response.headers['Content-Disposition']
        
        # Parse exported data
        export_data = json.loads(response.data)
        assert isinstance(export_data, list)
        assert len(export_data) >= 4  # admin + 3 test users
        
        # Verify structure
        user_data = export_data[0]
        assert 'id' in user_data
        assert 'username' in user_data
        assert 'email' in user_data
        assert 'password_hash' not in user_data  # Passwords should not be exported

    def test_export_users_selected(self, client, admin_user, login_admin):
        """Test exporting selected users"""
        payload = {
            'user_ids': [self.student1_id, self.student2_id]
        }
        
        response = client.post(url_for('admin.export_users'), 
                             json=payload)
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/json; charset=utf-8'
        
        # Parse exported data
        export_data = json.loads(response.data)
        assert len(export_data) == 2
        
        usernames = [user['username'] for user in export_data]
        assert 'student1' in usernames
        assert 'student2' in usernames

    def test_export_users_selected_empty(self, client, admin_user, login_admin):
        """Test exporting with empty selection fails"""
        payload = {'user_ids': []}
        
        response = client.post(url_for('admin.export_users'), json=payload)
        assert response.status_code == 400
        
        error_data = json.loads(response.data)
        assert error_data['success'] is False

    def test_users_page_shows_attempt_counts(self, client, admin_user, login_admin, app):
        """Test that users page shows attempt counts for each user"""
        with app.app_context():
            # Create topic and task
            topic = Topic(code="COUNT_TEST", name="Count Test Topic")
            db.session.add(topic)
            db.session.flush()
            
            task = MathTask(
                title="Count Test Task",
                description="A test math task",
                topic_id=topic.id,
                level="low",
                answer_type="number",
                correct_answer="42",
                created_by=admin_user.id
            )
            db.session.add(task)
            db.session.flush()
            
            # Create multiple attempts for student1
            for i in range(3):
                attempt = TaskAttempt(
                    user_id=self.student1.id,
                    task_id=task.id,
                    is_correct=i == 2,  # Last attempt is correct
                    attempt_number=i + 1
                )
                db.session.add(attempt)
            
            db.session.commit()
        
        response = client.get(url_for('admin.users'))
        assert response.status_code == 200
        # Should show attempt count somewhere in the response
        assert b'3' in response.data  # The count of attempts

    def test_csrf_protection(self, client, admin_user):
        """Test CSRF protection on POST endpoints"""
        # Skip this test since CSRF is disabled in test config
        pytest.skip("CSRF is disabled in test configuration")

    def _get_csrf_token(self, client, url):
        """Helper method to get CSRF token from a form page"""
        # Since CSRF is disabled in test config, return a dummy token
        return 'test_csrf_token'


class TestAdminUsersPageEdgeCases:
    """Additional edge case tests for admin users page"""

    def test_create_user_with_special_characters(self, client, admin_user, login_admin):
        """Test creating user with special characters in name"""
        data = {
            'username': 'user_with_underscore',
            'email': 'special@test.com',
            'first_name': 'José',
            'last_name': "O'Connor",
            'role': 'student',
            'password': 'password123',
            'csrf_token': 'test_csrf_token'
        }
        
        response = client.post(url_for('admin.create_user'), data=data, follow_redirects=True)
        assert response.status_code == 200
        
        user = User.query.filter_by(username='user_with_underscore').first()
        assert user is not None
        # Now create_user persists first_name/last_name
        assert user.email == 'special@test.com'
        assert user.first_name == 'José'
        assert user.last_name == "O'Connor"

    def test_edit_user_partial_update(self, client, admin_user, login_admin, app):
        """Test editing user with only some fields changed"""
        with app.app_context():
            # Create a test user for this edge case
            test_user = User(
                username="edge_test_user",
                email="edge@test.com",
                first_name="Edge",
                last_name="Test",
                role="student"
            )
            test_user.set_password("password123")
            db.session.add(test_user)
            db.session.commit()
            test_user_id = test_user.id
            
            data = {
                'username': test_user.username,
                'email': test_user.email,
                'first_name': 'UpdatedFirstName',  # Only change first name
                'last_name': test_user.last_name,
                'role': test_user.role,
                'csrf_token': 'test_csrf_token'
            }
            
            response = client.post(url_for('admin.edit_user', user_id=test_user_id), 
                                 data=data, follow_redirects=True)
            assert response.status_code == 200
            
            updated_user = User.query.get(test_user_id)
            assert updated_user.first_name == 'UpdatedFirstName'
            assert updated_user.email == test_user.email  # Should remain unchanged

    def test_large_user_list_performance(self, client, admin_user, login_admin, app):
        """Test users page performance with many users"""
        with app.app_context():
            # Create many users
            users = []
            for i in range(50):
                user = User(
                    username=f'bulk_user_{i}',
                    email=f'bulk{i}@test.com',
                    role='student'
                )
                user.set_password('password')
                users.append(user)
            
            db.session.add_all(users)
            db.session.commit()
        
        # Page should still load reasonably fast
        response = client.get(url_for('admin.users'))
        assert response.status_code == 200
        assert b'bulk_user_0' in response.data
        assert b'bulk_user_49' in response.data
