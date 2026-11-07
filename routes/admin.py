from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from extensions import db, socketio
from models import (
    User, PatientProfile, StaffProfile, Department, Counter,
    QueueToken, ServiceRecord, AuditLog, LoginHistory, HospitalSetting
)
from routes.auth import role_required
from services.analytics_service import AnalyticsService
from services.notification_service import NotificationService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    """Administrative command center featuring KPIs, Chart.js visualizations, and entity tables."""
    data = AnalyticsService.get_admin_dashboard_data()

    # Hospital Settings
    hospital_name = HospitalSetting.get_value('hospital_name', 'MediQueue General Hospital')
    app_name = HospitalSetting.get_value('app_name', 'MediQueue')
    admin_name = HospitalSetting.get_value('admin_display_name', current_user.full_name)
    contact_phone = HospitalSetting.get_value('contact_phone', '+1 (555) 019-2834')
    contact_email = HospitalSetting.get_value('contact_email', 'admin@mediqueue.org')
    hospital_address = HospitalSetting.get_value('hospital_address', '100 Medical Center Parkway, Metro City')

    return render_template(
        'admin/dashboard.html',
        kpis=data['kpis'],
        charts=data['charts'],
        department_stats=data['department_stats'],
        counter_performance=data['counter_performance'],
        staff_logs=data['staff_logs'],
        registered_patients=data['registered_patients'],
        staff_members=data['staff_members'],
        all_tokens_today=data['all_tokens_today'],
        hospital_name=hospital_name,
        app_name=app_name,
        admin_name=admin_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        hospital_address=hospital_address
    )


# --- SECTION 7: EDITABLE NAMES AND HOSPITAL SETTINGS (COMPULSORY) ---

@admin_bp.route('/edit_name', methods=['POST'])
@role_required('admin')
def edit_name():
    """
    Universal inline name & setting editing handler.
    Allows editing: Hospital name, App name, Admin name, Patient name, Staff name,
    Department name/description, Counter name.
    Preserves database IDs and foreign keys!
    Records old name, new name, admin ID, and timestamp in AuditLog.
    Emits Socket.IO update.
    """
    entity_type = request.form.get('entity_type', '').strip()  # 'setting', 'user', 'department', 'counter'
    entity_id = request.form.get('entity_id', '').strip()
    field_name = request.form.get('field_name', 'name').strip()
    new_value = request.form.get('new_value', '').strip()

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if not new_value:
        msg = "The new name/value cannot be empty."
        if is_ajax:
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.dashboard'))

    try:
        old_value = ""

        if entity_type == 'setting':
            # Edit hospital setting (e.g. hospital_name, app_name, contact_phone, etc.)
            setting = HospitalSetting.query.filter_by(setting_key=entity_id).first()
            if setting:
                old_value = setting.setting_value
                setting.setting_value = new_value
                setting.updated_at = datetime.utcnow()
                setting.updated_by = current_user.id
            else:
                setting = HospitalSetting(
                    setting_key=entity_id,
                    setting_value=new_value,
                    updated_by=current_user.id
                )
                db.session.add(setting)

        elif entity_type == 'user':
            user = User.query.get(int(entity_id))
            if not user:
                return jsonify({'success': False, 'error': 'User not found.'}), 404
            old_value = user.full_name
            user.full_name = new_value

        elif entity_type == 'department':
            dept = Department.query.get(int(entity_id))
            if not dept:
                return jsonify({'success': False, 'error': 'Department not found.'}), 404
            if field_name == 'description':
                old_value = dept.description
                dept.description = new_value
            else:
                old_value = dept.name
                dept.name = new_value

        elif entity_type == 'counter':
            counter = Counter.query.get(int(entity_id))
            if not counter:
                return jsonify({'success': False, 'error': 'Counter not found.'}), 404
            old_value = counter.name
            counter.name = new_value

        else:
            return jsonify({'success': False, 'error': 'Invalid entity type.'}), 400

        # Log into AuditLog
        log = AuditLog(
            user_id=current_user.id,
            action='NAME_EDIT',
            target_type=entity_type,
            target_id=str(entity_id),
            old_value=old_value,
            new_value=new_value,
            details=f"Admin {current_user.full_name} updated {entity_type} [{entity_id}] {field_name} from '{old_value}' to '{new_value}'"
        )
        db.session.add(log)
        db.session.commit()

        # Emit SocketIO real-time update
        socketio.emit('name_updated', {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'field_name': field_name,
            'new_value': new_value
        })

        success_msg = f"Successfully updated to '{new_value}'."
        if is_ajax:
            return jsonify({
                'success': True,
                'message': success_msg,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'new_value': new_value
            })

        flash(success_msg, "success")
        return redirect(url_for('admin.dashboard'))

    except Exception as e:
        db.session.rollback()
        err_msg = f"Failed to update name: {str(e)}"
        if is_ajax:
            return jsonify({'success': False, 'error': err_msg}), 500
        flash(err_msg, "danger")
        return redirect(url_for('admin.dashboard'))


# --- DEPARTMENT MANAGEMENT ---

@admin_bp.route('/department/add', methods=['POST'])
@role_required('admin')
def add_department():
    """Add a new clinical department."""
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()
    description = request.form.get('description', '').strip()
    service_time = request.form.get('default_service_time', 10, type=int)

    if not name or not code:
        flash("Department name and code are required.", "danger")
        return redirect(url_for('admin.dashboard'))

    if Department.query.filter((Department.name == name) | (Department.code == code)).first():
        flash("Department name or code already exists.", "warning")
        return redirect(url_for('admin.dashboard'))

    try:
        new_dept = Department(
            name=name,
            code=code,
            description=description,
            default_service_time=service_time,
            is_active=True
        )
        db.session.add(new_dept)
        db.session.flush()

        # Automatically create default Counter 1 for this department
        c1 = Counter(department_id=new_dept.id, name=f"{code} Counter 1", status='Available')
        db.session.add(c1)

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_DEPARTMENT',
            target_type='department',
            target_id=str(new_dept.id),
            new_value=name,
            details=f"Admin created department {name} ({code})"
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Department '{name}' ({code}) added successfully with initial counter station.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding department: {str(e)}", "danger")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/department/toggle/<int:dept_id>', methods=['POST'])
@role_required('admin')
def toggle_department(dept_id):
    """Activate or deactivate department."""
    dept = Department.query.get_or_404(dept_id)
    dept.is_active = not dept.is_active

    log = AuditLog(
        user_id=current_user.id,
        action='TOGGLE_DEPARTMENT',
        target_type='department',
        target_id=str(dept.id),
        new_value=str(dept.is_active),
        details=f"Department {dept.name} is now {'Active' if dept.is_active else 'Deactivated'}"
    )
    db.session.add(log)
    db.session.commit()

    status_str = "activated" if dept.is_active else "deactivated"
    flash(f"Department '{dept.name}' has been {status_str}.", "info")
    return redirect(url_for('admin.dashboard'))


# --- COUNTER MANAGEMENT ---

@admin_bp.route('/counter/add', methods=['POST'])
@role_required('admin')
def add_counter():
    """Add a new counter station to a department."""
    department_id = request.form.get('department_id', type=int)
    name = request.form.get('name', '').strip()

    if not department_id or not name:
        flash("Department and Counter Name are required.", "danger")
        return redirect(url_for('admin.dashboard'))

    try:
        new_counter = Counter(
            department_id=department_id,
            name=name,
            status='Available',
            is_active=True
        )
        db.session.add(new_counter)
        db.session.flush()

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_COUNTER',
            target_type='counter',
            target_id=str(new_counter.id),
            new_value=name,
            details=f"Admin created counter '{name}' in department #{department_id}"
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Counter '{name}' created successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding counter: {str(e)}", "danger")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/counter/toggle/<int:counter_id>', methods=['POST'])
@role_required('admin')
def toggle_counter(counter_id):
    """Activate or deactivate counter station."""
    counter = Counter.query.get_or_404(counter_id)
    counter.is_active = not counter.is_active

    log = AuditLog(
        user_id=current_user.id,
        action='TOGGLE_COUNTER',
        target_type='counter',
        target_id=str(counter.id),
        new_value=str(counter.is_active),
        details=f"Counter {counter.name} is now {'Active' if counter.is_active else 'Deactivated'}"
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Counter '{counter.name}' status updated.", "info")
    return redirect(url_for('admin.dashboard'))


# --- STAFF MANAGEMENT ---

@admin_bp.route('/staff/add', methods=['POST'])
@role_required('admin')
def add_staff():
    """Register a new clinical staff account."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', 'Staff@123').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    department_id = request.form.get('department_id', type=int)
    designation = request.form.get('designation', 'Clinical Specialist').strip()

    if not username or not full_name:
        flash("Username and full name are required.", "danger")
        return redirect(url_for('admin.dashboard'))

    if User.query.filter_by(username=username).first():
        flash("Username already exists. Please choose another.", "warning")
        return redirect(url_for('admin.dashboard'))

    try:
        new_staff = User(
            username=username,
            full_name=full_name,
            role='staff',
            email=email or None,
            phone=phone or None,
            is_active_account=True,
            must_change_password=True
        )
        new_staff.set_password(password)
        db.session.add(new_staff)
        db.session.flush()

        profile = StaffProfile(
            user_id=new_staff.id,
            department_id=department_id,
            designation=designation
        )
        db.session.add(profile)

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_STAFF',
            target_type='user',
            target_id=str(new_staff.id),
            details=f"Admin created staff account {full_name} (@{username}) for department #{department_id}"
        )
        db.session.add(log)
        db.session.commit()

        # Notify admins
        NotificationService.notify_admins(
            title="New Staff Account Created",
            message=f"Staff member {full_name} (@{username}) has been registered.",
            category="info"
        )

        flash(f"Staff account '{full_name}' created successfully. Default password: {password}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating staff account: {str(e)}", "danger")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/user/toggle/<int:user_id>', methods=['POST'])
@role_required('admin')
def toggle_user(user_id):
    """Activate or deactivate user account."""
    if user_id == current_user.id:
        flash("You cannot deactivate your own administrative account.", "danger")
        return redirect(url_for('admin.dashboard'))

    user = User.query.get_or_404(user_id)
    user.is_active_account = not user.is_active_account

    log = AuditLog(
        user_id=current_user.id,
        action='TOGGLE_USER',
        target_type='user',
        target_id=str(user.id),
        new_value=str(user.is_active_account),
        details=f"User {user.username} account was {'activated' if user.is_active_account else 'deactivated'}"
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Account for {user.full_name} (@{user.username}) updated.", "info")
    return redirect(url_for('admin.dashboard'))


# --- REPORTS & CSV EXPORT ---

@admin_bp.route('/reports')
@role_required('admin')
def reports():
    """Hospital analytics reports generator with filters."""
    departments = Department.query.filter_by(is_active=True).all()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('admin/reports.html', departments=departments, today=today)


@admin_bp.route('/export_csv')
@role_required('admin')
def export_csv():
    """Generate and download real CSV reports."""
    report_type = request.args.get('type', 'tokens')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)

    csv_data = AnalyticsService.export_csv_report(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        department_id=dept_id
    )

    filename = f"mediqueue_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


# --- AUDIT LOGS & LOGIN HISTORY ---

@admin_bp.route('/audit_logs')
@role_required('admin')
def audit_logs():
    """System-wide immutable audit trail."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('admin/audit_logs.html', logs=logs)


@admin_bp.route('/login_history')
@role_required('admin')
def login_history():
    """User authentication history log."""
    histories = LoginHistory.query.order_by(LoginHistory.login_time.desc()).limit(100).all()
    return render_template('admin/login_history.html', histories=histories)
