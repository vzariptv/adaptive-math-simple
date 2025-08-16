import json 

from flask_wtf import FlaskForm
from wtforms import SubmitField, FileField,StringField, TextAreaField, BooleanField, SelectField, FloatField, PasswordField, HiddenField, DateField, DateTimeField
from wtforms.validators import EqualTo, DataRequired, InputRequired, Length, Optional, Regexp, ValidationError, NumberRange, Email

from wtforms import IntegerField, StringField, FieldList
from wtforms import Form as NoCsrfForm  # подформа без отдельного CSRF
from wtforms import FormField
from wtforms.widgets import CheckboxInput


from models import Topic, User

# ---------- ВАЛИДАТОРЫ-ПОМОЩНИКИ ----------
class JSONText(ValidationError):
    """Маркерная ошибка для читаемого сообщения при парсинге JSON."""

def _strip(v):
    """
    Аккуратно триммит строку. Для не-строковых значений возвращает как есть.
    Пустые строки превращаем в None — это удобно для Optional()/nullable-полей.
    В связке с DataRequired() пустое значение всё равно провалит валидацию (и это ок).
    """
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v

def parse_json_or_error(value: str, field_label: str):
    """Безопасный парсер JSON для текстовых полей формы."""
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except Exception as e:
        raise ValidationError(f"{field_label}: некорректный JSON ({e})")

def validate_answer_json(obj):
    """
    Мини-валидация структуры correct_answer:
    ожидаем объект с ключом type и минимальными полями по типу.
    """
    if not isinstance(obj, dict):
        raise ValidationError("Правильный ответ: ожидается JSON-объект.")
    t = obj.get("type")
    if t not in {"number", "variables", "interval", "sequence"}:
        raise ValidationError("Правильный ответ: неизвестный type.")
    if t == "number" and not isinstance(obj.get("value"), (int, float)):
        raise ValidationError("Правильный ответ: для type=number нужен числовой value.")
    if t == "variables":
        if not isinstance(obj.get("variables"), list):
            raise ValidationError("Правильный ответ: для type=variables нужен список variables.")
        if not all(isinstance(v, dict) and "name" in v and "value" in v for v in obj.get("variables", [])):
            raise ValidationError("Правильный ответ: для type=variables все переменные должны иметь name и value.")
    if t == "sequence":
        vals = obj.get("sequence_values")
        if not isinstance(vals, list):
            raise ValidationError("Правильный ответ: для type=sequence нужен список sequence_values.")
        if not all(isinstance(v, (int, float)) for v in vals):
            raise ValidationError("Правильный ответ: для type=sequence значения должны быть числами.")
    if t == "interval":
        if "start" not in obj or "end" not in obj:
            raise ValidationError("Правильный ответ: для type=interval нужны поля start/end.")
        start = obj.get("start")
        end = obj.get("end")
        # null допустим для -∞/+∞, иначе — число
        if start is not None and not isinstance(start, (int, float)):
            raise ValidationError("Правильный ответ: start должен быть числом или null.")
        if end is not None and not isinstance(end, (int, float)):
            raise ValidationError("Правильный ответ: end должен быть числом или null.")
        if start is not None and end is not None and start >= end:
            raise ValidationError("Правильный ответ: start должен быть меньше end для интервала.")
    return True




LEVEL_CHOICES = [("low", "Низкий"), ("medium", "Средний"), ("high", "Высокий")]
ANSWER_TYPE_CHOICES = [
    ("number", "Число"),
    ("variables", "Переменные"),
    ("interval", "Интервал"),
    ("sequence", "Последовательность"),
]
ROLE_CHOICES = [("student", "Студент"), ("teacher", "Преподаватель"), ("admin", "Админ")]

# базовая форма для создания/редактирования пользователя
class UserBaseForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    role = SelectField("Роль", choices=ROLE_CHOICES, validators=[DataRequired()])
    first_name = StringField("Имя", validators=[Optional(), Length(max=50)])
    last_name = StringField("Фамилия", validators=[Optional(), Length(max=50)])
    is_active = BooleanField("Активен", default=True)
    instance_id = HiddenField()

    def validate_username(self, field):
        q = User.query.filter(User.username == field.data)
        if self.instance_id.data:
            q = q.filter(User.id != int(self.instance_id.data))
        if q.first():
            raise ValidationError("Логин уже занят.")

    def validate_email(self, field):
        if not field.data:
            return
        q = User.query.filter(User.email == field.data)
        if self.instance_id.data:
            q = q.filter(User.id != int(self.instance_id.data))
        if q.first():
            raise ValidationError("Email уже используется.")


class CreateUserForm(UserBaseForm):
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField("Создать")

class EditUserForm(UserBaseForm):
    new_password = PasswordField("Новый пароль", validators=[Optional(), Length(min=6, max=128)])
    confirm_password = PasswordField("Подтверждение", validators=[Optional(), EqualTo('new_password')])

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.instance_id.data = str(instance.id)
    submit = SubmitField("Сохранить")

# ---------- TOPIC ----------
# форма для создания/редактирования темы
class LevelConfigForm(NoCsrfForm):
    level = HiddenField(validators=[DataRequired()], render_kw={"readonly": True})
    task_count_threshold = IntegerField(
        "Порог задач",
        validators=[DataRequired(), NumberRange(min=0, max=100000)],
        render_kw={"placeholder": "10"},
        description="Сколько задач считаем «репрезентативными» на уровне."
    )
    reference_time = IntegerField(
        "Эталонное время (сек)",
        validators=[DataRequired(), NumberRange(min=1, max=86400)],
        render_kw={"placeholder": "900"},
        description="В секундах (900 = 15 минут)."
    )
    penalty_weights = StringField(
        "Штрафы (через запятую)",
        validators=[DataRequired()],
        filters=[_strip],
        render_kw={"placeholder": "0.7, 0.4"},
        description="Коэффициенты за повторные попытки: например «0.7, 0.4»."
    )

    # разберём строку в список чисел и сохраним как _weights
    def validate_penalty_weights(self, field):
        raw = (field.data or "").replace(";", ",")
        parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
        if not parts:
            raise ValidationError("Укажите хотя бы одно значение.")
        weights = []
        for p in parts:
            try:
                val = float(p)
            except ValueError:
                raise ValidationError(f"«{p}» — не число.")
            # обычно 0..1, но не жёстко ограничиваем — при желании можно включить NumberRange
            weights.append(val)
        self._weights = weights  # пригодится в роуте при сохранении

class TopicBaseForm(FlaskForm):
    """
    Базовая форма темы: общие поля + проверка формата.
    Uniqueness проверяем в validate_code (ниже), учитывая режим create/edit.
    """
    code = StringField(
        "Код",
        validators=[
            DataRequired(),
            Length(min=3, max=50),
            # только латиница/цифры/нижнее подчёркивание
            Regexp(r"^[a-z0-9_]+$", message="Разрешены строчные латинские буквы, цифры и «_»."),
        ],
        description="Уникальный идентификатор темы (только латинские буквы, цифры и _)",
        filters=[_strip],
        render_kw={
            # НЕ обязателен, но удобно: браузерная подсказка и базовые атрибуты
            "placeholder": "algebra_basics",
            "pattern": "^[a-z0-9_]+$",
            "title": "Только строчные латинские буквы, цифры и подчёркивания",
            "autocomplete": "off",
            # ПРОСЬБА: см. рекомендацию про class ниже
            # "class": "form-control",  # можно задать, но см. примечания ниже
        },
    )
    name = StringField("Название", validators=[DataRequired(), Length(min=3, max=100)],
        description="Отображаемое название темы",
        filters=[_strip],
        render_kw={
            "placeholder": "Основы алгебры",
            "autocomplete": "off",
        },
    )
    description = TextAreaField("Описание", validators=[Optional(), Length(max=5000)],
        filters=[_strip],
        description="Опционально: описание для преподавателей и студентов.",
        render_kw={
            "rows": 5,
            "placeholder": "Подробное описание темы и её содержания...",
        },
    )

    # instance_id нужен, чтобы при редактировании не ругаться на саму себя
    instance_id = HiddenField()  # заполняем в edit-форме

    def validate_code(self, field):
        q = Topic.query.filter(Topic.code == field.data)
        if self.instance_id.data:
            # исключаем текущую запись при редактировании
            q = q.filter(Topic.id != int(self.instance_id.data))
        if q.first():
            raise ValidationError("Тема с таким кодом уже существует.")


class CreateTopicForm(TopicBaseForm):
    """Используется в create: instance_id остаётся пустым."""
    submit = SubmitField("Создать")
    pass


class EditTopicForm(TopicBaseForm):
    """В edit мы прокинем текущий topic.id в hidden instance_id."""
     # три подформы: low / medium / high
    configs = FieldList(FormField(LevelConfigForm), min_entries=3, max_entries=3)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if instance is not None:
            self.instance_id.data = str(instance.id)
            
    submit = SubmitField("Сохранить")

# ---------- TASKS ----------
# форма для создания/редактирования задания

class NumberAnswerForm(NoCsrfForm):
    value = FloatField("Значение", validators=[InputRequired()],
                      render_kw={"placeholder": "42", "step": "any"})

class VariableForm(NoCsrfForm):
    name = StringField("Переменная", validators=[DataRequired(), Length(max=10)],
                      filters=[_strip],
                      render_kw={"placeholder": "x", "class": "form-control"})
    value = FloatField("Значение", validators=[InputRequired()],
                      render_kw={"placeholder": "0", "step": "any", "class": "form-control"})

class VariablesAnswerForm(NoCsrfForm):
    variables = FieldList(FormField(VariableForm), min_entries=1, max_entries=10)
    add_variable  = SubmitField("Добавить переменную")

class IntervalAnswerForm(NoCsrfForm):
    start = FloatField("Начало", validators=[Optional()],
                      render_kw={"placeholder": "начало", "step": "any"})
    end = FloatField("Конец", validators=[Optional()],
                    render_kw={"placeholder": "конец", "step": "any"})
    start_inclusive = BooleanField("Включая начало", default=True)
    end_inclusive = BooleanField("Включая конец", default=False)
    start_infinity = BooleanField("Начало: -∞", default=False)
    end_infinity = BooleanField("Конец: +∞", default=False)

    def validate(self, extra_validators=None):
        # Сначала запустим базовую валидацию полей
        if not super().validate(extra_validators):
            return False
        
        # Если родительская форма попросила пропустить доп.валидацию — выходим
        if getattr(self, "_skip_validation", False):
            return True
        
        # Проверяем логику интервала
        start = None if self.start_infinity.data else self.start.data
        end = None if self.end_infinity.data else self.end.data
        
        if start is not None and end is not None and start >= end:
            self.end.errors.append("Конец должен быть больше начала")
            return False
        
        return True

class SequenceAnswerForm(NoCsrfForm):
    sequence_input = StringField("Последовательность", validators=[DataRequired()],
                                filters=[_strip],
                                render_kw={"placeholder": "1, 2, 3, 5, 8, 13", "class": "form-control"})
    
    def validate_sequence_input(self, field):
        # Если подформу попросили пропустить (неактивный тип), не валидируем
        if getattr(self, "_skip_validation", False):
            return
        try:
            values = []
            for item in field.data.replace(';', ',').split(','):
                item = item.strip()
                if item:
                    values.append(float(item))
            if not values:
                raise ValidationError("Введите хотя бы одно число")
            self._sequence_values = values
        except ValueError:
            raise ValidationError("Все элементы должны быть числами")

class TaskForm(FlaskForm):
    title = StringField("Название", validators=[DataRequired(), Length(max=255)])
    code = StringField(
        "Внешний код",
        validators=[Optional(), Length(max=64), Regexp(r"^[A-Za-z0-9_.:\\-]*$", message="Допустимы только латиница, цифры и символы _ . : -")],
        render_kw={"placeholder": "migr_01_123"}
    )
    description = TextAreaField("Условие", validators=[Optional()])
    answer_type = SelectField("Тип ответа", choices=ANSWER_TYPE_CHOICES, validators=[DataRequired()])
    
    # Подформы для разных типов ответов
    number_answer = FormField(NumberAnswerForm)
    variables_answer = FormField(VariablesAnswerForm) 
    interval_answer = FormField(IntervalAnswerForm)
    sequence_answer = FormField(SequenceAnswerForm)
    
    # Оставляем текстовое поле как fallback/альтернативу
    correct_answer_json = TextAreaField("Правильный ответ (JSON режим)", validators=[Optional()])
    answer_schema = TextAreaField("Схема ответа (JSON, опц.)", validators=[Optional()])
    explanation = TextAreaField("Подсказка/объяснение", validators=[Optional()])
    topic_id = SelectField("Тема", coerce=int, validators=[DataRequired()])
    level = SelectField("Сложность", choices=LEVEL_CHOICES, validators=[DataRequired()])
    max_score = FloatField("Макс. балл", validators=[DataRequired(), NumberRange(min=0.0)])
    is_active = BooleanField("Активна", default=True)

    # Скрытое поле для окончательного JSON
    correct_answer = HiddenField()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Инициализируем переменные с одной пустой записью, если их нет
        try:
            if not self.variables_answer.form.variables.entries:
                self.variables_answer.form.variables.append_entry()
        except Exception as e:
            # Если что-то пошло не так, просто продолжаем без ошибок
            pass

    def handle_variable_actions(self, request_form) -> bool:
        """
        Обрабатывает добавление/удаление строк FieldList для переменных на стороне сервера.
        Возвращает True, если состав строк изменился (нужно просто перерендерить форму без validate_on_submit).
        """
        changed = False

        # Добавление новой строки через SubmitField
        # Имя submit-кнопки имеет вид: <prefix>-add_variable
        add_name = f"{self.variables_answer.id}-add_variable"
        if add_name in request_form:
            self.variables_answer.form.variables.append_entry()
            changed = True

        # Удаление помеченных строк. Ожидаем флаги вида <prefix>-variables-<i>-DELETE = "1"
        prefix = f"{self.variables_answer.id}-variables-"
        keep_entries = []
        for i, entry in enumerate(self.variables_answer.form.variables.entries):
            del_flag = request_form.get(f"{prefix}{i}-DELETE")
            if del_flag:
                changed = True
                continue
            keep_entries.append(entry)

        if changed:
            # Пересобираем entries; WTForms переиндексирует при следующем рендере
            self.variables_answer.form.variables.entries = keep_entries
            # гарантируем хотя бы одну строку, чтобы пользователь мог продолжить ввод
            if len(self.variables_answer.form.variables.entries) == 0:
                self.variables_answer.form.variables.append_entry()

        return changed

    def build_answer_json(self):
        """Собирает JSON ответа из текущих значений формы без строгой валидации.
        Используется для предпросмотра (опытный режим)."""
        answer_type = (self.answer_type.data or "").strip()

        def _num(v):
            if v is None:
                return None
            try:
                # поддержка запятой в дробных
                if isinstance(v, str):
                    v = v.strip()
                    if v == "":
                        return None
                    v = v.replace(",", ".")
                return float(v)
            except Exception:
                return None

        if answer_type == 'number':
            return {
                'type': 'number',
                'value': _num(self.number_answer.form.value.data)
            }

        if answer_type == 'variables':
            vars_out = []
            try:
                for entry in self.variables_answer.form.variables:
                    name = (entry.form.name.data or '').strip()
                    val = _num(entry.form.value.data)
                    if name:
                        vars_out.append({'name': name, 'value': val})
            except Exception:
                pass
            return {'type': 'variables', 'variables': vars_out}

        if answer_type == 'interval':
            f = self.interval_answer.form
            start = None if getattr(f, 'start_infinity', None) and f.start_infinity.data else _num(getattr(f, 'start', None).data if hasattr(f, 'start') else None)
            end = None if getattr(f, 'end_infinity', None) and f.end_infinity.data else _num(getattr(f, 'end', None).data if hasattr(f, 'end') else None)
            return {
                'type': 'interval',
                'start': start,
                'end': end,
                'start_inclusive': bool(getattr(f, 'start_inclusive', None).data) if hasattr(f, 'start_inclusive') else True,
                'end_inclusive': bool(getattr(f, 'end_inclusive', None).data) if hasattr(f, 'end_inclusive') else False,
            }

        if answer_type == 'sequence':
            raw = (self.sequence_answer.form.sequence_input.data or '')
            if isinstance(raw, str):
                parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
                nums = []
                for p in parts:
                    n = _num(p)
                    if n is not None:
                        nums.append(n)
            else:
                nums = []
            return {'type': 'sequence', 'sequence_values': nums}

        # Fallback: показать то, что в JSON-поле, без строгой ошибки
        if self.correct_answer_json.data:
            try:
                return json.loads(self.correct_answer_json.data)
            except Exception:
                return self.correct_answer_json.data

        return None

    def validate(self, extra_validators=None):
        # Перед базовой валидацией включим required только для активного типа ответа,
        # а для остальных подформ сделаем Optional(), чтобы они не падали.
        at = (self.answer_type.data or '').strip()

        # Сообщим подформам, какие из них неактивны (чтобы они пропустили свою доп.валидацию)
        self.number_answer.form._skip_validation = (at != 'number')
        self.variables_answer.form._skip_validation = (at != 'variables')
        self.interval_answer.form._skip_validation = (at != 'interval')
        self.sequence_answer.form._skip_validation = (at != 'sequence')

        # helpers to toggle validators
        def _stash(field):
            if not hasattr(field, '_orig_validators'):
                field._orig_validators = list(field.validators)

        def _enable_required(field):
            _stash(field)
            field.validators = list(getattr(field, '_orig_validators', field.validators))

        def _disable_required(field):
            _stash(field)
            field.validators = [Optional()]

        # number
        if at == 'number':
            _enable_required(self.number_answer.form.value)
        else:
            _disable_required(self.number_answer.form.value)

        # variables (каждую подформу в FieldList)
        for entry in self.variables_answer.form.variables:
            if at == 'variables':
                _enable_required(entry.form.name)
                _enable_required(entry.form.value)
            else:
                _disable_required(entry.form.name)
                _disable_required(entry.form.value)

        # sequence
        if at == 'sequence':
            _enable_required(self.sequence_answer.form.sequence_input)
        else:
            _disable_required(self.sequence_answer.form.sequence_input)

        # interval — поля уже Optional, ничего не делаем

        # Теперь запускаем базовую валидацию только с актуальными required
        if not super().validate(extra_validators):
            return False

        # Валидация в зависимости от типа ответа
        # Сначала очистим ошибки неактивных подформ (на случай повторной отправки с другим типом)
        if at != 'number':
            self.number_answer.form.value.errors = []
        if at != 'variables':
            for entry in self.variables_answer.form.variables:
                entry.form.name.errors = []
                entry.form.value.errors = []
        if at != 'sequence':
            self.sequence_answer.form.sequence_input.errors = []
        if at != 'interval':
            try:
                f = self.interval_answer.form
                f.start.errors = []
                f.end.errors = []
                f.start_inclusive.errors = []
                f.end_inclusive.errors = []
            except Exception:
                pass

        # Собираем и проверяем только активный тип
        if at == 'number':
            try:
                v = self.number_answer.form.value.data
                self._answer_data = {"type": "number", "value": float(v)}
            except Exception:
                self.number_answer.form.value.errors.append("Введите число")
                return False

        elif at == 'variables':
            variables = []
            for entry in self.variables_answer.form.variables:
                name = (entry.form.name.data or '').strip()
                if not name:
                    entry.form.name.errors.append("Имя переменной обязательно")
                    return False
                try:
                    val = float(entry.form.value.data)
                except Exception:
                    entry.form.value.errors.append("Значение должно быть числом")
                    return False
                variables.append({"name": name, "value": val})
            self._answer_data = {"type": "variables", "variables": variables}

        elif at == 'sequence':
            raw = (self.sequence_answer.form.sequence_input.data or "").strip()
            if not raw:
                self.sequence_answer.form.sequence_input.errors.append("Введите хотя бы одно число")
                return False
            parts = [p.strip() for p in raw.replace(';', ',').split(',') if p.strip()]
            nums = []
            for p in parts:
                try:
                    nums.append(float(p.replace(',', '.')))
                except Exception:
                    self.sequence_answer.form.sequence_input.errors.append(f"Некорректное число: {p}")
                    return False
            self._answer_data = {"type": "sequence", "sequence_values": nums}

        elif at == 'interval':
            f = self.interval_answer.form
            # учтём бесконечности
            start = None if (hasattr(f, 'start_infinity') and f.start_infinity.data) else f.start.data
            end = None if (hasattr(f, 'end_infinity') and f.end_infinity.data) else f.end.data
            start_inc = bool(getattr(f, 'start_inclusive', True))
            end_inc = bool(getattr(f, 'end_inclusive', False))

            # преобразуем к float, если заданы
            try:
                start_val = None if start in (None, "") else float(str(start).replace(',', '.'))
            except Exception:
                f.start.errors.append("Начало должно быть числом или пусто")
                return False
            try:
                end_val = None if end in (None, "") else float(str(end).replace(',', '.'))
            except Exception:
                f.end.errors.append("Конец должен быть числом или пусто")
                return False

            # если обе границы заданы — проверим порядок
            if start_val is not None and end_val is not None and start_val >= end_val:
                f.end.errors.append("Конец должен быть больше начала")
                return False

            self._answer_data = {
                "type": "interval",
                "start": start_val,
                "end": end_val,
                "start_inclusive": start_inc,
                "end_inclusive": end_inc,
            }

        else:
            # неизвестный тип
            self.answer_type.errors.append("Неизвестный тип ответа")
            return False

        # Сохраняем JSON в скрытое поле
        self.correct_answer.data = json.dumps(self._answer_data)
        return True
    
    def populate_answer_forms(self, answer_data):
        """Заполняет подформы данными из JSON"""
        if not answer_data or not isinstance(answer_data, dict):
            return
            
        answer_type = answer_data.get('type')
        
        try:
            if answer_type == 'number' and 'value' in answer_data:
                self.number_answer.form.value.data = answer_data['value']
                
            elif answer_type == 'variables' and 'variables' in answer_data:
                variables = answer_data['variables']
                # Очищаем существующие
                while len(self.variables_answer.form.variables) > 0:
                    self.variables_answer.form.variables.pop_entry()
                # Добавляем из данных
                for var in variables:
                    entry = self.variables_answer.form.variables.append_entry()
                    entry.form.name.data = var.get('name', '')
                    entry.form.value.data = var.get('value', 0)
                # Добавляем пустую для редактирования
                if len(variables) == 0:
                    self.variables_answer.form.variables.append_entry()
                    
            elif answer_type == 'interval':
                form = self.interval_answer.form
                start = answer_data.get('start')
                end = answer_data.get('end')
                
                form.start_infinity.data = start is None
                form.end_infinity.data = end is None
                form.start.data = start
                form.end.data = end
                form.start_inclusive.data = answer_data.get('start_inclusive', True)
                form.end_inclusive.data = answer_data.get('end_inclusive', False)
                
            elif answer_type == 'sequence' and 'sequence_values' in answer_data:
                values = answer_data['sequence_values']
                # Поддержка старого формата [{"value": x}, ...]
                if isinstance(values, list) and values and all(isinstance(v, dict) and 'value' in v for v in values):
                    values = [v['value'] for v in values]
                self.sequence_answer.form.sequence_input.data = ', '.join(map(str, values))
                
            # Также заполняем JSON поле для fallback
            self.correct_answer_json.data = json.dumps(answer_data, ensure_ascii=False, indent=2)
                
        except Exception as e:
            # В случае ошибки просто заполняем JSON поле
            self.correct_answer_json.data = json.dumps(answer_data, ensure_ascii=False, indent=2)
    
    # Разберём JSON-поля и провалидируем структуру (оставляем для answer_schema)
    def validate_answer_schema(self, field):
        if field.data:
            obj = parse_json_or_error(field.data, "Схема ответа")
            self._answer_schema_obj = obj
        else:
            self._answer_schema_obj = None


# общие формы для импорта и удаления (через модальные окна)
class ImportFileForm(FlaskForm):
    file = FileField("Файл (.json)", validators=[DataRequired()])
    submit = SubmitField("Импортировать")

class ConfirmDeleteForm(FlaskForm):
    submit = SubmitField("Удалить")

# ---------- ATTEMPTS ----------
class AttemptFilterForm(FlaskForm):
    """Фильтры журнала попыток (просмотр для админа/преподавателя)."""
    student_id = SelectField("Студент", coerce=int, validators=[Optional()])
    task_id    = SelectField("Задача",  coerce=int, validators=[Optional()])
    topic_id   = SelectField("Тема",    coerce=int, validators=[Optional()])
    date_from  = DateField("С", validators=[Optional()])
    date_to    = DateField("По", validators=[Optional()])
    per_page   = SelectField(
        "На странице",
        coerce=int,
        choices=[(20, "20"), (50, "50"), (100, "100")],
        default=20,
        validators=[Optional()],
    )

class AttemptForm(FlaskForm):
    """Базовая форма попытки (используется в create/edit)."""
    user_id        = SelectField("Студент", coerce=int, validators=[DataRequired()])
    task_id        = SelectField("Задача",  coerce=int, validators=[DataRequired()])
    attempt_number = IntegerField("Номер попытки", validators=[Optional(), NumberRange(min=1)])
    is_correct     = BooleanField("Правильно", default=False)
    partial_score  = FloatField(
        "Частичный балл (авто)",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"readonly": True, "disabled": True},
        description="Вычисляется автоматически по политике темы и номеру попытки."
    )
    time_spent     = IntegerField("Время (сек)", validators=[Optional(), NumberRange(min=0)])
    hints_used     = IntegerField("Подсказки", validators=[Optional(), NumberRange(min=0)])
    created_at     = DateTimeField("Создано", validators=[Optional()])
    user_answer    = TextAreaField("Ответ (JSON или текст)", validators=[Optional()],
                                   description="Можно ввести JSON или обычную строку")
    instance_id    = HiddenField()

class CreateAttemptForm(AttemptForm):
    prefill_from_task = SubmitField("Подставить ответ задачи")
    submit = SubmitField("Добавить попытку")

class EditAttemptForm(AttemptForm):
    submit = SubmitField("Сохранить изменения")
