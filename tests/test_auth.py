"""
Authentication tests for MediQueue.
Covers registration, login, logout, duplicate prevention, and role-based redirects.
"""
import pytest
from conftest import login, logout


# ── Registration ───────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_page_loads(self, client):
        resp = client.get('/register')
        assert resp.status_code == 200
        assert b'Register' in resp.data or b'register' in resp.data.lower()

    def test_successful_registration(self, client, app_ctx):
        resp = client.post('/register', data={
            'username': 'newpatient',
            'password': 'NewPass1!',
            'confirm_password': 'NewPass1!',
            'full_name': 'New Patient',
            'email': 'newpatient@test.com',
            'phone': '9876543210',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # After registration the user is logged in and redirected to patient dashboard
        assert b'dashboard' in resp.data.lower() or b'patient' in resp.data.lower()

    def test_duplicate_username_rejected(self, client):
        resp = client.post('/register', data={
            'username': 'testpatient',   # already seeded
            'password': 'NewPass1!',
            'confirm_password': 'NewPass1!',
            'full_name': 'Duplicate User',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'taken' in resp.data.lower() or b'already' in resp.data.lower()

    def test_duplicate_email_rejected(self, client):
        resp = client.post('/register', data={
            'username': 'uniqueuser99',
            'password': 'NewPass1!',
            'confirm_password': 'NewPass1!',
            'full_name': 'Unique User',
            'email': 'patient@test.com',  # already seeded
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'registered' in resp.data.lower() or b'already' in resp.data.lower()

    def test_mismatched_passwords_rejected(self, client):
        resp = client.post('/register', data={
            'username': 'mismatch_user',
            'password': 'Pass1!',
            'confirm_password': 'Different!',
            'full_name': 'Mismatch User',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'do not match' in resp.data.lower() or b'mismatch' in resp.data.lower()

    def test_short_password_rejected(self, client):
        resp = client.post('/register', data={
            'username': 'shortpass_user',
            'password': 'ab',
            'confirm_password': 'ab',
            'full_name': 'Short Pass User',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'6 character' in resp.data.lower() or b'at least' in resp.data.lower()

    def test_missing_required_fields_rejected(self, client):
        resp = client.post('/register', data={
            'username': '',
            'password': '',
            'confirm_password': '',
            'full_name': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'required' in resp.data.lower()


# ── Login ──────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'login' in resp.data.lower()

    def test_patient_login_redirects_to_patient_dashboard(self, client):
        resp = login(client, 'testpatient', 'Patient@123')
        assert resp.status_code == 200
        assert b'patient' in resp.data.lower() or b'dashboard' in resp.data.lower()
        logout(client)

    def test_staff_login_redirects_to_staff_dashboard(self, client):
        resp = login(client, 'teststaff', 'Staff@123')
        assert resp.status_code == 200
        assert b'staff' in resp.data.lower() or b'dashboard' in resp.data.lower()
        logout(client)

    def test_admin_login_redirects_to_admin_dashboard(self, client):
        resp = login(client, 'testadmin', 'Admin@123')
        assert resp.status_code == 200
        assert b'admin' in resp.data.lower() or b'dashboard' in resp.data.lower()
        logout(client)

    def test_wrong_password_rejected(self, client):
        resp = login(client, 'testpatient', 'WrongPassword!')
        assert resp.status_code == 200
        assert b'invalid' in resp.data.lower()

    def test_nonexistent_user_rejected(self, client):
        resp = login(client, 'nobody_xyz', 'any_password')
        assert resp.status_code == 200
        assert b'invalid' in resp.data.lower()

    def test_inactive_account_rejected(self, client):
        resp = login(client, 'inactivepatient', 'Patient@123')
        assert resp.status_code == 200
        assert b'deactivated' in resp.data.lower() or b'contact' in resp.data.lower()

    def test_empty_credentials_rejected(self, client):
        resp = client.post('/login', data={'username': '', 'password': ''},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b'required' in resp.data.lower()

    def test_login_by_email(self, client):
        """Users can log in with their email address instead of username."""
        resp = login(client, 'patient@test.com', 'Patient@123')
        assert resp.status_code == 200
        assert b'dashboard' in resp.data.lower() or b'patient' in resp.data.lower()
        logout(client)


# ── Logout ─────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_redirects_to_login(self, client):
        login(client, 'testpatient', 'Patient@123')
        resp = logout(client)
        assert resp.status_code == 200
        assert b'login' in resp.data.lower() or b'sign' in resp.data.lower()

    def test_unauthenticated_logout_does_not_error(self, client):
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
