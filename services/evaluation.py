from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from models import TaskAttempt, MathTask, StudentTopicProgress, TopicLevelConfig, EvaluationSystemConfig
import json

# Core, framework-agnostic helpers for evaluation computations.
# These are pure functions so we can unit test them without DB access.


@dataclass(frozen=True)
class LevelConfig:
    task_count_threshold: int
    reference_time: float  # seconds
    penalty_weights: Dict[str, float]  # {"2": 0.7, "3": 0.4}


@dataclass(frozen=True)
class SystemConfig:
    weight_accuracy: float
    weight_time: float
    weight_progress: float
    weight_motivation: float
    engagement_weight_alpha: float
    working_weekdays: Sequence[int] = (0, 1, 2, 3, 4)  # Mon..Fri


@dataclass(frozen=True)
class Attempt:
    task_id: int
    is_correct: bool
    time_spent: Optional[float]  # seconds
    attempt_number: int
    created_at: datetime


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def group_attempts_by_task(attempts: Iterable[Attempt]) -> Dict[int, List[Attempt]]:
    by_task: Dict[int, List[Attempt]] = {}
    for a in attempts:
        by_task.setdefault(a.task_id, []).append(a)
    # sort by attempt_number then created_at for determinism
    for tid in by_task:
        by_task[tid].sort(key=lambda a: (a.attempt_number, a.created_at))
    return by_task


def compute_accuracy(attempts: Iterable[Attempt], penalty_weights: Dict[str, float]) -> Tuple[float, Dict[str, int]]:
    """Per-task accuracy using first successful attempt.
    Mapping: 1st->1.0; 2nd->penalty_weights["2"]; 3rd->penalty_weights["3"]; else 0.0
    Returns (accuracy, breakdown_counts)
    breakdown_counts keys: a1, a2, a3, unsolved
    """
    by_task = group_attempts_by_task(attempts)
    scores: List[float] = []
    a1 = a2 = a3 = unsolved = 0
    for tid, seq in by_task.items():
        first_success = next((a for a in seq if a.is_correct), None)
        if first_success is None:
            scores.append(0.0)
            unsolved += 1
        else:
            n = first_success.attempt_number
            if n <= 1:
                scores.append(1.0)
                a1 += 1
            elif n == 2:
                s = float(penalty_weights.get("2", 0.7))
                scores.append(s)
                a2 += 1
            elif n == 3:
                s = float(penalty_weights.get("3", 0.4))
                scores.append(s)
                a3 += 1
            else:
                # attempts >3 are treated as 0.0 per doc (capped in import flow)
                scores.append(0.0)
                unsolved += 1
    acc = sum(scores) / len(scores) if scores else 0.0
    return acc, {"a1": a1, "a2": a2, "a3": a3, "unsolved": unsolved}


def compute_median_time(attempts: Iterable[Attempt]) -> Optional[float]:
    times = [a.time_spent for a in attempts if a.time_spent is not None and a.time_spent > 0]
    if not times:
        return None
    return float(median(times))


def compute_time_score(median_time: Optional[float], ref_time_level: float) -> float:
    if median_time is None:
        return 0.0
    denom = max(1.0, float(median_time))
    return clamp(ref_time_level / denom, 0.0, 1.0)


def compute_progress(tasks_solved: int, task_count_threshold: int) -> float:
    denom = max(1, int(task_count_threshold))
    return clamp(tasks_solved / denom, 0.0, 1.0)


def load_system_config(db_session) -> SystemConfig:
    """Загружает системную конфигурацию из БД, создаёт при отсутствии.
    Возвращает объект SystemConfig, используемый сервисом оценки.
    """
    cfg = (
        db_session.query(EvaluationSystemConfig)
        .order_by(EvaluationSystemConfig.id.desc())
        .first()
    )
    if not cfg:
        cfg = EvaluationSystemConfig()
        db_session.add(cfg)
        db_session.commit()

    return SystemConfig(
        weight_accuracy=float(cfg.weight_accuracy or 0.3),
        weight_time=float(cfg.weight_time or 0.2),
        weight_progress=float(cfg.weight_progress or 0.3),
        weight_motivation=float(cfg.weight_motivation or 0.2),
        engagement_weight_alpha=float(getattr(cfg, 'engagement_weight_alpha', 0.667) or 0.667),
    )


def count_activity_details(attempts: Iterable[Attempt], working_weekdays: Sequence[int]) -> Tuple[int, int, int, int]:
    """
    Подсчитывает детали активности для новой формулы мотивации
    Returns: (active_working_days, weekend_days, total_attempts, unique_days_total)
    """
    days = {a.created_at.date() for a in attempts}
    active_working_days = sum(1 for d in days if d.weekday() in working_weekdays)
    weekend_days = sum(1 for d in days if d.weekday() not in working_weekdays)
    total_attempts = len(list(attempts))
    unique_days_total = len(days)
    return active_working_days, weekend_days, total_attempts, unique_days_total


def compute_motivation_v3(
    active_working_days: int,
    weekend_days: int,
    attempts_count: int,
    unique_days_count: int,
    engagement_weight_alpha: float,
) -> float:
    """
    Чистая поведенческая модель мотивации с параметризованными весами
    Формула: Motivation = w_cons×Consistency + w_eng×Engagement
    где w_cons = 1/(1+α), w_eng = α/(1+α)
    """
    # Вычисляем веса на основе alpha
    w_consistency = 1.0 / (1.0 + float(engagement_weight_alpha))
    w_engagement = float(engagement_weight_alpha) / (1.0 + float(engagement_weight_alpha))
    # 1. Consistency: регулярность работы
    consistency = min(active_working_days / 5.0, 1.0)
    # 2. Engagement: вовлеченность
    # 2a. Выходная работа
    gamma_weekend = 0.4 if weekend_days > 0 else 0.0
    # 2b. Интенсивность попыток
    if active_working_days > 0:
        gamma_intensity = min(0.4, attempts_count / (active_working_days * 15.0))
    else:
        gamma_intensity = 0.0
    # 2c. Распределение активности
    gamma_distribution = min(0.2, unique_days_count / 7.0)
    engagement = min(1.0, gamma_weekend + gamma_intensity + gamma_distribution)
    # 3. Motivation: мотивация
    return clamp(w_consistency * consistency + w_engagement * engagement, 0.0, 1.0)


def compute_total(
    accuracy: float,
    time_score: float,
    progress_score: float,
    motivation_score: float,
    cfg: SystemConfig,
) -> float:
    return (
        cfg.weight_accuracy * accuracy
        + cfg.weight_time * time_score
        + cfg.weight_progress * progress_score
        + cfg.weight_motivation * motivation_score
    )


def make_level_decision(
    current_level: str,
    total_score: float,
    system_cfg_row: EvaluationSystemConfig,
) -> Tuple[str, str]:
    """
    Принимает решение о переходе между уровнями.
    Returns: (new_level, change_type) where change_type in ['up','down','stay','mastered']
    """
    min_low = float(getattr(system_cfg_row, 'min_threshold_low', 0.3) or 0.3)
    max_low = float(getattr(system_cfg_row, 'max_threshold_low', 0.7) or 0.7)
    min_med = float(getattr(system_cfg_row, 'min_threshold_medium', 0.4) or 0.4)
    max_med = float(getattr(system_cfg_row, 'max_threshold_medium', 0.8) or 0.8)

    lvl = (current_level or 'low').lower()
    if lvl == 'low':
        if total_score < min_low:
            return 'low', 'stay'
        elif total_score >= max_low:
            return 'medium', 'up'
        else:
            return 'low', 'stay'
    elif lvl == 'medium':
        if total_score < min_med:
            return 'low', 'down'
        elif total_score >= max_med:
            return 'high', 'up'
        else:
            return 'medium', 'stay'
    elif lvl == 'high':
        if total_score < min_med:  # используем порог medium для понижения
            return 'medium', 'down'
        elif total_score >= max_med:
            return 'mastered', 'mastered'
        else:
            return 'high', 'stay'
    else:
        return 'mastered', 'stay'


def _working_weekdays_in_period(start: date, end: date, working_weekdays: Sequence[int]) -> int:
    days = 0
    d = start
    one = timedelta(days=1)
    while d <= end:
        if d.weekday() in working_weekdays:
            days += 1
        d += one
    return days


def preview(
    db_session,
    user_ids: Sequence[int],
    topic_ids: Sequence[int],
    period_start: date,
    period_end: date,
) -> List[Dict]:
    """Compute aggregates/metrics per (user, topic) for the current level only, without persisting.
    Returns list of dicts with metrics and aggregates. Decision can be added later.
    """
    results: List[Dict] = []

    # Preload current progress for (user, topic)
    prog_rows = (
        db_session.query(StudentTopicProgress)
        .filter(StudentTopicProgress.user_id.in_(user_ids))
        .filter(StudentTopicProgress.topic_id.in_(topic_ids))
        .all()
    )
    progress_map: Dict[Tuple[int, int], StudentTopicProgress] = {
        (p.user_id, p.topic_id): p for p in prog_rows
    }

    # Preload level configs for requested topics
    level_cfgs: Dict[Tuple[int, str], LevelConfig] = {}
    cfg_rows = (
        db_session.query(TopicLevelConfig)
        .filter(TopicLevelConfig.topic_id.in_(topic_ids))
        .all()
    )
    def _normalize_pw(raw) -> Dict[str, float]:
        """Normalize penalty_weights from various possible storage formats:
        - dict like {"2": 0.7, "3": 0.4}
        - list/tuple like [0.7, 0.4] -> {"2": 0.7, "3": 0.4}
        - JSON string representing a dict or list
        - CSV string like "0.7, 0.4"
        """
        if raw is None:
            return {}
        # already a dict
        if isinstance(raw, dict):
            out: Dict[str, float] = {}
            for k, v in raw.items():
                try:
                    out[str(k)] = float(v)
                except Exception:
                    continue
            return out
        # list/tuple -> map attempt numbers 2,3
        if isinstance(raw, (list, tuple)):
            vals: List[float] = []
            for x in raw:
                try:
                    vals.append(float(x))
                except Exception:
                    vals.append(0.0)
            m: Dict[str, float] = {}
            if len(vals) >= 1:
                m["2"] = vals[0]
            if len(vals) >= 2:
                m["3"] = vals[1]
            return m
        # string: try JSON first
        if isinstance(raw, str):
            s = raw.strip()
            if s:
                try:
                    data = json.loads(s)
                    return _normalize_pw(data)
                except Exception:
                    # fallback: CSV
                    parts = [p.strip() for p in s.split(',') if p.strip()]
                    vals: List[float] = []
                    for p in parts:
                        try:
                            vals.append(float(p))
                        except Exception:
                            vals.append(0.0)
                    m: Dict[str, float] = {}
                    if len(vals) >= 1:
                        m["2"] = vals[0]
                    if len(vals) >= 2:
                        m["3"] = vals[1]
                    return m
        # unknown type
        return {}

    for r in cfg_rows:
        level_cfgs[(r.topic_id, r.level)] = LevelConfig(
            task_count_threshold=r.task_count_threshold,
            reference_time=float(r.reference_time),
            penalty_weights=_normalize_pw(getattr(r, 'penalty_weights', None)),
        )

    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end, datetime.max.time())

    # Load system configuration from DB (or create defaults)
    system_cfg = load_system_config(db_session)
    # Also fetch the row to access threshold fields for decision logic
    eval_cfg_row: Optional[EvaluationSystemConfig] = (
        db_session.query(EvaluationSystemConfig)
        .order_by(EvaluationSystemConfig.id.desc())
        .first()
    )

    for uid in user_ids:
        for tid in topic_ids:
            prog = progress_map.get((uid, tid))
            level_before: Optional[str] = None
            notes: Optional[str] = None
            warning: Optional[str] = None

            if prog:
                level_before = prog.current_level
            else:
                # We'll try to infer level from attempts below
                warning = "no_progress_row"

            # Helper: fetch attempts optionally filtering by level
            def fetch_attempts(level: Optional[str]) -> List[TaskAttempt]:
                q = (
                    db_session.query(TaskAttempt)
                    .join(MathTask, TaskAttempt.task_id == MathTask.id)
                    .filter(TaskAttempt.user_id == uid)
                    .filter(MathTask.topic_id == tid)
                    .filter(TaskAttempt.created_at >= start_dt)
                    .filter(TaskAttempt.created_at <= end_dt)
                )
                if level is not None:
                    q = q.filter(MathTask.level == level)
                return q.all()

            # Try attempts at progress level if we have it
            rows: List[TaskAttempt] = fetch_attempts(level_before) if level_before else []

            # If no attempts at progress level or no progress row, try to infer level by attempts
            if not rows:
                # fetch any attempts in topic/date regardless of level
                all_rows: List[TaskAttempt] = fetch_attempts(None)
                if not all_rows:
                    # Truly no attempts for user/topic in period
                    results.append({
                        "user_id": uid,
                        "topic_id": tid,
                        "level_before": level_before,
                        "warning": warning or "no_attempts",
                    })
                    continue

                # Infer most frequent level among attempts
                level_counts: Dict[str, int] = {}
                for r in all_rows:
                    # r.task is available thanks to relationship; ensure it's loaded
                    lvl = r.task.level if hasattr(r, "task") and r.task is not None else None
                    if lvl:
                        level_counts[lvl] = level_counts.get(lvl, 0) + 1
                inferred_level = None
                if level_counts:
                    inferred_level = max(level_counts.items(), key=lambda kv: kv[1])[0]

                # Use inferred level if progress missing or mismatch produced no rows
                if inferred_level:
                    level_before = level_before or inferred_level
                    rows = [r for r in all_rows if hasattr(r, "task") and r.task and r.task.level == inferred_level]
                    notes = (notes or "") + ("; " if notes else "") + "used_level_inferred"
                else:
                    # Fallback: use all attempts if we cannot infer level (shouldn't happen normally)
                    rows = all_rows
                    notes = (notes or "") + ("; " if notes else "") + "used_all_levels"

            # Obtain level config for the chosen level (may be inferred)
            used_level = level_before or (rows[0].task.level if rows and hasattr(rows[0], "task") and rows[0].task else None)
            lvl_cfg = level_cfgs.get((tid, used_level)) if used_level else None
            if not lvl_cfg:
                # If still no level config, report but continue computing with safe defaults
                warning = (warning or "") + ("; " if warning else "") + "no_level_config"
                lvl_cfg = LevelConfig(task_count_threshold=20, reference_time=300.0, penalty_weights={"2": 0.7, "3": 0.4})

            attempts: List[Attempt] = [
                Attempt(
                    task_id=r.task_id,
                    is_correct=bool(r.is_correct),
                    time_spent=float(r.time_spent) if r.time_spent is not None else None,
                    attempt_number=int(r.attempt_number or 1),
                    created_at=r.created_at,
                )
                for r in rows
            ]

            accuracy, a_breakdown = compute_accuracy(attempts, lvl_cfg.penalty_weights)
            median_t = compute_median_time(attempts)
            time_score = compute_time_score(median_t, lvl_cfg.reference_time)

            # Aggregates
            unique_tasks = {a.task_id for a in attempts}
            tasks_solved = 0
            if attempts:
                by_task = group_attempts_by_task(attempts)
                for seq in by_task.values():
                    if any(a.is_correct for a in seq):
                        tasks_solved += 1

            progress_score = compute_progress(tasks_solved, lvl_cfg.task_count_threshold)
            active_working, weekend_days, attempts_count, unique_days = count_activity_details(attempts, system_cfg.working_weekdays)
            motivation_score = compute_motivation_v3(
                active_working,
                weekend_days,
                attempts_count,
                unique_days,
                system_cfg.engagement_weight_alpha,
            )
            total_score = compute_total(accuracy, time_score, progress_score, motivation_score, system_cfg)
            # Weekday activity (Mon..Sun)
            weekday_counts = [0, 0, 0, 0, 0, 0, 0]
            for a in attempts:
                try:
                    idx = a.created_at.weekday()  # 0..6 (Mon..Sun)
                    if 0 <= idx <= 6:
                        weekday_counts[idx] += 1
                except Exception:
                    continue
            # Solved tasks by weekday (first successful attempt date)
            solved_counts = [0, 0, 0, 0, 0, 0, 0]
            try:
                by_task = group_attempts_by_task(attempts)
                for seq in by_task.values():
                    first_success = next((x for x in seq if x.is_correct), None)
                    if first_success is not None:
                        di = first_success.created_at.weekday()
                        if 0 <= di <= 6:
                            solved_counts[di] += 1
            except Exception:
                pass
            # Decision
            level_after, level_change = (used_level, 'stay')
            if eval_cfg_row is not None and used_level is not None:
                level_after, level_change = make_level_decision(used_level, total_score, eval_cfg_row)

            results.append({
                "user_id": uid,
                "topic_id": tid,
                "level_before": used_level,
                "level_after": level_after,
                "level_change": level_change,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "tasks_total": lvl_cfg.task_count_threshold,
                "tasks_solved": tasks_solved,
                "attempts_total": len(attempts),
                "a1": a_breakdown.get("a1", 0),
                "a2": a_breakdown.get("a2", 0),
                "a3": a_breakdown.get("a3", 0),
                "accuracy": accuracy,
                "avg_time": median_t,
                "time_score": time_score,
                "progress_score": progress_score,
                "motivation_score": motivation_score,
                "total_score": total_score,
                "active_working_days": active_working,
                "weekend_days": weekend_days,
                "activity_by_weekday": weekday_counts,
                "solved_by_weekday": solved_counts,
                "notes": notes,
                "warning": warning,
            })

    return results
