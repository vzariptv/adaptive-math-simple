import json
import pytest
from flask import url_for

from extensions import db
from models import Topic, MathTask, TopicLevelConfig, TaskAttempt


def make_topic_level(app, topic, level='low', penalty_weights=None):
    with app.app_context():
        conf = TopicLevelConfig(
            topic_id=topic.id,
            level=level,
            task_count_threshold=10,
            reference_time=60,
            penalty_weights=penalty_weights or [0.7, 0.4],
        )
        db.session.add(conf)
        db.session.commit()
        conf_id = conf.id
        db.session.expunge(conf)
        conf.id = conf_id
        return conf


def make_task(app, creator_id, topic, level='low', answer_type='number', correct_answer=42, description='desc', explanation='hint'):
    with app.app_context():
        t = MathTask(
            title='Test Task',
            description=description,
            answer_type=answer_type,
            correct_answer=correct_answer,
            answer_schema=None,
            explanation=explanation,
            topic_id=topic.id,
            level=level,
            max_score=1.0,
            created_by=creator_id,
            is_active=True,
        )
        db.session.add(t)
        db.session.commit()
        task_id = t.id
        db.session.expunge(t)
        t.id = task_id
        return t


@pytest.fixture
def topic_low(app, admin_user):
    with app.app_context():
        topic = Topic(code='arithm', name='Арифметика', description='test')
        db.session.add(topic)
        db.session.commit()
        make_topic_level(app, topic, 'low', [0.7, 0.4])
        return topic


def test_tasks_list_shows_link_and_lock(client, app, login_student, admin_user, topic_low):
    # Create two tasks: one blocked (after 3 wrong attempts), one available
    t1 = make_task(app, admin_user.id, topic_low, correct_answer=5)
    t2 = make_task(app, admin_user.id, topic_low, correct_answer=7)

    # Trigger three wrong attempts for t1
    for _ in range(3):
        client.post(f"/student/tasks/{t1.id}", data={"answer": "999"}, follow_redirects=True)

    # List page
    resp = client.get(f"/student/tasks?topic_id={topic_low.id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # t1 should be shown as blocked with lock and disabled button
    assert 'заблокирована' in html
    assert f"/student/tasks/{t2.id}" in html  # available has link


def test_view_and_submit_correct_first_try(client, app, login_student, admin_user, topic_low):
    task = make_task(app, admin_user.id, topic_low, correct_answer=11)

    # GET page renders
    r1 = client.get(f"/student/tasks/{task.id}")
    assert r1.status_code == 200

    # Submit correct on first try
    r2 = client.post(f"/student/tasks/{task.id}", data={"answer": "11"}, follow_redirects=True)
    assert r2.status_code == 200
    html = r2.get_data(as_text=True)
    assert 'Верно!' in html

    # Next task should be None yet (no other tasks), but page still renders success state
    assert 'Следующая задача' not in html


def test_hint_and_blocking_logic(client, app, login_student, admin_user, topic_low):
    # Create two tasks so next task can appear later
    t1 = make_task(app, admin_user.id, topic_low, correct_answer=3)
    t2 = make_task(app, admin_user.id, topic_low, correct_answer=4)

    # First wrong -> no hint yet on initial GET, but after wrong we expect hint
    r_wrong1 = client.post(f"/student/tasks/{t1.id}", data={"answer": "0"}, follow_redirects=True)
    assert r_wrong1.status_code == 200
    html1 = r_wrong1.get_data(as_text=True)
    assert 'Неверно' in html1

    # After first wrong attempt, hint should be visible
    r_get2 = client.get(f"/student/tasks/{t1.id}")
    html2 = r_get2.get_data(as_text=True)
    assert 'Подсказка' in html2  # explanation shown

    # Make two more wrong attempts to block
    client.post(f"/student/tasks/{t1.id}", data={"answer": "0"}, follow_redirects=True)
    client.post(f"/student/tasks/{t1.id}", data={"answer": "0"}, follow_redirects=True)

    # Now GET should redirect back to list due to blocking
    r_block = client.get(f"/student/tasks/{t1.id}", follow_redirects=True)
    assert r_block.status_code == 200
    assert 'Задача заблокирована' in r_block.get_data(as_text=True)

    # Solve t2 to check next task logic (no blocked/solved candidates available -> no next button)
    r_ok = client.post(f"/student/tasks/{t2.id}", data={"answer": "4"}, follow_redirects=True)
    assert r_ok.status_code == 200
    html_ok = r_ok.get_data(as_text=True)
    assert 'Верно!' in html_ok
    # No other available same-topic, same-level tasks -> next not shown
    assert 'Следующая задача' not in html_ok
