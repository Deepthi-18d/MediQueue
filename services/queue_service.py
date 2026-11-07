import io
import base64
from datetime import datetime
import qrcode
from extensions import db, socketio
from models import (
    QueueToken, Department, Counter, ServiceRecord,
    User, AuditLog, PatientProfile
)
from services.waiting_time_service import WaitingTimeService
from services.notification_service import NotificationService

class QueueService:

    @staticmethod
    def generate_qr_code(data_string):
        """Generate a base64 encoded PNG QR code image data URI."""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(data_string)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            print(f"QR generation error: {e}")
            return None

    @staticmethod
    def get_patient_active_token(patient_id):
        """Retrieve patient's current non-final token with waiting-time calculation."""
        token = QueueToken.query.filter(
            QueueToken.patient_id == patient_id,
            QueueToken.status.in_(['WAITING', 'CALLED', 'SERVING'])
        ).order_by(QueueToken.created_at.desc()).first()

        if token:
            wait_data = WaitingTimeService.calculate_for_token(token.id)
            qr_data = f"MediQueue Token: {token.token_number} | Patient ID: {token.patient_id} | Dept: {token.department.name} | Date: {token.date}"
            return {
                'id': token.id,
                'token_number': token.token_number,
                'department_id': token.department_id,
                'department_name': token.department.name,
                'department_code': token.department.code,
                'counter_id': token.counter_id,
                'counter_name': token.counter.name if token.counter else 'Pending Assignment',
                'status': token.status,
                'is_priority': token.is_priority,
                'priority_reason': token.priority_reason,
                'date': token.date,
                'created_at': token.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'called_at': token.called_at.strftime('%H:%M:%S') if token.called_at else None,
                'queue_position': wait_data['queue_position'],
                'patients_ahead': wait_data['patients_ahead'],
                'estimated_wait_time': wait_data['estimated_wait_time'],
                'active_counters': wait_data['active_counters'],
                'currently_serving_token': wait_data['currently_serving_token'],
                'qr_code_data': QueueService.generate_qr_code(qr_data),
                'disclaimer': wait_data['disclaimer']
            }
        return None

    @staticmethod
    def generate_token(patient_id, department_id):
        """
        Create a new queue token for a patient in a department.
        Validates duplicate active tokens, generates token sequence, commits transaction.
        """
        today = datetime.now().strftime('%Y-%m-%d')
        dept = Department.query.get(department_id)
        if not dept:
            return {"success": False, "error": "Department not found."}
        if not dept.is_active:
            return {"success": False, "error": f"The {dept.name} department is currently not accepting new tokens."}

        # Check for duplicate active tokens
        existing = QueueToken.query.filter(
            QueueToken.patient_id == patient_id,
            QueueToken.department_id == department_id,
            QueueToken.status.in_(['WAITING', 'CALLED', 'SERVING'])
        ).first()

        if existing:
            return {
                "success": False,
                "error": f"You already hold an active token ({existing.token_number}) in {dept.name}. Please complete or cancel it before booking another.",
                "token_id": existing.id
            }

        try:
            # Count tokens generated today for this department to generate sequence
            today_tokens_count = QueueToken.query.filter(
                QueueToken.department_id == department_id,
                QueueToken.date == today
            ).count()

            seq_num = 101 + today_tokens_count
            token_number = f"{dept.code}-{seq_num}"

            new_token = QueueToken(
                token_number=token_number,
                patient_id=patient_id,
                department_id=department_id,
                status='WAITING',
                date=today,
                created_at=datetime.utcnow()
            )
            db.session.add(new_token)
            db.session.commit()

            # Create notification for patient
            NotificationService.send_notification(
                user_id=patient_id,
                title="Token Issued Successfully",
                message=f"Your token #{token_number} for {dept.name} has been booked. You are placed in queue.",
                category="success",
                link=f"/patient/token/{new_token.id}"
            )

            # Notify department staff
            NotificationService.notify_department_staff(
                department_id=department_id,
                title="New Patient in Queue",
                message=f"Token #{token_number} added to {dept.name} waiting list.",
                category="info"
            )

            # Emit SocketIO event
            socketio.emit('queue_updated', {'department_id': department_id})

            return {
                "success": True,
                "message": f"Token #{token_number} created successfully!",
                "token_id": new_token.id,
                "token_number": token_number
            }
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": f"Failed to generate token: {str(e)}"}

    @staticmethod
    def call_next_patient(staff_id, counter_id, department_id, target_token_id=None):
        """
        Staff calls next patient in queue (priority first, then FIFO) or specific token.
        Ensures counter conflict prevention and transactional safety.
        """
        counter = Counter.query.get(counter_id)
        if not counter:
            return {"success": False, "error": "Counter not found."}

        # Check if counter already has a serving token
        if counter.current_token_id:
            active_token = QueueToken.query.get(counter.current_token_id)
            if active_token and active_token.status in ['CALLED', 'SERVING']:
                return {
                    "success": False,
                    "error": f"Counter {counter.name} is currently serving token {active_token.token_number}. Please complete or clear it first."
                }

        today = datetime.now().strftime('%Y-%m-%d')
        
        # Select target token or next in queue
        if target_token_id:
            token = QueueToken.query.filter(
                QueueToken.id == target_token_id,
                QueueToken.department_id == department_id,
                QueueToken.status == 'WAITING'
            ).first()
        else:
            token = QueueToken.query.filter(
                QueueToken.department_id == department_id,
                QueueToken.date == today,
                QueueToken.status == 'WAITING'
            ).order_by(QueueToken.is_priority.desc(), QueueToken.created_at.asc()).first()

        if not token:
            return {"success": False, "error": "No waiting patients in queue for this department."}

        try:
            token.status = 'CALLED'
            token.counter_id = counter.id
            token.called_at = datetime.utcnow()

            counter.current_token_id = token.id
            counter.status = 'Busy'
            counter.assigned_staff_id = staff_id

            # Audit log
            log = AuditLog(
                user_id=staff_id,
                action='CALL_TOKEN',
                target_type='token',
                target_id=str(token.id),
                old_value='WAITING',
                new_value='CALLED',
                details=f"Staff called token {token.token_number} to {counter.name}"
            )
            db.session.add(log)
            db.session.commit()

            # Patient notification
            NotificationService.send_notification(
                user_id=token.patient_id,
                title="Your Token is Called!",
                message=f"Please proceed to {counter.name} for your consultation with {counter.department.name}.",
                category="warning",
                link=f"/patient/token/{token.id}"
            )

            # Socket.IO notifications
            socketio.emit('queue_updated', {'department_id': department_id})
            socketio.emit('token_called', {
                'token_id': token.id,
                'token_number': token.token_number,
                'counter_name': counter.name,
                'department_id': department_id,
                'patient_id': token.patient_id
            })

            return {
                "success": True,
                "message": f"Token {token.token_number} called to {counter.name}.",
                "token_id": token.id,
                "token_number": token.token_number,
                "counter_name": counter.name
            }
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": f"Database error calling token: {str(e)}"}

    @staticmethod
    def start_serving(token_id, staff_id):
        """Staff officially begins consultation."""
        token = QueueToken.query.get(token_id)
        if not token:
            return {"success": False, "error": "Token not found."}

        try:
            token.status = 'SERVING'
            token.serving_started_at = datetime.utcnow()
            
            log = AuditLog(
                user_id=staff_id,
                action='START_SERVING',
                target_type='token',
                target_id=str(token.id),
                old_value='CALLED',
                new_value='SERVING',
                details=f"Consultation started for token {token.token_number}"
            )
            db.session.add(log)
            db.session.commit()

            socketio.emit('queue_updated', {'department_id': token.department_id})
            return {"success": True, "message": f"Started consultation for token {token.token_number}."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def complete_service(token_id, staff_id, counter_id, notes=""):
        """Staff marks consultation completed and logs duration into ServiceRecords."""
        token = QueueToken.query.get(token_id)
        if not token:
            return {"success": False, "error": "Token not found."}

        counter = Counter.query.get(counter_id)
        now = datetime.utcnow()

        try:
            # Calculate duration in minutes
            start_time = token.serving_started_at or token.called_at or token.created_at
            duration_minutes = max(1.0, round((now - start_time).total_seconds() / 60.0, 1))

            token.status = 'COMPLETED'
            token.completed_at = now

            # Create ServiceRecord
            record = ServiceRecord(
                token_id=token.id,
                department_id=token.department_id,
                counter_id=counter_id,
                staff_id=staff_id,
                start_time=start_time,
                end_time=now,
                duration_minutes=duration_minutes,
                notes=notes or "Routine clinical consultation completed."
            )
            db.session.add(record)

            # Clear counter
            if counter:
                counter.current_token_id = None
                counter.status = 'Available'

            # Audit log
            log = AuditLog(
                user_id=staff_id,
                action='COMPLETE_SERVICE',
                target_type='token',
                target_id=str(token.id),
                old_value='SERVING',
                new_value='COMPLETED',
                details=f"Completed service for {token.token_number} (Duration: {duration_minutes} mins)"
            )
            db.session.add(log)
            db.session.commit()

            # Patient notification
            NotificationService.send_notification(
                user_id=token.patient_id,
                title="Consultation Completed",
                message=f"Your consultation for token {token.token_number} has concluded. Thank you for visiting MediQueue Hospital.",
                category="success"
            )

            socketio.emit('queue_updated', {'department_id': token.department_id})
            return {"success": True, "message": f"Service for {token.token_number} completed successfully!"}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": f"Error completing service: {str(e)}"}

    @staticmethod
    def mark_noshow(token_id, staff_id):
        """Mark patient as no-show and free the counter station."""
        token = QueueToken.query.get(token_id)
        if not token:
            return {"success": False, "error": "Token not found."}

        try:
            token.status = 'NOSHOW'
            
            # Clear counter if assigned
            if token.counter_id:
                counter = Counter.query.get(token.counter_id)
                if counter and counter.current_token_id == token.id:
                    counter.current_token_id = None
                    counter.status = 'Available'

            log = AuditLog(
                user_id=staff_id,
                action='MARK_NOSHOW',
                target_type='token',
                target_id=str(token.id),
                old_value=token.status,
                new_value='NOSHOW',
                details=f"Token {token.token_number} marked as No-Show by staff"
            )
            db.session.add(log)
            db.session.commit()

            socketio.emit('queue_updated', {'department_id': token.department_id})
            return {"success": True, "message": f"Token {token.token_number} marked as No-Show."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_token(token_id, user_id, is_staff=False, reason="Patient self-cancellation"):
        """Cancel a token with audit trail."""
        token = QueueToken.query.get(token_id)
        if not token:
            return {"success": False, "error": "Token not found."}

        if not is_staff and token.patient_id != user_id:
            return {"success": False, "error": "Unauthorized to cancel this token."}

        if token.status in ['COMPLETED', 'CANCELLED', 'NOSHOW']:
            return {"success": False, "error": f"Cannot cancel token that is already {token.status.lower()}."}

        try:
            old_status = token.status
            token.status = 'CANCELLED'
            token.cancelled_at = datetime.utcnow()
            token.cancel_reason = reason

            # Free counter if assigned
            if token.counter_id:
                counter = Counter.query.get(token.counter_id)
                if counter and counter.current_token_id == token.id:
                    counter.current_token_id = None
                    counter.status = 'Available'

            log = AuditLog(
                user_id=user_id,
                action='CANCEL_TOKEN',
                target_type='token',
                target_id=str(token.id),
                old_value=old_status,
                new_value='CANCELLED',
                details=f"Token {token.token_number} cancelled: {reason}"
            )
            db.session.add(log)
            db.session.commit()

            socketio.emit('queue_updated', {'department_id': token.department_id})
            return {"success": True, "message": f"Token {token.token_number} has been cancelled."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_priority(token_id, staff_id, is_priority, reason=""):
        """Flag or unflag priority for a token by authorized clinical staff."""
        token = QueueToken.query.get(token_id)
        if not token:
            return {"success": False, "error": "Token not found."}

        try:
            token.is_priority = is_priority
            token.priority_reason = reason if is_priority else None
            token.priority_by = staff_id if is_priority else None

            log = AuditLog(
                user_id=staff_id,
                action='FLAG_PRIORITY' if is_priority else 'UNFLAG_PRIORITY',
                target_type='token',
                target_id=str(token.id),
                old_value='0' if not is_priority else '1',
                new_value='1' if is_priority else '0',
                details=f"Token {token.token_number} priority set to {is_priority}. Reason: {reason}"
            )
            db.session.add(log)
            db.session.commit()

            socketio.emit('queue_updated', {'department_id': token.department_id})
            return {"success": True, "message": f"Priority status updated for token {token.token_number}."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_counter_status(counter_id, staff_id, status):
        """Set counter status (Available, Busy, Offline)."""
        counter = Counter.query.get(counter_id)
        if not counter:
            return {"success": False, "error": "Counter not found."}

        if status not in ['Available', 'Busy', 'Offline']:
            return {"success": False, "error": "Invalid counter status."}

        try:
            old_status = counter.status
            counter.status = status
            counter.assigned_staff_id = staff_id

            log = AuditLog(
                user_id=staff_id,
                action='COUNTER_STATUS_CHANGE',
                target_type='counter',
                target_id=str(counter.id),
                old_value=old_status,
                new_value=status,
                details=f"Counter {counter.name} status changed to {status}"
            )
            db.session.add(log)
            db.session.commit()

            socketio.emit('queue_updated', {'department_id': counter.department_id})
            socketio.emit('counter_updated', {'counter_id': counter.id, 'status': status})
            return {"success": True, "message": f"Counter {counter.name} is now {status}."}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}
