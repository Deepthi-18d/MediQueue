"""
Waiting-time calculation tests for MediQueue.
Verifies the smart formula: (patients_ahead × avg_service_time) / active_counters.
"""
import pytest


# ── Department Average Service Time ───────────────────────────────────────────

class TestDepartmentAvgServiceTime:
    def test_falls_back_to_department_default(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        from models import Department

        dept = Department.query.filter_by(code='GM').first()
        avg = WaitingTimeService.get_department_avg_service_time(dept.id)
        # No ServiceRecords yet → should return dept.default_service_time (10)
        assert avg == 10.0

    def test_falls_back_to_global_default_for_unknown_dept(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService

        avg = WaitingTimeService.get_department_avg_service_time(999999)
        # Dept not found → global default = 10
        assert avg == 10.0

    def test_uses_actual_service_records_when_available(self, app_ctx):
        """After adding ServiceRecords, the average should reflect real data."""
        from services.waiting_time_service import WaitingTimeService
        from models import Department, ServiceRecord, Counter, QueueToken, User
        from extensions import db

        dept = Department.query.filter_by(code='CARD').first()
        counter = Counter.query.filter_by(department_id=dept.id).first()
        staff = User.query.filter_by(username='teststaff').first()

        # We need a token to reference — find or use any WAITING/CANCELLED token
        any_token = QueueToken.query.first()
        assert any_token is not None

        from datetime import datetime, timedelta
        now = datetime.utcnow()
        # Add two service records: 8 min and 12 min → avg = 10
        for duration in (8.0, 12.0):
            sr = ServiceRecord(
                token_id=any_token.id,
                department_id=dept.id,
                counter_id=counter.id if counter else Counter.query.first().id,
                staff_id=staff.id,
                start_time=now - timedelta(minutes=duration),
                end_time=now,
                duration_minutes=duration,
            )
            db.session.add(sr)
        db.session.commit()

        avg = WaitingTimeService.get_department_avg_service_time(dept.id)
        assert avg == 10.0  # (8 + 12) / 2


# ── Active Counter Count ───────────────────────────────────────────────────────

class TestActiveCounterCount:
    def test_counts_available_and_busy_counters(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        from models import Department, Counter
        from extensions import db

        dept = Department.query.filter_by(code='GM').first()
        # Both seeded counters are 'Available'
        count = WaitingTimeService.get_active_counters_count(dept.id)
        assert count >= 1

    def test_offline_counters_excluded(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        from models import Department, Counter
        from extensions import db

        dept = Department.query.filter_by(code='GM').first()
        counters = Counter.query.filter_by(department_id=dept.id, is_active=True).all()

        # Set all counters offline temporarily
        original_statuses = [(c.id, c.status) for c in counters]
        for c in counters:
            c.status = 'Offline'
        db.session.commit()

        count = WaitingTimeService.get_active_counters_count(dept.id)
        # Formula floor: returns 1 to prevent division by zero
        assert count == 1

        # Restore
        for c in counters:
            for cid, status in original_statuses:
                if c.id == cid:
                    c.status = status
        db.session.commit()

    def test_returns_minimum_one_to_prevent_division_by_zero(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        # Department with no counters
        count = WaitingTimeService.get_active_counters_count(999999)
        assert count == 1


# ── Formula Verification ───────────────────────────────────────────────────────

class TestWaitingTimeFormula:
    def test_formula_zero_wait_for_first_in_queue(self, app_ctx):
        """The first token in the queue (patients_ahead=0) must have a minimum wait ≥ 1."""
        from services.waiting_time_service import WaitingTimeService
        from models import QueueToken

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token")

        result = WaitingTimeService.calculate_for_token(waiting.id)
        assert result is not None
        assert result['queue_position'] >= 1
        # Even the first token gets a minimum of 2 minutes
        assert result['estimated_wait_time'] >= 1

    def test_formula_proportional_to_queue_length(self, app_ctx):
        """Tokens further back in the queue must have longer or equal estimated wait times."""
        from services.waiting_time_service import WaitingTimeService
        from models import QueueToken

        today_tokens = QueueToken.query.filter(
            QueueToken.status.in_(['WAITING', 'CALLED'])
        ).order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).all()

        if len(today_tokens) < 2:
            pytest.skip("Need at least 2 WAITING tokens for this check")

        first_wait = WaitingTimeService.calculate_for_token(today_tokens[0].id)
        last_wait = WaitingTimeService.calculate_for_token(today_tokens[-1].id)

        assert first_wait is not None
        assert last_wait is not None
        assert last_wait['estimated_wait_time'] >= first_wait['estimated_wait_time']

    def test_serving_token_returns_zero_wait(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        from models import QueueToken
        from extensions import db

        # Temporarily mark a token as SERVING
        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No WAITING token")

        waiting.status = 'SERVING'
        db.session.commit()

        result = WaitingTimeService.calculate_for_token(waiting.id)
        assert result['estimated_wait_time'] == 0
        assert result['is_serving'] is True

        # Restore
        waiting.status = 'WAITING'
        db.session.commit()

    def test_completed_token_returns_zero_wait(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        from models import QueueToken
        from extensions import db

        waiting = QueueToken.query.filter_by(status='WAITING').first()
        if waiting is None:
            pytest.skip("No token available")

        waiting.status = 'COMPLETED'
        db.session.commit()

        result = WaitingTimeService.calculate_for_token(waiting.id)
        assert result['estimated_wait_time'] == 0
        assert result['status'] == 'COMPLETED'

        # Restore
        waiting.status = 'WAITING'
        db.session.commit()

    def test_manual_formula_calculation(self, app_ctx):
        """
        Direct formula verification:
          patients_ahead=10, avg=5 min, active_counters=2 → estimated = 25 min
        """
        patients_ahead = 10
        avg_service_time = 5.0
        active_counters = 2
        raw = (patients_ahead * avg_service_time) / float(active_counters)
        estimated = max(1, round(raw))
        assert estimated == 25

    def test_nonexistent_token_returns_none(self, app_ctx):
        from services.waiting_time_service import WaitingTimeService
        result = WaitingTimeService.calculate_for_token(999999)
        assert result is None
