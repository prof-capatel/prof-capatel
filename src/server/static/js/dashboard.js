/* ==========================================================
   Face Recognition Attendance System - Client JavaScript
   ========================================================== */

function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initLiveStream();
    initFilters();

    // Prevent accidental mouse-wheel adjustment on focused numeric inputs
    document.addEventListener("wheel", (e) => {
        if (document.activeElement && document.activeElement.type === "number") {
            document.activeElement.blur();
        }
    }, { passive: true });
});

/**
 * Initializes Server-Sent Events (SSE) for Real-Time Attendance Updates
 */
function initLiveStream() {
    const liveFeedContainer = document.getElementById("liveFeedContainer");
    const streamStatusBadge = document.getElementById("streamStatusBadge");

    if (!liveFeedContainer) return;

    const eventSource = new EventSource("/api/v1/attendance/live-stream");

    eventSource.onopen = () => {
        console.log("[*] SSE Live Stream Connected.");
        if (streamStatusBadge) {
            streamStatusBadge.innerHTML = '<span class="pulse-dot"></span> LIVE FEED ACTIVE';
        }
    };

    eventSource.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.type === "ATTENDANCE_LOGGED") {
                handleNewAttendanceEvent(payload.data);
            } else if (payload.type === "MANUAL_OVERRIDE_LOGGED") {
                handleManualOverrideEvent(payload.data);
            } else if (payload.type === "SPOOF_ATTEMPT") {
                handleSpoofAttemptEvent(payload.data);
            }
        } catch (e) {
            // Ping or parse error
        }
    };

    eventSource.onerror = () => {
        console.warn("[!] SSE Connection interrupted. Reconnecting...");
        if (streamStatusBadge) {
            streamStatusBadge.innerHTML = '<span style="color:var(--accent-amber); font-weight:700;">● RECONNECTING...</span>';
        }
    };
}

const seenFeedRecordIds = new Set();

/**
 * Inserts new face attendance item into the live feed
 */
function handleNewAttendanceEvent(data) {
    if (!data) return;
    const recordId = data.id || `${data.student_id || data.roll_number}_${data.timestamp}`;
    if (seenFeedRecordIds.has(recordId)) {
        return; // Suppress duplicate display
    }
    seenFeedRecordIds.add(recordId);
    if (seenFeedRecordIds.size > 250) {
        const firstKey = seenFeedRecordIds.values().next().value;
        seenFeedRecordIds.delete(firstKey);
    }

    const liveFeed = document.getElementById("liveFeedContainer");
    if (!liveFeed) return;
    const emptyState = document.getElementById("emptyFeedState");
    if (emptyState) emptyState.remove();

    // Increment today's counters
    const presentCounter = document.getElementById("statPresentCount");
    if (presentCounter) {
        let current = parseInt(presentCounter.innerText) || 0;
        presentCounter.innerText = current + 1;
    }

    const item = document.createElement("div");
    item.className = "feed-item highlight";
    item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 14px;">
            <div class="feed-avatar">
                ${data.snapshot_path 
                    ? `<img src="/data/${data.snapshot_path}" alt="Face">` 
                    : `<span>${data.student_name ? data.student_name.charAt(0) : 'U'}</span>`}
            </div>
            <div>
                <h4 style="font-size: 14px; font-weight: 700; color: var(--text-heading);">${data.student_name || "Unknown Member"}</h4>
                <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 10px; margin-top: 2px;">
                    <span>ID: <strong>${data.roll_number || 'N/A'}</strong></span>
                    <span>•</span>
                    <span>Node: <strong>${data.node_id}</strong></span>
                </div>
            </div>
        </div>
        <div style="text-align: right;">
            <span class="badge badge-present">✓ ${data.match_confidence_pct}% Match</span>
            <div style="font-size: 11px; color: var(--text-light); margin-top: 4px;">Just now (${data.timestamp.split(' ')[1] || ''})</div>
        </div>
    `;

    liveFeed.prepend(item);

    // Trigger HUD recognition flash overlay if active on dashboard
    if (typeof window.showCaptureToast === "function") {
        try {
            window.showCaptureToast(
                data.student_name || "Employee",
                data.roll_number || "",
                data.match_confidence_pct || 99,
                data.punch_type || "Checked In",
                data.department || ""
            );
        } catch (err) {
            console.debug("HUD toast trigger notice:", err);
        }
    }

    setTimeout(() => {
        item.classList.remove("highlight");
    }, 4000);
}

/**
 * Inserts manual override item into the live feed
 */
function handleManualOverrideEvent(data) {
    const liveFeed = document.getElementById("liveFeedContainer");
    const emptyState = document.getElementById("emptyFeedState");
    if (emptyState) emptyState.remove();

    const item = document.createElement("div");
    item.className = "feed-item highlight";
    item.style.borderColor = "var(--badge-emerald-border)";
    item.style.background = "var(--badge-emerald-bg)";
    item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 14px;">
            <div class="feed-avatar" style="background: var(--badge-emerald-bg); color: var(--badge-emerald-text);">
                <i class="fa-solid fa-user-check"></i>
            </div>
            <div>
                <h4 style="font-size: 14px; font-weight: 700; color: var(--badge-emerald-text);">${data.student_name}</h4>
                <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 10px; margin-top: 2px;">
                    <span>Roll: <strong>${data.roll_number}</strong></span>
                    <span>•</span>
                    <span>Reason: <em>${data.override_reason || 'Manual Verification'}</em></span>
                </div>
            </div>
        </div>
        <div style="text-align: right;">
            <span class="badge badge-present"><i class="fa-solid fa-shield-check"></i> Manual check in/out</span>
            <div style="font-size: 11px; color: var(--text-light); margin-top: 4px;">By ${data.override_by || 'Admin'}</div>
        </div>
    `;

    liveFeed.prepend(item);

    setTimeout(() => {
        item.classList.remove("highlight");
    }, 4000);
}

/**
 * Inserts security warning banner when a spoof attack is blocked
 */
function handleSpoofAttemptEvent(data) {
    const liveFeed = document.getElementById("liveFeedContainer");
    if (!liveFeed) return;

    const emptyState = document.getElementById("emptyFeedState");
    if (emptyState) emptyState.remove();

    const item = document.createElement("div");
    item.className = "feed-item";
    item.style.border = "1px solid var(--badge-rose-border)";
    item.style.background = "var(--badge-rose-bg)";
    item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 14px;">
            <div class="feed-avatar" style="background: var(--badge-rose-bg); color: var(--accent-rose); border-color: var(--badge-rose-border);">
                <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <div>
                <h4 style="font-size: 14px; font-weight: 700; color: var(--badge-rose-text);">⚠️ Spoof Attack Blocked!</h4>
                <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 10px; margin-top: 2px;">
                    <span>Node: <strong>${data.node_id}</strong></span>
                    <span>•</span>
                    <span>${data.reasons ? data.reasons[0] : 'Photo/Screen detected'}</span>
                </div>
            </div>
        </div>
        <div style="text-align: right;">
            <span class="badge badge-unknown">ATTACK REFUSED</span>
            <div style="font-size: 11px; color: var(--text-light); margin-top: 4px;">${data.timestamp ? data.timestamp.split(' ')[1] : 'Just now'}</div>
        </div>
    `;

    liveFeed.prepend(item);
}

/**
 * Attendance Logs Multi-Parameter Filter Handlers
 */
function initFilters() {
    const filterBtn = document.getElementById("btnApplyFilter");
    if (filterBtn) {
        filterBtn.addEventListener("click", applyLogFilters);
    }
}

function selectLogsPreset(preset) {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const toIso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

    let s = new Date(now);
    let e = new Date(now);

    if (preset === 'today') {
        // today
    } else if (preset === 'week') {
        const day = now.getDay();
        const diff = now.getDate() - day + (day === 0 ? -6 : 1);
        s = new Date(now.setDate(diff));
        e = new Date();
    } else if (preset === 'month') {
        s = new Date(now.getFullYear(), now.getMonth(), 1);
        e = new Date();
    } else if (preset === 'last30') {
        s = new Date(now.getTime() - (29 * 24 * 60 * 60 * 1000));
        e = new Date();
    }

    const sStr = toIso(s);
    const eStr = toIso(e);

    if (document.getElementById("filterStartDate")) document.getElementById("filterStartDate").value = sStr;
    if (document.getElementById("filterEndDate")) document.getElementById("filterEndDate").value = eStr;
    if (document.getElementById("filterDate")) document.getElementById("filterDate").value = sStr;

    const dateLabel = document.getElementById("logsDateLabel");
    if (dateLabel) {
        dateLabel.innerText = sStr === eStr ? sStr : `${sStr} to ${eStr}`;
    }

    document.querySelectorAll('.preset-btn').forEach(btn => {
        if (btn.getAttribute('data-preset') === preset) {
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-secondary');
        } else {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
        }
    });

    applyLogFilters();
}

function onCustomLogsDateChange() {
    const sStr = document.getElementById("filterStartDate")?.value || "";
    const eStr = document.getElementById("filterEndDate")?.value || "";
    const dateLabel = document.getElementById("logsDateLabel");
    if (dateLabel) {
        dateLabel.innerText = sStr === eStr ? sStr : `${sStr} to ${eStr}`;
    }

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-secondary');
    });

    applyLogFilters();
}

async function applyLogFilters() {
    const startDate = document.getElementById("filterStartDate")?.value;
    const endDate = document.getElementById("filterEndDate")?.value;
    const dateInput = document.getElementById("filterDate")?.value;
    const rollInput = document.getElementById("filterRoll")?.value;
    const deptInput = document.getElementById("filterDept")?.value;
    const roleInput = document.getElementById("filterRole")?.value;
    const overrideInput = document.getElementById("filterOverride")?.value;
    const viewModeInput = document.getElementById("filterViewMode")?.value || "active";
    const tableBody = document.getElementById("logsTableBody");

    if (!tableBody) return;

    const colSpan = window.IS_CORPORATE ? 11 : 10;
    tableBody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center; padding: 24px; color: var(--text-muted); font-weight: 500;"><i class="fa-solid fa-spinner fa-spin"></i> Loading attendance audit records...</td></tr>`;

    let url = `/api/v1/attendance/records?limit=300&view_mode=${encodeURIComponent(viewModeInput)}`;
    if (startDate && endDate) {
        url += `&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    } else if (startDate) {
        url += `&start_date=${encodeURIComponent(startDate)}`;
    } else if (dateInput) {
        url += `&date_str=${encodeURIComponent(dateInput)}`;
    }

    if (rollInput) url += `&roll_number=${encodeURIComponent(rollInput)}`;
    if (deptInput) url += `&department=${encodeURIComponent(deptInput)}`;
    if (roleInput) url += `&user_role=${encodeURIComponent(roleInput)}`;
    if (overrideInput !== undefined && overrideInput !== "") url += `&is_override=${encodeURIComponent(overrideInput)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        renderLogsTable(data.records);
    } catch (e) {
        tableBody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center; color: var(--accent-rose); padding: 24px; font-weight: 600;">Failed to fetch logs from server.</td></tr>`;
    }
}

function formatAttendanceDateTime(dtStr) {
    if (!dtStr) return null;
    const s = String(dtStr).trim();
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/);
    if (m) {
        const year = m[1];
        const month = m[2];
        const day = m[3];
        const hour = m[4];
        const min = m[5];
        const sec = m[6] || "00";
        return `${day}-${month}-${year} ${hour}:${min}:${sec}`;
    }
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const hour = String(d.getHours()).padStart(2, '0');
        const min = String(d.getMinutes()).padStart(2, '0');
        const sec = String(d.getSeconds()).padStart(2, '0');
        return `${day}-${month}-${year} ${hour}:${min}:${sec}`;
    }
    return s;
}

function renderLogsTable(records) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    const isCorp = window.IS_CORPORATE || false;
    const colSpan = isCorp ? 11 : 10;

    if (!records || records.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center; padding: 36px; color: var(--text-muted);">No attendance records found matching filters.</td></tr>`;
        return;
    }

    tableBody.innerHTML = records.map(r => {
        let roleBadge = '<span class="badge badge-present">Student</span>';
        if (r.user_role === 'teacher') roleBadge = '<span class="badge badge-node">Faculty</span>';
        else if (r.user_role === 'admin_staff') roleBadge = '<span class="badge badge-amber">Admin Staff</span>';
        else if (r.user_role === 'employee') roleBadge = '<span class="badge badge-present">Employee</span>';
        else if (r.user_role === 'manager') roleBadge = '<span class="badge badge-node">Manager</span>';
        else if (r.user_role === 'contractor') roleBadge = '<span class="badge badge-amber">Contractor</span>';
        else if (r.user_role === 'intern') roleBadge = '<span class="badge badge-node">Intern</span>';
        else if (r.user_role === 'other') roleBadge = '<span class="badge badge-node">Other</span>';
        else if (r.user_role) {
            const formatted = r.user_role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            roleBadge = `<span class="badge badge-node">${formatted}</span>`;
        }

        let verificationBadge = `<span class="badge badge-present">✓ ${r.match_confidence_pct}% Face Match</span>`;
        if (r.is_manual_override) {
            verificationBadge = `<span class="badge badge-amber" title="Override Reason: ${r.override_reason || 'N/A'} (By ${r.override_by || 'Admin'})"><i class="fa-solid fa-shield-check"></i> Manual check in/out</span>`;
        } else if (r.is_self_attendance) {
            verificationBadge = `<span class="badge badge-emerald" title="GPS Dist: ${r.geo_distance_meters !== null ? r.geo_distance_meters + 'm' : 'Verified'} • Lat: ${r.geo_latitude || 'N/A'}, Lon: ${r.geo_longitude || 'N/A'}"><i class="fa-solid fa-satellite-dish"></i> ${r.match_confidence_pct}% (GPS)</span>`;
        }

        let nodeBadge = `<span class="badge ${r.is_manual_override ? 'badge-amber' : 'badge-node'}">${r.node_id}</span>`;
        if (r.is_self_attendance) {
            nodeBadge = `<span class="badge badge-emerald" title="GPS Geofenced Check-in"><i class="fa-solid fa-mobile-screen"></i> ${r.geo_distance_meters !== null ? r.geo_distance_meters + 'm from Campus' : 'Self-Mobile'}</span>`;
        }

        // Action button (Soft delete or Restore)
        let actionBtnHtml = '';
        if (r.is_deleted) {
            actionBtnHtml = `
                <div style="display: flex; gap: 6px; justify-content: flex-end; align-items: center;">
                    <span class="badge badge-rose" style="font-size: 10px; padding: 2px 6px;"><i class="fa-solid fa-trash-can"></i> Deleted</span>
                    <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; color: var(--accent-emerald); cursor: pointer;" title="Restore / Undelete attendance record" onclick="restoreAttendanceRecord(${r.id}, '${escapeHtml(r.student_name || 'Member')}')">
                        <i class="fa-solid fa-rotate-left"></i> Restore
                    </button>
                </div>
            `;
        } else {
            const timeForModal = (isCorp ? (r.check_in_time || r.timestamp) : r.timestamp) || 'N/A';
            const detailForModal = isCorp ? (r.punch_type || 'CHECK_IN') : (r.node_id || 'NODE');
            actionBtnHtml = `
                <div style="display: flex; gap: 6px; justify-content: flex-end; align-items: center;">
                    <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; color: var(--accent-rose); border-color: rgba(239, 68, 68, 0.25); cursor: pointer;" title="Soft delete record" onclick="openDeleteAttendanceModal(${r.id}, '${escapeHtml(r.student_name || 'Member')}', '${escapeHtml(timeForModal)}', '${escapeHtml(detailForModal)}')">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            `;
        }

        if (isCorp) {
            // Corporate check-in/out presentation: Calendar Date + Precise Timestamp (DD-MM-YYYY HH:MM:SS)
            let formattedIn = formatAttendanceDateTime(r.check_in_time || r.timestamp);
            let inTime = formattedIn || r.check_in_short || '--:--';

            let formattedOut = formatAttendanceDateTime(r.check_out_time);
            let outTime = formattedOut || (r.check_out_time ? r.check_out_time : '<span style="color: var(--text-muted);">--:--</span>');
            
            let durationHtml = '<span style="color: var(--text-muted);">--</span>';
            if (r.work_duration_formatted) {
                durationHtml = `<strong style="color: var(--accent-primary);"><i class="fa-solid fa-stopwatch" style="margin-right: 4px; font-size: 11px;"></i>${r.work_duration_formatted}</strong>`;
            } else if (r.check_in_time && !r.check_out_time && r.shift_status !== 'MISSED_CHECKOUT') {
                durationHtml = `<span class="badge badge-amber" style="font-size: 11px;"><i class="fa-solid fa-person-walking"></i> In Progress</span>`;
            }

            let statusBadge = `<span class="badge badge-present"><i class="fa-solid fa-check"></i> On Time</span>`;
            if (r.shift_status === 'LATE_CHECKIN' || r.shift_status === 'LATE') {
                statusBadge = `<span class="badge badge-amber"><i class="fa-solid fa-clock"></i> Late Check-In</span>`;
            } else if (r.shift_status === 'EARLY_DEPARTURE') {
                statusBadge = `<span class="badge badge-amber"><i class="fa-solid fa-arrow-right-from-bracket"></i> Early Departure</span>`;
            } else if (r.shift_status === 'COMPLETED') {
                statusBadge = `<span class="badge badge-present"><i class="fa-solid fa-circle-check"></i> Completed</span>`;
            } else if (r.shift_status === 'MISSED_CHECKOUT') {
                statusBadge = `<span class="badge badge-rose" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);"><i class="fa-solid fa-triangle-exclamation"></i> Missed Checkout</span>`;
            } else if (r.shift_status) {
                statusBadge = `<span class="badge badge-node">${r.shift_status}</span>`;
            }

            let desigBadge = `<span class="badge badge-sky"><i class="fa-solid fa-id-badge"></i> ${escapeHtml(r.designation || 'Staff')}</span>`;

            return `
                <tr style="${r.is_deleted ? 'opacity: 0.65; background: rgba(239, 68, 68, 0.04);' : ''}">
                    <td>#${r.id}</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div class="feed-avatar" style="width: 32px; height: 32px; font-size: 12px;">
                                ${r.snapshot_path ? `<img src="/data/${r.snapshot_path}" alt="Face">` : `<span>${(r.student_name || 'U').charAt(0)}</span>`}
                            </div>
                            <strong style="color: var(--text-heading);">${r.student_name || 'Unknown'}</strong>
                        </div>
                    </td>
                    <td><code>${r.roll_number || 'N/A'}</code></td>
                    <td>${desigBadge}</td>
                    <td>${r.department || 'N/A'}</td>
                    <td>${nodeBadge}</td>
                    <td><strong style="color: var(--text-heading); font-family: monospace; font-size: 12px;">${inTime}</strong></td>
                    <td><strong style="color: var(--text-heading); font-family: monospace; font-size: 12px;">${outTime}</strong></td>
                    <td>${durationHtml}</td>
                    <td>${statusBadge}</td>
                    <td style="text-align: right;">${actionBtnHtml}</td>
                </tr>
            `;
        }

        return `
            <tr style="${r.is_deleted ? 'opacity: 0.65; background: rgba(239, 68, 68, 0.04);' : ''}">
                <td>#${r.id}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="feed-avatar" style="width: 32px; height: 32px; font-size: 12px;">
                            ${r.snapshot_path ? `<img src="/data/${r.snapshot_path}" alt="Face">` : `<span>${(r.student_name || 'U').charAt(0)}</span>`}
                        </div>
                        <strong style="color: var(--text-heading);">${r.student_name || 'Unknown'}</strong>
                    </div>
                </td>
                <td><code>${r.roll_number || 'N/A'}</code></td>
                <td>${roleBadge}</td>
                <td>${r.department || 'N/A'}</td>
                <td><span class="badge badge-node">${r.class_semester || 'General'}</span></td>
                <td>${nodeBadge}</td>
                <td><span style="font-family: monospace; font-size: 12px;">${formatAttendanceDateTime(r.timestamp) || r.timestamp || '--'}</span></td>
                <td>${verificationBadge}</td>
                <td style="text-align: right;">${actionBtnHtml}</td>
            </tr>
        `;
    }).join("");
}

function openDeleteAttendanceModal(recordId, memberName, timestamp, punchDetails) {
    const modal = document.getElementById("deleteAttendanceModal");
    if (!modal) return;
    document.getElementById("deleteTargetRecordId").value = recordId;
    const idEl = document.getElementById("deleteModalRecordId");
    if (idEl) idEl.textContent = `#${recordId}`;
    const nameEl = document.getElementById("deleteModalMemberName");
    if (nameEl) nameEl.textContent = memberName;
    const timeEl = document.getElementById("deleteModalTimestamp");
    if (timeEl) timeEl.textContent = timestamp;
    const detEl = document.getElementById("deleteModalDetails");
    if (detEl) detEl.textContent = punchDetails;
    modal.classList.add("active");
}

function closeDeleteAttendanceModal() {
    const modal = document.getElementById("deleteAttendanceModal");
    if (modal) modal.classList.remove("active");
}

async function executeDeleteAttendanceRecord() {
    const recordId = document.getElementById("deleteTargetRecordId")?.value;
    if (!recordId) return;

    const btn = document.getElementById("btnConfirmDeleteAttendance");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Deleting...';
    }

    try {
        const res = await fetch(`/api/v1/attendance/records/${recordId}`, {
            method: "DELETE",
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
            closeDeleteAttendanceModal();
            if (typeof showToast === "function") {
                showToast(data.message || `Record #${recordId} soft-deleted`, "success");
            }
            await applyLogFilters();
        } else {
            alert(data.detail || data.message || "Failed to delete attendance record.");
        }
    } catch (e) {
        alert("Network or server error while deleting record.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> <span>Confirm Delete</span>';
        }
    }
}

async function restoreAttendanceRecord(recordId, memberName) {
    if (!confirm(`Restore attendance log #${recordId} for ${memberName}? It will be reactivated and included in reports and payroll.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/attendance/records/${recordId}/restore`, {
            method: "POST",
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
            if (typeof showToast === "function") {
                showToast(data.message || `Record #${recordId} restored`, "success");
            }
            await applyLogFilters();
        } else {
            alert(data.detail || data.message || "Failed to restore record.");
        }
    } catch (e) {
        alert("Network error while restoring record.");
    }
}

function exportData(format) {
    const startDate = document.getElementById("filterStartDate")?.value || "";
    const endDate = document.getElementById("filterEndDate")?.value || "";
    const dateInput = document.getElementById("filterDate")?.value || "";
    const rollInput = document.getElementById("filterRoll")?.value || "";
    const deptInput = document.getElementById("filterDept")?.value || "";
    const roleInput = document.getElementById("filterRole")?.value || "";
    const overrideInput = document.getElementById("filterOverride")?.value || "";
    let url = `/api/v1/attendance/export?export_format=${format}`;
    if (startDate && endDate) {
        url += `&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    } else if (startDate) {
        url += `&start_date=${encodeURIComponent(startDate)}`;
    } else if (dateInput) {
        url += `&date_str=${encodeURIComponent(dateInput)}`;
    }
    if (rollInput) url += `&roll_number=${encodeURIComponent(rollInput)}`;
    if (deptInput) url += `&department=${encodeURIComponent(deptInput)}`;
    if (roleInput) url += `&user_role=${encodeURIComponent(roleInput)}`;
    if (overrideInput !== undefined && overrideInput !== "") url += `&is_override=${encodeURIComponent(overrideInput)}`;
    window.location.href = url;
}

/* ==========================================================
   Student Directory Multi-Parameter Filtering Handlers
   ========================================================== */
function onDirDeptFilterChanged() {
    const deptId = document.getElementById("dirDeptFilter")?.value || "";
    const classSelect = document.getElementById("dirClassFilter");
    const divSelect = document.getElementById("dirDivFilter");
    const desigSelect = document.getElementById("dirDesigFilter");

    if (classSelect) {
        Array.from(classSelect.options).forEach((opt, idx) => {
            if (idx === 0) {
                opt.style.display = "";
                return;
            }
            const optDeptId = opt.getAttribute("data-dept-id");
            if (!deptId || !optDeptId || optDeptId === deptId) {
                opt.style.display = "";
            } else {
                opt.style.display = "none";
            }
        });
        classSelect.value = "";
    }

    if (divSelect) {
        divSelect.value = "";
    }

    if (desigSelect) {
        Array.from(desigSelect.options).forEach((opt, idx) => {
            if (idx === 0) {
                opt.style.display = "";
                return;
            }
            const optDeptId = opt.getAttribute("data-dept-id");
            if (!deptId || !optDeptId || optDeptId === deptId) {
                opt.style.display = "";
            } else {
                opt.style.display = "none";
            }
        });
        desigSelect.value = "";
    }

    applyDirectoryFilters();
}

function onDirClassFilterChanged() {
    const classId = document.getElementById("dirClassFilter")?.value || "";
    const divSelect = document.getElementById("dirDivFilter");

    if (divSelect) {
        Array.from(divSelect.options).forEach((opt, idx) => {
            if (idx === 0) {
                opt.style.display = "";
                return;
            }
            const optClassId = opt.getAttribute("data-class-id");
            if (!classId || !optClassId || optClassId === classId) {
                opt.style.display = "";
            } else {
                opt.style.display = "none";
            }
        });
        divSelect.value = "";
    }

    applyDirectoryFilters();
}

window.currentDirectoryStatusFilter = "active";

function setEmployeeStatusFilter(statusVal) {
    window.currentDirectoryStatusFilter = statusVal;
    
    // Update active pill UI
    document.querySelectorAll(".status-pill-btn").forEach(btn => btn.classList.remove("active"));
    if (statusVal === "active") {
        document.getElementById("pillStatusActive")?.classList.add("active");
    } else if (statusVal === "relieved") {
        document.getElementById("pillStatusRelieved")?.classList.add("active");
    } else {
        document.getElementById("pillStatusAll")?.classList.add("active");
    }

    applyDirectoryFilters();
}

function applyDirectoryFilters() {
    const searchVal = (document.getElementById("dirSearchInput")?.value || "").toLowerCase().trim();
    const deptFilterEl = document.getElementById("dirDeptFilter");
    const deptIdVal = deptFilterEl?.value || "";
    const deptTextVal = deptIdVal && deptFilterEl ? (deptFilterEl.options[deptFilterEl.selectedIndex]?.text || "").toLowerCase().trim() : "";

    const desigFilterEl = document.getElementById("dirDesigFilter");
    const desigIdVal = desigFilterEl?.value || "";

    const shiftFilterEl = document.getElementById("dirShiftFilter");
    const shiftIdVal = shiftFilterEl?.value || "";

    const classIdVal = document.getElementById("dirClassFilter")?.value || "";
    const divIdVal = document.getElementById("dirDivFilter")?.value || "";
    const roleVal = document.getElementById("dirRoleFilter")?.value || "";
    const statusVal = window.currentDirectoryStatusFilter || "active";

    const rows = document.querySelectorAll(".student-row");
    let visibleCount = 0;

    rows.forEach(row => {
        const name = (row.getAttribute("data-name") || "").toLowerCase();
        const roll = (row.getAttribute("data-roll") || "").toLowerCase();
        const rowDeptId = row.getAttribute("data-dept-id") || "";
        const rowDept = (row.getAttribute("data-dept") || "").toLowerCase();
        const rowDesigId = row.getAttribute("data-desig-id") || "";
        const rowShiftId = row.getAttribute("data-shift-id") || "";
        const rowClassId = row.getAttribute("data-class-id") || "";
        const rowDivId = row.getAttribute("data-div-id") || "";
        const rowRole = row.getAttribute("data-role") || "student";
        const rowStatus = row.getAttribute("data-status") || "active";

        let matchSearch = !searchVal || name.includes(searchVal) || roll.includes(searchVal);
        let matchDept = !deptIdVal || rowDeptId === deptIdVal || (rowDept && rowDept === deptTextVal);
        let matchDesig = !desigIdVal || rowDesigId === desigIdVal;
        let matchShift = !shiftIdVal || rowShiftId === shiftIdVal;
        let matchClass = !classIdVal || rowClassId === classIdVal;
        let matchDiv = !divIdVal || rowDivId === divIdVal;
        let matchRole = !roleVal || rowRole === roleVal;
        let matchStatus = (statusVal === "all") || (rowStatus === statusVal);

        if (matchSearch && matchDept && matchDesig && matchShift && matchClass && matchDiv && matchRole && matchStatus) {
            row.style.display = "";
            visibleCount++;
        } else {
            row.style.display = "none";
        }
    });

    const countLabel = document.getElementById("dirFilterCountLabel");
    if (countLabel) {
        countLabel.innerText = `Showing ${visibleCount} of ${rows.length} profiles`;
    }
}

function resetDirectoryFilters() {
    if (document.getElementById("dirSearchInput")) document.getElementById("dirSearchInput").value = "";
    if (document.getElementById("dirDeptFilter")) document.getElementById("dirDeptFilter").value = "";
    if (document.getElementById("dirShiftFilter")) document.getElementById("dirShiftFilter").value = "";
    if (document.getElementById("dirRoleFilter")) document.getElementById("dirRoleFilter").value = "";
    
    const desigSelect = document.getElementById("dirDesigFilter");
    if (desigSelect) {
        Array.from(desigSelect.options).forEach(opt => opt.style.display = "");
        desigSelect.value = "";
    }

    const classSelect = document.getElementById("dirClassFilter");
    if (classSelect) {
        Array.from(classSelect.options).forEach(opt => opt.style.display = "");
        classSelect.value = "";
    }

    const divSelect = document.getElementById("dirDivFilter");
    if (divSelect) {
        Array.from(divSelect.options).forEach(opt => opt.style.display = "");
        divSelect.value = "";
    }

    setEmployeeStatusFilter("active");
}

function openRelieveModal(studentId, studentName, rollNumber) {
    const modal = document.getElementById("relieveEmployeeModal");
    if (!modal) return;

    let sName = studentName;
    let sRoll = rollNumber;
    if ((!sName || !sRoll) && window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
        const found = window.allTenantStudents.find(x => Number(x.id) === Number(studentId));
        if (found) {
            sName = sName || found.name;
            sRoll = sRoll || found.roll_number;
        }
    }
    if (!sName) {
        sName = document.getElementById(`stdNameLabel${studentId}`)?.innerText.trim() || "";
    }
    if (!sRoll) {
        sRoll = document.getElementById(`stdRollLabel${studentId}`)?.innerText.trim() || "";
    }

    const idInput = document.getElementById("relieveStudentId");
    if (idInput) idInput.value = studentId;

    const nameInput = document.getElementById("relieveStudentName");
    if (nameInput) nameInput.value = sRoll ? `${sName || ''} (${sRoll})` : (sName || '');
    
    // Set default date to today
    const todayStr = new Date().toISOString().split("T")[0];
    const dateInput = document.getElementById("relieveDateInput");
    if (dateInput) dateInput.value = todayStr;

    const reasonInput = document.getElementById("relieveReasonInput");
    if (reasonInput) reasonInput.value = "";

    const alertBox = document.getElementById("relieveResultAlert");
    if (alertBox) alertBox.style.display = "none";

    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeRelieveModal() {
    const modal = document.getElementById("relieveEmployeeModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

async function submitRelieveEmployee(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const studentId = document.getElementById("relieveStudentId")?.value;
    const statusVal = document.getElementById("relieveExitStatus")?.value || "RELIEVED";
    const dateVal = document.getElementById("relieveDateInput")?.value || "";
    const reasonVal = document.getElementById("relieveReasonInput")?.value || "";

    const btn = document.getElementById("btnConfirmRelieve");
    const alertBox = document.getElementById("relieveResultAlert");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Relieving...';
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}/relieve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                reason: reasonVal,
                employment_status: statusVal,
                relieved_at: dateVal,
            }),
        });

        const data = await res.json();
        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Employee successfully relieved.");
            }
            setTimeout(() => {
                closeRelieveModal();
                window.location.reload();
            }, 750);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Failed to relieve employee.");
            }
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-user-slash"></i> Confirm Relieving';
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-user-slash"></i> Confirm Relieving';
        }
    }
}

async function reinstateEmployee(studentId, studentName) {
    let sName = studentName;
    if (!sName && window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
        const found = window.allTenantStudents.find(x => Number(x.id) === Number(studentId));
        if (found) sName = found.name;
    }
    if (!sName) {
        sName = document.getElementById(`stdNameLabel${studentId}`)?.innerText.trim() || "";
    }
    if (!confirm(`Are you sure you want to reinstate "${sName || 'Employee'}" back to active employee status?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}/reinstate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: "Reinstated from Tenant Admin Directory" }),
        });
        const data = await res.json();

        if (res.ok) {
            alert(data.message || `"${sName || 'Employee'}" has been reinstated successfully!`);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to reinstate employee.");
        }
    } catch (err) {
        alert("Network error while reinstating employee.");
    }
}

/**
 * Delete Student / Employee
 */
async function deleteStudent(studentId, studentName) {
    let sName = studentName;
    if (!sName && window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
        const found = window.allTenantStudents.find(x => Number(x.id) === Number(studentId));
        if (found) sName = found.name;
    }
    if (!sName) {
        sName = document.getElementById(`stdNameLabel${studentId}`)?.innerText.trim() || "";
    }
    if (!confirm(`Are you sure you want to delete profile "${sName || 'Employee'}" and all associated face embeddings?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            alert(`Profile "${sName || 'Employee'}" deleted successfully.`);
            window.location.reload();
        } else {
            alert(`Error: ${data.detail || 'Could not delete profile'}`);
        }
    } catch (e) {
        alert("Failed to delete profile.");
    }
}

/* ==========================================================
   Department / Team Transfer Handlers
   ========================================================== */
function openTransferDepartmentModal(idOrObj, name, deptId, classId, divId) {
    const modal = document.getElementById("transferEmployeeModal");
    if (!modal) return;

    let s = {};
    let studentId = null;

    if (typeof idOrObj === "object" && idOrObj !== null) {
        s = idOrObj;
        studentId = s.id;
    } else if (idOrObj !== undefined && idOrObj !== null && String(idOrObj).trim() !== "") {
        studentId = Number(idOrObj);
        const cached = (window.allTenantStudents && Array.isArray(window.allTenantStudents))
            ? window.allTenantStudents.find(x => Number(x.id) === Number(studentId))
            : null;
        if (cached) {
            s = Object.assign({}, cached);
        } else {
            const domName = document.getElementById(`stdNameLabel${studentId}`)?.innerText.trim();
            const domRow = document.getElementById(`studentRow${studentId}`);
            s = {
                id: studentId,
                name: name || domName || "",
                department_id: deptId || (domRow?.getAttribute("data-dept-id") ? Number(domRow.getAttribute("data-dept-id")) : null),
                designation_id: domRow?.getAttribute("data-desig-id") ? Number(domRow.getAttribute("data-desig-id")) : null,
                class_id: classId || (domRow?.getAttribute("data-class-id") ? Number(domRow.getAttribute("data-class-id")) : null),
                division_id: divId || (domRow?.getAttribute("data-div-id") ? Number(domRow.getAttribute("data-div-id")) : null)
            };
        }
    }

    const idInput = document.getElementById("transferStudentId");
    if (idInput) idInput.value = s.id || studentId || "";

    const nameInput = document.getElementById("transferStudentName");
    if (nameInput) nameInput.value = s.name || name || "";
    
    const deptSelect = document.getElementById("transferTargetDept");
    if (deptSelect) {
        deptSelect.value = s.department_id || deptId || "";
        if (typeof onTransferDeptChanged === "function") onTransferDeptChanged(s.class_id || classId, s.designation_id);
    }

    const classSelect = document.getElementById("transferTargetClass");
    if (classSelect) {
        classSelect.value = s.class_id || classId || "";
        if (typeof onTransferClassChanged === "function") onTransferClassChanged(s.division_id || divId);
    }

    const divSelect = document.getElementById("transferTargetDiv");
    if (divSelect) {
        divSelect.value = s.division_id || divId || "";
    }

    const desigSelect = document.getElementById("transferTargetDesignation");
    if (desigSelect && s.designation_id) {
        desigSelect.value = s.designation_id;
    }

    const alertBox = document.getElementById("transferResultAlert");
    if (alertBox) alertBox.style.display = "none";

    const saveBtn = document.getElementById("btnConfirmTransfer") || document.getElementById("btnSaveTransfer");
    if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-arrow-right-arrow-left"></i> Confirm Transfer';
    }

    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeTransferDepartmentModal() {
    const modal = document.getElementById("transferEmployeeModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

function onTransferDeptChanged(targetClassId = null, targetDesigId = null) {
    const deptVal = document.getElementById("transferTargetDept")?.value;
    const deptId = deptVal ? parseInt(deptVal) : null;

    // 1. Cascading Designations for Corporate Tenants
    const desigSelect = document.getElementById("transferTargetDesignation");
    if (desigSelect) {
        if (window.allTenantDesignations && Array.isArray(window.allTenantDesignations)) {
            const filteredDesigs = deptId 
                ? window.allTenantDesignations.filter(d => !d.department_id || Number(d.department_id) === Number(deptId))
                : window.allTenantDesignations;
            let desigHtml = '<option value="">-- Choose New Designation --</option>';
            let stillValid = false;
            filteredDesigs.forEach(d => {
                const isSel = targetDesigId && Number(d.id) === Number(targetDesigId);
                if (isSel) stillValid = true;
                const codeTxt = d.code ? ` (${escapeHtml(d.code)})` : '';
                desigHtml += `<option value="${d.id}" data-dept-id="${d.department_id || ''}" data-title="${escapeHtml(d.title)}" ${isSel ? 'selected' : ''}>${escapeHtml(d.title)}${codeTxt}</option>`;
            });
            desigSelect.innerHTML = desigHtml;
            if (!stillValid && !targetDesigId) desigSelect.value = "";
        } else {
            Array.from(desigSelect.options).forEach((opt, idx) => {
                if (idx === 0) return;
                const dId = opt.getAttribute("data-dept-id");
                opt.hidden = (!deptVal || !dId || dId === deptVal) ? false : true;
            });
            if (desigSelect.selectedOptions[0]?.hidden) {
                desigSelect.value = "";
            }
        }
    }

    // 2. Cascading Classes & Divisions for Educational Tenants
    const classSelect = document.getElementById("transferTargetClass");
    if (classSelect && window.allTenantClasses && Array.isArray(window.allTenantClasses)) {
        const filteredClasses = deptId ? window.allTenantClasses.filter(c => c.department_id === deptId) : window.allTenantClasses;
        let classHtml = '<option value="">Unassigned / General</option>';
        let stillValid = false;
        filteredClasses.forEach(c => {
            const isSel = targetClassId && c.id === Number(targetClassId);
            if (isSel) stillValid = true;
            classHtml += `<option value="${c.id}" data-dept-id="${c.department_id || ''}" ${isSel ? 'selected' : ''}>${escapeHtml(c.name)}</option>`;
        });
        classSelect.innerHTML = classHtml;
        if (!stillValid && !targetClassId) classSelect.value = "";
    } else if (classSelect) {
        Array.from(classSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.hidden = (!deptVal || !dId || dId === deptVal) ? false : true;
        });
    }
    onTransferClassChanged();
}

function onTransferClassChanged(targetDivId = null) {
    const classVal = document.getElementById("transferTargetClass")?.value;
    const classId = classVal ? parseInt(classVal) : null;
    const divSelect = document.getElementById("transferTargetDiv");
    if (divSelect && window.allTenantDivisions && Array.isArray(window.allTenantDivisions)) {
        const filteredDivs = classId ? window.allTenantDivisions.filter(d => d.class_id === classId) : window.allTenantDivisions;
        let divHtml = '<option value="">Unassigned</option>';
        let stillValid = false;
        filteredDivs.forEach(dv => {
            const isSel = targetDivId && dv.id === Number(targetDivId);
            if (isSel) stillValid = true;
            divHtml += `<option value="${dv.id}" data-class-id="${dv.class_id}" ${isSel ? 'selected' : ''}>${escapeHtml(dv.name)}</option>`;
        });
        divSelect.innerHTML = divHtml;
        if (!stillValid && !targetDivId) divSelect.value = "";
    } else if (divSelect) {
        Array.from(divSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const cId = opt.getAttribute("data-class-id");
            opt.hidden = (!classVal || !cId || cId === classVal) ? false : true;
        });
    }
}

async function submitDepartmentTransfer(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const studentId = document.getElementById("transferStudentId")?.value;
    const deptSelect = document.getElementById("transferTargetDept");
    const deptId = deptSelect?.value;
    const desigSelect = document.getElementById("transferTargetDesignation");
    const desigId = desigSelect?.value || null;
    const desigTitle = desigSelect && desigSelect.selectedIndex > 0 ? (desigSelect.options[desigSelect.selectedIndex]?.getAttribute("data-title") || desigSelect.options[desigSelect.selectedIndex]?.text) : null;
    const classId = document.getElementById("transferTargetClass")?.value || null;
    const divId = document.getElementById("transferTargetDiv")?.value || null;

    if (!studentId || !deptId) {
        alert("Please select a target department.");
        return;
    }

    if (desigSelect && desigSelect.hasAttribute("required") && !desigId) {
        alert("Please select a target designation.");
        return;
    }

    const saveBtn = document.getElementById("btnConfirmTransfer") || document.getElementById("btnSaveTransfer");
    const alertBox = document.getElementById("transferResultAlert");

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Transferring...';
    }

    try {
        const payload = {
            department_id: parseInt(deptId),
            designation_id: desigId ? parseInt(desigId) : null,
            designation: desigTitle || null,
            class_id: classId ? parseInt(classId) : null,
            division_id: divId ? parseInt(divId) : null,
        };

        const res = await fetch(`/api/v1/enroll/student/${studentId}/transfer-department`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Transferred successfully!");
            }

            if (window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
                const sIdx = window.allTenantStudents.findIndex(x => Number(x.id) === Number(studentId));
                if (sIdx !== -1) {
                    const targetDeptName = deptSelect.options[deptSelect.selectedIndex]?.text || "";
                    window.allTenantStudents[sIdx].department_id = parseInt(deptId);
                    window.allTenantStudents[sIdx].department = targetDeptName;
                    if (desigId) {
                        window.allTenantStudents[sIdx].designation_id = parseInt(desigId);
                        window.allTenantStudents[sIdx].designation = desigTitle;
                    }
                    if (classId) window.allTenantStudents[sIdx].class_id = parseInt(classId);
                    if (divId) window.allTenantStudents[sIdx].division_id = parseInt(divId);
                }
            }

            setTimeout(() => {
                closeTransferDepartmentModal();
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-arrow-right-arrow-left"></i> Confirm Transfer';
                }
                window.location.reload();
            }, 600);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Transfer failed.");
            }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-arrow-right-arrow-left"></i> Confirm Transfer';
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-arrow-right-arrow-left"></i> Confirm Transfer';
        }
    }
}

/* ==========================================================
   LightBox Photo Viewer
   ========================================================== */
function openLightbox(url, caption) {
    const modal = document.getElementById("lightboxModal");
    const img = document.getElementById("lightboxImg");
    const cap = document.getElementById("lightboxCaption");
    if (!modal || !img) return;

    img.src = url;
    if (cap) cap.innerText = caption || "Enrolled Face Sample";
    modal.classList.add("active");
}

function closeLightbox() {
    const modal = document.getElementById("lightboxModal");
    if (modal) modal.classList.remove("active");
}

/* ==========================================================
   Edit Student Profile Modal (Cascading Dropdowns)
   ========================================================== */
function onEditRoleChanged() {
    const role = document.getElementById("editUserRole")?.value || "student";
    const classDivSec = document.getElementById("editClassDivSection");
    if (classDivSec) {
        // Classes and Divisions are relevant for students, optional for teachers/staff
        classDivSec.style.opacity = role === "student" ? "1" : "0.75";
    }
}

function onEditDeptSelectChanged(targetDesigId = null) {
    const deptVal = document.getElementById("editDepartmentSelect")?.value || "";
    const deptId = deptVal ? parseInt(deptVal) : null;
    const classSelect = document.getElementById("editClassSelect");
    const divSelect = document.getElementById("editDivisionSelect");
    const desigSelect = document.getElementById("editDesignationSelect");

    // 1. Dynamic Class Cascading (Educational)
    if (classSelect && window.allTenantClasses && Array.isArray(window.allTenantClasses)) {
        const currentClassVal = classSelect.value ? parseInt(classSelect.value) : null;
        const filteredClasses = deptId
            ? window.allTenantClasses.filter(c => c.department_id === deptId)
            : window.allTenantClasses;

        let classHtml = '<option value="">Unassigned / General</option>';
        let classStillValid = false;
        filteredClasses.forEach(c => {
            const isSel = currentClassVal && c.id === currentClassVal;
            if (isSel) classStillValid = true;
            classHtml += `<option value="${c.id}" data-dept-id="${c.department_id || ''}" ${isSel ? 'selected' : ''}>${escapeHtml(c.name)}</option>`;
        });
        classSelect.innerHTML = classHtml;
        if (!classStillValid) {
            classSelect.value = "";
        }
    }

    if (divSelect && window.allTenantDivisions && Array.isArray(window.allTenantDivisions)) {
        divSelect.innerHTML = '<option value="">Unassigned</option>';
        divSelect.value = "";
    }

    // 2. Dynamic Designation Cascading (Corporate / Institutional)
    if (desigSelect) {
        const desigs = (window.allTenantDesignations && Array.isArray(window.allTenantDesignations))
            ? window.allTenantDesignations
            : [];
        
        let desiredDesigId = (targetDesigId !== null && targetDesigId !== undefined && String(targetDesigId).trim() !== "")
            ? parseInt(targetDesigId)
            : (desigSelect.value ? parseInt(desigSelect.value) : null);

        let desigHtml = '<option value="">-- Unassigned Designation --</option>';

        if (desigs.length > 0) {
            const filteredDesigs = deptId
                ? desigs.filter(d => !d.department_id || d.department_id === deptId)
                : desigs;

            let desigStillValid = false;
            filteredDesigs.forEach(d => {
                const isSel = desiredDesigId && d.id === desiredDesigId;
                if (isSel) desigStillValid = true;
                const codeStr = d.code ? ` (${escapeHtml(d.code)})` : '';
                desigHtml += `<option value="${d.id}" data-dept-id="${d.department_id || ''}" data-title="${escapeHtml(d.title)}" data-template-id="${d.salary_template_id || ''}" ${isSel ? 'selected' : ''}>${escapeHtml(d.title)}${codeStr}</option>`;
            });
            desigSelect.innerHTML = desigHtml;
            if (desiredDesigId && desigStillValid) {
                desigSelect.value = String(desiredDesigId);
            } else {
                desigSelect.value = "";
            }
        } else {
            // Fallback if cache not available: filter existing options by data-dept-id
            Array.from(desigSelect.options).forEach((opt, idx) => {
                if (idx === 0) return;
                const optDeptId = opt.getAttribute("data-dept-id");
                const matches = (!deptVal || !optDeptId || optDeptId === deptVal);
                opt.hidden = !matches;
                opt.disabled = !matches;
                if (matches && desiredDesigId && String(opt.value) === String(desiredDesigId)) {
                    desigSelect.value = String(desiredDesigId);
                }
            });
        }
        onEditDesignationChanged();
    }
}

function onEditClassSelectChanged(targetDivId = null) {
    const classVal = document.getElementById("editClassSelect")?.value || "";
    const classId = classVal ? parseInt(classVal) : null;
    const divSelect = document.getElementById("editDivisionSelect");

    if (divSelect && window.allTenantDivisions && Array.isArray(window.allTenantDivisions)) {
        const currentDivVal = (targetDivId !== null && targetDivId !== undefined && String(targetDivId).trim() !== "")
            ? parseInt(targetDivId)
            : (divSelect.value ? parseInt(divSelect.value) : null);

        const filteredDivs = classId
            ? window.allTenantDivisions.filter(d => d.class_id === classId)
            : window.allTenantDivisions;

        let divHtml = '<option value="">Unassigned</option>';
        let divStillValid = false;
        filteredDivs.forEach(dv => {
            const isSel = currentDivVal && dv.id === currentDivVal;
            if (isSel) divStillValid = true;
            divHtml += `<option value="${dv.id}" data-class-id="${dv.class_id}" ${isSel ? 'selected' : ''}>${escapeHtml(dv.name)}</option>`;
        });
        divSelect.innerHTML = divHtml;
        if (currentDivVal && divStillValid) {
            divSelect.value = String(currentDivVal);
        } else {
            divSelect.value = "";
        }
    }
}

function onEditDesignationChanged() {
    const desigSelect = document.getElementById("editDesignationSelect");
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    if (!desigSelect || !tplSelect) return;

    if (desigSelect.selectedIndex >= 0) {
        const opt = desigSelect.options[desigSelect.selectedIndex];
        if (opt && opt.value) {
            const tplId = opt.getAttribute("data-template-id");
            if (tplId) {
                tplSelect.value = tplId;
            }
        }
    }
    updateEditRateInputVisibility();
}

function onEditSalaryTemplateChanged() {
    updateEditRateInputVisibility();
}

function updateEditRateInputVisibility() {
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    const desigSelect = document.getElementById("editDesignationSelect");
    
    let model = "STRUCTURED_SALARY";
    if (tplSelect && tplSelect.value) {
        const opt = tplSelect.options[tplSelect.selectedIndex];
        if (opt) model = opt.getAttribute("data-model") || "STRUCTURED_SALARY";
    } else if (desigSelect && desigSelect.value) {
        const dOpt = desigSelect.options[desigSelect.selectedIndex];
        const tplId = dOpt ? dOpt.getAttribute("data-template-id") : null;
        if (tplId && tplSelect) {
            const matchingTplOpt = Array.from(tplSelect.options).find(o => String(o.value) === String(tplId));
            if (matchingTplOpt) model = matchingTplOpt.getAttribute("data-model") || "STRUCTURED_SALARY";
        }
    }

    const monthlyGrp = document.getElementById("editMonthlySalaryGroup");
    const dailyGrp = document.getElementById("editDailyRateGroup");
    const hourlyGrp = document.getElementById("editHourlyRateGroup");

    if (!monthlyGrp || !dailyGrp || !hourlyGrp) return;

    if (model === "HOURLY") {
        hourlyGrp.style.display = "block";
        dailyGrp.style.display = "none";
        monthlyGrp.style.display = "none";
    } else if (model === "DAILY_WAGE") {
        dailyGrp.style.display = "block";
        hourlyGrp.style.display = "none";
        monthlyGrp.style.display = "none";
    } else {
        monthlyGrp.style.display = "block";
        dailyGrp.style.display = "none";
        hourlyGrp.style.display = "none";
    }
}

function openEditModal(idOrObj, name, roll, dept, email, role, classSem, deptId, classId, divId, hourlyRate, monthlySalary, doj, shiftId, locationId, designationId, salaryTemplateId, dailyRate) {
    try {
        const modal = document.getElementById("editStudentModal");
        if (!modal) {
            console.error("Modal #editStudentModal element not found in DOM");
            return;
        }

        let s = {};
        let studentId = null;

        if (typeof idOrObj === "object" && idOrObj !== null) {
            s = idOrObj;
            studentId = s.id;
        } else if (idOrObj !== undefined && idOrObj !== null && String(idOrObj).trim() !== "") {
            studentId = Number(idOrObj);
            const cached = (window.allTenantStudents && Array.isArray(window.allTenantStudents))
                ? window.allTenantStudents.find(x => Number(x.id) === Number(studentId))
                : null;
            if (cached) {
                s = Object.assign({}, cached);
            } else {
                const domName = document.getElementById(`stdNameLabel${studentId}`)?.innerText.trim();
                const domRoll = document.getElementById(`stdRollLabel${studentId}`)?.innerText.trim();
                const domEmail = document.getElementById(`stdEmailLabel${studentId}`)?.innerText.trim();
                const domRow = document.getElementById(`studentRow${studentId}`);
                s = {
                    id: studentId,
                    name: name || domName || "",
                    roll_number: roll || domRoll || "",
                    department: dept || domRow?.getAttribute("data-dept") || "",
                    email: email || (domEmail === "No email registered" ? "" : domEmail) || "",
                    user_role: role || domRow?.getAttribute("data-role") || "",
                    class_semester: classSem || "",
                    department_id: deptId || (domRow?.getAttribute("data-dept-id") ? Number(domRow.getAttribute("data-dept-id")) : null),
                    class_id: classId || (domRow?.getAttribute("data-class-id") ? Number(domRow.getAttribute("data-class-id")) : null),
                    division_id: divId || (domRow?.getAttribute("data-div-id") ? Number(domRow.getAttribute("data-div-id")) : null),
                    hourly_rate: hourlyRate,
                    daily_rate: dailyRate,
                    monthly_base_salary: monthlySalary,
                    date_of_joining: doj || "",
                    shift_id: shiftId || (domRow?.getAttribute("data-shift-id") ? Number(domRow.getAttribute("data-shift-id")) : null),
                    location_id: locationId,
                    designation_id: designationId,
                    salary_template_id: salaryTemplateId
                };
            }
        }

        function populateFields(data) {
            if (!data) return;
            const idInput = document.getElementById("editStudentId");
            if (idInput) idInput.value = data.id || "";

            const nameInput = document.getElementById("editStudentName");
            if (nameInput && data.name !== undefined) nameInput.value = data.name || "";

            const rollInput = document.getElementById("editRollNumber");
            if (rollInput && data.roll_number !== undefined) rollInput.value = data.roll_number || "";

            const emailInput = document.getElementById("editEmail");
            if (emailInput) emailInput.value = (data.email && data.email !== "No email registered") ? data.email : "";

            const roleSelect = document.getElementById("editUserRole");
            if (roleSelect) {
                let targetRole = data.user_role || data.role || "";
                const isCorp = window.IS_CORPORATE || (document.getElementById("statShiftHours") !== null) || (window.location.pathname.includes('/employees'));
                if (isCorp && (targetRole === "student" || targetRole === "teacher" || !targetRole)) {
                    targetRole = "employee";
                } else if (!targetRole) {
                    targetRole = "student";
                }

                if (roleSelect.tagName === "SELECT" && roleSelect.options) {
                    let hasOption = false;
                    for (let i = 0; i < roleSelect.options.length; i++) {
                        if (roleSelect.options[i].value === targetRole) {
                            hasOption = true;
                            break;
                        }
                    }
                    if (!hasOption && targetRole) {
                        const opt = document.createElement("option");
                        opt.value = targetRole;
                        opt.text = targetRole.replace(/_/g, ' ').replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        roleSelect.appendChild(opt);
                    }
                }
                roleSelect.value = targetRole;
            }

            const dojInput = document.getElementById("editDateOfJoining");
            if (dojInput && data.date_of_joining !== undefined) dojInput.value = data.date_of_joining || "";

            const shiftSelect = document.getElementById("editShiftSelect");
            if (shiftSelect && data.shift_id !== undefined) shiftSelect.value = (data.shift_id !== null && data.shift_id !== undefined) ? String(data.shift_id) : "";

            const locSelect = document.getElementById("editLocationSelect");
            if (locSelect && data.location_id !== undefined) locSelect.value = (data.location_id !== null && data.location_id !== undefined) ? String(data.location_id) : "";

            const deptSelect = document.getElementById("editDepartmentSelect");
            if (deptSelect) {
                if (data.department_id) {
                    deptSelect.value = String(data.department_id);
                } else if (data.department) {
                    for (let i = 0; i < deptSelect.options.length; i++) {
                        if (deptSelect.options[i].text.toLowerCase() === data.department.toLowerCase()) {
                            deptSelect.selectedIndex = i;
                            break;
                        }
                    }
                }
                // Dynamically filter designations matching this department and select employee designation
                onEditDeptSelectChanged(data.designation_id);
            }

            const classSelect = document.getElementById("editClassSelect");
            if (classSelect) {
                if (data.class_id) classSelect.value = String(data.class_id);
                onEditClassSelectChanged(data.division_id);
            }

            const tplSelect = document.getElementById("editSalaryTemplateSelect");
            if (tplSelect && data.salary_template_id !== undefined) {
                tplSelect.value = (data.salary_template_id !== null && data.salary_template_id !== undefined) ? String(data.salary_template_id) : "";
            }

            const hourlyInput = document.getElementById("editHourlyRate");
            if (hourlyInput && data.hourly_rate !== undefined) hourlyInput.value = (data.hourly_rate !== null && data.hourly_rate !== undefined) ? data.hourly_rate : "";

            const dailyInput = document.getElementById("editDailyRate");
            if (dailyInput && data.daily_rate !== undefined) dailyInput.value = (data.daily_rate !== null && data.daily_rate !== undefined) ? data.daily_rate : "";

            const monthlyInput = document.getElementById("editMonthlyBaseSalary");
            if (monthlyInput && data.monthly_base_salary !== undefined) monthlyInput.value = (data.monthly_base_salary !== null && data.monthly_base_salary !== undefined) ? data.monthly_base_salary : "";

            updateEditRateInputVisibility();

            try { if (typeof onEditRoleChanged === "function") onEditRoleChanged(); } catch (e) {}
        }

        // 1. Populate immediately with local cache / arguments
        populateFields(s);

        const alertBox = document.getElementById("editResultAlert");
        if (alertBox) alertBox.style.display = "none";

        // 2. Open Modal Immediately
        modal.classList.add("active");
        modal.style.display = "flex";

        // 3. Trigger photo loading and async fetch for full profile
        if (studentId) {
            if (typeof loadStudentPhotosPreview === "function") {
                loadStudentPhotosPreview(studentId, "editStudentPhotosPreview");
            }
            fetch(`/api/v1/enroll/student/${studentId}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.student) {
                        populateFields(data.student);
                    }
                })
                .catch(err => {
                    console.warn("Could not fetch remote student details:", err);
                });
        }
    } catch (err) {
        console.error("Error opening edit modal:", err);
        const modal = document.getElementById("editStudentModal");
        if (modal) {
            modal.classList.add("active");
            modal.style.display = "flex";
        }
    }
}

function closeEditModal() {
    const modal = document.getElementById("editStudentModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

async function loadStudentPhotosPreview(studentId, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const countBadge = document.getElementById("editPhotosCountBadge");
    if (countBadge) {
        countBadge.innerText = "Loading...";
        countBadge.className = "badge badge-node";
    }

    container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 14px; font-size: 12px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading enrolled photos...</div>';

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`);
        const data = await res.json();
        if (res.ok && data.student && data.student.photos && data.student.photos.length > 0) {
            const count = data.student.photos.length;
            if (countBadge) {
                countBadge.innerText = `${count} ${count === 1 ? 'Photo' : 'Photos'}`;
                countBadge.className = "badge badge-present";
            }
            container.innerHTML = data.student.photos.map(p => `
                <div class="photo-preview-card" style="cursor: pointer;" onclick="openLightbox('${p.url}', '${escapeHtml(data.student.name)} (${p.angle || 'Sample'})')" title="Click to view full image">
                    <img class="photo-preview-img" src="${p.url}" alt="${p.angle}" onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\\'aspect-ratio:1/1; display:flex; align-items:center; justify-content:center; color:var(--text-light); font-size:20px;\\'><i class=\\'fa-regular fa-image\\'></i></div><div class=\\'photo-preview-label\\'>Crop Missing</div>';">
                    <div class="photo-preview-label">${p.angle ? p.angle.replace('_', ' ').toUpperCase() : 'FACE CROP'}</div>
                </div>
            `).join("");
        } else {
            if (countBadge) {
                countBadge.innerText = "0 Photos";
                countBadge.className = "badge badge-node";
            }
            container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 16px; font-size: 12px; color: var(--text-muted); background: #ffffff; border: 1px dashed var(--border-color); border-radius: var(--radius-sm);"><i class="fa-regular fa-image" style="margin-right: 6px;"></i> No photo crops saved on server yet.</div>';
        }
    } catch (e) {
        if (countBadge) {
            countBadge.innerText = "Error";
            countBadge.className = "badge badge-amber";
        }
        container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 10px; font-size: 12px; color: var(--accent-rose);">Could not load registered photos.</div>';
    }
}

async function submitStudentEdit(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const id = document.getElementById("editStudentId")?.value;
    if (!id) {
        alert("Employee ID is missing.");
        return;
    }

    const name = document.getElementById("editStudentName")?.value.trim() || "";
    const roll = document.getElementById("editRollNumber")?.value.trim() || "";
    const email = document.getElementById("editEmail")?.value.trim() || "";
    const role = document.getElementById("editUserRole")?.value || "employee";

    const deptSelect = document.getElementById("editDepartmentSelect");
    const deptId = deptSelect?.value ? parseInt(deptSelect.value) : null;
    const deptName = (deptSelect && deptSelect.selectedIndex >= 0) ? deptSelect.options[deptSelect.selectedIndex].text : "General";

    const classSelect = document.getElementById("editClassSelect");
    const classId = classSelect?.value ? parseInt(classSelect.value) : null;
    const className = (classSelect && classSelect.selectedIndex > 0) ? classSelect.options[classSelect.selectedIndex].text : "General";

    const divSelect = document.getElementById("editDivisionSelect");
    const divId = divSelect?.value ? parseInt(divSelect.value) : null;

    const shiftSelect = document.getElementById("editShiftSelect");
    const shiftId = (shiftSelect && shiftSelect.value) ? parseInt(shiftSelect.value) : null;

    const locSelect = document.getElementById("editLocationSelect");
    const locId = (locSelect && locSelect.value) ? parseInt(locSelect.value) : null;

    const desigSelect = document.getElementById("editDesignationSelect");
    const desigId = (desigSelect && desigSelect.value) ? parseInt(desigSelect.value) : null;
    const desigOption = (desigSelect && desigSelect.selectedIndex > 0) ? desigSelect.options[desigSelect.selectedIndex] : null;
    const desigTitle = (desigId && desigOption) ? (desigOption.getAttribute("data-title") || desigOption.text) : null;

    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    const tplId = (tplSelect && tplSelect.value) ? parseInt(tplSelect.value) : null;

    const hourlyRateInput = document.getElementById("editHourlyRate")?.value;
    const dailyRateInput = document.getElementById("editDailyRate")?.value;
    const monthlySalaryInput = document.getElementById("editMonthlyBaseSalary")?.value;
    const dojInput = document.getElementById("editDateOfJoining")?.value;

    const saveBtn = document.getElementById("btnSaveEdit");
    const alertBox = document.getElementById("editResultAlert");

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: name,
                roll_number: roll,
                department_id: deptId,
                department: deptName,
                class_id: classId,
                class_semester: className,
                division_id: divId,
                shift_id: shiftId,
                location_id: locId,
                designation_id: desigId,
                designation: desigTitle,
                salary_template_id: tplId,
                email: email || null,
                user_role: role,
                hourly_rate: hourlyRateInput ? parseFloat(hourlyRateInput) : null,
                daily_rate: dailyRateInput ? parseFloat(dailyRateInput) : null,
                monthly_base_salary: monthlySalaryInput ? parseFloat(monthlySalaryInput) : null,
                date_of_joining: (dojInput && dojInput.trim()) ? dojInput.trim() : null,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            const updatedStudent = data.student || {};
            // Sync cache
            if (window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
                const idx = window.allTenantStudents.findIndex(x => Number(x.id) === Number(id));
                if (idx >= 0) {
                    window.allTenantStudents[idx] = Object.assign({}, window.allTenantStudents[idx], updatedStudent);
                }
            }
            // Instantly update the DOM table row dynamically without full page reload
            updateStudentTableRowInDOM(updatedStudent);

            closeEditModal();
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
            }

            showFloatingToast(`Profile for '${name}' updated successfully.`, "success");
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Update failed.");
            }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
            }
        }
    } catch (e) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
        }
    }
}

function updateStudentTableRowInDOM(student) {
    if (!student || !student.id) return;
    const sId = student.id;

    // Update labels
    const nameLabel = document.getElementById(`stdNameLabel${sId}`);
    if (nameLabel) nameLabel.innerText = student.name;

    // Avatar initials
    const row = document.getElementById(`studentRow${sId}`);
    if (row) {
        const avatar = row.querySelector(".user-avatar");
        if (avatar && student.name) {
            avatar.innerText = student.name.slice(0, 2).toUpperCase();
        }
    }

    const emailLabel = document.getElementById(`stdEmailLabel${sId}`);
    if (emailLabel) emailLabel.innerText = student.email || "No email registered";

    const rollLabel = document.getElementById(`stdRollLabel${sId}`);
    if (rollLabel) rollLabel.innerText = student.roll_number;

    const deptLabel = document.getElementById(`stdDeptLabel${sId}`);
    if (deptLabel) deptLabel.innerText = student.department || "—";

    const dojLabel = document.getElementById(`stdDojLabel${sId}`);
    if (dojLabel) dojLabel.innerText = student.date_of_joining || "—";

    // Designation badge for corporate tenants
    const desigBadge = document.getElementById(`stdDesigBadge${sId}`);
    if (desigBadge) {
        desigBadge.className = "badge badge-sky";
        desigBadge.innerHTML = `<i class="fa-solid fa-id-badge"></i> ${escapeHtml(student.designation || 'Staff')}`;
    }

    const roleBadge = document.getElementById(`stdRoleBadge${sId}`);
    if (roleBadge) {
        const r = (student.user_role || "student").toLowerCase();
        if (["teacher", "faculty"].includes(r)) {
            roleBadge.className = "badge badge-node";
            roleBadge.innerHTML = '<i class="fa-solid fa-chalkboard-user"></i> Faculty';
        } else if (r === "manager") {
            roleBadge.className = "badge badge-sky";
            roleBadge.innerHTML = '<i class="fa-solid fa-user-gear"></i> Manager';
        } else if (r === "admin_staff") {
            roleBadge.className = "badge badge-amber";
            roleBadge.innerHTML = '<i class="fa-solid fa-user-shield"></i> Admin Staff';
        } else {
            const isCorp = window.IS_CORPORATE || (document.getElementById("statShiftHours") !== null) || (window.location.pathname.includes('/employees'));
            roleBadge.className = "badge badge-present";
            roleBadge.innerHTML = `<i class="fa-solid fa-user"></i> ${isCorp ? 'Employee' : 'Student'}`;
        }
    }

    const shiftBadge = document.getElementById(`stdShiftBadge${sId}`);
    if (shiftBadge) {
        if (student.shift_name) {
            shiftBadge.className = "badge";
            shiftBadge.style.background = "rgba(99, 102, 241, 0.12)";
            shiftBadge.style.color = "var(--accent-primary)";
            shiftBadge.style.border = "1px solid rgba(99, 102, 241, 0.25)";
            shiftBadge.innerHTML = `<i class="fa-solid fa-clock"></i> ${escapeHtml(student.shift_name)}`;
            shiftBadge.title = student.shift_display || student.shift_name;
        } else {
            shiftBadge.className = "";
            shiftBadge.style = "font-size: 11.5px; color: var(--text-light); font-style: italic;";
            shiftBadge.innerText = "Default Shift";
        }
    }

    const classLabel = document.getElementById(`stdClassLabel${sId}`);
    if (classLabel) {
        classLabel.innerText = student.class_name || student.class_semester || "General";
    }

    if (row) {
        row.setAttribute("data-name", (student.name || "").toLowerCase());
        row.setAttribute("data-roll", (student.roll_number || "").toLowerCase());
        row.setAttribute("data-dept-id", student.department_id || "");
        row.setAttribute("data-dept", student.department || "");
        row.setAttribute("data-desig-id", student.designation_id || "");
        row.setAttribute("data-desig", (student.designation || "").toLowerCase());
        row.setAttribute("data-shift-id", student.shift_id || "");
        row.setAttribute("data-role", student.user_role || "");
        row.setAttribute("data-class-id", student.class_id || "");
        row.setAttribute("data-div-id", student.division_id || "");
    }
}

function showFloatingToast(message, type = "success") {
    let toast = document.getElementById("floatingToastAlert");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "floatingToastAlert";
        toast.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 99999; padding: 12px 20px; border-radius: var(--radius-sm, 6px); font-size: 13px; box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0,0,0,0.1)); transition: all 0.3s ease; display: none; align-items: center; gap: 8px;";
        document.body.appendChild(toast);
    }
    const isSuccess = type === "success";
    toast.style.background = isSuccess ? "var(--badge-emerald-bg, #ecfdf5)" : "var(--badge-rose-bg, #fff1f2)";
    toast.style.color = isSuccess ? "var(--badge-emerald-text, #065f46)" : "var(--badge-rose-text, #9f1239)";
    toast.style.border = isSuccess ? "1px solid var(--badge-emerald-border, #a7f3d0)" : "1px solid var(--badge-rose-border, #fecdd3)";
    toast.innerHTML = `<i class="fa-solid ${isSuccess ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> <span>${escapeHtml(message)}</span>`;
    toast.style.display = "flex";
    setTimeout(() => {
        toast.style.display = "none";
    }, 3500);
}

/* ==========================================================
   Retake / Update Reference Photos Modal
   ========================================================== */
let retakeStudentId = null;
let retakeFiles = [];
let retakeWebcamStream = null;

function openRetakeModal(id, name, roll) {
    const modal = document.getElementById("retakePhotosModal");
    if (!modal) return;

    let sName = name;
    let sRoll = roll;
    if ((!sName || !sRoll) && window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
        const found = window.allTenantStudents.find(x => Number(x.id) === Number(id));
        if (found) {
            sName = sName || found.name;
            sRoll = sRoll || found.roll_number;
        }
    }
    if (!sName) {
        sName = document.getElementById(`stdNameLabel${id}`)?.innerText.trim() || "";
    }
    if (!sRoll) {
        sRoll = document.getElementById(`stdRollLabel${id}`)?.innerText.trim() || "";
    }

    retakeStudentId = id;
    const idInput = document.getElementById("retakeStudentId");
    if (idInput) idInput.value = id;

    const titleEl = document.getElementById("retakeModalTitle");
    if (titleEl) titleEl.innerText = `Update Photos: ${sName || ''}`;

    const subEl = document.getElementById("retakeModalSubtitle");
    if (subEl) subEl.innerText = `ID / Roll Number: ${sRoll || ''} | Overwrite with 3 fresh reference images`;

    retakeFiles = [];
    updateRetakePreviews();

    // Reset capture buttons
    const btnFrontal = document.getElementById("btnRetakeCapFrontal");
    if (btnFrontal) {
        btnFrontal.disabled = false;
        btnFrontal.className = "btn btn-secondary";
    }
    const btnLeft = document.getElementById("btnRetakeCapLeft");
    if (btnLeft) {
        btnLeft.disabled = true;
        btnLeft.className = "btn btn-secondary";
    }
    const btnRight = document.getElementById("btnRetakeCapRight");
    if (btnRight) {
        btnRight.disabled = true;
        btnRight.className = "btn btn-secondary";
    }

    const camFb = document.getElementById("retakeCamFeedback");
    if (camFb) {
        camFb.style.display = "none";
        camFb.innerHTML = "";
    }

    const alertBox = document.getElementById("retakeResultAlert");
    if (alertBox) alertBox.style.display = "none";

    loadStudentPhotosPreview(id, "retakeExistingPhotosPreview");

    switchRetakeMode("upload");
    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeRetakeModal() {
    const modal = document.getElementById("retakePhotosModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
    stopRetakeWebcam();
    if (typeof window.resumeFromSecondaryCamera === "function") {
        window.resumeFromSecondaryCamera();
    }
}

async function switchRetakeMode(mode) {
    const tabUpload = document.getElementById("tabRetakeUpload");
    const tabWebcam = document.getElementById("tabRetakeWebcam");
    const secUpload = document.getElementById("secRetakeUpload");
    const secWebcam = document.getElementById("secRetakeWebcam");

    if (mode === "upload") {
        if (tabUpload) tabUpload.classList.add("active");
        if (tabWebcam) tabWebcam.classList.remove("active");
        if (secUpload) secUpload.style.display = "block";
        if (secWebcam) secWebcam.style.display = "none";
        stopRetakeWebcam();
        if (typeof window.resumeFromSecondaryCamera === "function") {
            window.resumeFromSecondaryCamera();
        }
    } else {
        // Camera Arbitration: Prompt admin if live attendance feed is active
        if (window.isContinuousActive && typeof window.pauseForSecondaryCamera === "function") {
            const proceed = confirm("Live Attendance Feed is currently capturing attendance.\n\nWould you like to temporarily pause the live attendance feed to use the webcam for taking reference photos?");
            if (!proceed) {
                if (tabUpload) tabUpload.classList.add("active");
                if (tabWebcam) tabWebcam.classList.remove("active");
                if (secUpload) secUpload.style.display = "block";
                if (secWebcam) secWebcam.style.display = "none";
                return;
            }
            window.pauseForSecondaryCamera();
        }

        if (tabWebcam) tabWebcam.classList.add("active");
        if (tabUpload) tabUpload.classList.remove("active");
        if (secWebcam) secWebcam.style.display = "block";
        if (secUpload) secUpload.style.display = "none";
        await startRetakeWebcam();
    }
}

// Retake Dropzone & Previews
const retakeFileInput = document.getElementById("retakeFileInput");
const retakeDropzone = document.getElementById("retakeDropzone");

if (retakeDropzone) {
    retakeDropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        retakeDropzone.classList.add("dragover");
    });
    retakeDropzone.addEventListener("dragleave", () => {
        retakeDropzone.classList.remove("dragover");
    });
    retakeDropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        retakeDropzone.classList.remove("dragover");
        handleRetakeFiles(e.dataTransfer.files);
    });
}

if (retakeFileInput) {
    retakeFileInput.addEventListener("change", (e) => {
        handleRetakeFiles(e.target.files);
    });
}

function handleRetakeFiles(filesList) {
    const newFiles = Array.from(filesList).filter(f => f.type.startsWith("image/"));
    for (const f of newFiles) {
        if (retakeFiles.length < 3) {
            retakeFiles.push(f);
        }
    }
    updateRetakePreviews();
}

function updateRetakePreviews() {
    const hint = document.getElementById("retakeUploadHint");
    const submitBtn = document.getElementById("btnSubmitRetakeUpload");

    for (let i = 0; i < 3; i++) {
        const imgEl = document.getElementById(`retakePrevImg${i}`);
        const phEl = document.getElementById(`retakePh${i}`);

        if (!imgEl || !phEl) continue;

        if (retakeFiles[i]) {
            const url = URL.createObjectURL(retakeFiles[i]);
            imgEl.src = url;
            imgEl.style.display = "block";
            phEl.style.display = "none";
        } else {
            imgEl.src = "";
            imgEl.style.display = "none";
            phEl.style.display = "flex";
        }
    }

    if (retakeFiles.length === 3) {
        if (hint) hint.innerHTML = '<span style="color:var(--badge-emerald-text); font-weight:700;"><i class="fa-solid fa-circle-check"></i> Exactly 3 photos selected. Ready to overwrite!</span>';
        if (submitBtn) submitBtn.disabled = false;
    } else {
        if (hint) hint.innerHTML = `<span style="color:var(--accent-amber); font-weight:600;"><i class="fa-solid fa-circle-exclamation"></i> Select exactly 3 new photos (${3 - retakeFiles.length} more needed).</span>`;
        if (submitBtn) submitBtn.disabled = true;
    }
}

async function submitRetakeUpload() {
    if (retakeFiles.length !== 3 || !retakeStudentId) {
        alert("Please select exactly 3 photos before submitting.");
        return;
    }

    const submitBtn = document.getElementById("btnSubmitRetakeUpload");
    const alertBox = document.getElementById("retakeResultAlert");

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extracting Vectors & Overwriting...';
    }

    if (alertBox) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-indigo-bg)";
        alertBox.style.border = "1px solid var(--badge-indigo-border)";
        alertBox.innerHTML = '<span style="color:var(--accent-primary); font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Generating 128-d embeddings for 3 photos...</span>';
    }

    const formData = new FormData();
    retakeFiles.forEach((file) => {
        formData.append("images", file);
    });

    try {
        const res = await fetch(`/api/v1/enroll/student/${retakeStudentId}/update-photos`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = `<span style="color:var(--badge-emerald-text); font-weight:700;"><i class="fa-solid fa-circle-check"></i> ${data.message}</span>`;
            if (submitBtn) submitBtn.innerHTML = '<i class="fa-solid fa-check"></i> Updated Successfully';
            setTimeout(() => {
                closeRetakeModal();
                window.location.reload();
            }, 1000);
        } else {
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Upload failed.'}</span>`;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Try Again';
            }
        }
    } catch (err) {
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to backend.</span>';
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Try Again';
        }
    }
}

// Live Webcam Retake Handlers
function toggleRetakeWebcam() {
    if (retakeWebcamStream) {
        stopRetakeWebcam();
    } else {
        startRetakeWebcam();
    }
}

async function startRetakeWebcam() {
    if (retakeWebcamStream) return;
    const video = document.getElementById("retakeWebcamVideo");
    const toggleBtn = document.getElementById("btnToggleRetakeCam");
    const fb = document.getElementById("retakeCamFeedback");
    try {
        retakeWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });
        if (video) video.srcObject = retakeWebcamStream;
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-video-slash"></i> Stop Camera';
            toggleBtn.className = "btn btn-secondary";
        }
        if (fb) {
            fb.style.display = "none";
            fb.innerHTML = "";
        }
    } catch (e) {
        if (fb) {
            fb.style.display = "block";
            fb.style.background = "var(--badge-rose-bg)";
            fb.style.color = "var(--badge-rose-text)";
            fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Camera in use or permission denied.';
        }
    }
}

function stopRetakeWebcam() {
    if (retakeWebcamStream) {
        retakeWebcamStream.getTracks().forEach(t => t.stop());
        retakeWebcamStream = null;
        const video = document.getElementById("retakeWebcamVideo");
        if (video) video.srcObject = null;
    }
    const toggleBtn = document.getElementById("btnToggleRetakeCam");
    if (toggleBtn) {
        toggleBtn.innerHTML = '<i class="fa-solid fa-video"></i> Start Camera';
    }
}

async function captureRetakeSample(angle) {
    if (!retakeStudentId) return;
    const video = document.getElementById("retakeWebcamVideo");
    let canvas = document.getElementById("retakeCaptureCanvas");
    if (!canvas) {
        canvas = document.createElement("canvas");
        canvas.id = "retakeCaptureCanvas";
        canvas.style.display = "none";
        document.body.appendChild(canvas);
    }
    if (!video || !video.videoWidth) {
        const fb = document.getElementById("retakeCamFeedback");
        if (fb) {
            fb.style.display = "block";
            fb.style.background = "var(--badge-rose-bg)";
            fb.style.color = "var(--badge-rose-text)";
            fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Camera stream not active. Please start camera first.';
        }
        return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const fb = document.getElementById("retakeCamFeedback");
    if (fb) {
        fb.style.display = "block";
        fb.style.background = "var(--badge-indigo-bg)";
        fb.style.color = "var(--accent-primary)";
        fb.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing and saving ${angle} sample...`;
    }

    canvas.toBlob(async (blob) => {
        if (!blob) {
            if (fb) {
                fb.style.display = "block";
                fb.style.background = "var(--badge-rose-bg)";
                fb.style.color = "var(--badge-rose-text)";
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Failed to capture image frame.';
            }
            return;
        }
        const formData = new FormData();
        formData.append("student_id", retakeStudentId);
        formData.append("sample_angle", angle);
        formData.append("image", blob, `retake_${angle}.jpg`);

        try {
            const res = await fetch("/api/v1/enroll/capture-sample", {
                method: "POST",
                body: formData,
            });
            const data = await res.json();
            if (res.ok) {
                if (fb) {
                    fb.style.display = "block";
                    fb.style.background = "var(--badge-emerald-bg)";
                    fb.style.color = "var(--badge-emerald-text)";
                    fb.innerHTML = `<i class="fa-solid fa-circle-check"></i> ✓ ${angle} pose recorded successfully!`;
                }
                if (angle === 'frontal') {
                    const btnF = document.getElementById("btnRetakeCapFrontal");
                    if (btnF) {
                        btnF.disabled = true;
                        btnF.className = "btn btn-primary";
                    }
                    const btnL = document.getElementById("btnRetakeCapLeft");
                    if (btnL) {
                        btnL.disabled = false;
                        btnL.focus();
                    }
                } else if (angle === 'left') {
                    const btnL = document.getElementById("btnRetakeCapLeft");
                    if (btnL) {
                        btnL.disabled = true;
                        btnL.className = "btn btn-primary";
                    }
                    const btnR = document.getElementById("btnRetakeCapRight");
                    if (btnR) {
                        btnR.disabled = false;
                        btnR.focus();
                    }
                } else if (angle === 'right') {
                    const btnR = document.getElementById("btnRetakeCapRight");
                    if (btnR) {
                        btnR.disabled = true;
                        btnR.className = "btn btn-primary";
                    }
                    if (fb) {
                        fb.style.display = "block";
                        fb.style.background = "var(--badge-emerald-bg)";
                        fb.style.color = "var(--badge-emerald-text)";
                        fb.innerHTML = '<i class="fa-solid fa-circle-check"></i> <strong>✓ All 3 samples retaken!</strong> Refreshing directory...';
                    }
                    stopRetakeWebcam();
                    setTimeout(() => {
                        closeRetakeModal();
                        window.location.reload();
                    }, 1200);
                }
            } else {
                if (fb) {
                    fb.style.display = "block";
                    fb.style.background = "var(--badge-rose-bg)";
                    fb.style.color = "var(--badge-rose-text)";
                    fb.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || "Capture failed. Please try again."}`;
                }
            }
        } catch (e) {
            if (fb) {
                fb.style.display = "block";
                fb.style.background = "var(--badge-rose-bg)";
                fb.style.color = "var(--badge-rose-text)";
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error during upload.';
            }
        }
    }, "image/jpeg", 0.9);
}

/* ==========================================================
   Universal Manual Override Modal Handlers
   ========================================================== */
let currentOverrideEmployeeStatus = null;

async function populateStudentDropdown() {
    try {
        const res = await fetch("/api/v1/enroll/students");
        const data = await res.json();
        const select = document.getElementById("overrideStudentSelect");
        if (!select || !data.students) return;

        const currentVal = select.value;
        select.innerHTML = '<option value="">-- Choose Member --</option>' +
            data.students.map(s => `<option value="${s.id}">${s.name} (${s.roll_number} - ${s.department}) [${s.user_role || 'student'}]</option>`).join("");
        if (currentVal) select.value = currentVal;
    } catch (e) {}
}

function openManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (modal) {
        modal.classList.add("active");
        modal.style.display = "flex";
    }
    const alertBox = document.getElementById("overrideResultAlert");
    if (alertBox) alertBox.style.display = "none";
    const statusBanner = document.getElementById("overrideStudentStatusBanner");
    if (statusBanner) statusBanner.style.display = "none";
    
    // Set default datetime to now in local input format
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const tsInput = document.getElementById("overrideTimestamp");
    if (tsInput && !tsInput.value) {
        tsInput.value = now.toISOString().slice(0, 16);
    }
    
    updateOverrideButtonState("AUTO");
    populateStudentDropdown();
}

function openManualOverrideForStudent(studentId) {
    openManualOverrideModal();
    setTimeout(() => {
        const select = document.getElementById("overrideStudentSelect");
        if (select) {
            select.value = studentId;
            onOverrideStudentChanged();
        }
    }, 150);
}

function closeManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

async function onOverrideStudentChanged() {
    const select = document.getElementById("overrideStudentSelect");
    const statusBanner = document.getElementById("overrideStudentStatusBanner");
    const punchTypeSelect = document.getElementById("overridePunchType");
    const studentId = select ? parseInt(select.value) : null;

    if (!studentId) {
        if (statusBanner) statusBanner.style.display = "none";
        currentOverrideEmployeeStatus = null;
        updateOverrideButtonState(punchTypeSelect ? punchTypeSelect.value : "AUTO");
        return;
    }

    if (statusBanner) {
        statusBanner.style.display = "flex";
        statusBanner.style.background = "var(--bg-subtle)";
        statusBanner.style.color = "var(--text-muted)";
        statusBanner.style.border = "1px solid var(--border-color)";
        statusBanner.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking active punch status for today...';
    }

    try {
        const res = await fetch(`/api/v1/attendance/employee-status/${studentId}`);
        const data = await res.json();
        if (res.ok && data.status) {
            currentOverrideEmployeeStatus = data;
            if (statusBanner) {
                if (data.status === "CHECKED_IN") {
                    statusBanner.style.background = "rgba(59, 130, 246, 0.1)";
                    statusBanner.style.color = "#2563eb";
                    statusBanner.style.border = "1px solid rgba(59, 130, 246, 0.3)";
                    const inTime = data.check_in_time ? new Date(data.check_in_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "Active";
                    statusBanner.innerHTML = `<i class="fa-solid fa-circle-check" style="color:#2563eb;"></i> <span><strong>Currently Checked In:</strong> In-time: <code>${inTime}</code>. Next Action: <strong>CHECK-OUT</strong>.</span>`;
                } else if (data.status === "CHECKED_OUT") {
                    statusBanner.style.background = "rgba(16, 185, 129, 0.1)";
                    statusBanner.style.color = "#059669";
                    statusBanner.style.border = "1px solid rgba(16, 185, 129, 0.3)";
                    const outTime = data.check_out_time ? new Date(data.check_out_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Completed";
                    statusBanner.innerHTML = `<i class="fa-solid fa-flag-checkered" style="color:#059669;"></i> <span><strong>Shift Completed:</strong> Out-time: <code>${outTime}</code>.</span>`;
                } else {
                    statusBanner.style.background = "rgba(245, 158, 11, 0.1)";
                    statusBanner.style.color = "#d97706";
                    statusBanner.style.border = "1px solid rgba(245, 158, 11, 0.3)";
                    statusBanner.innerHTML = `<i class="fa-solid fa-clock" style="color:#d97706;"></i> <span><strong>Not Punched Today:</strong> Next Action: <strong>CHECK-IN</strong>.</span>`;
                }
            }
        }
    } catch (e) {
        if (statusBanner) statusBanner.style.display = "none";
    }

    const currentPunch = punchTypeSelect ? punchTypeSelect.value : "AUTO";
    updateOverrideButtonState(currentPunch);
}

function onOverridePunchTypeChanged() {
    const punchTypeSelect = document.getElementById("overridePunchType");
    const punchType = punchTypeSelect ? punchTypeSelect.value : "AUTO";
    updateOverrideButtonState(punchType);
}

function updateOverrideButtonState(punchType) {
    const saveBtn = document.getElementById("btnSaveOverride");
    if (!saveBtn) return;

    let effectiveAction = punchType;
    if (punchType === "AUTO") {
        if (currentOverrideEmployeeStatus && currentOverrideEmployeeStatus.status === "CHECKED_IN") {
            effectiveAction = "CHECK_OUT";
        } else {
            effectiveAction = "CHECK_IN";
        }
    }

    if (effectiveAction === "CHECK_OUT") {
        saveBtn.className = "btn btn-primary";
        saveBtn.style.background = "#2563eb";
        saveBtn.style.borderColor = "#2563eb";
        saveBtn.innerHTML = '<i class="fa-solid fa-right-from-bracket"></i> Force Mark Check-Out';
    } else {
        saveBtn.className = "btn btn-primary";
        saveBtn.style.background = "";
        saveBtn.style.borderColor = "";
        saveBtn.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> Force Mark Check-In';
    }
}

function applyReasonPreset() {
    const preset = document.getElementById("overridePresetSelect")?.value;
    const input = document.getElementById("overrideReasonInput");
    if (!input) return;
    if (preset !== "Custom") {
        input.value = preset;
    } else {
        input.value = "";
        input.focus();
    }
}

async function submitManualOverride(e) {
    e.preventDefault();
    const studentId = parseInt(document.getElementById("overrideStudentSelect").value);
    const punchType = document.getElementById("overridePunchType")?.value || "AUTO";
    const timestamp = document.getElementById("overrideTimestamp").value;
    const reason = document.getElementById("overrideReasonInput").value.trim();
    const overrideBy = document.getElementById("overrideByInput").value.trim();

    const saveBtn = document.getElementById("btnSaveOverride");
    const alertBox = document.getElementById("overrideResultAlert");

    if (!studentId) {
        alert("Please select a student/member first.");
        return;
    }

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Recording...';

    try {
        const res = await fetch("/api/v1/attendance/manual-override", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                student_id: studentId,
                punch_type: punchType,
                timestamp: timestamp || null,
                reason: reason,
                override_by: overrideBy || "Admin",
            })
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message}`;

            setTimeout(() => {
                closeManualOverrideModal();
                saveBtn.disabled = false;
                updateOverrideButtonState(punchType);
                if (typeof loadAnalyticsData === "function") loadAnalyticsData();
                if (typeof applyLogFilters === "function") applyLogFilters();
                if (window.location.pathname.includes('/students') || window.location.pathname.includes('/employees')) {
                    window.location.reload();
                }
            }, 900);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Failed to record override.'}`;
            saveBtn.disabled = false;
            updateOverrideButtonState(punchType);
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.';
        saveBtn.disabled = false;
        updateOverrideButtonState(punchType);
    }
}

/* ==========================================================
   Mobile Navigation Drawer Handlers
   ========================================================== */
function toggleMobileMenu() {
    const sidebar = document.getElementById("mainSidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (!sidebar) return;

    sidebar.classList.toggle("open");
    if (backdrop) {
        backdrop.classList.toggle("active", sidebar.classList.contains("open"));
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById("mainSidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("active");
}

// Close drawer & modals on Escape key
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeMobileMenu();
        closeLightbox();
        closeEditModal();
        closeRetakeModal();
        closeManualOverrideModal();
    }
});

/* ==========================================================
   Multi-Theme Engine Handlers
   ========================================================== */
function initThemeSwitcher() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
    if (typeof updateQuickThemeButton === "function") {
        updateQuickThemeButton(currentTheme);
    }
    updateThemeSelectionCards(currentTheme);
    updateThemeDropdown(currentTheme);
}

function setAppTheme(themeName) {
    let normalized = themeName;
    if (normalized === "academic") normalized = "warm";
    if (normalized === "corporate" || normalized === "slate") normalized = "warm";
    if (!["light", "dark", "warm"].includes(normalized)) {
        normalized = "light";
    }
    document.documentElement.setAttribute("data-theme", normalized);
    try {
        localStorage.setItem("app_theme", normalized);
    } catch (e) {}

    updateThemeSelectionCards(normalized);
    updateThemeDropdown(normalized);
}

function cycleAppTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
    let nextTheme = "light";
    if (currentTheme === "light") nextTheme = "dark";
    else if (currentTheme === "dark") nextTheme = "warm";
    else nextTheme = "light";

    setAppTheme(nextTheme);
}

function updateThemeDropdown(theme) {
    let current = theme || document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
    if (current === "academic" || current === "corporate" || current === "slate") current = "warm";
    const select = document.getElementById("appThemeSelect");
    const mobileSelect = document.getElementById("mobileAppThemeSelect");
    const icon = document.getElementById("themeIconIndicator");
    if (select) select.value = current;
    if (mobileSelect) mobileSelect.value = current;
    if (icon) {
        if (current === "dark") {
            icon.className = "fa-solid fa-moon";
            icon.style.color = "#38bdf8";
        } else if (current === "warm") {
            icon.className = "fa-solid fa-fire-flame-curved";
            icon.style.color = "#ea580c";
        } else {
            icon.className = "fa-solid fa-sun";
            icon.style.color = "#f59e0b";
        }
    }
}

function updateThemeSelectionCards(theme) {
    let current = theme || document.documentElement.getAttribute("data-theme") || "light";
    if (current === "academic" || current === "corporate" || current === "slate") current = "warm";
    const cardLight = document.getElementById("themeCardLight");
    const cardDark = document.getElementById("themeCardDark");
    const cardWarm = document.getElementById("themeCardWarm") || document.getElementById("themeCardAcademic");
    const badge = document.getElementById("activeThemeBadge");

    if (cardLight) cardLight.classList.toggle("active", current === "light");
    if (cardDark) cardDark.classList.toggle("active", current === "dark");
    if (cardWarm) cardWarm.classList.toggle("active", current === "warm");

    if (badge) {
        if (current === "dark") {
            badge.className = "badge badge-sky";
            badge.innerHTML = '<i class="fa-solid fa-moon"></i> Active: Midnight Dark';
        } else if (current === "warm") {
            badge.className = "badge badge-amber";
            badge.innerHTML = '<i class="fa-solid fa-fire-flame-curved"></i> Active: Warm';
        } else {
            badge.className = "badge badge-present";
            badge.innerHTML = '<i class="fa-solid fa-sun"></i> Active: Clean Light';
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
});

/* ==========================================================
   Collapsible Biometric Terminal Gateway Handler
   ========================================================== */
function toggleBiometricGateway() {
    const body = document.getElementById("biometricGatewayBody");
    const chevron = document.getElementById("gatewayChevron");
    const toggleText = document.getElementById("gatewayToggleText");
    if (!body) return;

    const isCollapsed = body.style.display === "none" || getComputedStyle(body).display === "none";
    if (isCollapsed) {
        body.style.display = "block";
        if (chevron) chevron.style.transform = "rotate(90deg)";
        if (toggleText) toggleText.textContent = "Hide Details";
    } else {
        body.style.display = "none";
        if (chevron) chevron.style.transform = "rotate(0deg)";
        if (toggleText) toggleText.textContent = "Show Details";
    }
}
window.toggleBiometricGateway = toggleBiometricGateway;

