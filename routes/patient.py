from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Department, QueueToken, PatientProfile, User, AuditLog
from routes.auth import role_required
from services.queue_service import QueueService
from services.waiting_time_service import WaitingTimeService

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

@patient_bp.route('/dashboard')
@role_required('patient')
def dashboard():
    """Patient dashboard showing active token tracker, book token section, department status, and history."""
    patient_id = current_user.id
    departments = Department.query.filter_by(is_active=True).all()
    active_token = QueueService.get_patient_active_token(patient_id)

    # Total completed visits
    total_visits = QueueToken.query.filter_by(patient_id=patient_id, status='COMPLETED').count()

    # Department queue summaries for quick glance
    dept_summaries = []
    for d in departments:
        waiting_count = QueueToken.query.filter_by(
            department_id=d.id,
            status='WAITING'
        ).count()
        active_counters = WaitingTimeService.get_active_counters_count(d.id)
        avg_time = WaitingTimeService.get_department_avg_service_time(d.id)
        est_wait = round((waiting_count * avg_time) / float(active_counters)) if waiting_count > 0 else 0

        dept_summaries.append({
            'id': d.id,
            'name': d.name,
            'code': d.code,
            'description': d.description,
            'waiting_count': waiting_count,
            'active_counters': active_counters,
            'avg_service_time': avg_time,
            'est_wait': est_wait
        })

    # Recent token history
    history = QueueToken.query.filter_by(patient_id=patient_id)\
        .order_by(QueueToken.created_at.desc())\
        .limit(10).all()

    return render_template(
        'patient/dashboard.html',
        active_token=active_token,
        departments=departments,
        dept_summaries=dept_summaries,
        total_visits=total_visits,
        history=history
    )


@patient_bp.route('/token/generate', methods=['POST'])
@role_required('patient')
def generate_token():
    """Book a new queue token."""
    dept_id = request.form.get('department_id', type=int)
    if not dept_id:
        flash("Please select a department.", "warning")
        return redirect(url_for('patient.dashboard'))

    result = QueueService.generate_token(current_user.id, dept_id)
    if result["success"]:
        flash(result["message"], "success")
        return redirect(url_for('patient.view_token', token_id=result["token_id"]))
    else:
        flash(result["error"], "warning")
        if "token_id" in result:
            return redirect(url_for('patient.view_token', token_id=result["token_id"]))
        return redirect(url_for('patient.dashboard'))


@patient_bp.route('/token/<int:token_id>')
@login_required
def view_token(token_id):
    """View unique printable / shareable digital token with QR code."""
    token = QueueToken.query.get_or_404(token_id)

    # Ensure patient only views their own token, unless staff/admin
    if current_user.role == 'patient' and token.patient_id != current_user.id:
        flash("You are not authorized to view this token.", "danger")
        return redirect(url_for('patient.dashboard'))

    wait_data = WaitingTimeService.calculate_for_token(token.id)
    qr_data = f"MediQueue Token: {token.token_number} | Patient: {token.patient.full_name} | Dept: {token.department.name} | Date: {token.date}"
    qr_code_uri = QueueService.generate_qr_code(qr_data)

    return render_template(
        'patient/token_view.html',
        token=token,
        wait_data=wait_data,
        qr_code_uri=qr_code_uri
    )


@patient_bp.route('/token/cancel', methods=['POST'])
@role_required('patient')
def cancel_token():
    """Self-service cancellation for waiting tokens."""
    token_id = request.form.get('token_id', type=int)
    if not token_id:
        flash("Token ID required.", "danger")
        return redirect(url_for('patient.dashboard'))

    result = QueueService.cancel_token(
        token_id=token_id,
        user_id=current_user.id,
        is_staff=False,
        reason="Patient self-cancellation from dashboard"
    )

    if result["success"]:
        flash(result["message"], "info")
    else:
        flash(result["error"], "danger")

    return redirect(url_for('patient.dashboard'))


@patient_bp.route('/profile', methods=['GET', 'POST'])
@role_required('patient')
def profile():
    """View and update permitted personal details."""
    profile = current_user.patient_profile
    if not profile:
        profile = PatientProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        date_of_birth = request.form.get('date_of_birth', '').strip()
        address = request.form.get('address', '').strip()

        if full_name:
            current_user.full_name = full_name
        current_user.phone = phone
        profile.emergency_contact = emergency_contact
        profile.blood_group = blood_group
        profile.date_of_birth = date_of_birth
        profile.address = address

        log = AuditLog(
            user_id=current_user.id,
            action='UPDATE_PROFILE',
            target_type='patient_profile',
            target_id=str(current_user.id),
            details="Patient updated personal contact information"
        )
        db.session.add(log)
        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('patient.profile'))

    return render_template('patient/profile.html', profile=profile)
