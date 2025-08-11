from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from datetime import datetime
from extensions import db
from . import auth_bp
from .forms import LoginForm, RegistrationForm
from models import User

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user or not user.check_password(form.password.data):
            flash("Неверный логин или пароль", "error")
            return redirect(url_for(".login"))

        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=form.remember.data)
        flash("Добро пожаловать!", "success")
        next_url = request.args.get("next") or url_for("main.dashboard")
        return redirect(next_url)

    return render_template("auth/login.html", form=form)

@auth_bp.get("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Вы вышли из системы", "info")
    return redirect(url_for(".login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Пользователь с таким именем уже существует", "error")
            return redirect(url_for(".register"))

        if User.query.filter_by(email=form.email.data).first():
            flash("Пользователь с таким email уже существует", "error")
            return redirect(url_for(".register"))

        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Регистрация прошла успешно! Теперь войдите в систему.", "success")
        return redirect(url_for("auth.login"))
    else:
        # Debug: show validation errors
        if request.method == 'POST':
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле {field}: {error}", "error")

    return render_template("auth/register.html", form=form)