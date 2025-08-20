# Admin Evaluation Page and Adaptive Scoring – Design Doc

Last updated: 2025-08-19

## Scope

- Admin page to evaluate student attempts per topic/level for a period.
- Implement metric computation (accuracy, time, progress, motivation), final score, and level decision, aligned with the article in `docs/article_1.pdf` and `docs/article_1.tex`.
- Persist results to logs and update current topic progress.

## Current State (Repo)

- Models present in `models.py`:
  - `TaskAttempt` with indices `ix_attempts_user_created` and `ix_attempts_task_created` (OK for 7-day windows).
  - `MathTask` has `code` (external code), `topic_id`, `level`, `max_score` (OK for imports and joins).
  - `TopicLevelConfig` with `task_count_threshold`, `reference_time`, `penalty_weights` (OK).
  - `StudentEvaluationLog` exists with: `user_id`, `topic_id`, `level`, `period_start`, `period_end`, metrics, `total_score`, `level_change` (basic log only).
  - `StudentTopicProgress` tracks `current_level`, `is_mastered`, `last_evaluated_at`.
  - `EvaluationSystemConfig` has: `evaluation_period_days`, weights for metrics, thresholds for level transitions, `weekend_bonus_multiplier` (OK).
- Admin attempts UI/routes/templates exist. No dedicated evaluation UI/routes yet.
- Imports already resolve attempts from `task_code` and `username` in `blueprints/admin/routes.py` (OK).

## External Proposal – Alignment and Conflicts

**Status after alignment (decisions locked):**
- **Attempts indices**: ALIGNED (already present: `ix_attempts_user_created`, `ix_attempts_task_created`).
- **Thick log approach**: ADOPTED. `StudentEvaluationLog` will store aggregates, metrics, level decision, and `calc_trace`.
- **Add `StudentEvaluationRun`**: ADOPTED (header of each batch evaluation).
- **Attempt limit**: ADOPTED as a code-level constant `3` (weights imply effective penalties; excess attempts are capped/ignored in import and flagged in import report).
- **System config**:
  - Keep `EvaluationSystemConfig` as the single source of truth for thresholds and weights.
  - Add `working_weekdays` (JSON), default `[0,1,2,3,4]`.
  - Keep `weekend_bonus_multiplier` (multiplicative model; no additive bonus).
- **Per-topic overrides**: NOT IN MVP. Use global thresholds from EvaluationSystemConfig only.
- **Import flow**: ALIGNED (`MathTask.code` is used to resolve `task_id`).

**Resolved mismatches**
- **Accuracy is per-task, not per-attempt**: use first successful attempt with `penalty_weights`; attempts are not averaged directly.
- **Mastery on High**: add a rule to transition to `mastered` when High exceeds configured max threshold (and/or meets mastery guardrails).
- **TimeScore reference**: use `MathTask.benchmark_time_sec` override when present; else `TopicLevelConfig.reference_time`. Median of all attempt times (incl. unsuccessful) is used.
- **Motivation**: multiplicative weekend model — `consistency * weekend_bonus_multiplier` (if any weekend activity), clamped to `[0,1]`.
- **Progress**: denominator is `TopicLevelConfig.task_count_threshold` for the current level; only tasks of the student’s current level in the period are counted.
- **Thresholds**: use only values from `EvaluationSystemConfig.thresholds`; examples in docs must not hardcode other numbers.

## Data Model Changes (Migrations)

1) **New table `StudentEvaluationRun`** (header of a batch evaluation)
- Columns: `id` (PK), `triggered_by` (FK→`users.id`, nullable), `period_start` (date), `period_end` (date), `created_at` (datetime, default now)
- Index: `ix_eval_run_created_at (created_at)`

2) **Extend `StudentEvaluationLog`** (thick log that replaces weekly aggregate table)
- New columns:
  - `evaluation_run_id` (FK→`student_evaluation_runs.id`)
  - `level_before` (str), `level_after` (str; allow `low|medium|high|mastered`), `level_change` (`up|down|stay|mastered`)
  - Aggregates (period):
    - `tasks_total` (int; equals configured `task_count_threshold` for the level)
    - `tasks_solved` (int; unique tasks solved in period at this level)
    - `attempts_total` (int; all attempts in period at this level)
    - `a1`,`a2`,`a3` (int; solved on 1st/2nd/3rd attempt)
    - `avg_time` (float; median or mean seconds across all attempts — we use median in service)
    - `active_days` (int; working days with attempts), `weekend_days` (int)
  - Metrics and total: `accuracy`, `time_score`, `progress_score`, `motivation_score`, `total_score`
  - `calc_trace` (JSON; full input parameters and guards)
  - `decided_at` (datetime)
- Constraints/indices:
  - `UNIQUE (evaluation_run_id, user_id, topic_id)`
  - `ix_eval_log_user_topic_decided (user_id, topic_id, decided_at)`
  - Optional: index on `(user_id, topic_id, period_start, period_end)` if those dates are stored redundantly for convenience

3) **Optional (future)**
- `EvaluationSystemConfig.working_weekdays` (JSON, default `[0,1,2,3,4]`), if not already present
- `TopicLevelConfig.threshold_min`, `threshold_max` (float) for per-topic overrides. NOT IN MVP.

*Note:* Attempts indices already exist; no changes required there.

## Evaluation Service (`services/evaluation.py`)

**Responsibilities**
- Fetch `TaskAttempt` for each (user, topic) within `[period_start, period_end]`, joining `MathTask` to constrain by `topic_id` and by the student’s **current level** for the period.
- Compute per-topic **aggregates** and **metrics** for that level only.
- Compute `total_score` and level decision using `EvaluationSystemConfig` only (no per-topic overrides in MVP).
- Entry points:
  - `preview(user_ids, topic_ids, period, options)` → list of result dicts (not persisted)
  - `run(user_ids, topic_ids, period, options, triggered_by)` → creates `StudentEvaluationRun` and `StudentEvaluationLog` rows; updates `StudentTopicProgress`.

**Metric definitions (final)**
- **Accuracy (0..1; per-task):**
  - For each unique task in the period at the target level, find the **first successful attempt** and map it to a score using `TopicLevelConfig.penalty_weights`:
    - 1st attempt → `1.0`
    - 2nd attempt → `penalty_weights["2"]`
    - 3rd attempt → `penalty_weights["3"]`
    - not solved → `0.0`
  - `accuracy = mean(task_scores)` across unique tasks in the period (size ≤ task_count_threshold). This is an arithmetic mean over tasks, not over attempts.
  - If `partial_score` is present on attempts, you may cross-check, but accuracy aggregation remains **per-task**, not per-attempt.

- **Time score (0..1; robust to outliers):**
  - For each task use `ref_time = task.benchmark_time_sec or TopicLevelConfig.reference_time`; compute a single **level reference** as the mean of `ref_time` across tasks in scope (or simply the level reference when overrides absent).
  - Compute `median_time` over **all attempts** in the period at this level (successful and failed). Then
    `time_score = min(1.0, ref_time_level / max(1.0, median_time))`.
  - Record `time_ref_used` and whether any per-task overrides were present in `calc_trace`.

- **Progress (0..1):**
  - `progress = clamp(tasks_solved / max(1, task_count_threshold), 0, 1)` where both numerator and denominator consider **only tasks of the student’s current level** in the period.
  - `tasks_solved` counts unique tasks solved (any number of attempts, but must reach a correct attempt).

- **Motivation (0..1; multiplicative weekend model):**
  - `working_weekdays_in_period` = count of configured working weekdays (default Mon–Fri) that fall within the period.
  - `consistency = active_working_days / max(1, working_weekdays_in_period)`.
  - If there is any weekend activity (`weekend_days > 0`), then `motivation = clamp(consistency * weekend_bonus_multiplier, 0, 1)`; else `motivation = clamp(consistency, 0, 1)`.

- **Final score:**
  - Missing component → treat as `0` for that component; weights remain as configured.
  - `total = w_acc*accuracy + w_time*time_score + w_prog*progress + w_mot*motivation` with weights from `EvaluationSystemConfig`.


**Level decision**
- Read `StudentTopicProgress.current_level` at `period_start` (snapshot) as `level_before`. If the student is already `mastered`, no change is applied.
- Thresholds come **only** from `EvaluationSystemConfig.thresholds[level_before]` (record effective values in `calc_trace.thresholds_used`). No per-topic overrides in MVP.
- Let `total_score` be the computed final score for the period. Apply deterministic tie‑breaking and terminal state rules:
  - **Comparators:** promotion uses `total_score ≥ max`; demotion uses `total_score < min`; otherwise `stay`.
  - **Rounding:** comparisons are done on raw floats; if UI displays rounded values, the decision still uses raw values.
  - **Terminal states:** if `level_before = done|mastered`, then `level_after = mastered` (no further changes).
- Rules per level:
  - `low`:
    - if `total_score ≥ thresholds.low.max` → promote to `medium`;
    - else `stay` (demotion below `low` is not applicable).
  - `medium`:
    - if `total_score ≥ thresholds.medium.max` → promote to `high`;
    - else if `total_score < thresholds.medium.min` → demote to `low`;
    - else `stay`.
  - `high`:
    - if `total_score ≥ thresholds.high.max` → `mastered`;
    - else if `total_score < thresholds.high.min` → demote to `medium` (optional: disable via config flag);
    - else `stay`.
- Persist `level_before`, `level_after`, and `level_change` (`up|down|stay|mastered`).

**Calc trace (`calc_trace` JSON)** — include at least:
```json
{
  "weights": {"accuracy": 0.5, "time": 0.2, "progress": 0.2, "motivation": 0.1},
  "thresholds_used": {"level": "medium", "min": 0.70, "max": 0.85, "source": "system"},
  "penalty_weights": {"2": 0.7, "3": 0.4},
  "time_ref_used": {"level": 300, "overrides": false},
  "a_breakdown": {"a1": 9, "a2": 4, "a3": 3, "unsolved": 4},
  "period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "tz": "UTC"},
  "working_weekdays": [0,1,2,3,4],
  "weekend_bonus_multiplier": 1.1,
  "notes": "…"
}
```

**Guards & edge cases**
- **Period window (7 days)**: `period_start = period_end - 6 days`; `period_end` is inclusive (23:59:59). Use a consistent timezone (UTC recommended) and record it in `calc_trace`.
- **Insufficient data**: if `tasks_solved < task_count_threshold` you may flag the row; level change still allowed unless `allow_insufficient_data_level_change=False` is set.
- **Missing `TopicLevelConfig` for (topic, level)**: surface error in preview; skip on run.
- **Zero/None `time_spent`**: exclude from median; if no valid samples, set `time_score=None` (counts as 0 in total).
- **Outliers**: median already robust; optionally add winsorization toggle.
- **partial_score NULL**: preview auto-computes accuracy from attempts; RUN supports two modes:
  - Strict: require backfill first.
  - Auto-compute: compute on the fly and (optionally) offer a post-run backfill.
- **attempt_number > 3**: cap to 3 in import; record skip in import report.
- **Mixed levels within a week**: not supported; we evaluate only the level `level_before` for the week.

## Admin UI/Routes

Routes under `blueprints/admin/routes.py` (names illustrative):
- `GET /admin/evaluation` – filters + preview page.
- `POST /admin/evaluation/preview` – compute via service; render results (no writes). Shows warnings for missing partials and insufficiency.
- `POST /admin/evaluation/run` – create `StudentEvaluationRun`, persist `StudentEvaluationLog`, update `StudentTopicProgress`. Guard: support two modes for missing `partial_score`: (a) Strict — require backfill first; (b) Auto-compute — compute from attempts on the fly, then optionally prompt to backfill for persistence.
- `POST /admin/evaluation/backfill-partial-scores` – admin maintenance action to populate `TaskAttempt.partial_score` where missing, based on `is_correct`, `attempt_number`, and `TopicLevelConfig.penalty_weights`. Supports dry-run and filtered scope.
- `GET /admin/evaluation/history` – list logs with filters and export (JSON/CSV).

Forms in `blueprints/admin/forms.py`:
- `EvaluationFilterForm`
  - student_ids (multi-select), topic_ids (multi-select)
  - date_from, date_to (default from `evaluation_period_days`)
  - toggles: apply_weekend_bonus (default true), allow_insufficient_data_level_change (default false)
- `BackfillPartialScoresForm`
  - same filters as above (optional scope)
  - dry_run (default true)
- `EvaluationOverrideForm` (optional)
  - level_after override or level_change override
  - reason (text)

Templates under `templates/admin/`:
- `evaluation.html` – filters + preview table + Run button; per-row override controls; includes a "Backfill partial_score" button opening a confirm modal that performs dry-run then apply.
- `evaluation_history.html` – logs table with filters and export.

Client JS `static/js/admin_evaluation.js`:
- Handles preview/run submissions (AJAX), loading states, per-row attempt details accordion.
- Handles backfill dry-run (fetch and display counts/skips) and apply actions with progress and result summary.

### Partial Score Backfill flow

- Admin triggers "Backfill partial_score" from `evaluation.html`.
- Dry-run shows: total attempts scanned, updated count (missing partials), skipped count with reasons (no TopicLevelConfig, invalid penalty weights, etc.).
- Confirm applies updates to `TaskAttempt.partial_score` where NULL.
- After success, preview/run can proceed without the missing partials guard.

## Recommendations Summary

- Adopt the "thick log" model by extending `StudentEvaluationLog` and adding `StudentEvaluationRun`.
- Keep attempts indices as-is (already aligned).
- Add optional `working_weekdays` to `EvaluationSystemConfig`; keep `weekend_bonus_multiplier` and map behavior in service.
- Consider optional per-topic threshold overrides in `TopicLevelConfig` only if needed by pedagogy.
- Implement preview-first workflow, then run/persist, with manual override option.

## Consistency Checklist (pre-dev)
- [ ] Accuracy computed per unique task (first successful attempt + `penalty_weights`), not per attempt.
- [ ] High→Mastered rule implemented with thresholds from `EvaluationSystemConfig`.
- [ ] Thresholds in examples removed; service reads only from `EvaluationSystemConfig.thresholds` and records them in `calc_trace`.
- [ ] TimeScore uses `MathTask.benchmark_time_sec` override when present; otherwise `TopicLevelConfig.reference_time`; median over all attempts.
- [ ] Motivation uses multiplicative weekend model with `working_weekdays` and `weekend_bonus_multiplier`.
- [ ] Progress denominator equals `TopicLevelConfig.task_count_threshold` for the current level; only tasks of that level count.
- [ ] `StudentEvaluationLog` stores aggregates + metrics + decision + `calc_trace`; `StudentEvaluationRun` added.
- [ ] Period window logic (inclusive end, timezone) is clarified.
- [ ] attempt_limit=3 enforced on import and documented.

## Open Questions to Validate Against Article

- Exact formulas for time score and motivation components.
- Hysteresis or minimum-period rules for promotion/demotion and mastery.
- Whether progress must consider diversity/uniqueness of tasks (vs repeats).

## Implementation Plan (Phased)

1) Service + Preview (no writes)
- Build `services/evaluation.py` with core calculations; unit-test on synthetic data.

2) Migrations
- Add `StudentEvaluationRun`; extend `StudentEvaluationLog`; add indices/constraints.

3) Admin UI
- Add routes, forms, templates, JS for preview and run.

4) Persistence
- Implement run action; update `StudentTopicProgress`.

5) History + Export
- History view and JSON/CSV export of logs.

6) Polish & Edge cases
- Validation, permissions, CSRF, error UX, performance.

## Detailed Task List (Executable)

Use this as the step-by-step backlog. Each task is independently shippable. We can execute them one by one.

1) Migrations – header + thick log [DB]
- Files: `migrations/` (alembic), `models.py`
- Do: add `StudentEvaluationRun`; extend `StudentEvaluationLog` per Data Model section; add indices/constraints.
- Accept: `flask db migrate && flask db upgrade` succeeds; models reflect new fields.

2) Evaluation service – core preview computation [Backend]
- Files: `services/evaluation.py` (new), `models.py` (imports only)
- Do: implement `preview(user_ids, topic_ids, period, options)` returning aggregates, metrics, `total_score`, `level_before/after`, warnings.
- Accept: unit test on synthetic data covers accuracy (per-task), time (median), progress, motivation, totals.

3) Admin routes – preview endpoint [Backend]
- Files: `blueprints/admin/routes.py`, `blueprints/admin/forms.py`
- Do: add `EvaluationFilterForm`; add `POST /admin/evaluation/preview` calling service; return JSON for table.
- Accept: request validates inputs, returns rows with flags (insufficient data, missing config, missing partials).

4) Admin page – preview UI [Frontend]
- Files: `templates/admin/evaluation.html`, `static/js/admin_evaluation.js`
- Do: filters form, AJAX preview, results table, badges for warnings, Run button (disabled on blocking guards).
- Accept: round-trip preview works, table renders aggregates and decision.

5) Backfill partial_score – route + form + UI [Backend/Frontend]
- Files: `blueprints/admin/routes.py`, `blueprints/admin/forms.py`, `templates/admin/evaluation.html`, `static/js/admin_evaluation.js`
- Do: add `BackfillPartialScoresForm`; route `POST /admin/evaluation/backfill-partial-scores` with dry-run and apply; modal in UI.
- Logic: if `partial_score` is NULL then compute from `is_correct` + `attempt_number` + `TopicLevelConfig.penalty_weights` (1st=1.0, 2nd=weights["2"], 3rd=weights["3"], else 0.0).
- Accept: dry-run returns counts and reasons; apply updates rows; summary displayed.

6) Evaluation run – guard + persistence [Backend]
- Files: `services/evaluation.py`, `blueprints/admin/routes.py`
- Do: add `run(...)` creating `StudentEvaluationRun` + rows in `StudentEvaluationLog`; update `StudentTopicProgress`.
- Guard: configurable modes for missing partials (Strict vs Auto-compute) per doc; default Strict.
- Accept: run creates header + logs, updates progress deterministically.

7) History + export [Backend/Frontend]
- Files: `blueprints/admin/routes.py`, `templates/admin/evaluation_history.html`
- Do: `GET /admin/evaluation/history` with filters; CSV/JSON export endpoints.
- Accept: admin can filter by user/topic/date; downloads CSV/JSON with all fields.

8) System config wiring [Backend]
- Files: `models.py`, `services/evaluation.py`, `config.py`
- Do: read `EvaluationSystemConfig` once; use thresholds/weights/`weekend_bonus_multiplier`; optional `working_weekdays` default [0..4].
- Accept: `calc_trace` records thresholds and weights actually used.

9) Attempt limit handling [Backend]
- Files: `services/evaluation.py`, `blueprints/admin/routes.py` (import path if needed)
- Do: cap effective attempts at 3 for accuracy mapping; flag >3 attempts in preview notes; ensure import flow documents cap.
- Accept: rows with >3 attempts still compute accuracy with cap and show note.

10) Permissions, CSRF, error UX [Backend/Frontend]
- Files: admin blueprint decorators, forms, templates
- Do: ensure admin-only access, CSRF tokens on forms, friendly errors/warnings.
- Accept: unauthorized users blocked; errors shown via flash/alerts.

11) Tests [Backend]
- Files: `tests/test_evaluation_service.py`, `tests/test_admin_evaluation_routes.py`
- Do: unit tests for service metrics, guards, decisions; route tests for preview/run/backfill.
- Accept: green test run in CI or local pytest.

12) Docs and ops
- Files: `README.md`, this design doc section
- Do: usage instructions (preview, backfill, run, history), CSV schema, known limitations.
- Accept: docs reviewed; admin can operate the flow end-to-end.

13) Optional: CLI for backfill
- Files: Flask CLI factory or a script
- Do: `flask eval backfill-partials --apply` with filters.
- Accept: CLI prints dry-run summary and apply results.

## Task Board (Updatable)

Use these checkboxes to track progress. Refer to tasks by ID (e.g., T1). I will update statuses here as we complete them.

- [x] T1 – Migrations: header + thick log [DB]
  - Files: `migrations/`, `models.py`
  - Do: add `StudentEvaluationRun`; extend `StudentEvaluationLog`; indices/constraints.
  - Accept: `flask db migrate && flask db upgrade` succeeds; new fields present.

- [x] T2 – Evaluation service: preview computation [Backend]
  - Files: `services/evaluation.py`
  - Do: implement `preview(...)` with aggregates, metrics, totals, decisions, warnings.
  - Accept: unit tests on synthetic data pass.

- [x] T3 – Admin routes: preview endpoint [Backend]
  - Files: `blueprints/admin/routes.py`, `blueprints/admin/forms.py`
  - Do: `POST /admin/evaluation/preview`; add `EvaluationFilterForm`.
  - Accept: validated input; JSON rows with flags.

- [ ] T4 – Admin page: preview UI [Frontend]
  - Files: `templates/admin/evaluation.html`, `static/js/admin_evaluation.js`
  - Do: filters, AJAX preview, table, badges, Run button (guard-aware).
  - Accept: end-to-end preview works.

- [ ] T5 – Backfill partial_score: route + form + UI [Fullstack]
  - Files: `blueprints/admin/routes.py`, `blueprints/admin/forms.py`, `templates/admin/evaluation.html`, `static/js/admin_evaluation.js`
  - Do: `POST /admin/evaluation/backfill-partial-scores` with dry-run/apply + modal.
  - Accept: counts and reasons shown; apply updates rows.

- [ ] T6 – Evaluation run: guard + persistence [Backend]
  - Files: `services/evaluation.py`, `blueprints/admin/routes.py`
  - Do: implement `run(...)`; create header + logs; update `StudentTopicProgress`.
  - Accept: deterministic updates; guard modes honored.

- [ ] T7 – History + export [Fullstack]
  - Files: `blueprints/admin/routes.py`, `templates/admin/evaluation_history.html`
  - Do: history view with filters; CSV/JSON export.
  - Accept: filtering works; files download with correct schema.

- [ ] T8 – System config wiring [Backend]
  - Files: `models.py`, `services/evaluation.py`, `config.py`
  - Do: wire thresholds/weights/`weekend_bonus_multiplier`; optional `working_weekdays`.
  - Accept: `calc_trace` records values used.

- [ ] T9 – Attempt limit handling [Backend]
  - Files: `services/evaluation.py`, `blueprints/admin/routes.py`
  - Do: cap to 3 attempts for mapping; flag extras.
  - Accept: preview notes reflect caps; scores correct.

- [ ] T10 – Permissions, CSRF, error UX [Fullstack]
  - Files: admin decorators, forms, templates
  - Do: admin-only; CSRF tokens; friendly errors.
  - Accept: unauthorized blocked; errors surfaced.

- [ ] T11 – Tests [Backend]
  - Files: `tests/test_evaluation_service.py`, `tests/test_admin_evaluation_routes.py`
  - Do: unit + route tests (preview/run/backfill).
  - Accept: all tests green.

- [ ] T12 – Docs and ops
  - Files: `README.md`, this doc
  - Do: usage instructions, CSV schema, limitations.
  - Accept: docs reviewed; admin can operate E2E.

- [ ] T13 – Optional: CLI for backfill
  - Files: Flask CLI module/script
  - Do: `flask eval backfill-partials --apply` with filters.
  - Accept: prints dry-run summary and apply results.

## Appendix – Existing Helpers to Reuse

- `_compute_partial_score(task, attempt_number, is_correct)` in `blueprints/admin/routes.py` – used when creating/importing attempts; metrics should rely on stored `partial_score` rather than recompute per attempt.
- Import by `task_code`/`username` already supported in `admin.attempts` import route.
