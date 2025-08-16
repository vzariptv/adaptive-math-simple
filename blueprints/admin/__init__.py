from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../../templates",   # если шаблоны лежат в /templates/admin/*.html
    static_folder="../../static"
)

# Регистрируем маршруты (важно импортировать после создания admin_bp)
from . import routes  # noqa: E402,F401
