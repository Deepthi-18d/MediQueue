from routes.main import main_bp
from routes.auth import auth_bp
from routes.patient import patient_bp
from routes.staff import staff_bp
from routes.admin import admin_bp
from routes.api import api_bp

__all__ = [
    'main_bp',
    'auth_bp',
    'patient_bp',
    'staff_bp',
    'admin_bp',
    'api_bp'
]
