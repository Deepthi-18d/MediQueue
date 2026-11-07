from extensions import db, socketio
from models import Notification, User

class NotificationService:

    @staticmethod
    def send_notification(user_id, title, message, category='info', link=None):
        """
        Create a notification record in SQLite and broadcast it via Flask-SocketIO.
        """
        try:
            notif = Notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                link=link
            )
            db.session.add(notif)
            db.session.commit()

            # Emit real-time notification to client
            socketio.emit('new_notification', {
                'id': notif.id,
                'user_id': user_id,
                'title': title,
                'message': message,
                'category': category,
                'link': link,
                'created_at': notif.created_at.strftime('%H:%M')
            })
            return notif
        except Exception as e:
            db.session.rollback()
            print(f"Error sending notification: {e}")
            return None

    @staticmethod
    def notify_admins(title, message, category='info', link=None):
        """Notify all admin accounts."""
        admins = User.query.filter_by(role='admin', is_active_account=True).all()
        for admin in admins:
            NotificationService.send_notification(admin.id, title, message, category, link)

    @staticmethod
    def notify_department_staff(department_id, title, message, category='info', link=None):
        """Notify staff assigned to a department."""
        from models import StaffProfile
        staff_profiles = StaffProfile.query.filter_by(department_id=department_id).all()
        for sp in staff_profiles:
            NotificationService.send_notification(sp.user_id, title, message, category, link)

    @staticmethod
    def get_user_notifications(user_id, limit=20):
        """Retrieve recent notifications for a user."""
        return Notification.query.filter_by(user_id=user_id)\
            .order_by(Notification.created_at.desc())\
            .limit(limit).all()

    @staticmethod
    def get_unread_count(user_id):
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def mark_as_read(notification_id, user_id):
        notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notif:
            notif.is_read = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(user_id):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
        return True
