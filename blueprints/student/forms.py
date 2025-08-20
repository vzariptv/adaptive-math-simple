from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, EqualTo


class UpdateProfileForm(FlaskForm):
    first_name = StringField('Имя', validators=[Optional(), Length(max=50)])
    last_name = StringField('Фамилия', validators=[Optional(), Length(max=50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    submit_profile = SubmitField('Сохранить профиль')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтверждение', validators=[DataRequired(), EqualTo('new_password', message='Пароли должны совпадать')])
    submit_password = SubmitField('Обновить пароль')
