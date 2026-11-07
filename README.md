# MediQueue 🏥
### Smart Hospital Queue & Waiting-Time Optimization System
> TECHNOVATE 2.0 — Problem Statement 13

---

## Overview

**MediQueue** is a full-stack hospital queue management web application that eliminates physical waiting lines. It provides real-time digital token generation, smart waiting-time estimation, role-specific dashboards, and live queue updates — all running locally on Windows with zero cloud dependency.

| Feature | Detail |
|---|---|
| **Backend** | Python Flask (modular factory pattern) |
| **Database** | SQLite via Flask-SQLAlchemy |
| **Auth** | Flask-Login + Werkzeug password hashing |
| **Real-time** | Flask-SocketIO (WebSocket) |
| **Frontend** | Bootstrap 5 + Font Awesome + Chart.js |
| **QR Codes** | Python `qrcode` library |
| **Charts** | Chart.js (data from live DB) |
| **Export** | CSV reports |

---

## Quick Start

### 1 — Prerequisites

| Software | Minimum Version | Download |
|---|---|---|
| Python | 3.9+ | [python.org](https://www.python.org/downloads/) |
| VS Code | Any recent | [code.visualstudio.com](https://code.visualstudio.com/) |

### 2 — Clone / Extract the Project

Place the `MediQueue` folder anywhere you like, for example:
```
C:\Projects\MediQueue
```

### 3 — Create a Virtual Environment *(recommended)*

Open **PowerShell** or the **VS Code Terminal** and run:

```powershell
cd C:\Projects\MediQueue
python -m venv venv
```

**Activate it:**

```powershell
# PowerShell
.\venv\Scripts\Activate.ps1

# CMD (alternative)
venv\Scripts\activate.bat
```

> If PowerShell blocks activation, run this once:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 4 — Install Dependencies

```powershell
pip install -r requirements.txt
```

### 5 — Seed the Database

```powershell
python run.py --seed
```

This creates the SQLite database and populates it with demo departments, counters, staff, and patients.

### 6 — Start the Server

```powershell
python run.py
```

Open your browser and visit: **http://127.0.0.1:5000**

---

## Demo Credentials

> ⚠️ Change all passwords after your first login in a real deployment.

### Admin
| Field | Value |
|---|---|
| Username | `admin` |
| Password | `Admin@123` |
| **Note** | First login requires a password change |

### Staff Accounts

| Username | Password | Department |
|---|---|---|
| `dr_sharma` | `Staff@123` | General Medicine |
| `dr_patel` | `Staff@123` | Cardiology |
| `dr_mehta` | `Staff@123` | Orthopaedics |
| `dr_khan` | `Staff@123` | Dermatology |
| `dr_singh` | `Staff@123` | Paediatrics |
| `dr_rao` | `Staff@123` | ENT |
| `dr_verma` | `Staff@123` | Dental |
| `dr_bose` | `Staff@123` | Neurology |
| `dr_iyer` | `Staff@123` | Ophthalmology |

### Patient Accounts

| Username | Password |
|---|---|
| `patient1` through `patient11` | `Patient@123` |

---

## User Roles & Dashboards

### 🧑‍⚕️ Patient
- Register or log in
- Select a department and generate a digital token
- View current queue position, estimated wait time, and counter number
- Receive real-time status updates (Waiting → Called → Serving → Completed)
- Download or view QR code for token
- Cancel eligible tokens
- View full visit history

### 👩‍💼 Staff
- View the live waiting queue for their assigned department
- Call the next patient, start serving, complete or mark no-show
- Flag patients for clinical priority (moves them ahead in the queue)
- Set counter availability (Available / Busy / Offline)
- All actions are logged to the audit trail

### 🛡️ Admin
- Full KPI dashboard (8 live statistics)
- Five Chart.js analytics charts powered by real database data
- Manage departments, counters, staff, and patients
- **Edit any name from the UI** — hospital name, app name, department names, counter names, patient/staff display names — via the ✏️ pencil icon (Section 7, compulsory requirement)
- View login history and staff audit logs
- Export any report as CSV
- Configure default service duration and other hospital settings

---

## Resetting Demo Data

```powershell
# Full reset — drops and re-seeds all demo data
python run.py --reset --seed
```

---

## Project Structure

```
MediQueue/
├── app.py                  Flask application factory
├── run.py                  Entry point (--seed, --reset flags)
├── config.py               Configuration class
├── extensions.py           Shared Flask extensions (db, login, socketio)
├── requirements.txt
│
├── models/                 SQLAlchemy data models
│   ├── user.py             User, PatientProfile, StaffProfile
│   ├── department.py       Department
│   ├── counter.py          Counter
│   ├── queue_token.py      QueueToken, ServiceRecord
│   ├── notification.py     Notification
│   ├── audit_log.py        AuditLog, LoginHistory
│   └── settings.py         HospitalSetting
│
├── routes/                 Flask Blueprints
│   ├── auth.py             Login, register, logout, change password
│   ├── patient.py          Patient dashboard and token management
│   ├── staff.py            Staff dashboard and queue control
│   ├── admin.py            Admin dashboard, management, reports
│   ├── api.py              REST API for real-time polling fallback
│   └── main.py             Public live board (no login required)
│
├── services/               Business logic layer
│   ├── queue_service.py    Token generation, calling, completion
│   ├── waiting_time_service.py  Smart wait-time formula
│   ├── notification_service.py  In-app + Socket.IO notifications
│   └── analytics_service.py    KPIs and chart data
│
├── templates/              Jinja2 HTML templates
│   ├── base.html           Shared layout (nav, dark-mode, notifications)
│   ├── index.html          Public live queue board
│   ├── auth/               Login, register, change-password
│   ├── patient/            Patient dashboard, token view, profile
│   ├── staff/              Staff dashboard
│   ├── admin/              Admin dashboard, reports, audit logs
│   └── errors/             400, 403, 404, 500 error pages
│
├── static/
│   ├── css/style.css       Full design system (light + dark mode)
│   └── js/main.js          Dark mode, Socket.IO client, Section 7 editor
│
├── scripts/
│   └── seed_data.py        Database seeding script
│
└── tests/                  Pytest test suite
    ├── conftest.py          Fixtures and helpers
    ├── test_auth.py         Authentication tests
    ├── test_queue.py        Queue management tests
    ├── test_waiting_time.py Waiting-time formula tests
    └── test_permissions.py  RBAC and access-control tests
```

---

## Running Tests

```powershell
# Install test dependencies (once)
pip install pytest pytest-flask

# Run the full test suite
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_auth.py -v

# Run with coverage (optional)
pip install pytest-cov
python -m pytest tests/ --cov=. --cov-report=term-missing -v
```

---

## Smart Waiting-Time Formula

```
Estimated Wait = (Patients Ahead × Avg Service Duration) ÷ Active Counters
```

**Example:**
- 10 patients ahead
- Average service time: 5 minutes (calculated from actual completed visits)
- 2 active counters open

→ Estimated wait: **(10 × 5) ÷ 2 = 25 minutes**

The system automatically:
- Calculates average service time from real `ServiceRecord` history
- Falls back to department-configured default if no history exists
- Falls back to global admin-configurable default (10 min) as final fallback
- Respects clinical priority flags (priority patients move to front of queue)
- Updates all estimates in real-time via Socket.IO when any queue change occurs

> ℹ️ Displayed wait times are estimates based on current queue load.
> Emergency clinical triages may affect actual service order.

---

## Real-Time Updates (Socket.IO)

The following events update all connected clients automatically:

| Event | Trigger |
|---|---|
| `queue_updated` | Token called, completed, cancelled, or created |
| `counter_updated` | Counter status changes |
| `token_called` | Specific patient is called — highlights their token card |
| `name_updated` | Admin edits a name via Section 7 — updates DOM live |
| `notification` | New in-app notification dispatched |

A polling fallback via `/api/queue-summary` activates if WebSocket is unavailable.

---

## Section 7 — Editable Names (Compulsory)

The admin can click the ✏️ pencil icon beside any name on the dashboard to open an edit modal. Changes are:

1. Validated and saved to SQLite
2. Written to the audit log (old value, new value, admin ID, timestamp)
3. Broadcast via Socket.IO so all connected dashboards update live

Editable names include: hospital name, app display name, admin display name, patient names, staff names, department names, department descriptions, counter names, and counter labels.

---

## VS Code Setup

1. Open the `MediQueue` folder: **File → Open Folder**
2. Install the **Python** extension by Microsoft
3. Select the venv interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `.\venv\Scripts\python.exe`
4. Open the integrated terminal: `` Ctrl+` ``
5. Run `python run.py`

**Recommended extensions:**
- Python (Microsoft)
- Pylance
- SQLite Viewer (for inspecting `instance/mediqueue.db`)
- Thunder Client (for testing API endpoints)

---

## Key Dependencies

```
Flask==3.1.1
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-SocketIO==5.4.1
simple-websocket==1.1.0
Werkzeug==3.1.8
qrcode==8.1
Pillow==11.2.1
pytest==8.x
pytest-flask==1.x
```

Full list in [requirements.txt](requirements.txt).

---

## Security Notes

- Passwords are **never stored in plain text** — Werkzeug PBKDF2-SHA256 hashing
- Role-based access control enforced on every protected route
- Login history recorded for every login attempt (success and failure)
- All staff actions written to an immutable audit log
- Inactive accounts cannot log in
- Duplicate email and username prevention on registration
- Tokens can only be cancelled by their owner or authorized staff

---

## License

Built for TECHNOVATE 2.0 — Problem Statement 13. For educational and demonstration purposes.
