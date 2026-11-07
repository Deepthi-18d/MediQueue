import functools
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, PatientProfile, LoginHistory, AuditLog

auth_bp = Blueprint('auth', __name__)

def role_required(*allowed_roles):
    """Enforce role-based access control."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "warning")
                return redirect(url_for('auth.login', next=request.path))

            if current_user.must_change_password and request.endpoint not in ['auth.change_password', 'auth.logout']:
                flash("Security requirement: You must change your password on first login.", "warning")
                return redirect(url_for('auth.change_password'))

            if current_user.role not in allowed_roles:
                flash("Access denied. You do not have permission for this section.", "danger")
                if current_user.role == 'patient':
                    return redirect(url_for('patient.dashboard'))
                elif current_user.role == 'staff':
                    return redirect(url_for('staff.dashboard'))
                elif current_user.role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                return redirect(url_for('main.index'))

            return view(**kwargs)
        return wrapped_view
    return decorator


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication with role-based routing and login audit logging."""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'staff':
            return redirect(url_for('staff.dashboard'))
        return redirect(url_for('patient.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template('auth/login.html')

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')[:250]

        if user and user.check_password(password):
            if not user.is_active_account:
                flash("Your account has been deactivated. Please contact hospital administration.", "danger")
                return render_template('auth/login.html')

            login_user(user, remember=True)

            # Record Login History
            history = LoginHistory(
                user_id=user.id,
                ip_address=ip,
                user_agent=user_agent,
                login_time=datetime.utcnow(),
                status='SUCCESS'
            )
            db.session.add(history)
            db.session.commit()
            session['login_history_id'] = history.id

            flash(f"Welcome back, {user.full_name}!", "success")

            if user.must_change_password:
                flash("First-time login: Please update your password to proceed.", "info")
                return redirect(url_for('auth.change_password'))

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'staff':
                return redirect(url_for('staff.dashboard'))
            return redirect(url_for('patient.dashboard'))
        else:
            # Failed login record if user exists
            if user:
                history = LoginHistory(
                    user_id=user.id,
                    ip_address=ip,
                    user_agent=user_agent,
                    login_time=datetime.utcnow(),
                    status='FAILED'
                )
                db.session.add(history)
                db.session.commit()

            flash("Invalid username or password.", "danger")

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Patient self-registration."""
    if current_user.is_authenticated:
        return redirect(url_for('patient.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not username or not password or not full_name:
            flash("Username, password, and full name are required.", "danger")
            return render_template('auth/register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('auth/register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html')

        # Check unique username and email
        if User.query.filter_by(username=username).first():
            flash("Username is already taken. Please choose another.", "warning")
            return render_template('auth/register.html')

        if email and User.query.filter_by(email=email).first():
            flash("Email address is already registered. Please sign in instead.", "warning")
            return render_template('auth/register.html')

        try:
            new_user = User(
                username=username,
                full_name=full_name,
                role='patient',
                email=email or None,
                phone=phone or None,
                is_active_account=True,
                must_change_password=False
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()

            # Create patient profile
            profile = PatientProfile(user_id=new_user.id)
            db.session.add(profile)

            # Audit log
            log = AuditLog(
                user_id=new_user.id,
                action='REGISTER',
                target_type='user',
                target_id=str(new_user.id),
                details=f"New patient self-registration: {full_name} (@{username})"
            )
            db.session.add(log)
            db.session.commit()

            login_user(new_user)
            flash("Account registered successfully! Welcome to MediQueue.", "success")
            return redirect(url_for('patient.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Registration failed: {str(e)}", "danger")

    return render_template('auth/register.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allows user to change their password or complete required first login change."""
    if request.method == 'POST':
        current_pwd = request.form.get('current_password', '').strip()
        new_pwd = request.form.get('new_password', '').strip()
        confirm_pwd = request.form.get('confirm_password', '').strip()

        if not current_user.check_password(current_pwd):
            flash("Current password is incorrect.", "danger")
            return render_template('auth/change_password.html')

        if len(new_pwd) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return render_template('auth/change_password.html')

        if new_pwd != confirm_pwd:
            flash("New passwords do not match.", "danger")
            return render_template('auth/change_password.html')

        current_user.set_password(new_pwd)
        current_user.must_change_password = False

        log = AuditLog(
            user_id=current_user.id,
            action='CHANGE_PASSWORD',
            target_type='user',
            target_id=str(current_user.id),
            details=f"User {current_user.username} updated password"
        )
        db.session.add(log)
        db.session.commit()

        flash("Password updated successfully!", "success")
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'staff':
            return redirect(url_for('staff.dashboard'))
        return redirect(url_for('patient.dashboard'))

    return render_template('auth/change_password.html')


@auth_bp.route('/logout')
def logout():
    """Sign out user and record logout timestamp in login history."""
    if current_user.is_authenticated:
        history_id = session.get('login_history_id')
        if history_id:
            h = LoginHistory.query.get(history_id)
            if h:
                h.logout_time = datetime.utcnow()
                db.session.commit()
        logout_user()

    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('auth.login'))
