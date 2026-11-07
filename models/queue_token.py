from datetime import datetime
from extensions import db

class QueueToken(db.Model):
    __tablename__ = 'tokens'

    id = db.Column(db.Integer, primary_key=True)
    token_number = db.Column(db.String(30), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False, index=True)
    counter_id = db.Column(db.Integer, db.ForeignKey('counters.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(20), default='WAITING', nullable=False, index=True)  # WAITING, CALLED, SERVING, COMPLETED, CANCELLED, NOSHOW
    is_priority = db.Column(db.Boolean, default=False, nullable=False, index=True)
    priority_reason = db.Column(db.Text, nullable=True)
    priority_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    called_at = db.Column(db.DateTime, nullable=True)
    serving_started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.Text, nullable=True)

    # Relationships
    counter = db.relationship('Counter', foreign_keys=[counter_id])
    priority_staff = db.relationship('User', foreign_keys=[priority_by])
    service_records = db.relationship('ServiceRecord', backref='token', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f"<QueueToken {self.token_number} ({self.status})>"


class ServiceRecord(db.Model):
    __tablename__ = 'service_records'

    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('tokens.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False)
    counter_id = db.Column(db.Integer, db.ForeignKey('counters.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    staff = db.relationship('User', foreign_keys=[staff_id])
    department = db.relationship('Department', foreign_keys=[department_id])
    counter = db.relationship('Counter', foreign_keys=[counter_id])
