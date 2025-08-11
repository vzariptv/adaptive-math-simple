from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo

class LoginForm(FlaskForm):
    username = StringField("Логин", 
        validators=[
            DataRequired(message="Введите имя пользователя"),
            Length(min=4, max=25, message="Логин должен содержать от 4 до 25 символов")
        ],
        render_kw={"placeholder": "Логин"}
    )
    password = PasswordField("Пароль", validators=[DataRequired(message="Введите пароль")])
    remember = BooleanField("Запомнить меня")
    submit = SubmitField("Войти")

class RegistrationForm(FlaskForm):
    username = StringField("Имя пользователя", 
        validators=[
            DataRequired(message="Введите имя пользователя"),
            Length(min=4, max=25, message="Логин должен содержать от 4 до 25 символов")
        ],
        render_kw={"placeholder": "Имя пользователя"}
    )
    email = StringField("Email", 
        validators=[
            DataRequired(message="Введите email"),
            Email(message="Неверный формат email")
        ],
        render_kw={"placeholder": "Email"}
    )
    password = PasswordField("Пароль", validators=[DataRequired(message="Введите пароль")])
    confirm_password = PasswordField("Подтвердите пароль", validators=[
        DataRequired(message="Подтвердите пароль"),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    
    first_name = StringField("Имя", 
        validators=[
            Length(min=2, max=50, message="Имя должно содержать от 2 до 50 символов")
        ],
        render_kw={"placeholder": "Имя"}
    )
    last_name = StringField("Фамилия", 
        validators=[
            Length(min=2, max=50, message="Фамилия должна содержать от 2 до 50 символов")
        ],
        render_kw={"placeholder": "Фамилия"}
    )
    role = SelectField("Роль", choices=[('student', 'Студент'), ('teacher', 'Преподаватель'), ('admin', 'Администратор')], validators=[DataRequired(message="Выберите роль")])  
    submit = SubmitField("Зарегистрироваться")