/**
 * MediQueue - Global Client-Side Application Controller
 * Handles Socket.IO, Dark Mode Toggle, In-App Notifications,
 * and Section 7 Universal Inline Name Editing Modal.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Dark Mode Initialization
    initThemeToggle();

    // 2. Socket.IO Connection
    initSocketIO();

    // 3. Section 7: Universal Inline Name & Setting Editor
    initUniversalNameEditor();

    // 4. In-App Notifications
    initNotificationSystem();
});

/* --- 1. Theme Toggle System --- */
function initThemeToggle() {
    const savedTheme = localStorage.getItem('mediqueue_theme') || 'light';
    applyTheme(savedTheme);

    const toggleBtn = document.getElementById('themeToggleBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
            localStorage.setItem('mediqueue_theme', nextTheme);
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const themeIcon = document.getElementById('themeToggleIcon');
    if (themeIcon) {
        if (theme === 'dark') {
            themeIcon.classList.remove('fa-moon');
            themeIcon.classList.add('fa-sun', 'text-warning');
        } else {
            themeIcon.classList.remove('fa-sun', 'text-warning');
            themeIcon.classList.add('fa-moon');
        }
    }
}

/* --- 2. Socket.IO Real-Time Stream --- */
function initSocketIO() {
    if (typeof io === 'undefined') return;

    window.mqSocket = io({ transports: ['websocket', 'polling'] });

    const indicator = document.getElementById('socketStatusIndicator');

    window.mqSocket.on('connect', () => {
        if (indicator) {
            indicator.innerHTML = '<span class="pulse-indicator me-1"></span> Live Data Stream';
            indicator.className = 'badge bg-success-subtle text-success px-3 py-2';
        }
    });

    window.mqSocket.on('disconnect', () => {
        if (indicator) {
            indicator.innerHTML = '<i class="fa-solid fa-triangle-exclamation me-1"></i> Reconnecting...';
            indicator.className = 'badge bg-warning-subtle text-warning px-3 py-2';
        }
    });

    // Handle real-time name edits across all dashboards
    window.mqSocket.on('name_updated', (data) => {
        const selector = `[data-editable-id="${data.entity_type}_${data.entity_id}"]`;
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            el.textContent = data.new_value;
        });

        if (data.entity_type === 'setting' && data.entity_id === 'hospital_name') {
            document.querySelectorAll('.hospital-name-display').forEach(el => el.textContent = data.new_value);
        }
    });

    // Handle token called alert
    window.mqSocket.on('token_called', (data) => {
        // If on public board or patient dashboard
        if (window.onTokenCalled) {
            window.onTokenCalled(data);
        }
    });
}

/* --- 3. SECTION 7: Universal Inline Name & Hospital Setting Editor --- */
function initUniversalNameEditor() {
    const editModalEl = document.getElementById('universalEditModal');
    if (!editModalEl) return;

    const modal = new bootstrap.Modal(editModalEl);
    const form = document.getElementById('universalEditForm');
    const titleEl = document.getElementById('editModalTitle');
    const labelEl = document.getElementById('editModalLabel');
    const inputEl = document.getElementById('editModalInput');
    const typeEl = document.getElementById('editEntityType');
    const idEl = document.getElementById('editEntityId');
    const fieldEl = document.getElementById('editFieldName');

    // Attach click listeners to all edit pencil buttons
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-edit-pencil');
        if (!btn) return;

        e.preventDefault();
        const entityType = btn.getAttribute('data-entity-type');
        const entityId = btn.getAttribute('data-entity-id');
        const fieldName = btn.getAttribute('data-field-name') || 'name';
        const currentValue = btn.getAttribute('data-current-value') || '';
        const title = btn.getAttribute('data-title') || 'Edit Name';

        titleEl.textContent = title;
        labelEl.textContent = `New ${title}:`;
        inputEl.value = currentValue;
        typeEl.value = entityType;
        idEl.value = entityId;
        fieldEl.value = fieldName;

        modal.show();
        setTimeout(() => inputEl.focus(), 300);
    });

    // Handle AJAX Form Submit
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> Saving...';

            const formData = new FormData(form);

            try {
                const response = await fetch('/admin/edit_name', {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    modal.hide();
                    showToast(data.message, 'success');

                    // Update DOM elements on current page
                    const selector = `[data-editable-id="${data.entity_type}_${data.entity_id}"]`;
                    document.querySelectorAll(selector).forEach(el => {
                        el.textContent = data.new_value;
                    });

                    // Update trigger button attribute
                    const btn = document.querySelector(`.btn-edit-pencil[data-entity-type="${data.entity_type}"][data-entity-id="${data.entity_id}"]`);
                    if (btn) {
                        btn.setAttribute('data-current-value', data.new_value);
                    }
                } else {
                    alert(data.error || 'Failed to update name.');
                }
            } catch (err) {
                console.error(err);
                alert('Connection error occurred while saving.');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        });
    }
}

/* --- 4. In-App Notification System --- */
function initNotificationSystem() {
    const bellBtn = document.getElementById('notificationDropdownBtn');
    const badge = document.getElementById('notificationBadge');
    const container = document.getElementById('notificationList');

    if (!bellBtn || !container) return;

    // Load initial notifications
    fetchNotifications();

    if (window.mqSocket) {
        window.mqSocket.on('new_notification', (data) => {
            fetchNotifications();
            showToast(`<b>${data.title}</b><br>${data.message}`, data.category || 'info');
        });
    }
}

async function fetchNotifications() {
    try {
        const res = await fetch('/api/notifications');
        const data = await res.json();

        if (data.success) {
            const badge = document.getElementById('notificationBadge');
            const container = document.getElementById('notificationList');

            if (badge) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            }

            if (container) {
                if (data.notifications.length === 0) {
                    container.innerHTML = '<div class="text-center py-3 text-muted small"><i class="fa-regular fa-bell-slash me-1"></i> No notifications</div>';
                    return;
                }

                container.innerHTML = data.notifications.map(n => `
                    <div class="dropdown-item py-2 border-bottom ${n.is_read ? 'opacity-75' : 'bg-light'}" onclick="markNotificationRead(${n.id}, '${n.link || ''}')">
                        <div class="d-flex justify-content-between align-items-center">
                            <span class="fw-bold small text-dark">${n.title}</span>
                            <span class="text-muted fs-xs">${n.created_at}</span>
                        </div>
                        <div class="small text-secondary mt-1">${n.message}</div>
                    </div>
                `).join('');
            }
        }
    } catch (e) {
        console.warn('Could not fetch notifications:', e);
    }
}

async function markNotificationRead(id, link) {
    try {
        await fetch(`/api/notifications/mark_read/${id}`, { method: 'POST' });
        if (link && link !== '') {
            window.location.href = link;
        } else {
            fetchNotifications();
        }
    } catch (e) {
        console.error(e);
    }
}

/* Toast Message Utility */
function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('mqToastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'mqToastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${type === 'warning' ? 'warning text-dark' : type === 'danger' ? 'danger' : type === 'success' ? 'success' : 'primary'} border-0 show shadow-lg`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toastEl);
    setTimeout(() => {
        toastEl.classList.remove('show');
        setTimeout(() => toastEl.remove(), 400);
    }, 4500);
}
