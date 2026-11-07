from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Department, Counter, QueueToken, StaffProfile, AuditLog
from routes.auth import role_required
from services.queue_service import QueueService
from services.waiting_time_service import WaitingTimeService

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.route('/dashboard')
@role_required('staff')
def dashboard():
    """Clinical staff console for queue servicing, counter management, and patient triage."""
    staff_profile = current_user.staff_profile
    user_dept_id = staff_profile.department_id if staff_profile and staff_profile.department_id else 1

    # Selected department filter
    dept_id = request.args.get('dept_id', default=user_dept_id, type=int)
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'WAITING').strip()

    departments = Department.query.filter_by(is_active=True).all()
    current_dept = Department.query.get(dept_id) or (departments[0] if departments else None)

    if not current_dept:
        flash("No active departments available.", "warning")
        return redirect(url_for('main.index'))

    today = datetime.now().strftime('%Y-%m-%d')

    # Counters for current department
    counters = Counter.query.filter_by(department_id=current_dept.id, is_active=True).all()

    # Find staff's counter
    user_counter = None
    for c in counters:
        if c.assigned_staff_id == current_user.id:
            user_counter = c
            break
    if not user_counter and counters:
        user_counter = counters[0]

    # Active serving token for this staff's counter
    serving_token = None
    if user_counter and user_counter.current_token_id:
        serving_token = QueueToken.query.get(user_counter.current_token_id)

    # Queue query with optional search & status filter
    queue_query = QueueToken.query.filter(
        QueueToken.department_id == current_dept.id,
        QueueToken.date == today
    )

    if status_filter and status_filter != 'ALL':
        queue_query = queue_query.filter(QueueToken.status == status_filter)

    if search_query:
        queue_query = queue_query.join(QueueToken.patient).filter(
            (QueueToken.token_number.ilike(f"%{search_query}%")) |
            (QueueToken.patient.has(full_name=search_query))
        )

    # Order: Priority first, then created_at
    queue = queue_query.order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).all()

    # Summary metrics for current department today
    total_waiting = QueueToken.query.filter_by(department_id=current_dept.id, date=today, status='WAITING').count()
    total_serving = QueueToken.query.filter_by(department_id=current_dept.id, date=today, status='SERVING').count()
    total_completed = QueueToken.query.filter_by(department_id=current_dept.id, date=today, status='COMPLETED').count()
    total_cancelled = QueueToken.query.filter(
        QueueToken.department_id == current_dept.id,
        QueueToken.date == today,
        QueueToken.status.in_(['CANCELLED', 'NOSHOW'])
    ).count()

    # Recent staff activity logs
    recent_logs = AuditLog.query.filter_by(user_id=current_user.id)\
        .order_by(AuditLog.created_at.desc())\
        .limit(10).all()

    return render_template(
        'staff/dashboard.html',
        departments=departments,
        current_dept=current_dept,
        counters=counters,
        user_counter=user_counter,
        serving_token=serving_token,
        queue=queue,
        search_query=search_query,
        status_filter=status_filter,
        total_waiting=total_waiting,
        total_serving=total_serving,
        total_completed=total_completed,
        total_cancelled=total_cancelled,
        recent_logs=recent_logs
    )


@staff_bp.route('/call_next', methods=['POST'])
@role_required('staff')
def call_next():
    """Call next patient to counter."""
    counter_id = request.form.get('counter_id', type=int)
    department_id = request.form.get('department_id', type=int)
    target_token_id = request.form.get('target_token_id', type=int)

    if not counter_id or not department_id:
        flash("Counter and department are required.", "danger")
        return redirect(url_for('staff.dashboard'))

    result = QueueService.call_next_patient(
        staff_id=current_user.id,
        counter_id=counter_id,
        department_id=department_id,
        target_token_id=target_token_id
    )

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "warning")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/start_serving', methods=['POST'])
@role_required('staff')
def start_serving():
    """Staff begins consultation."""
    token_id = request.form.get('token_id', type=int)
    department_id = request.form.get('department_id', type=int)

    result = QueueService.start_serving(token_id=token_id, staff_id=current_user.id)
    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/complete', methods=['POST'])
@role_required('staff')
def complete():
    """Staff marks consultation completed."""
    token_id = request.form.get('token_id', type=int)
    counter_id = request.form.get('counter_id', type=int)
    department_id = request.form.get('department_id', type=int)
    notes = request.form.get('notes', '').strip()

    result = QueueService.complete_service(
        token_id=token_id,
        staff_id=current_user.id,
        counter_id=counter_id,
        notes=notes
    )

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/noshow', methods=['POST'])
@role_required('staff')
def noshow():
    """Staff marks patient as no-show."""
    token_id = request.form.get('token_id', type=int)
    department_id = request.form.get('department_id', type=int)

    result = QueueService.mark_noshow(token_id=token_id, staff_id=current_user.id)
    if result["success"]:
        flash(result["message"], "info")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/cancel', methods=['POST'])
@role_required('staff')
def cancel():
    """Staff cancels a token with clinical reason."""
    token_id = request.form.get('token_id', type=int)
    department_id = request.form.get('department_id', type=int)
    reason = request.form.get('reason', 'Cancelled by clinical staff triage').strip()

    result = QueueService.cancel_token(
        token_id=token_id,
        user_id=current_user.id,
        is_staff=True,
        reason=reason
    )

    if result["success"]:
        flash(result["message"], "info")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/priority', methods=['POST'])
@role_required('staff')
def toggle_priority():
    """Flag or unflag priority for a patient."""
    token_id = request.form.get('token_id', type=int)
    department_id = request.form.get('department_id', type=int)
    is_priority = request.form.get('is_priority', '1') == '1'
    reason = request.form.get('priority_reason', '').strip()

    if is_priority and not reason:
        reason = "Clinical triage assessment - acute symptom priority"

    result = QueueService.set_priority(
        token_id=token_id,
        staff_id=current_user.id,
        is_priority=is_priority,
        reason=reason
    )

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))


@staff_bp.route('/counter_status', methods=['POST'])
@role_required('staff')
def counter_status():
    """Toggle counter status between Available, Busy, Offline."""
    counter_id = request.form.get('counter_id', type=int)
    department_id = request.form.get('department_id', type=int)
    status = request.form.get('status', '').strip()

    result = QueueService.set_counter_status(
        counter_id=counter_id,
        staff_id=current_user.id,
        status=status
    )

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('staff.dashboard', dept_id=department_id))
