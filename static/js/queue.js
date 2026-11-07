/**
 * MediQueue - Real-time Queue Sync Engine (Socket.IO + Fallback Polling)
 */

document.addEventListener('DOMContentLoaded', () => {
    let socket = null;

    // Check if Socket.IO library is loaded
    if (typeof io !== 'undefined') {
        socket = io({
            transports: ['websocket', 'polling'],
            reconnectionAttempts: 5,
            timeout: 5000
        });

        socket.on('connect', () => {
            console.log("Connected to MediQueue Live Socket server.");
            const socketStatusEl = document.getElementById('socketStatusIndicator');
            if (socketStatusEl) {
                socketStatusEl.innerHTML = '<span class="pulse-indicator me-1"></span> Live Sync Connected';
            }
        });

        socket.on('disconnect', () => {
            console.log("Disconnected from Socket server. Switching to fallback sync.");
            const socketStatusEl = document.getElementById('socketStatusIndicator');
            if (socketStatusEl) {
                socketStatusEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> Sync Polling';
            }
        });

        // Event: Queue updated anywhere in hospital
        socket.on('queue_updated', (data) => {
            console.log("Queue update signal received:", data);
            handleQueueUpdate(data);
        });

        // Event: A specific token was called to a counter
        socket.on('token_called', (data) => {
            console.log("Token called event:", data);
            handleTokenCalled(data);
        });

        // Event: Counter status changed
        socket.on('counter_updated', (data) => {
            console.log("Counter updated event:", data);
            handleQueueUpdate(data);
        });
    }

    // Function to handle queue changes based on active view
    function handleQueueUpdate(data) {
        // If on Patient Dashboard, update patient token details
        if (document.getElementById('patientActiveTokenCard')) {
            updatePatientActiveToken();
        }

        // If on Public Index Monitor, update department cards & live table
        if (document.getElementById('publicLiveQueueBoard')) {
            updatePublicLiveSummary();
        }

        // If on Staff Dashboard
        if (document.getElementById('staffConsoleRoot')) {
            updateStaffConsole();
        }

        // If on Admin Dashboard, update admin charts and KPI counts
        if (document.getElementById('adminDashboardRoot')) {
            updateAdminData();
        }
    }

    // Handle token called
    function handleTokenCalled(data) {
        const myActiveTokenNumEl = document.getElementById('myActiveTokenNumber');
        if (myActiveTokenNumEl) {
            const myTokenNum = myActiveTokenNumEl.innerText.trim();
            if (myTokenNum === data.token_number) {
                // Patient's turn!
                showTurnNotification(data.token_number, data.counter_name);
                // Also trigger an alert banner
                const turnBanner = document.getElementById('turnUrgentBanner');
                if (turnBanner) {
                    turnBanner.classList.remove('d-none');
                    const counterSpan = document.getElementById('turnCounterName');
                    if (counterSpan) counterSpan.innerText = data.counter_name;
                }
                updatePatientActiveToken();
            }
        }
    }

    // 1. Update Patient Active Token details via API
    function updatePatientActiveToken() {
        fetch('/api/patient/active_token')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.token) {
                    const t = data.token;
                    const posEl = document.getElementById('liveQueuePosition');
                    const aheadEl = document.getElementById('livePatientsAhead');
                    const waitEl = document.getElementById('liveEstimatedWait');
                    const servingEl = document.getElementById('liveCurrentServing');
                    const statusBadgeEl = document.getElementById('liveTokenStatusBadge');
                    const progressBarEl = document.getElementById('liveQueueProgress');

                    if (posEl) posEl.innerText = t.position ? `#${t.position}` : (t.status === 'SERVING' ? 'Serving Now' : '--');
                    if (aheadEl) aheadEl.innerText = t.patients_ahead !== null ? t.patients_ahead : 0;
                    if (waitEl) waitEl.innerText = `${t.estimated_wait_minutes} mins`;
                    if (servingEl) servingEl.innerText = t.current_serving || 'None';

                    if (statusBadgeEl) {
                        statusBadgeEl.innerText = t.status;
                        statusBadgeEl.className = `badge fs-6 ${t.status === 'SERVING' ? 'badge-status-serving' : 'badge-status-waiting'}`;
                    }

                    if (progressBarEl) {
                        // Calculate percentage progress: (1 / (ahead + 1)) * 100
                        const ahead = t.patients_ahead || 0;
                        const pct = t.status === 'SERVING' ? 100 : Math.min(95, Math.max(10, Math.round((1 / (ahead + 1)) * 100)));
                        progressBarEl.style.width = `${pct}%`;
                        progressBarEl.setAttribute('aria-valuenow', pct);
                    }
                } else {
                    // Token might have been completed or cancelled
                    const refreshNotice = document.getElementById('tokenCompletedNotice');
                    if (refreshNotice) refreshNotice.classList.remove('d-none');
                }
            })
            .catch(err => console.error("Error refreshing patient token:", err));
    }

    // 2. Update Public Index Monitor
    function updatePublicLiveSummary() {
        fetch('/api/queue/summary')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.departments) {
                    data.departments.forEach(dept => {
                        // Update waiting badge
                        const waitCountEl = document.getElementById(`dept-wait-${dept.id}`);
                        if (waitCountEl) waitCountEl.innerText = dept.waiting_count;

                        // Update serving badge
                        const servingEl = document.getElementById(`dept-serving-${dept.id}`);
                        if (servingEl) servingEl.innerText = dept.serving_tokens.join(', ');

                        // Update estimated wait
                        const estEl = document.getElementById(`dept-est-${dept.id}`);
                        if (estEl) estEl.innerText = `~${dept.estimated_wait_minutes}m`;
                    });
                }
            })
            .catch(err => console.error("Error updating public summary:", err));
    }

    // 3. Update Staff Console
    function updateStaffConsole() {
        const deptIdEl = document.getElementById('staffActiveDeptId');
        if (!deptIdEl) return;
        const deptId = deptIdEl.value;

        fetch(`/api/queue/department/${deptId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const queueCountEl = document.getElementById('staffWaitingCount');
                    if (queueCountEl && data.queue) {
                        queueCountEl.innerText = data.queue.waiting.length;
                    }
                    // If waiting table exists, re-render rows
                    renderStaffWaitingTable(data.queue.waiting);
                }
            })
            .catch(err => console.error("Error updating staff console:", err));
    }

    function renderStaffWaitingTable(waitingList) {
        const tbody = document.getElementById('staffWaitingTableBody');
        if (!tbody) return;

        if (!waitingList || waitingList.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4"><i class="fa-solid fa-clipboard-check fs-3 d-block mb-2 text-success"></i>All caught up! No waiting patients in this queue.</td></tr>`;
            return;
        }

        let html = '';
        waitingList.forEach((token, index) => {
            const priorityBadge = token.is_priority
                ? `<span class="badge badge-priority"><i class="fa-solid fa-triangle-exclamation me-1"></i>Priority</span>`
                : `<span class="badge bg-secondary-subtle text-secondary">Standard</span>`;

            html += `
            <tr class="${token.is_priority ? 'table-warning' : ''}">
                <td class="fw-bold text-muted">#${index + 1}</td>
                <td>
                    <span class="fw-bold fs-6 text-primary">${token.token_number}</span>
                    ${priorityBadge}
                </td>
                <td>
                    <div class="fw-semibold text-dark">${token.patient_name}</div>
                    <div class="small text-muted">${token.patient_phone || 'No phone'}</div>
                </td>
                <td>
                    <span class="small text-muted"><i class="fa-regular fa-clock me-1"></i>${token.created_at.split(' ')[1] || token.created_at}</span>
                </td>
                <td>
                    <span class="badge badge-status-waiting">WAITING</span>
                </td>
                <td class="text-end">
                    <form action="/staff/call_next" method="POST" class="d-inline">
                        <input type="hidden" name="counter_id" value="${document.getElementById('staffActiveCounterId')?.value || ''}">
                        <input type="hidden" name="department_id" value="${token.department_id}">
                        <input type="hidden" name="target_token_id" value="${token.id}">
                        <button type="submit" class="btn btn-sm btn-outline-primary" title="Call this specific patient">
                            <i class="fa-solid fa-bullhorn me-1"></i> Call
                        </button>
                    </form>
                </td>
            </tr>`;
        });
        tbody.innerHTML = html;
    }

    // 4. Update Admin Dashboard live data
    function updateAdminData() {
        fetch('/api/admin/data')
            .then(res => res.json())
            .then(resp => {
                if (resp.success && resp.data) {
                    const kpis = resp.data.kpis;
                    const setVal = (id, val) => {
                        const el = document.getElementById(id);
                        if (el) el.innerText = val;
                    };
                    setVal('kpi-total-today', kpis.total_patients_today);
                    setVal('kpi-waiting', kpis.total_waiting);
                    setVal('kpi-serving', kpis.currently_serving);
                    setVal('kpi-completed', kpis.completed_services);
                    setVal('kpi-cancelled', kpis.cancelled_tokens);
                    setVal('kpi-noshow', kpis.noshow_tokens);
                    setVal('kpi-active-counters', `${kpis.active_counters}/${kpis.total_counters}`);
                    setVal('kpi-avg-wait', `${kpis.avg_estimated_waiting_time}m`);
                    setVal('kpi-avg-service', `${kpis.avg_service_time}m`);

                    // Update Chart.js instances if global reference exists
                    if (window.adminCharts) {
                        if (window.adminCharts.statusChart && resp.data.charts.daily_status) {
                            window.adminCharts.statusChart.data.datasets[0].data = resp.data.charts.daily_status.datasets[0].data;
                            window.adminCharts.statusChart.update();
                        }
                    }
                }
            })
            .catch(err => console.error("Error updating admin data:", err));
    }

    // Periodic background sync fallback every 10 seconds
    setInterval(() => {
        handleQueueUpdate({});
    }, 10000);
});
