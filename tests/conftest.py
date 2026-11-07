"""
Pytest configuration and fixtures for MediQueue test suite.
Provides an isolated in-memory SQLite test database and test client.
"""
import pytest
import sys
import os

# Ensure project root is on the Python path so imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from extensions import db as _db
from models import User, Department, Counter, PatientProfile, StaffProfile


@pytest.fixture(scope='session')
def app():
    """Create an application instance configured for testing."""
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret-key-mediqueue',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': None,
    }
    application = create_app(test_config)
    return application


@pytest.fixture(scope='session')
def db(app):
    """Create all database tables in the in-memory database once per session."""
    with app.app_context():
        _db.create_all()
        _seed_test_data()
        yield _db
        _db.drop_all()


@pytest.fixture
def client(app, db):
    """Return a test HTTP client. Each test starts with a fresh request context."""
    with app.test_client() as c:
        with app.app_context():
            yield c


@pytest.fixture
def app_ctx(app, db):
    """Provide an active application context for service-layer tests."""
    with app.app_context():
        yield app


def _seed_test_data():
    """Seed minimal data required for the test suite."""
    from models import HospitalSetting

    # Departments
    dept_gm = Department(
        name='General Medicine',
        code='GM',
        description='General consultations',
        is_active=True,
        default_service_time=10,
    )
    dept_card = Department(
        name='Cardiology',
        code='CARD',
        description='Heart specialists',
        is_active=True,
        default_service_time=15,
    )
    dept_inactive = Department(
        name='Inactive Dept',
        code='INACT',
        description='Closed department',
        is_active=False,
        default_service_time=10,
    )
    _db.session.add_all([dept_gm, dept_card, dept_inactive])
    _db.session.flush()

    # Counters
    counter1 = Counter(
        name='Counter 1',
        code='GM-C1',
        department_id=dept_gm.id,
        is_active=True,
        status='Available',
    )
    counter2 = Counter(
        name='Counter 2',
        code='GM-C2',
        department_id=dept_gm.id,
        is_active=True,
        status='Available',
    )
    _db.session.add_all([counter1, counter2])
    _db.session.flush()

    # Admin user
    admin = User(
        username='testadmin',
        full_name='Test Admin',
        role='admin',
        email='admin@test.com',
        is_active_account=True,
        must_change_password=False,
    )
    admin.set_password('Admin@123')
    _db.session.add(admin)
    _db.session.flush()

    # Staff user
    staff = User(
        username='teststaff',
        full_name='Test Staff',
        role='staff',
        email='staff@test.com',
        is_active_account=True,
        must_change_password=False,
    )
    staff.set_password('Staff@123')
    _db.session.add(staff)
    _db.session.flush()

    staff_profile = StaffProfile(
        user_id=staff.id,
        department_id=dept_gm.id,
        assigned_counter_id=counter1.id,
        designation='Clinical Specialist',
        is_available=True,
    )
    _db.session.add(staff_profile)

    # Patient user
    patient = User(
        username='testpatient',
        full_name='Test Patient',
        role='patient',
        email='patient@test.com',
        is_active_account=True,
        must_change_password=False,
    )
    patient.set_password('Patient@123')
    _db.session.add(patient)
    _db.session.flush()

    patient_profile = PatientProfile(user_id=patient.id)
    _db.session.add(patient_profile)

    # Inactive patient account
    inactive_patient = User(
        username='inactivepatient',
        full_name='Inactive Patient',
        role='patient',
        email='inactive@test.com',
        is_active_account=False,
        must_change_password=False,
    )
    inactive_patient.set_password('Patient@123')
    _db.session.add(inactive_patient)

    # Hospital settings
    _db.session.add(HospitalSetting(key='hospital_name', value='Test Hospital'))
    _db.session.add(HospitalSetting(key='app_name', value='MediQueue Test'))
    _db.session.add(HospitalSetting(key='default_service_time', value='10'))

    _db.session.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

def login(client, username, password):
    """POST to /login and return the response."""
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def logout(client):
    """GET /logout."""
    return client.get('/logout', follow_redirects=True)
