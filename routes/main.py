from flask import Blueprint, render_template
from models import Department, Counter, QueueToken, HospitalSetting
from services.waiting_time_service import WaitingTimeService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Public landing page & live hospital queue display board."""
    departments = Department.query.filter_by(is_active=True).all()
    dept_summaries = []

    for d in departments:
        waiting = QueueToken.query.filter_by(department_id=d.id, status='WAITING').count()
        serving_token = QueueToken.query.filter_by(department_id=d.id, status='SERVING').first()
        active_counters = WaitingTimeService.get_active_counters_count(d.id)
        avg_time = WaitingTimeService.get_department_avg_service_time(d.id)
        est_wait = round((waiting * avg_time) / float(active_counters)) if waiting > 0 else 0

        dept_summaries.append({
            'department_id': d.id,
            'department_name': d.name,
            'department_code': d.code,
            'description': d.description,
            'waiting_count': waiting,
            'currently_serving': serving_token.token_number if serving_token else '--',
            'active_counters': active_counters,
            'avg_service_time': avg_time,
            'estimated_wait_time': est_wait
        })

    # Total hospital stats
    total_waiting = QueueToken.query.filter_by(status='WAITING').count()
    currently_serving = QueueToken.query.filter_by(status='SERVING').count()
    completed_today = QueueToken.query.filter_by(status='COMPLETED').count()
    active_counters_total = Counter.query.filter(Counter.is_active == True, Counter.status.in_(['Available', 'Busy'])).count()

    summary = {
        'total_waiting': total_waiting,
        'currently_serving': currently_serving,
        'completed_today': completed_today,
        'active_counters': active_counters_total
    }

    return render_template('index.html', departments=departments, dept_summaries=dept_summaries, summary=summary)
