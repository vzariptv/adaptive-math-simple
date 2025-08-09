**Спецификация: Модуль оценки профиля обучающегося для адаптации уровня задач**

---

## 1. Цель

Обеспечить расчет и логирование интегральной оценки обучающегося по четырем ключевым показателям (точность, время, прогресс, мотивация) в рамках ограниченного учебного периода. Итоговая оценка используется для адаптации уровня сложности задач по каждой теме.

Модуль использует следующие модели:

- `TaskAttempt`: источник данных о попытках решения задач (включая номер попытки `attempt_number`, результат `partial_score`, затраченное время `time_spent`, дату `created_at`)
- `MathTask`: описание задачи, включая связку `topic_id` и `level`
- `TopicLevelConfig`: параметры оценки (штрафы за попытки `penalty_weights`, эталонное время `reference_time`, количество задач `task_count_threshold`)
- `Topic`: справочник тем
- `StudentEvaluationLog`: журнал результатов оценки
- `StudentTopicProgress`: (опционально) — текущее состояние уровня по теме

Все расчеты производятся автоматически по окончании учебного периода. Модуль должен быть реализован как независимый сервис или компонент, интегрируемый в основную систему.

---

## 2. Период оценки

- Период оценки всегда составляет **7 календарных дней**, включая 5 рабочих и 2 выходных (суббота и воскресенье).
- Расчет оценки производится **вручную администратором**, нажатием специальной команды или кнопки в интерфейсе.
- Момент расчета фиксируется как `period_end` (обычно день запуска расчета), а `period_start` определяется как `period_end - 6 дней` (включительно).
- В расчет попадают все попытки (`TaskAttempt`), сделанные пользователем в этот интервал **по задачам одной темы и уровня сложности**.
- Если обучающийся не решал ни одной задачи за период — оценка не рассчитывается и обучающийся остается на том же уровне задач.
- Активность в выходные дни поощряется — см. коэффициент `weekend_bonus_multiplier` в разделе мотивации (см. раздел 3.4).

---

## 3. Показатели профиля обучающегося

### 3.1. Точность решений (Accuracy)

- Учитываются все попытки (максимум 3).
- Баллы (partial\_score) начисляются по следующей схеме. Первая попытка всегда оценивается в 1.0 балл по умолчанию и не входит в `penalty_weights`:
  - 2-я попытка: `penalty_weights[0]`
  - 3-я попытка: `penalty_weights[1]`
  - Неудачные попытки: 0 (если ни одна попытка не была успешной)
- **Расчет:**
  ```
  accuracy = сумма partial_score за период / task_count_threshold
  ```

### 3.2. Среднее время решения (AvgTime)

- Учитывается общее активное время на решение задачи (по всем попыткам).
- **Расчет:**
  ```
  avg_time = сумма(время_всех_попыток) / решённых_задач
  time_deviation = (avg_time - эталонное_время) / эталонное_время
  ```
- **Оценка:**\
  Преобразуется в положительную шкалу:
  ```
  time_score = max(0, 1 - time_deviation)
  ```
  (если время больше эталона на 20%, score = 0.8)

### 3.3. Прогресс (Progress)

- Оценивается разница между метриками первой и последней трети решённых задач за период.
- **Расчет:**
  ```
  progress_accuracy = accuracy_конец - accuracy_начало
  progress_time = avg_time_начало - avg_time_конец
  progress_score = 0.6 * progress_accuracy + 0.4 * progress_time / эталонное_время
  ```

### 3.4. Мотивация (Motivation)

- Учитывается:
  - Количество решённых задач;
  - Регулярность работы (по дням);
  - Наличие активности в выходные.
- **Расчет:**
  ```
  activity_ratio = решено_задач / пороговое_кол-во_задач
  work_days = число_дней_с_решениями_в_рабочие_дни
  weekend_days = число_дней_с_решениями_в_субботу/воскресенье
  regularity = (work_days + weekend_days * weekend_bonus_multiplier) / период_в_днях

  Где `период_в_днях` — это количество календарных дней между датой начала и датой последней решённой задачи в периоде, но не более `evaluation_period_days`. Если все задачи решены раньше, период укорачивается. В выходные дни применяется бонус.

  motivation_score = 0.5 * activity_ratio + 0.5 * regularity
  ```
  Где `weekend_bonus_multiplier` (поощрение за выходной) = **1.5** (задано централизовано)

---

## 4. Интегральная оценка и переход уровня

### 4.1. Итоговая формула

```
total_score = weight_accuracy * accuracy + weight_time * time_score + weight_progress * progress_score + weight_motivation * motivation_score
```

Где `weight_accuracy`, `weight_time`, `weight_progress`, `weight_motivation` — настраиваемые коэффициенты, задаваемые централизованно в параметрах системы.

### 4.2. Пороговые значения (по уровням):

- Задаются централизованно в параметрах системы:
  - **Минимальный порог**: переход вниз, если `total_score < min_threshold`
  - **Максимальный порог**: переход вверх, если `total_score >= max_threshold`
  - Промежуточный результат: остаётся на текущем уровне

### 4.3. Краевые случаи:

- Если уровень — **начальный**, возможен только переход вперёд
- Если уровень — **последний**, и score >= max\_threshold, — тема **считается освоенной**

---

## 5. Конфигурационные параметры

### 5.1. Централизованные:

- `evaluation_period_days` = 7
- `weekend_days` = (суббота, воскресенье)
- `weekend_bonus_multiplier` = 1.5
- Пороговые значения `min_threshold`, `max_threshold` — по каждому уровню, кроме 1-го и последнего

### 5.2. На уровне темы и сложности:

- `task_count_threshold`: пороговое количество задач
- `reference_time_per_task`: эталонное время задачи
- `penalty_weights`: список коэффициентов [1.0, 0.7, 0.4] за попытки

---

## 6. Логирование, сброс и сохранение статистики

### 6.1. Сохранение

- После завершения периода сохраняются:
  - Все сырые данные (попытки, время, дни)
  - Рассчитанные показатели по 4 метрикам
  - `total_score`
  - Результат: "Переход вперёд", "Переход назад", "Без изменений", "Тема освоена"

### 6.2. Где сохранять

- В таблице `student_evaluation_log` (или JSON в профиле студента):
  ```json
  {
    "student_id": ...,
    "topic": ...,
    "level": ...,
    "period_start": ...,
    "period_end": ...,
    "accuracy": ...,
    "avg_time": ...,
    "progress": ...,
    "motivation": ...,
    "total_score": ...,
    "level_change": "up" / "down" / "stay" / "mastered"
  }
  ```

### 6.3. Сброс статистики

- Поскольку период всегда фиксирован (7 дней), сброс статистики осуществляется автоматически при каждом запуске расчета.
- При расчете:
  - Все метрики обнуляются перед новым расчетом.
  - Предыдущие значения сохраняются только в `StudentEvaluationLog`.
- Повторный расчет за тот же период перезаписывает запись в логе, если она уже существует.
- При переходе на новый уровень обновляется `StudentTopicProgress` (если используется), но статистика попыток (`TaskAttempt`) сохраняется как есть.
- В статистику не включаются попытки, вышедшие за пределы 7-дневного окна.

---

## 7. Интерфейсы

- **Модуль должен предоставлять API / интерфейс функции**:
  - `evaluate_student(student_id, topic_id)` → возвращает структуру с итогом и логи.
  - Опционально: `get_student_progress_history(student_id)` → хронология.

---

## 8. Технические заметки

### 8.1. Дополнения к модели TaskAttempt

Для корректного расчета интегральной оценки в модели `TaskAttempt` необходимо следующее:

- `` — идентификатор обучающегося (есть)
- `` — привязка к задаче с уровнем сложности и темой (есть)

Нужно добавить:

- `` — номер попытки (1, 2, 3)
- `` — активное время, затраченное на попытку (в секундах)
- `` — была ли попытка успешной (да/нет)
- `` — дата и время попытки (нужно для определения активности и выходных)
- `` — оценка по шкале [0, 1] с учётом коэффициента штрафа за номер попытки

Рекомендуется при сохранении попытки сразу учитывать коэффициент штрафа (из `penalty_weights`) и сохранять результат в `partial_score`.

Дополнительно можно добавить:

- `evaluation_session_id` (опционально): привязка попытки к периоду оценки, если используется явное разделение периодов.



### 8.2. Модель темы и уровня сложности

Для оценки требуется модель, описывающая параметры темы и уровня сложности. Возможна структура:

```python
class TopicLevelConfig(db.Model):
    __tablename__ = 'topic_level_configs'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String, nullable=False)  # 'low', 'medium', 'high'

    task_count_threshold = db.Column(db.Integer, nullable=False)         # Пороговое число задач за период
    reference_time = db.Column(db.Integer, nullable=False)              # Эталонное время (сек)
    penalty_weights = db.Column(db.JSON, nullable=False)  # Только для второй и третьей попытки: [0.7, 0.4]                # Штрафы за попытки, например [1.0, 0.7, 0.4]

    __table_args__ = (UniqueConstraint('topic_id', 'level', name='_topic_level_uc'),)
```

- `task_count_threshold` — минимальное количество задач, необходимых для оценки.
- `reference_time` — эталонное время решения одной задачи в секундах.
- `penalty_weights` — список коэффициентов для второй и третьей попытки: [0.7, 0.4]. Первая попытка всегда имеет коэффициент 1.0 и не задается.

Модель может использоваться при генерации задач, в оценке, а также для настройки адаптивного перехода между уровнями.

### 8.3. Модель справочника тем

Для привязки задач и конфигураций к темам используется базовая сущность `Topic`:

```python
class Topic(db.Model):
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Например: 'quadratic_equations'
    name = db.Column(db.String(100), nullable=False)              # Название темы: 'Квадратные уравнения'
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

Эта таблица выступает как справочник и используется для:

- Привязки к `MathTask`
- Привязки к `TopicLevelConfig`
- Фильтрации и вывода тем в интерфейсе пользователя

### 8.4. Обновление модели MathTask

С учетом введения `Topic`, `TopicLevelConfig` и нормализации данных, модель `MathTask` стоит изменить следующим образом:

```python
class MathTask(db.Model):
    __tablename__ = 'math_tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    answer_type = db.Column(db.String(50), nullable=False)
    correct_answer = db.Column(db.JSON, nullable=False)
    answer_schema = db.Column(db.JSON)

    explanation = db.Column(db.Text)

    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'

    max_score = db.Column(db.Float, default=1.0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # связи
    attempts = db.relationship('TaskAttempt', backref='task', lazy='dynamic')
    topic = db.relationship('Topic', backref='tasks')

    def __repr__(self):
        return f'<MathTask {self.title}>'
```

Изменения:

- `topic` теперь отдельная сущность (`topic_id` → `Topic.id`)
- `difficulty_level` заменен на `level` (строковое значение, согласованное с `TopicLevelConfig`)

---

### 8.5. Модель логирования результатов оценки

Для хранения итогов расчета по каждому пользователю, теме и уровню сложности требуется:

```python
class StudentEvaluationLog(db.Model):
    __tablename__ = 'student_evaluation_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'

    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    accuracy = db.Column(db.Float)
    avg_time = db.Column(db.Float)
    progress = db.Column(db.Float)
    motivation = db.Column(db.Float)
    total_score = db.Column(db.Float)

    level_change = db.Column(db.String(10))  # 'up', 'down', 'stay', 'mastered'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 8.6. Модель текущего прогресса по теме (опционально)

Если необходимо отдельно отслеживать текущий уровень по теме без анализа логов:

```python
class StudentTopicProgress(db.Model):
    __tablename__ = 'student_topic_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)

    current_level = db.Column(db.String(10), nullable=False)  # 'low', 'medium', 'high'
    is_mastered = db.Column(db.Boolean, default=False)
    last_evaluated_at = db.Column(db.DateTime)

    __table_args__ = (db.UniqueConstraint('user_id', 'topic_id'),)
```

#### 8.7. Модель системной конфигурации

Для централизованного хранения глобальных параметров оценки используется отдельная таблица конфигурации:

```python
class EvaluationSystemConfig(db.Model):
    __tablename__ = 'evaluation_system_config'

    id = db.Column(db.Integer, primary_key=True)
    evaluation_period_days = db.Column(db.Integer, default=7)
    weekend_bonus_multiplier = db.Column(db.Float, default=1.5)

    weight_accuracy = db.Column(db.Float, default=0.3)
    weight_time = db.Column(db.Float, default=0.2)
    weight_progress = db.Column(db.Float, default=0.3)
    weight_motivation = db.Column(db.Float, default=0.2)

    min_threshold_low = db.Column(db.Float)
    max_threshold_low = db.Column(db.Float)
    min_threshold_medium = db.Column(db.Float)
    max_threshold_medium = db.Column(db.Float)
    # Последний уровень не требует min_threshold / max_threshold

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

- Должна использоваться только одна активная строка конфигурации в системе.
- Может обновляться администратором через интерфейс или административный API.
- Позволяет централизованно управлять всеми параметрами расчета без привязки к теме.

### 8.8. Устаревшая модель StudentProfile

Модель `StudentProfile`, содержащая произвольные поля (например, `knowledge_level`, `attention_span`, `preferred_difficulty`) **не используется** в механизме оценки. Ее требуется удалить.

---

## 9. Примечания

- Все расчёты округляются до 3 знаков после запятой.
- Уровень задач задается отдельно от темы, что позволяет использовать один и тот же механизм в разных темах с тремя уровнями сложности.

---

