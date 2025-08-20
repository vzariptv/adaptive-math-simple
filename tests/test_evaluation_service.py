import unittest
from datetime import datetime, timedelta

from services.evaluation import (
    Attempt,
    SystemConfig,
    compute_accuracy,
    compute_median_time,
    compute_time_score,
    compute_progress,
    count_activity_details,
    compute_motivation_v3,
    compute_total,
)


class TestEvaluationService(unittest.TestCase):
    def setUp(self):
        base = datetime(2025, 1, 6, 12, 0, 0)  # Monday
        # Build attempts across 3 tasks at the same level
        # Task 1: solved on 1st attempt
        self.attempts = [
            Attempt(task_id=1, is_correct=True, time_spent=120, attempt_number=1, created_at=base),
        ]
        # Task 2: solved on 2nd attempt
        self.attempts += [
            Attempt(task_id=2, is_correct=False, time_spent=200, attempt_number=1, created_at=base + timedelta(days=1)),
            Attempt(task_id=2, is_correct=True, time_spent=180, attempt_number=2, created_at=base + timedelta(days=1, minutes=5)),
        ]
        # Task 3: not solved within 3 attempts
        self.attempts += [
            Attempt(task_id=3, is_correct=False, time_spent=300, attempt_number=1, created_at=base + timedelta(days=2)),
            Attempt(task_id=3, is_correct=False, time_spent=320, attempt_number=2, created_at=base + timedelta(days=2, minutes=10)),
            Attempt(task_id=3, is_correct=False, time_spent=280, attempt_number=3, created_at=base + timedelta(days=3)),
        ]

        self.penalties = {"2": 0.7, "3": 0.4}
        self.cfg = SystemConfig(
            weight_accuracy=0.5,
            weight_time=0.2,
            weight_progress=0.2,
            weight_motivation=0.1,
            engagement_weight_alpha=2.0/3.0,
            working_weekdays=(0, 1, 2, 3, 4),
        )

    def test_accuracy_per_task(self):
        acc, breakdown = compute_accuracy(self.attempts, self.penalties)
        # Expect 3 tasks: [1.0, 0.7, 0.0] => mean = 0.566666...
        self.assertAlmostEqual(acc, (1.0 + 0.7 + 0.0) / 3, places=6)
        self.assertEqual(breakdown["a1"], 1)
        self.assertEqual(breakdown["a2"], 1)
        self.assertEqual(breakdown["a3"], 0)
        self.assertEqual(breakdown["unsolved"], 1)

    def test_time_median_and_score(self):
        m = compute_median_time(self.attempts)
        # times: [120,200,180,300,320,280] => sorted [120,180,200,280,300,320], median mean of middle two (200,280) => 240
        self.assertAlmostEqual(m, 240.0, places=6)
        # ref time level 300s => score = min(1, 300/240)=1.25->clamped to 1.0
        s = compute_time_score(median_time=m, ref_time_level=300.0)
        self.assertAlmostEqual(s, 1.0, places=6)

    def test_progress(self):
        # tasks_solved = 2 (task 1 and 2)
        p = compute_progress(tasks_solved=2, task_count_threshold=5)
        self.assertAlmostEqual(p, 0.4, places=6)

    def test_motivation_v3(self):
        # active days: base (Mon), Tue, Wed, Thu => 4 distinct days; no weekend
        aw, wd, attempts_count, unique_days = count_activity_details(self.attempts, self.cfg.working_weekdays)
        self.assertEqual(aw, 4)
        self.assertEqual(wd, 0)
        self.assertEqual(attempts_count, 6)
        self.assertEqual(unique_days, 4)
        mot = compute_motivation_v3(
            active_working_days=aw,
            weekend_days=wd,
            attempts_count=attempts_count,
            unique_days_count=unique_days,
            engagement_weight_alpha=self.cfg.engagement_weight_alpha,
        )
        # With alpha=2/3, expected ~0.6
        self.assertAlmostEqual(mot, 0.6, places=6)

    def test_total(self):
        acc, _ = compute_accuracy(self.attempts, self.penalties)
        m = compute_median_time(self.attempts)
        time_score = compute_time_score(m, 300.0)
        progress = compute_progress(2, 5)
        # motivation as above 0.8
        mot = 0.8
        total = compute_total(acc, time_score, progress, mot, self.cfg)
        expected = 0.5 * acc + 0.2 * time_score + 0.2 * progress + 0.1 * mot
        self.assertAlmostEqual(total, expected, places=6)


if __name__ == "__main__":
    unittest.main()
