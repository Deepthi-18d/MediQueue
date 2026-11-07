from datetime import datetime
from sqlalchemy import func
from extensions import db
from models import QueueToken, ServiceRecord, Counter, Department, HospitalSetting

class WaitingTimeService:

    @staticmethod
    def get_department_avg_service_time(department_id):
        """
        Calculate actual average service duration for a department from completed ServiceRecords.
        Falls back to Department default_service_time, then Hospital default setting (10 mins).
        """
        # Query completed service records for this department
        avg_result = db.session.query(func.avg(ServiceRecord.duration_minutes))\
            .filter(ServiceRecord.department_id == department_id)\
            .scalar()

        if avg_result is not None and avg_result > 0:
            return round(float(avg_result), 1)

        # Fallback to department config
        dept = Department.query.get(department_id)
        if dept and dept.default_service_time:
            return float(dept.default_service_time)

        # Fallback to hospital global setting
        default_global = HospitalSetting.get_value('default_service_time', '10')
        try:
            return float(default_global)
        except ValueError:
            return 10.0

    @staticmethod
    def get_active_counters_count(department_id):
        """
        Count active counters operating in the department.
        Considers counters that are 'Available' or 'Busy' (i.e. staffed/open).
        """
        count = Counter.query.filter(
            Counter.department_id == department_id,
            Counter.is_active == True,
            Counter.status.in_(['Available', 'Busy'])
        ).count()

        return count if count > 0 else 1  # Avoid division by zero, min 1 for calculation

    @staticmethod
    def calculate_for_token(token_id):
        """
        Calculate waiting time and queue position for a specific token.
        Estimated Waiting Time = (Patients Ahead × Avg Service Duration) ÷ Active Counters.
        Respects clinical priority: Priority tokens are ahead of non-priority tokens.
        """
        token = QueueToken.query.get(token_id)
        if not token:
            return None

        # If already serving or completed
        if token.status == 'SERVING':
            return {
                'token_id': token.id,
                'token_number': token.token_number,
                'status': 'SERVING',
                'queue_position': 0,
                'patients_ahead': 0,
                'estimated_wait_time': 0,
                'avg_service_time': WaitingTimeService.get_department_avg_service_time(token.department_id),
                'active_counters': WaitingTimeService.get_active_counters_count(token.department_id),
                'is_serving': True,
                'disclaimer': 'Patient is currently being attended by clinical staff at counter.'
            }

        if token.status in ['COMPLETED', 'CANCELLED', 'NOSHOW']:
            return {
                'token_id': token.id,
                'token_number': token.token_number,
                'status': token.status,
                'queue_position': 0,
                'patients_ahead': 0,
                'estimated_wait_time': 0,
                'avg_service_time': 0,
                'active_counters': 0,
                'is_serving': False,
                'disclaimer': f'Token is {token.status.lower()}. No active queue position.'
            }

        # For WAITING or CALLED tokens
        dept_id = token.department_id
        today = token.date

        # Fetch all active tokens in queue today for this department
        # Priority order: is_priority DESC, created_at ASC
        active_tokens = QueueToken.query.filter(
            QueueToken.department_id == dept_id,
            QueueToken.date == today,
            QueueToken.status.in_(['WAITING', 'CALLED'])
        ).order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).all()

        # Find position of current token in the ordered queue
        patients_ahead = 0
        queue_pos = 1
        for idx, t in enumerate(active_tokens):
            if t.id == token.id:
                queue_pos = idx + 1
                patients_ahead = idx
                break

        avg_duration = WaitingTimeService.get_department_avg_service_time(dept_id)
        active_counters = WaitingTimeService.get_active_counters_count(dept_id)

        # Smart formula
        raw_est = (patients_ahead * avg_duration) / float(active_counters)
        estimated_minutes = max(1, round(raw_est)) if patients_ahead > 0 else 2

        # Check currently serving token at counter
        currently_serving_token = QueueToken.query.filter(
            QueueToken.department_id == dept_id,
            QueueToken.date == today,
            QueueToken.status == 'SERVING'
        ).first()

        return {
            'token_id': token.id,
            'token_number': token.token_number,
            'status': token.status,
            'department_id': dept_id,
            'department_name': token.department.name if token.department else 'General',
            'department_code': token.department.code if token.department else 'GEN',
            'queue_position': queue_pos,
            'patients_ahead': patients_ahead,
            'estimated_wait_time': estimated_minutes,
            'avg_service_time': avg_duration,
            'active_counters': active_counters,
            'is_serving': False,
            'is_priority': token.is_priority,
            'priority_reason': token.priority_reason,
            'currently_serving_token': currently_serving_token.token_number if currently_serving_token else 'None',
            'disclaimer': 'Estimated wait times are dynamically calculated based on current queue load and clinical service averages. Emergency triages may affect schedules.'
        }
