from datetime import datetime
from extensions import db

class Counter(db.Model):
    __tablename__ = 'counters'

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='Available', nullable=False)  # Available, Busy, Offline
    current_token_id = db.Column(db.Integer, nullable=True)
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assigned_staff = db.relationship('User', foreign_keys=[assigned_staff_id])

    def __repr__(self):
        return f"<Counter {self.name} ({self.status})>"
