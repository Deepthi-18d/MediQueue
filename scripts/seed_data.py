import os
import sys
from datetime import datetime, timedelta

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from models import (
    User, PatientProfile, StaffProfile, Department, Counter,
    QueueToken, ServiceRecord, AuditLog, LoginHistory, HospitalSetting, Notification
)
from config import Config

def seed_database(force_reset=False):
    """Seed comprehensive demonstration data for Technovate 2.0 Hackathon."""
    if force_reset:
        db.drop_all()
        db.create_all()

    # 1. Hospital Settings
    settings_data = [
        ('hospital_name', 'MediQueue General Hospital', 'Official hospital operational name'),
        ('app_name', 'MediQueue', 'Application branding and portal display name'),
        ('admin_display_name', 'Dr. Sarah Mitchell (Administrator)', 'Super Administrator display title'),
        ('contact_phone', '+1 (555) 019-2834', 'Hospital reception and triage contact helpline'),
        ('contact_email', 'helpdesk@mediqueue.org', 'Hospital central inquiry email address'),
        ('hospital_address', '100 Medical Center Parkway, Metro City', 'Physical hospital campus location'),
        ('default_service_time', '10', 'Global fallback consultation service duration in minutes')
    ]

    for key, val, desc in settings_data:
        existing = HospitalSetting.query.filter_by(setting_key=key).first()
        if not existing:
            setting = HospitalSetting(setting_key=key, setting_value=val, description=desc)
            db.session.add(setting)

    db.session.commit()

    # 2. Departments
    dept_map = {}
    for d_data in Config.DEPARTMENTS:
        dept = Department.query.filter_by(code=d_data['code']).first()
        if not dept:
            dept = Department(
                name=d_data['name'],
                code=d_data['code'],
                description=d_data['description'],
                default_service_time=d_data['default_service_time'],
                is_active=True
            )
            db.session.add(dept)
            db.session.flush()
        dept_map[dept.code] = dept

    db.session.commit()

    # 3. Counters (2 counters per department)
    counter_map = {}
    for code, dept in dept_map.items():
        c1_name = f"{code} Counter 1"
        c2_name = f"{code} Counter 2"

        c1 = Counter.query.filter_by(department_id=dept.id, name=c1_name).first()
        if not c1:
            c1 = Counter(department_id=dept.id, name=c1_name, status='Available', is_active=True)
            db.session.add(c1)
            db.session.flush()

        c2 = Counter.query.filter_by(department_id=dept.id, name=c2_name).first()
        if not c2:
            c2 = Counter(department_id=dept.id, name=c2_name, status='Available', is_active=True)
            db.session.add(c2)
            db.session.flush()

        counter_map[f"{code}_1"] = c1
        counter_map[f"{code}_2"] = c2

    db.session.commit()

    # 4. Users (Admin, Staff, Patients)
    # A. Default Admin Account (Must change password flag requirement supported)
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            full_name='Dr. Sarah Mitchell (Administrator)',
            role='admin',
            email='admin@mediqueue.com',
            phone='+1-555-0100',
            is_active_account=True,
            must_change_password=False
        )
        admin_user.set_password('Admin@123')
        db.session.add(admin_user)
        db.session.flush()

    # B. Staff Accounts
    staff_defs = [
        ('staff', 'Dr. Alexander Wright, MD', 'GM', 'staff@mediqueue.com', '+1-555-0101', 'Chief Internal Medicine Specialist'),
        ('staff_gm', 'Dr. Alexander Wright, MD', 'GM', 'alex.wright@mediqueue.org', '+1-555-0101', 'General Physician'),
        ('staff_cardio', 'Dr. Elena Rostova, FACC', 'CARD', 'elena.rostova@mediqueue.org', '+1-555-0102', 'Senior Cardiologist'),
        ('staff_ortho', 'Dr. Marcus Vance, MS', 'ORTH', 'marcus.vance@mediqueue.org', '+1-555-0103', 'Orthopaedic Surgeon'),
        ('staff_ped', 'Dr. Anita Desai, MD', 'PED', 'anita.desai@mediqueue.org', '+1-555-0104', 'Lead Paediatrician'),
        ('staff_derm', 'Dr. Chloe Martin, MD', 'DERM', 'chloe.martin@mediqueue.org', '+1-555-0105', 'Consultant Dermatologist'),
        ('staff_neur', 'Dr. Samuel Brooks, PhD', 'NEUR', 'samuel.brooks@mediqueue.org', '+1-555-0106', 'Consultant Neurologist'),
        ('staff_ent', 'Dr. Priya Patel, MS', 'ENT', 'priya.patel@mediqueue.org', '+1-555-0107', 'ENT Specialist'),
        ('staff_dent', 'Dr. Michael Chen, DDS', 'DENT', 'michael.chen@mediqueue.org', '+1-555-0108', 'Senior Dental Surgeon')
    ]

    staff_map = {}
    for username, full_name, dept_code, email, phone, desig in staff_defs:
        s_user = User.query.filter_by(username=username).first()
        dept = dept_map.get(dept_code)
        if not s_user:
            s_user = User(
                username=username,
                full_name=full_name,
                role='staff',
                email=email,
                phone=phone,
                is_active_account=True,
                must_change_password=False
            )
            s_user.set_password('Staff@123')
            db.session.add(s_user)
            db.session.flush()

            sp = StaffProfile(
                user_id=s_user.id,
                department_id=dept.id if dept else None,
                designation=desig
            )
            db.session.add(sp)
        staff_map[username] = s_user

    db.session.commit()

    # Assign staff to Counter 1 of GM and CARD for active demo
    gm_c1 = counter_map.get('GM_1')
    if gm_c1 and 'staff_gm' in staff_map:
        gm_c1.assigned_staff_id = staff_map['staff_gm'].id
        gm_c1.status = 'Busy'

    card_c1 = counter_map.get('CARD_1')
    if card_c1 and 'staff_cardio' in staff_map:
        card_c1.assigned_staff_id = staff_map['staff_cardio'].id
        card_c1.status = 'Available'

    # C. Patient Accounts (At least 10 demo patients)
    patient_defs = [
        ('patient', 'Johnathan Doe', 'patient@mediqueue.com', '+1-555-0201', 'O+', '1992-05-14', '742 Evergreen Terrace'),
        ('john_doe', 'Johnathan Doe', 'john.doe@gmail.com', '+1-555-0201', 'O+', '1992-05-14', '742 Evergreen Terrace'),
        ('emma_watson', 'Emma Watson', 'emma.w@gmail.com', '+1-555-0202', 'A+', '1990-04-15', '45 Parkside Crescent'),
        ('robert_smith', 'Robert Smith', 'robert.smith@yahoo.com', '+1-555-0203', 'B+', '1985-11-20', '12 Baker Street'),
        ('lisa_ray', 'Lisa Ray', 'lisa.ray@gmail.com', '+1-555-0204', 'AB+', '1965-08-30', '88 Sunset Boulevard'),
        ('david_kim', 'David Kim', 'david.kim@outlook.com', '+1-555-0205', 'O-', '1995-02-18', '21 Elm Street'),
        ('clara_oswald', 'Clara Oswald', 'clara.o@gmail.com', '+1-555-0206', 'A-', '1993-11-23', '350 Fifth Avenue'),
        ('harvey_specter', 'Harvey Specter', 'harvey@specter.com', '+1-555-0207', 'O+', '1978-01-22', '100 Wall Street'),
        ('bruce_wayne', 'Bruce Wayne', 'bruce@wayne-enterprises.com', '+1-555-0208', 'B-', '1982-02-19', '1007 Mountain Drive'),
        ('peter_parker', 'Peter Parker', 'peter@dailybugle.net', '+1-555-0209', 'A+', '2001-08-10', '20 Ingram Street'),
        ('diana_prince', 'Diana Prince', 'diana@themyscira.gov', '+1-555-0210', 'O+', '1988-03-22', '1600 Pennsylvania Ave')
    ]

    patient_map = {}
    for username, full_name, email, phone, blood, dob, address in patient_defs:
        p_user = User.query.filter_by(username=username).first()
        if not p_user:
            p_user = User(
                username=username,
                full_name=full_name,
                role='patient',
                email=email,
                phone=phone,
                is_active_account=True,
                must_change_password=False
            )
            p_user.set_password('Patient@123')
            db.session.add(p_user)
            db.session.flush()

            pp = PatientProfile(
                user_id=p_user.id,
                blood_group=blood,
                date_of_birth=dob,
                address=address,
                emergency_contact="+1-555-9999"
            )
            db.session.add(pp)
        patient_map[username] = p_user

    db.session.commit()

    # 5. Tokens & Real Service Records for Today
    today_str = datetime.now().strftime('%Y-%m-%d')
    now = datetime.utcnow()

    # Check if tokens exist today
    if QueueToken.query.filter_by(date=today_str).count() == 0:
        gm_id = dept_map['GM'].id
        card_id = dept_map['CARD'].id
        orth_id = dept_map['ORTH'].id
        ped_id = dept_map['PED'].id
        gm_c1_id = gm_c1.id if gm_c1 else 1

        staff_gm = staff_map.get('staff_gm')
        staff_gm_id = staff_gm.id if staff_gm else 1

        # A. Completed Token 1: David Kim (GM-101)
        t1 = QueueToken(
            token_number='GM-101',
            patient_id=patient_map['david_kim'].id,
            department_id=gm_id,
            counter_id=gm_c1_id,
            status='COMPLETED',
            date=today_str,
            created_at=now - timedelta(minutes=55),
            called_at=now - timedelta(minutes=50),
            completed_at=now - timedelta(minutes=38)
        )
        db.session.add(t1)
        db.session.flush()

        sr1 = ServiceRecord(
            token_id=t1.id,
            department_id=gm_id,
            counter_id=gm_c1_id,
            staff_id=staff_gm_id,
            start_time=now - timedelta(minutes=50),
            end_time=now - timedelta(minutes=38),
            duration_minutes=12.0,
            notes='General physical checkup and blood pressure assessment.'
        )
        db.session.add(sr1)

        # B. Completed Token 2: Clara Oswald (GM-102)
        t2 = QueueToken(
            token_number='GM-102',
            patient_id=patient_map['clara_oswald'].id,
            department_id=gm_id,
            counter_id=gm_c1_id,
            status='COMPLETED',
            date=today_str,
            created_at=now - timedelta(minutes=36),
            called_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=18)
        )
        db.session.add(t2)
        db.session.flush()

        sr2 = ServiceRecord(
            token_id=t2.id,
            department_id=gm_id,
            counter_id=gm_c1_id,
            staff_id=staff_gm_id,
            start_time=now - timedelta(minutes=30),
            end_time=now - timedelta(minutes=18),
            duration_minutes=12.0,
            notes='Fever and viral symptom consultation with medication prescription.'
        )
        db.session.add(sr2)

        # C. Currently Serving Token: Robert Smith (GM-103)
        t3 = QueueToken(
            token_number='GM-103',
            patient_id=patient_map['robert_smith'].id,
            department_id=gm_id,
            counter_id=gm_c1_id,
            status='SERVING',
            date=today_str,
            created_at=now - timedelta(minutes=22),
            called_at=now - timedelta(minutes=8),
            serving_started_at=now - timedelta(minutes=6)
        )
        db.session.add(t3)
        db.session.flush()
        if gm_c1:
            gm_c1.current_token_id = t3.id

        # D. Waiting Token with Priority Triage: Lisa Ray (GM-104)
        t4 = QueueToken(
            token_number='GM-104',
            patient_id=patient_map['lisa_ray'].id,
            department_id=gm_id,
            status='WAITING',
            is_priority=True,
            priority_reason='Elderly patient exhibiting acute chest tightness - flagged by triage nurse',
            priority_by=staff_gm_id,
            date=today_str,
            created_at=now - timedelta(minutes=16)
        )
        db.session.add(t4)

        # E. Waiting Token Regular: John Doe (GM-105)
        t5 = QueueToken(
            token_number='GM-105',
            patient_id=patient_map['john_doe'].id,
            department_id=gm_id,
            status='WAITING',
            is_priority=False,
            date=today_str,
            created_at=now - timedelta(minutes=12)
        )
        db.session.add(t5)

        # F. Waiting Token Regular: Emma Watson (GM-106)
        t6 = QueueToken(
            token_number='GM-106',
            patient_id=patient_map['emma_watson'].id,
            department_id=gm_id,
            status='WAITING',
            is_priority=False,
            date=today_str,
            created_at=now - timedelta(minutes=6)
        )
        db.session.add(t6)

        # G. Cardiology Waiting Token: Harvey Specter (CARD-101)
        t7 = QueueToken(
            token_number='CARD-101',
            patient_id=patient_map['harvey_specter'].id,
            department_id=card_id,
            status='WAITING',
            is_priority=False,
            date=today_str,
            created_at=now - timedelta(minutes=14)
        )
        db.session.add(t7)

        # H. Paediatrics Completed Token: Emma Watson child checkup (PED-101)
        t8 = QueueToken(
            token_number='PED-101',
            patient_id=patient_map['emma_watson'].id,
            department_id=ped_id,
            status='COMPLETED',
            date=today_str,
            created_at=now - timedelta(hours=2),
            called_at=now - timedelta(hours=1, minutes=50),
            completed_at=now - timedelta(hours=1, minutes=38)
        )
        db.session.add(t8)
        db.session.flush()

        sr8 = ServiceRecord(
            token_id=t8.id,
            department_id=ped_id,
            counter_id=counter_map['PED_1'].id if 'PED_1' in counter_map else 1,
            staff_id=staff_map.get('staff_ped', staff_gm).id,
            start_time=now - timedelta(hours=1, minutes=50),
            end_time=now - timedelta(hours=1, minutes=38),
            duration_minutes=12.0,
            notes='Infant routine developmental and immunization evaluation.'
        )
        db.session.add(sr8)

        # 6. Pre-seeded Audit Logs
        logs = [
            AuditLog(user_id=staff_gm_id, action='CALL_TOKEN', target_type='token', target_id=str(t3.id), old_value='WAITING', new_value='CALLED', details=f"Called token GM-103 to {gm_c1.name if gm_c1 else 'Counter 1'}", created_at=now - timedelta(minutes=8)),
            AuditLog(user_id=staff_gm_id, action='FLAG_PRIORITY', target_type='token', target_id=str(t4.id), old_value='0', new_value='1', details="Flagged GM-104: Acute symptom triage priority", created_at=now - timedelta(minutes=15)),
            AuditLog(user_id=staff_gm_id, action='COMPLETE_SERVICE', target_type='token', target_id=str(t2.id), old_value='SERVING', new_value='COMPLETED', details="Completed consultation for GM-102 (Duration: 12.0m)", created_at=now - timedelta(minutes=18)),
            AuditLog(user_id=admin_user.id, action='NAME_EDIT', target_type='hospital_setting', target_id='hospital_name', old_value='General Clinic', new_value='MediQueue General Hospital', details="Admin updated Hospital Name", created_at=now - timedelta(days=1))
        ]
        for l in logs:
            db.session.add(l)

        # 7. Pre-seeded Sample In-App Notifications
        notifs = [
            Notification(user_id=patient_map['john_doe'].id, title="Token Confirmed", message="Your token GM-105 has been registered in General Medicine.", category="info", created_at=now - timedelta(minutes=12)),
            Notification(user_id=patient_map['robert_smith'].id, title="Token Called", message="Please report to GM Counter 1 for consultation.", category="warning", created_at=now - timedelta(minutes=8)),
            Notification(user_id=admin_user.id, title="System Operational", message="MediQueue smart optimization engine initialized with 9 departments and 18 counters.", category="success", created_at=now - timedelta(hours=1))
        ]
        for n in notifs:
            db.session.add(n)

        # 8. Sample Login Histories
        histories = [
            LoginHistory(user_id=admin_user.id, ip_address='127.0.0.1', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)', login_time=now - timedelta(hours=3), status='SUCCESS'),
            LoginHistory(user_id=staff_gm_id, ip_address='127.0.0.1', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)', login_time=now - timedelta(hours=2), status='SUCCESS'),
            LoginHistory(user_id=patient_map['john_doe'].id, ip_address='127.0.0.1', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)', login_time=now - timedelta(minutes=15), status='SUCCESS')
        ]
        for h in histories:
            db.session.add(h)

        db.session.commit()

    print("[SUCCESS] Seeded MediQueue data successfully.")

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        force = '--reset' in sys.argv
        seed_database(force_reset=force)
