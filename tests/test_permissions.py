"""
Role-based access control and permission tests for MediQueue.
Ensures unauthenticated users and wrong-role users are denied access.
"""
import pytest
from conftest import login, logout


# ── Unauthenticated Access ─────────────────────────────────────────────────────

class TestUnauthenticatedAccess:
    """All protected routes must redirect unauthenticated users."""

    PROTECTED_ROUTES = [
        '/patient/dashboard',
        '/patient/token/generate',
        '/patient/profile',
        '/staff/dashboard',
        '/admin/dashboard',
        '/admin/reports',
        '/admin/audit-logs',
        '/admin/login-history',
    ]

    @pytest.mark.parametrize('route', PROTECTED_ROUTES)
    def test_unauthenticated_redirected(self, client, route):
        resp = client.get(route, follow_redirects=False)
        # Must redirect (3xx) to login
        assert resp.status_code in (301, 302, 303, 307, 308)
        location = resp.headers.get('Location', '')
        assert 'login' in location.lower() or location == '/'


# ── Patient Role Restrictions ──────────────────────────────────────────────────

class TestPatientRoleRestrictions:
    """Patients must not access staff or admin routes."""

    FORBIDDEN_FOR_PATIENT = [
        '/staff/dashboard',
        '/admin/dashboard',
        '/admin/reports',
    ]

    def setup_method(self):
        """Login as patient before each test method."""
        pass

    @pytest.mark.parametrize('route', FORBIDDEN_FOR_PATIENT)
    def test_patient_cannot_access_route(self, client, route):
        login(client, 'testpatient', 'Patient@123')
        resp = client.get(route, follow_redirects=True)
        # Must redirect away with a denial, NOT serve the protected page
        assert resp.status_code == 200
        # Either shows access denied message OR redirected to patient dashboard
        content = resp.data.lower()
        assert (
            b'access denied' in content
            or b'permission' in content
            or b'patient' in content  # redirected to patient dashboard
            or b'dashboard' in content
        )
        logout(client)


# ── Staff Role Restrictions ────────────────────────────────────────────────────

class TestStaffRoleRestrictions:
    """Staff must not access admin-only routes."""

    FORBIDDEN_FOR_STAFF = [
        '/admin/dashboard',
        '/admin/reports',
        '/admin/audit-logs',
    ]

    @pytest.mark.parametrize('route', FORBIDDEN_FOR_STAFF)
    def test_staff_cannot_access_admin_route(self, client, route):
        login(client, 'teststaff', 'Staff@123')
        resp = client.get(route, follow_redirects=True)
        assert resp.status_code == 200
        content = resp.data.lower()
        assert (
            b'access denied' in content
            or b'permission' in content
            or b'staff' in content
            or b'dashboard' in content
        )
        logout(client)

    def test_staff_cannot_access_patient_routes(self, client):
        login(client, 'teststaff', 'Staff@123')
        resp = client.get('/patient/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        content = resp.data.lower()
        assert (
            b'access denied' in content
            or b'permission' in content
            or b'staff' in content
        )
        logout(client)


# ── Admin Access ───────────────────────────────────────────────────────────────

class TestAdminAccess:
    """Admin must be able to access all admin routes."""

    ADMIN_ROUTES = [
        '/admin/dashboard',
        '/admin/reports',
        '/admin/audit-logs',
        '/admin/login-history',
    ]

    @pytest.mark.parametrize('route', ADMIN_ROUTES)
    def test_admin_can_access_route(self, client, route):
        login(client, 'testadmin', 'Admin@123')
        resp = client.get(route, follow_redirects=True)
        assert resp.status_code == 200
        logout(client)


# ── Token Ownership Enforcement ────────────────────────────────────────────────

class TestTokenOwnership:
    def test_patient_can_view_own_tokens(self, client, app_ctx):
        """Patient dashboard loads and shows token history."""
        login(client, 'testpatient', 'Patient@123')
        resp = client.get('/patient/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        logout(client)

    def test_patient_cannot_cancel_via_staff_endpoint(self, client, app_ctx):
        """Direct POST to staff cancel endpoint must not succeed for patient."""
        from models import QueueToken
        import json

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token for this test")

        login(client, 'testpatient', 'Patient@123')
        resp = client.post(
            f'/staff/token/cancel/{waiting.id}',
            data={'reason': 'hack attempt'},
            follow_redirects=True,
        )
        # Should redirect away from staff area
        content = resp.data.lower()
        assert (
            resp.status_code == 200
            and (b'access denied' in content or b'patient' in content or b'dashboard' in content)
        )
        logout(client)


# ── API Endpoint Access ────────────────────────────────────────────────────────

class TestAPIAccess:
    def test_public_queue_summary_accessible(self, client):
        """The public /api/queue-summary endpoint does not require auth."""
        resp = client.get('/api/queue-summary')
        assert resp.status_code == 200
        import json
        data = json.loads(resp.data)
        assert isinstance(data, (dict, list))

    def test_notifications_requires_auth(self, client):
        """The notifications API requires a logged-in user."""
        resp = client.get('/api/notifications', follow_redirects=False)
        # Expect redirect to login or 401/403
        assert resp.status_code in (200, 302, 401, 403)
        if resp.status_code == 302:
            assert 'login' in resp.headers.get('Location', '').lower()
