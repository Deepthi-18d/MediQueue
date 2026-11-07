from datetime import datetime
from extensions import db

class HospitalSetting(db.Model):
    __tablename__ = 'hospital_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    updater = db.relationship('User', foreign_keys=[updated_by])

    @classmethod
    def get_value(cls, key, default=None):
        setting = cls.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default

    @classmethod
    def set_value(cls, key, value, description=None, user_id=None):
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            old_val = setting.setting_value
            setting.setting_value = str(value)
            setting.updated_at = datetime.utcnow()
            setting.updated_by = user_id
            if description:
                setting.description = description
            return old_val, setting
        else:
            setting = cls(
                setting_key=key,
                setting_value=str(value),
                description=description,
                updated_by=user_id
            )
            db.session.add(setting)
            return None, setting

    def __repr__(self):
        return f"<HospitalSetting {self.setting_key}={self.setting_value}>"
