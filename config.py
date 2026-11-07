import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mediqueue-technovate2026-secret-key-prod')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(basedir, 'instance', 'mediqueue.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Hospital Defaults
    HOSPITAL_NAME = "MediQueue General Hospital"
    APP_NAME = "MediQueue"
    ADMIN_DISPLAY_NAME = "Hospital Super Admin"
    DEFAULT_SERVICE_TIME = 10  # minutes fallback
    
    DEPARTMENTS = [
        {"name": "General Medicine", "code": "GM", "description": "Primary healthcare, viral fevers, general adult ailments & consultations.", "default_service_time": 10},
        {"name": "Cardiology", "code": "CARD", "description": "Heart disease, hypertension, ECG checks, and cardiovascular wellness.", "default_service_time": 15},
        {"name": "Orthopaedics", "code": "ORTH", "description": "Bone fractures, joint disorders, sports injuries, and arthritis care.", "default_service_time": 12},
        {"name": "Paediatrics", "code": "PED", "description": "Child development, newborn wellness, pediatric infections & immunizations.", "default_service_time": 10},
        {"name": "Dermatology", "code": "DERM", "description": "Skin health, eczema, allergies, psoriasis, and cosmetic dermatology.", "default_service_time": 8},
        {"name": "Neurology", "code": "NEUR", "description": "Nervous system conditions, migraines, neuropathy, and stroke recovery.", "default_service_time": 20},
        {"name": "ENT (Otolaryngology)", "code": "ENT", "description": "Ear infections, nasal blockages, sinusitis, and throat ailments.", "default_service_time": 10},
        {"name": "Dental Surgery", "code": "DENT", "description": "Oral health, cavity fillings, tooth extractions, and dental cleanings.", "default_service_time": 15},
        {"name": "Ophthalmology", "code": "OPHT", "description": "Vision tests, cataract evaluation, eye infections, and optical care.", "default_service_time": 12}
    ]
