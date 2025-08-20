#!/usr/bin/env python3
"""
Seed Week 2 scenario from docs/article_1.tex for one student/topic.
- 20 tasks on Medium level
- attempts total = 51
- solved tasks: a1=0, a2=9, a3=7, unsolved=4 (so 16 solved, 4 unsolved)
- distribute over Mon..Fri of given week_start (YYYY-MM-DD, Monday recommended)
- time_spent around 314s

Usage examples:
  venv/bin/python scripts/seed_article_week2_petr.py \
      --username petr_zaletniy \
      --topic-name "Квадратные уравнения" \
      --week-start 2025-08-18 \
      --clear-existing

You can also use --user-id and --topic-id instead of names.
"""
import argparse
import random
from datetime import datetime, date, timedelta

from flask import Flask
from app import app as flask_app  # use existing Flask app
from extensions import db
from models import User, Topic, MathTask, TaskAttempt, TopicLevelConfig, StudentTopicProgress


def pick_user(user_id: int, username: str) -> User:
    q = User.query
    if user_id:
        u = q.get(user_id)
        if not u:
            raise SystemExit(f"User id={user_id} not found")
        return u
    if username:
        u = q.filter_by(username=username).first()
        if not u:
            raise SystemExit(f"User username='{username}' not found")
        return u
    raise SystemExit("Specify --user-id or --username")


def pick_topic(topic_id: int, topic_name: str) -> Topic:
    q = Topic.query
    if topic_id:
        t = q.get(topic_id)
        if not t:
            raise SystemExit(f"Topic id={topic_id} not found")
        return t
    if topic_name:
        t = q.filter_by(name=topic_name).first()
        if not t:
            raise SystemExit(f"Topic name='{topic_name}' not found")
        return t
    raise SystemExit("Specify --topic-id or --topic-name")


def ensure_level_config(topic: Topic, level: str = "medium") -> TopicLevelConfig:
    cfg = TopicLevelConfig.query.filter_by(topic_id=topic.id, level=level).first()
    if cfg:
        return cfg
    cfg = TopicLevelConfig(
        topic_id=topic.id,
        level=level,
        task_count_threshold=20,
        reference_time=300,
        penalty_weights={"2": 0.7, "3": 0.4},
    )
    db.session.add(cfg)
    db.session.commit()
    return cfg


def ensure_progress(user: User, topic: Topic, level: str = "medium") -> StudentTopicProgress:
    prog = StudentTopicProgress.query.filter_by(user_id=user.id, topic_id=topic.id).first()
    if not prog:
        prog = StudentTopicProgress(user_id=user.id, topic_id=topic.id, current_level=level, is_mastered=False)
        db.session.add(prog)
    else:
        prog.current_level = level
    db.session.commit()
    return prog


def ensure_tasks(topic: Topic, level: str = "medium", need: int = 20):
    tasks = MathTask.query.filter_by(topic_id=topic.id, level=level).order_by(MathTask.id.asc()).all()
    if len(tasks) >= need:
        return tasks[:need]
    # create additional synthetic tasks
    created = []
    for i in range(len(tasks) + 1, need + 1):
        t = MathTask(
            title=f"Synthetic {topic.name} {level} #{i}",
            code=f"syn-{topic.id}-{level}-{i}",
            description="Synthetic task for seeding",
            answer_type="number",
            correct_answer={"value": 42},
            answer_schema={"fields": [{"name": "value", "type": "number"}]},
            topic_id=topic.id,
            level=level,
            max_score=1.0,
            created_by=1,
        )
        db.session.add(t)
        created.append(t)
    db.session.commit()
    return MathTask.query.filter_by(topic_id=topic.id, level=level).order_by(MathTask.id.asc()).limit(need).all()


def parse_week_start(s: str) -> date:
    d = datetime.strptime(s, "%Y-%m-%d").date()
    return d


def daterange_workweek(start: date):
    # Mon..Fri starting from provided start date
    days = []
    d = start
    for _ in range(7):
        if d.weekday() < 5:  # 0..4 Mon..Fri
            days.append(d)
        d += timedelta(days=1)
    return days[:5]


def clear_existing_attempts(user_id: int, topic_id: int, level: str, start: datetime, end: datetime):
    q = (db.session.query(TaskAttempt)
         .join(MathTask, TaskAttempt.task_id == MathTask.id)
         .filter(TaskAttempt.user_id == user_id)
         .filter(MathTask.topic_id == topic_id)
         .filter(MathTask.level == level)
         .filter(TaskAttempt.created_at >= start)
         .filter(TaskAttempt.created_at <= end))
    cnt = q.count()
    if cnt:
        print(f"Deleting {cnt} existing attempts in range for user={user_id} topic={topic_id} level={level}")
        q.delete(synchronize_session=False)
        db.session.commit()


def seed_attempts(user: User, topic: Topic, week_start: date, level: str = "medium", clear_existing: bool = False):
    ensure_level_config(topic, level)
    ensure_progress(user, topic, level)
    tasks = ensure_tasks(topic, level, need=20)

    # Time window
    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = start_dt + timedelta(days=6, hours=23, minutes=59, seconds=59)

    if clear_existing:
        clear_existing_attempts(user.id, topic.id, level, start_dt, end_dt)

    workdays = daterange_workweek(week_start)

    # We need a1=0, a2=9, a3=7, unsolved=4 and total attempts 51.
    # Distribution across days, roughly even.
    # Build sequences per task: list of (is_correct, attempt_number)
    sequences = []
    # 9 tasks solved on 2nd attempt
    for _ in range(9):
        sequences.append([(False, 1), (True, 2)])
    # 7 tasks solved on 3rd attempt
    for _ in range(7):
        sequences.append([(False, 1), (False, 2), (True, 3)])
    # 4 tasks unsolved with 3 attempts each
    for _ in range(4):
        sequences.append([(False, 1), (False, 2), (False, 3)])

    assert len(sequences) == 20

    # Assign sequences to first 20 tasks
    rnd = random.Random(42)
    rnd.shuffle(sequences)

    created = 0
    for idx, (task, seq) in enumerate(zip(tasks, sequences)):
        # Pick a day for this task's attempts
        day = workdays[idx % len(workdays)]
        # Spread attempts within the day
        base_time = datetime.combine(day, datetime.min.time()).replace(hour=10)
        for step, (is_correct, attempt_number) in enumerate(seq):
            ts = base_time + timedelta(minutes=step * 30)
            ta = TaskAttempt(
                user_id=user.id,
                task_id=task.id,
                user_answer={"value": 42 if is_correct else 0},
                is_correct=is_correct,
                partial_score=1.0 if is_correct else 0.0,
                component_scores=None,
                time_spent=int(rnd.uniform(300, 330)),
                hints_used=0,
                attempt_number=attempt_number,
                created_at=ts,
            )
            db.session.add(ta)
            created += 1
    db.session.commit()
    print(f"Created {created} attempts for user={user.username} topic={topic.name} level={level}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=0)
    parser.add_argument("--username", type=str, default="")
    parser.add_argument("--topic-id", type=int, default=0)
    parser.add_argument("--topic-name", type=str, default="")
    parser.add_argument("--week-start", type=str, required=True, help="YYYY-MM-DD (preferably Monday)")
    parser.add_argument("--level", type=str, default="medium", choices=["low", "medium", "high"], help="level to seed")
    parser.add_argument("--clear-existing", action="store_true")
    args = parser.parse_args()

    with flask_app.app_context():
        user = pick_user(args.user_id, args.username)
        topic = pick_topic(args.topic_id, args.topic_name)
        week_start = parse_week_start(args.week_start)
        seed_attempts(user, topic, week_start, level=args.level, clear_existing=args.clear_existing)
        print("Done.")
