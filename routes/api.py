from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Department, Counter, QueueToken, Notification
from services.queue_service import QueueService
from services.waiting_time_service import WaitingTimeService
from services.analytics_service import AnalyticsService
from services.notification_service import NotificationService

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/queue/summary')
def queue_summary():
    """Live public hospital queue display data."""
    departments = Department.query.filter_by(is_active=True).all()
    summary = []

    for d in departments:
        waiting = QueueToken.query.filter_by(department_id=d.id, status='WAITING').count()
        serving_token = QueueToken.query.filter_by(department_id=d.id, status='SERVING').first()
        active_counters = WaitingTimeService.get_active_counters_count(d.id)
        avg_time = WaitingTimeService.get_department_avg_service_time(d.id)
        est_wait = round((waiting * avg_time) / float(active_counters)) if waiting > 0 else 0

        summary.append({
            'department_id': d.id,
            'department_name': d.name,
            'department_code': d.code,
            'waiting_count': waiting,
            'currently_serving': serving_token.token_number if serving_token else '--',
            'active_counters': active_counters,
            'avg_service_time': avg_time,
            'estimated_wait_time': est_wait
        })

    return jsonify({'success': True, 'departments': summary})


@api_bp.route('/queue/department/<int:dept_id>')
def department_queue(dept_id):
    """Department specific queue and counters for real-time boards."""
    dept = Department.query.get_or_404(dept_id)
    tokens = QueueToken.query.filter_by(department_id=dept.id, status='WAITING')\
        .order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).all()
    counters = Counter.query.filter_by(department_id=dept.id, is_active=True).all()

    token_list = [{
        'id': t.id,
        'token_number': t.token_number,
        'is_priority': t.is_priority,
        'priority_reason': t.priority_reason,
        'created_at': t.created_at.strftime('%H:%M:%S')
    } for t in tokens]

    counter_list = [{
        'id': c.id,
        'name': c.name,
        'status': c.status,
        'staff_name': c.assigned_staff.full_name if c.assigned_staff else 'Unassigned'
    } for c in counters]

    return jsonify({
        'success': True,
        'department': {'id': dept.id, 'name': dept.name, 'code': dept.code},
        'queue': token_list,
        'counters': counter_list
    })


@api_bp.route('/patient/active_token')
@login_required
def patient_active_token():
    """Live poll endpoint for patient dashboard."""
    token = QueueService.get_patient_active_token(current_user.id)
    return jsonify({'success': True, 'token': token})


@api_bp.route('/admin/data')
@login_required
def admin_data():
    """Live KPI updates for admin dashboard."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    data = AnalyticsService.get_admin_dashboard_data()
    return jsonify({'success': True, 'data': data})


@api_bp.route('/notifications')
@login_required
def get_notifications():
    """Fetch notifications for current user."""
    notifs = NotificationService.get_user_notifications(current_user.id)
    unread_count = NotificationService.get_unread_count(current_user.id)
    return jsonify({
        'success': True,
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifs]
    })


@api_bp.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark single notification read."""
    success = NotificationService.mark_as_read(notif_id, current_user.id)
    return jsonify({'success': success})


@api_bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications read."""
    success = NotificationService.mark_all_as_read(current_user.id)
    return jsonify({'success': success})
