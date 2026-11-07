from datetime import datetime
from extensions import db

class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    default_service_time = db.Column(db.Integer, default=10, nullable=False)  # in minutes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    counters = db.relationship('Counter', backref='department', cascade='all, delete-orphan', lazy='dynamic')
    tokens = db.relationship('QueueToken', backref='department', lazy='dynamic')

    def __repr__(self):
        return f"<Department {self.code} - {self.name}>"
