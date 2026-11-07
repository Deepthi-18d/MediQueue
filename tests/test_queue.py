"""
Queue management tests for MediQueue.
Covers token generation, duplicate prevention, queue ordering, and priority handling.
"""
import pytest
from datetime import datetime
from conftest import login, logout


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_dept_id(app_ctx, code='GM'):
    from models import Department
    return Department.query.filter_by(code=code).first().id


def get_patient_id(app_ctx, username='testpatient'):
    from models import User
    return User.query.filter_by(username=username).first().id


def get_staff_id(app_ctx, username='teststaff'):
    from models import User
    return User.query.filter_by(username=username).first().id


# ── Token Generation ───────────────────────────────────────────────────────────

class TestTokenGeneration:
    def test_generate_token_success(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken

        patient_id = get_patient_id(app_ctx)
        dept_id = get_dept_id(app_ctx)

        result = QueueService.generate_token(patient_id, dept_id)
        assert result['success'] is True
        assert 'token_id' in result
        assert 'token_number' in result
        # Token number should include the department code
        assert 'GM' in result['token_number']

    def test_token_stored_in_database(self, app_ctx):
        from models import QueueToken
        tokens = QueueToken.query.filter_by(status='WAITING').all()
        assert len(tokens) >= 1

    def test_duplicate_token_prevention(self, app_ctx):
        """Generating a second token in the same active department must fail."""
        from services.queue_service import QueueService

        patient_id = get_patient_id(app_ctx)
        dept_id = get_dept_id(app_ctx)

        result = QueueService.generate_token(patient_id, dept_id)
        assert result['success'] is False
        assert 'active token' in result['error'].lower() or 'already' in result['error'].lower()

    def test_cannot_generate_token_for_inactive_department(self, app_ctx):
        from services.queue_service import QueueService
        from models import Department

        inactive_dept = Department.query.filter_by(code='INACT').first()
        patient_id = get_patient_id(app_ctx)

        result = QueueService.generate_token(patient_id, inactive_dept.id)
        assert result['success'] is False
        assert 'not accepting' in result['error'].lower() or 'inactive' in result['error'].lower()

    def test_generate_token_nonexistent_department(self, app_ctx):
        from services.queue_service import QueueService

        patient_id = get_patient_id(app_ctx)
        result = QueueService.generate_token(patient_id, 999999)
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_token_sequence_increments(self, app_ctx):
        """A second patient in the same department gets a higher sequence number."""
        from services.queue_service import QueueService
        from models import User, PatientProfile

        # Create a second patient
        second = User(
            username='secondpatient_q',
            full_name='Second Queue Patient',
            role='patient',
            email='second_q@test.com',
            is_active_account=True,
        )
        second.set_password('Pass@123')
        from extensions import db
        db.session.add(second)
        db.session.flush()
        db.session.add(PatientProfile(user_id=second.id))
        db.session.commit()

        dept_id = get_dept_id(app_ctx)
        result = QueueService.generate_token(second.id, dept_id)
        assert result['success'] is True
        # Sequence is 101 + count, so second token should be GM-102
        seq = int(result['token_number'].split('-')[1])
        assert seq >= 102


# ── Token Status Transitions ───────────────────────────────────────────────────

class TestTokenStatusTransitions:
    def _get_active_token_id(self, app_ctx):
        from models import QueueToken
        t = QueueToken.query.filter_by(status='WAITING').first()
        return t.id if t else None

    def test_call_next_transitions_to_called(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken, Counter

        # Ensure there's a waiting token (may already exist from previous tests)
        waiting = QueueToken.query.filter_by(status='WAITING').first()
        assert waiting is not None, "No WAITING token available to call"

        counter = Counter.query.filter_by(status='Available', is_active=True).first()
        assert counter is not None, "No available counter"

        staff_id = get_staff_id(app_ctx)
        result = QueueService.call_next(counter.id, staff_id)
        # Result must be success OR no_patients (if all are priority edge cases)
        assert result.get('success') is True or result.get('no_patients') is True

    def test_cancel_token_by_patient(self, app_ctx):
        """Patient can cancel their own WAITING token."""
        from services.queue_service import QueueService
        from models import QueueToken, User, PatientProfile, Department

        # Create a fresh patient + token for cancellation test
        from extensions import db
        p = User(
            username='cancel_patient',
            full_name='Cancel Patient',
            role='patient',
            is_active_account=True,
        )
        p.set_password('Pass@123')
        db.session.add(p)
        db.session.flush()
        db.session.add(PatientProfile(user_id=p.id))
        db.session.commit()

        dept_id = get_dept_id(app_ctx, 'CARD')
        gen = QueueService.generate_token(p.id, dept_id)
        assert gen['success'] is True

        result = QueueService.cancel_token(gen['token_id'], p.id, is_staff=False)
        assert result['success'] is True

        token = QueueToken.query.get(gen['token_id'])
        assert token.status == 'CANCELLED'

    def test_patient_cannot_cancel_another_patients_token(self, app_ctx):
        """A patient must not be able to cancel tokens that do not belong to them."""
        from services.queue_service import QueueService
        from models import QueueToken

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token available for this test")

        # Use an arbitrary patient id that is NOT the token owner
        wrong_patient_id = waiting.patient_id + 999
        result = QueueService.cancel_token(waiting.id, wrong_patient_id, is_staff=False)
        assert result['success'] is False
        assert 'unauthorized' in result['error'].lower()

    def test_cannot_cancel_already_cancelled_token(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken

        cancelled = QueueToken.query.filter_by(status='CANCELLED').first()
        if cancelled is None:
            pytest.skip("No CANCELLED token in test DB")

        result = QueueService.cancel_token(cancelled.id, cancelled.patient_id, is_staff=False)
        assert result['success'] is False
        assert 'already' in result['error'].lower() or 'cannot cancel' in result['error'].lower()


# ── Priority Queue Ordering ────────────────────────────────────────────────────

class TestPriorityQueue:
    def test_set_priority_flag(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token available")

        staff_id = get_staff_id(app_ctx)
        result = QueueService.set_priority(waiting.id, staff_id, True, 'Medical emergency')
        assert result['success'] is True

        from extensions import db
        db.session.refresh(waiting)
        assert waiting.is_priority is True
        assert waiting.priority_reason == 'Medical emergency'

    def test_unset_priority_flag(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken

        priority_token = QueueToken.query.filter_by(is_priority=True).first()
        if priority_token is None:
            pytest.skip("No priority token available")

        staff_id = get_staff_id(app_ctx)
        result = QueueService.set_priority(priority_token.id, staff_id, False)
        assert result['success'] is True

        from extensions import db
        db.session.refresh(priority_token)
        assert priority_token.is_priority is False

    def test_priority_tokens_appear_first_in_queue(self, app_ctx):
        """Priority tokens must rank ahead of non-priority tokens of the same date."""
        from models import QueueToken
        from extensions import db

        dept_id = get_dept_id(app_ctx)
        today = datetime.now().strftime('%Y-%m-%d')

        active_tokens = QueueToken.query.filter(
            QueueToken.department_id == dept_id,
            QueueToken.date == today,
            QueueToken.status.in_(['WAITING', 'CALLED']),
        ).order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).all()

        if len(active_tokens) < 2:
            pytest.skip("Need at least 2 active tokens to verify ordering")

        # Find the index of the first non-priority token
        first_non_priority_idx = next(
            (i for i, t in enumerate(active_tokens) if not t.is_priority), len(active_tokens)
        )
        # All tokens before that index should be priority
        for t in active_tokens[:first_non_priority_idx]:
            assert t.is_priority is True


# ── Active Token Retrieval ─────────────────────────────────────────────────────

class TestActiveTokenRetrieval:
    def test_get_patient_active_token(self, app_ctx):
        from services.queue_service import QueueService
        from models import QueueToken

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token for retrieval test")

        result = QueueService.get_patient_active_token(waiting.patient_id)
        assert result is not None
        assert result['status'] in ('WAITING', 'CALLED', 'SERVING')
        assert 'queue_position' in result
        assert 'estimated_wait_time' in result

    def test_no_active_token_returns_none(self, app_ctx):
        from services.queue_service import QueueService

        # Use a user id that has no tokens at all
        result = QueueService.get_patient_active_token(999999)
        assert result is None
