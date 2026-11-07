from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='patient', index=True)  # patient, staff, admin
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(30), nullable=True)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient_profile = db.relationship('PatientProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    staff_profile = db.relationship('StaffProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    tokens = db.relationship('QueueToken', backref='patient', foreign_keys='QueueToken.patient_id', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', cascade='all, delete-orphan', lazy='dynamic')
    login_records = db.relationship('LoginHistory', backref='user', cascade='all, delete-orphan', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    @property
    def is_active(self):
        """Flask-Login requirement."""
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class PatientProfile(db.Model):
    __tablename__ = 'patient_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    emergency_contact = db.Column(db.String(50), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    medical_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StaffProfile(db.Model):
    __tablename__ = 'staff_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    assigned_counter_id = db.Column(db.Integer, db.ForeignKey('counters.id', ondelete='SET NULL'), nullable=True)
    qualification = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), default='Clinical Specialist', nullable=True)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to department
    department = db.relationship('Department', backref='staff_members')
