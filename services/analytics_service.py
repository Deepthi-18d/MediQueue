import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import func
from extensions import db
from models import (
    User, Department, Counter, QueueToken,
    ServiceRecord, AuditLog, LoginHistory, HospitalSetting
)
from services.waiting_time_service import WaitingTimeService

class AnalyticsService:

    @staticmethod
    def get_admin_dashboard_data():
        """Retrieve aggregated KPI counts and Chart.js datasets for Admin Dashboard."""
        today = datetime.now().strftime('%Y-%m-%d')

        # 1. KPIs
        total_registered_patients = User.query.filter_by(role='patient').count()
        total_patients_today = QueueToken.query.filter_by(date=today).count()
        total_waiting = QueueToken.query.filter(QueueToken.date == today, QueueToken.status.in_(['WAITING', 'CALLED'])).count()
        currently_serving = QueueToken.query.filter(QueueToken.date == today, QueueToken.status == 'SERVING').count()
        completed_services = QueueToken.query.filter(QueueToken.date == today, QueueToken.status == 'COMPLETED').count()
        cancelled_tokens = QueueToken.query.filter(QueueToken.date == today, QueueToken.status == 'CANCELLED').count()
        noshow_tokens = QueueToken.query.filter(QueueToken.date == today, QueueToken.status == 'NOSHOW').count()

        active_counters = Counter.query.filter(Counter.is_active == True, Counter.status.in_(['Available', 'Busy'])).count()
        total_counters = Counter.query.filter_by(is_active=True).count()

        # Avg service duration
        avg_service_res = db.session.query(func.avg(ServiceRecord.duration_minutes)).scalar()
        avg_service_time = round(float(avg_service_res), 1) if avg_service_res else 10.0

        # Dept stats list
        departments = Department.query.filter_by(is_active=True).all()
        dept_stats = []
        total_wait_accum = 0

        for d in departments:
            d_total = QueueToken.query.filter_by(department_id=d.id, date=today).count()
            d_waiting = QueueToken.query.filter(QueueToken.department_id == d.id, QueueToken.date == today, QueueToken.status.in_(['WAITING', 'CALLED'])).count()
            d_serving = QueueToken.query.filter(QueueToken.department_id == d.id, QueueToken.date == today, QueueToken.status == 'SERVING').count()
            d_completed = QueueToken.query.filter(QueueToken.department_id == d.id, QueueToken.date == today, QueueToken.status == 'COMPLETED').count()
            d_cancelled = QueueToken.query.filter(QueueToken.department_id == d.id, QueueToken.date == today, QueueToken.status.in_(['CANCELLED', 'NOSHOW'])).count()

            d_active_counters = Counter.query.filter(Counter.department_id == d.id, Counter.is_active == True, Counter.status.in_(['Available', 'Busy'])).count()
            d_avg_time = WaitingTimeService.get_department_avg_service_time(d.id)
            d_calc_counters = d_active_counters if d_active_counters > 0 else 1
            d_est_wait = round((d_waiting * d_avg_time) / float(d_calc_counters)) if d_waiting > 0 else 0

            total_wait_accum += d_est_wait

            dept_stats.append({
                'id': d.id,
                'name': d.name,
                'code': d.code,
                'description': d.description,
                'total_tokens': d_total,
                'waiting_count': d_waiting,
                'serving_count': d_serving,
                'completed_count': d_completed,
                'dropped_count': d_cancelled,
                'active_counters': d_active_counters,
                'avg_service_time': d_avg_time,
                'estimated_wait_time': d_est_wait
            })

        avg_est_wait = round(total_wait_accum / max(1, len(departments))) if departments else 0

        # 2. Charts
        # Chart 1: Daily status breakdown
        daily_status_chart = {
            'labels': ['Waiting', 'Serving', 'Completed', 'Cancelled', 'No-Show'],
            'datasets': [{
                'data': [total_waiting, currently_serving, completed_services, cancelled_tokens, noshow_tokens],
                'backgroundColor': ['#0d9488', '#0284c7', '#10b981', '#ef4444', '#f59e0b']
            }]
        }

        # Chart 2: Department load distribution
        dept_dist_labels = [d.name for d in departments]
        dept_dist_data = [d['total_tokens'] for d in dept_stats]
        dept_distribution_chart = {
            'labels': dept_dist_labels,
            'datasets': [{
                'label': "Today's Tokens",
                'data': dept_dist_data,
                'backgroundColor': ['#0284c7', '#0d9488', '#6366f1', '#ec4899', '#f59e0b', '#8b5cf6', '#14b8a6', '#f97316', '#06b6d4'][:len(departments)]
            }]
        }

        # Chart 3: Hourly patient arrivals (peak hospital hours)
        hours_labels = [f"{h:02d}:00" for h in range(8, 19)]
        hours_counts = [0] * len(hours_labels)

        today_tokens = QueueToken.query.filter_by(date=today).all()
        for t in today_tokens:
            if t.created_at:
                h = t.created_at.hour
                if 8 <= h <= 18:
                    hours_counts[h - 8] += 1

        peak_hours_chart = {
            'labels': hours_labels,
            'datasets': [{
                'label': 'Patients Checked-In',
                'data': hours_counts
            }]
        }

        # Chart 4: Average service duration by department
        avg_service_chart = {
            'labels': [d.name for d in departments],
            'datasets': [{
                'data': [d['avg_service_time'] for d in dept_stats]
            }]
        }

        # Chart 5: Counter throughput
        counters = Counter.query.filter_by(is_active=True).all()
        counter_labels = []
        counter_served_data = []
        counter_performance = []

        for c in counters:
            served_count = ServiceRecord.query.filter_by(counter_id=c.id).count()
            avg_handle = db.session.query(func.avg(ServiceRecord.duration_minutes)).filter_by(counter_id=c.id).scalar()
            avg_h_time = round(float(avg_handle), 1) if avg_handle else 0.0

            counter_labels.append(c.name)
            counter_served_data.append(served_count)

            counter_performance.append({
                'id': c.id,
                'name': c.name,
                'department_id': c.department_id,
                'department_name': c.department.name if c.department else 'General',
                'status': c.status,
                'current_staff': c.assigned_staff.full_name if c.assigned_staff else 'Unassigned',
                'patients_served': served_count,
                'avg_handling_time': avg_h_time
            })

        counter_chart = {
            'labels': counter_labels,
            'datasets': [{
                'data': counter_served_data
            }]
        }

        # Lists for tables
        staff_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
        registered_patients = User.query.filter_by(role='patient').order_by(User.created_at.desc()).all()
        staff_members = User.query.filter_by(role='staff').order_by(User.full_name.asc()).all()
        all_tokens_today = QueueToken.query.filter_by(date=today).order_by(QueueToken.created_at.desc()).all()

        return {
            'kpis': {
                'total_registered_patients': total_registered_patients,
                'total_patients_today': total_patients_today,
                'total_waiting': total_waiting,
                'currently_serving': currently_serving,
                'completed_services': completed_services,
                'cancelled_tokens': cancelled_tokens,
                'noshow_tokens': noshow_tokens,
                'active_counters': active_counters,
                'total_counters': total_counters,
                'avg_service_time': avg_service_time,
                'avg_estimated_waiting_time': avg_est_wait
            },
            'charts': {
                'daily_status': daily_status_chart,
                'dept_distribution': dept_distribution_chart,
                'peak_hours': peak_hours_chart,
                'avg_service_time': avg_service_chart,
                'counter_performance': counter_chart
            },
            'department_stats': dept_stats,
            'counter_performance': counter_performance,
            'staff_logs': staff_logs,
            'registered_patients': registered_patients,
            'staff_members': staff_members,
            'all_tokens_today': all_tokens_today
        }

    @staticmethod
    def export_csv_report(report_type='tokens', start_date=None, end_date=None, department_id=None):
        """
        Generate downloadable CSV reports with date and department filtering.
        Report types: 'tokens', 'services', 'departments', 'audit_logs', 'login_history'.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'tokens':
            writer.writerow(['Token ID', 'Token Number', 'Patient Name', 'Patient Email', 'Department', 'Counter', 'Status', 'Priority', 'Priority Reason', 'Date', 'Created Time', 'Called Time', 'Completed Time'])
            query = QueueToken.query
            if start_date:
                query = query.filter(QueueToken.date >= start_date)
            if end_date:
                query = query.filter(QueueToken.date <= end_date)
            if department_id:
                query = query.filter(QueueToken.department_id == department_id)
            tokens = query.order_by(QueueToken.created_at.desc()).all()

            for t in tokens:
                writer.writerow([
                    t.id,
                    t.token_number,
                    t.patient.full_name if t.patient else 'Unknown',
                    t.patient.email if t.patient else '',
                    t.department.name if t.department else '',
                    t.counter.name if t.counter else '',
                    t.status,
                    'Yes' if t.is_priority else 'No',
                    t.priority_reason or '',
                    t.date,
                    t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else '',
                    t.called_at.strftime('%Y-%m-%d %H:%M:%S') if t.called_at else '',
                    t.completed_at.strftime('%Y-%m-%d %H:%M:%S') if t.completed_at else ''
                ])

        elif report_type == 'services':
            writer.writerow(['Record ID', 'Token Number', 'Department', 'Counter', 'Staff Name', 'Start Time', 'End Time', 'Duration (Mins)', 'Clinical Notes'])
            query = ServiceRecord.query
            if department_id:
                query = query.filter(ServiceRecord.department_id == department_id)
            records = query.order_by(ServiceRecord.start_time.desc()).all()

            for r in records:
                writer.writerow([
                    r.id,
                    r.token.token_number if r.token else '',
                    r.department.name if r.department else '',
                    r.counter.name if r.counter else '',
                    r.staff.full_name if r.staff else '',
                    r.start_time.strftime('%Y-%m-%d %H:%M:%S') if r.start_time else '',
                    r.end_time.strftime('%Y-%m-%d %H:%M:%S') if r.end_time else '',
                    r.duration_minutes,
                    r.notes or ''
                ])

        elif report_type == 'audit_logs':
            writer.writerow(['Log ID', 'Timestamp', 'User', 'Action', 'Target Type', 'Target ID', 'Old Value', 'New Value', 'Details'])
            logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
            for l in logs:
                writer.writerow([
                    l.id,
                    l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else '',
                    l.user.full_name if l.user else 'System',
                    l.action,
                    l.target_type or '',
                    l.target_id or '',
                    l.old_value or '',
                    l.new_value or '',
                    l.details or ''
                ])

        elif report_type == 'login_history':
            writer.writerow(['Record ID', 'User', 'Role', 'IP Address', 'User Agent', 'Login Time', 'Logout Time', 'Status'])
            histories = LoginHistory.query.order_by(LoginHistory.login_time.desc()).all()
            for h in histories:
                writer.writerow([
                    h.id,
                    h.user.full_name if h.user else 'Unknown',
                    h.user.role if h.user else '',
                    h.ip_address or '',
                    h.user_agent or '',
                    h.login_time.strftime('%Y-%m-%d %H:%M:%S') if h.login_time else '',
                    h.logout_time.strftime('%Y-%m-%d %H:%M:%S') if h.logout_time else '',
                    h.status
                ])

        output.seek(0)
        return output.getvalue()
