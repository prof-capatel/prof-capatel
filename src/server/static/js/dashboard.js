/* ==========================================================
   Face Recognition Attendance System - Client JavaScript
   ========================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initLiveStream();
    initFilters();
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

/**
 * Inserts new face attendance item into the live feed
 */
function handleNewAttendanceEvent(data) {
    const liveFeed = document.getElementById("liveFeedContainer");
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
    const tableBody = document.getElementById("logsTableBody");

    if (!tableBody) return;

    const colSpan = window.IS_CORPORATE ? 10 : 9;
    tableBody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center; padding: 24px; color: var(--text-muted); font-weight: 500;"><i class="fa-solid fa-spinner fa-spin"></i> Loading attendance audit records...</td></tr>`;

    let url = `/api/v1/attendance/records?limit=300`;
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
    const colSpan = isCorp ? 10 : 9;

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

            return `
                <tr>
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
                    <td>${nodeBadge}</td>
                    <td><strong style="color: var(--text-heading); font-family: monospace; font-size: 12px;">${inTime}</strong></td>
                    <td><strong style="color: var(--text-heading); font-family: monospace; font-size: 12px;">${outTime}</strong></td>
                    <td>${durationHtml}</td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        }

        return `
            <tr>
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
            </tr>
        `;
    }).join("");
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
        const rowClassId = row.getAttribute("data-class-id") || "";
        const rowDivId = row.getAttribute("data-div-id") || "";
        const rowShiftId = row.getAttribute("data-shift-id") || "";
        const rowRole = row.getAttribute("data-role") || "student";
        const rowStatus = row.getAttribute("data-status") || "active";

        let matchSearch = !searchVal || name.includes(searchVal) || roll.includes(searchVal);
        let matchDept = !deptIdVal || rowDeptId === deptIdVal || (rowDept && rowDept === deptTextVal);
        let matchShift = !shiftIdVal || rowShiftId === shiftIdVal;
        let matchClass = !classIdVal || rowClassId === classIdVal;
        let matchDiv = !divIdVal || rowDivId === divIdVal;
        let matchRole = !roleVal || rowRole === roleVal;
        let matchStatus = (statusVal === "all") || (rowStatus === statusVal);

        if (matchSearch && matchDept && matchShift && matchClass && matchDiv && matchRole && matchStatus) {
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

    document.getElementById("relieveStudentId").value = studentId;
    document.getElementById("relieveStudentName").value = `${studentName} (${rollNumber})`;
    
    // Set default date to today
    const todayStr = new Date().toISOString().split("T")[0];
    const dateInput = document.getElementById("relieveDateInput");
    if (dateInput) dateInput.value = todayStr;

    const reasonInput = document.getElementById("relieveReasonInput");
    if (reasonInput) reasonInput.value = "";

    const alertBox = document.getElementById("relieveResultAlert");
    if (alertBox) alertBox.style.display = "none";

    modal.classList.add("active");
}

function closeRelieveModal() {
    const modal = document.getElementById("relieveEmployeeModal");
    if (modal) modal.classList.remove("active");
}

async function submitRelieveEmployee(e) {
    e.preventDefault();
    const studentId = document.getElementById("relieveStudentId").value;
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
    if (!confirm(`Are you sure you want to reinstate "${studentName}" back to active employee status?`)) {
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
            alert(data.message || `"${studentName}" has been reinstated successfully!`);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to reinstate employee.");
        }
    } catch (err) {
        alert("Network error while reinstating employee.");
    }
}

/**
 * Delete Student
 */
async function deleteStudent(studentId, studentName) {
    if (!confirm(`Are you sure you want to delete profile "${studentName}" and all associated face embeddings?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            alert(`Profile "${studentName}" deleted successfully.`);
            window.location.reload();
        } else {
            alert(`Error: ${data.detail || 'Could not delete profile'}`);
        }
    } catch (e) {
        alert("Failed to delete profile.");
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

function onEditDeptSelectChanged() {
    const deptId = document.getElementById("editDepartmentSelect")?.value || "";
    const classSelect = document.getElementById("editClassSelect");
    const divSelect = document.getElementById("editDivisionSelect");

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
}

function onEditClassSelectChanged() {
    const classId = document.getElementById("editClassSelect")?.value || "";
    const divSelect = document.getElementById("editDivisionSelect");

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
}

function onEditDesignationChanged() {
    const desigSelect = document.getElementById("editDesignationSelect");
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    if (!desigSelect || !tplSelect) return;

    const opt = desigSelect.options[desigSelect.selectedIndex];
    if (opt) {
        const tplId = opt.getAttribute("data-template-id");
        if (tplId) {
            tplSelect.value = tplId;
        }
    }
}

function onEditDesignationChanged() {
    const desigSelect = document.getElementById("editDesignationSelect");
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    if (!desigSelect || !tplSelect) return;

    const opt = desigSelect.options[desigSelect.selectedIndex];
    if (opt) {
        const tplId = opt.getAttribute("data-template-id");
        if (tplId && !tplSelect.value) {
            tplSelect.value = tplId;
        }
    }
}

function openEditModal(id, name, roll, dept, email, role, classSem, deptId, classId, divId, hourlyRate, monthlySalary, doj, shiftId, locationId, designationId, salaryTemplateId) {
    const modal = document.getElementById("editStudentModal");
    if (!modal) return;

    document.getElementById("editStudentId").value = id;
    document.getElementById("editStudentName").value = name;
    document.getElementById("editRollNumber").value = roll;
    document.getElementById("editEmail").value = email || "";
    const roleSelect = document.getElementById("editUserRole");
    if (roleSelect) {
        let targetRole = role || "";
        const isCorp = window.IS_CORPORATE || (document.getElementById("statShiftHours") !== null) || (window.location.pathname.includes('/employees'));
        
        if (isCorp && (targetRole === "student" || targetRole === "teacher" || !targetRole)) {
            targetRole = "employee";
        } else if (!targetRole) {
            targetRole = "student";
        }

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

        roleSelect.value = targetRole;
    }

    if (document.getElementById("editDateOfJoining")) {
        document.getElementById("editDateOfJoining").value = doj || "";
    }

    if (document.getElementById("editShiftSelect")) {
        document.getElementById("editShiftSelect").value = (shiftId !== undefined && shiftId !== null) ? shiftId : "";
    }

    if (document.getElementById("editLocationSelect")) {
        document.getElementById("editLocationSelect").value = (locationId !== undefined && locationId !== null) ? locationId : "";
    }

    if (document.getElementById("editDesignationSelect")) {
        document.getElementById("editDesignationSelect").value = (designationId !== undefined && designationId !== null) ? designationId : "";
    }

    if (document.getElementById("editSalaryTemplateSelect")) {
        document.getElementById("editSalaryTemplateSelect").value = (salaryTemplateId !== undefined && salaryTemplateId !== null) ? salaryTemplateId : "";
    }

    if (document.getElementById("editHourlyRate")) {
        document.getElementById("editHourlyRate").value = (hourlyRate !== undefined && hourlyRate !== null) ? hourlyRate : "";
    }

    if (document.getElementById("editMonthlyBaseSalary")) {
        document.getElementById("editMonthlyBaseSalary").value = (monthlySalary !== undefined && monthlySalary !== null) ? monthlySalary : "";
    }

    const deptSelect = document.getElementById("editDepartmentSelect");
    if (deptSelect) {
        if (deptId) {
            deptSelect.value = deptId;
        } else {
            // Find by text
            for (let i = 0; i < deptSelect.options.length; i++) {
                if (deptSelect.options[i].text.toLowerCase() === (dept || "").toLowerCase()) {
                    deptSelect.selectedIndex = i;
                    break;
                }
            }
        }
        onEditDeptSelectChanged();
    }

    const classSelect = document.getElementById("editClassSelect");
    if (classSelect) {
        if (classId) {
            classSelect.value = classId;
        } else {
            classSelect.value = "";
        }
        onEditClassSelectChanged();
    }

    const divSelect = document.getElementById("editDivisionSelect");
    if (divSelect) {
        if (divId) {
            divSelect.value = divId;
        } else {
            divSelect.value = "";
        }
    }

    onEditRoleChanged();

    const alertBox = document.getElementById("editResultAlert");
    if (alertBox) alertBox.style.display = "none";

    loadStudentPhotosPreview(id, "editStudentPhotosPreview");

    modal.classList.add("active");
}

function closeEditModal() {
    const modal = document.getElementById("editStudentModal");
    if (modal) modal.classList.remove("active");
}

async function loadStudentPhotosPreview(studentId, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 14px; font-size: 12px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading enrolled photos...</div>';

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`);
        const data = await res.json();
        if (res.ok && data.student && data.student.photos && data.student.photos.length > 0) {
            container.innerHTML = data.student.photos.map(p => `
                <div class="photo-preview-card" style="cursor: pointer;" onclick="openLightbox('${p.url}', '${data.student.name} (${p.angle || 'Sample'})')" title="Click to view full image">
                    <img class="photo-preview-img" src="${p.url}" alt="${p.angle}" onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\'aspect-ratio:1/1; display:flex; align-items:center; justify-content:center; color:var(--text-light); font-size:20px;\'><i class=\'fa-regular fa-image\'></i></div><div class=\'photo-preview-label\'>Crop Missing</div>';">
                    <div class="photo-preview-label">${p.angle ? p.angle.replace('_', ' ').toUpperCase() : 'FACE CROP'}</div>
                </div>
            `).join("");
        } else {
            container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 16px; font-size: 12px; color: var(--text-muted); background: #ffffff; border: 1px dashed var(--border-color); border-radius: var(--radius-sm);"><i class="fa-regular fa-image" style="margin-right: 6px;"></i> No photo crops saved on server yet.</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 10px; font-size: 12px; color: var(--accent-rose);">Could not load registered photos.</div>';
    }
}

async function submitStudentEdit(e) {
    e.preventDefault();
    const id = document.getElementById("editStudentId").value;
    const name = document.getElementById("editStudentName").value.trim();
    const roll = document.getElementById("editRollNumber").value.trim();
    const email = document.getElementById("editEmail").value.trim();
    const role = document.getElementById("editUserRole")?.value || "student";

    const deptSelect = document.getElementById("editDepartmentSelect");
    const deptId = deptSelect?.value ? parseInt(deptSelect.value) : null;
    const deptName = deptSelect && deptSelect.selectedIndex >= 0 ? deptSelect.options[deptSelect.selectedIndex].text : "Computer Science";

    const classSelect = document.getElementById("editClassSelect");
    const classId = classSelect?.value ? parseInt(classSelect.value) : null;
    const className = classSelect && classSelect.selectedIndex > 0 ? classSelect.options[classSelect.selectedIndex].text : "General";

    const divSelect = document.getElementById("editDivisionSelect");
    const divId = divSelect?.value ? parseInt(divSelect.value) : null;

    const shiftSelect = document.getElementById("editShiftSelect");
    const shiftId = (shiftSelect && shiftSelect.value) ? parseInt(shiftSelect.value) : null;

    const locSelect = document.getElementById("editLocationSelect");
    const locId = (locSelect && locSelect.value) ? parseInt(locSelect.value) : null;

    const desigSelect = document.getElementById("editDesignationSelect");
    const desigId = (desigSelect && desigSelect.value) ? parseInt(desigSelect.value) : null;
    const desigOption = (desigSelect && desigSelect.selectedIndex >= 0) ? desigSelect.options[desigSelect.selectedIndex] : null;
    const desigTitle = desigOption ? (desigOption.getAttribute("data-title") || desigOption.text) : null;

    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    const tplId = (tplSelect && tplSelect.value) ? parseInt(tplSelect.value) : null;

    const hourlyRateInput = document.getElementById("editHourlyRate")?.value;
    const monthlySalaryInput = document.getElementById("editMonthlyBaseSalary")?.value;
    const dojInput = document.getElementById("editDateOfJoining")?.value;

    const saveBtn = document.getElementById("btnSaveEdit");
    const alertBox = document.getElementById("editResultAlert");

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

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
                monthly_base_salary: monthlySalaryInput ? parseFloat(monthlySalaryInput) : null,
                date_of_joining: dojInput !== undefined ? dojInput : null,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Profile updated successfully!';

            setTimeout(() => {
                closeEditModal();
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
                window.location.reload();
            }, 700);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Update failed.");
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
        }
    } catch (e) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
    }
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

    retakeStudentId = id;
    document.getElementById("retakeStudentId").value = id;
    document.getElementById("retakeModalTitle").innerText = `Update Photos: ${name}`;
    document.getElementById("retakeModalSubtitle").innerText = `Roll Number: ${roll} | Overwrite with 3 fresh reference images`;

    retakeFiles = [];
    updateRetakePreviews();

    const alertBox = document.getElementById("retakeResultAlert");
    if (alertBox) alertBox.style.display = "none";

    loadStudentPhotosPreview(id, "retakeExistingPhotosPreview");

    switchRetakeMode("upload");
    modal.classList.add("active");
}

function closeRetakeModal() {
    const modal = document.getElementById("retakePhotosModal");
    if (modal) modal.classList.remove("active");
    stopRetakeWebcam();
}

function switchRetakeMode(mode) {
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
    } else {
        if (tabWebcam) tabWebcam.classList.add("active");
        if (tabUpload) tabUpload.classList.remove("active");
        if (secWebcam) secWebcam.style.display = "block";
        if (secUpload) secUpload.style.display = "none";
        startRetakeWebcam();
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
async function startRetakeWebcam() {
    if (retakeWebcamStream) return;
    const video = document.getElementById("retakeWebcamVideo");
    try {
        retakeWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });
        if (video) video.srcObject = retakeWebcamStream;
    } catch (e) {
        const fb = document.getElementById("retakeCamFeedback");
        if (fb) fb.innerHTML = '<span style="color:var(--accent-rose); font-weight:600;">Camera in use or permission denied.</span>';
    }
}

function stopRetakeWebcam() {
    if (retakeWebcamStream) {
        retakeWebcamStream.getTracks().forEach(t => t.stop());
        retakeWebcamStream = null;
        const video = document.getElementById("retakeWebcamVideo");
        if (video) video.srcObject = null;
    }
}

async function captureRetakeSample(angle) {
    if (!retakeStudentId) return;
    const video = document.getElementById("retakeWebcamVideo");
    const canvas = document.getElementById("retakeCaptureCanvas");
    if (!video || !canvas) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append("student_id", retakeStudentId);
        formData.append("sample_angle", angle);
        formData.append("image", blob, `retake_${angle}.jpg`);

        const fb = document.getElementById("retakeCamFeedback");
        if (fb) fb.innerHTML = `<span style="color:var(--accent-primary);"><i class="fa-solid fa-spinner fa-spin"></i> Saving ${angle} sample...</span>`;

        try {
            const res = await fetch("/api/v1/enroll/capture-sample", {
                method: "POST",
                body: formData,
            });
            const data = await res.json();
            if (res.ok) {
                if (fb) fb.innerHTML = `<span style="color:var(--badge-emerald-text); font-weight:600;">✓ ${angle} pose recorded!</span>`;
                if (angle === 'frontal') {
                    document.getElementById("btnRetakeCapFrontal").disabled = true;
                    document.getElementById("btnRetakeCapFrontal").className = "btn btn-primary";
                    document.getElementById("btnRetakeCapLeft").disabled = false;
                } else if (angle === 'left') {
                    document.getElementById("btnRetakeCapLeft").disabled = true;
                    document.getElementById("btnRetakeCapLeft").className = "btn btn-primary";
                    document.getElementById("btnRetakeCapRight").disabled = false;
                } else if (angle === 'right') {
                    document.getElementById("btnRetakeCapRight").disabled = true;
                    document.getElementById("btnRetakeCapRight").className = "btn btn-primary";
                    if (fb) fb.innerHTML = '<span style="color:var(--badge-emerald-text); font-weight:700;">✓ All 3 samples retaken! Refreshing directory...</span>';
                    stopRetakeWebcam();
                    setTimeout(() => window.location.reload(), 1000);
                }
            } else {
                if (fb) fb.innerHTML = `<span style="color:var(--accent-rose);">${data.detail}</span>`;
            }
        } catch (e) {
            if (fb) fb.innerHTML = '<span style="color:var(--accent-rose);">Upload failed. Try again.</span>';
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
    if (modal) modal.classList.add("active");
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
    if (modal) modal.classList.remove("active");
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
    if (normalized === "corporate") normalized = "slate";
    if (!["light", "dark", "warm", "slate"].includes(normalized)) {
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
    else if (currentTheme === "warm" || currentTheme === "academic") nextTheme = "slate";
    else nextTheme = "light";

    setAppTheme(nextTheme);
}

function updateThemeDropdown(theme) {
    let current = theme || document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
    if (current === "academic") current = "warm";
    if (current === "corporate") current = "slate";
    const select = document.getElementById("appThemeSelect");
    const icon = document.getElementById("themeIconIndicator");
    if (select) select.value = current;
    if (icon) {
        if (current === "dark") {
            icon.className = "fa-solid fa-moon";
            icon.style.color = "#38bdf8";
        } else if (current === "warm") {
            icon.className = "fa-solid fa-fire-flame-curved";
            icon.style.color = "#ea580c";
        } else if (current === "slate") {
            icon.className = "fa-solid fa-briefcase";
            icon.style.color = "#1e40af";
        } else {
            icon.className = "fa-solid fa-sun";
            icon.style.color = "#f59e0b";
        }
    }
}

function updateThemeSelectionCards(theme) {
    let current = theme || document.documentElement.getAttribute("data-theme") || "light";
    if (current === "academic") current = "warm";
    if (current === "corporate") current = "slate";
    const cardLight = document.getElementById("themeCardLight");
    const cardDark = document.getElementById("themeCardDark");
    const cardWarm = document.getElementById("themeCardWarm") || document.getElementById("themeCardAcademic");
    const cardSlate = document.getElementById("themeCardSlate") || document.getElementById("themeCardCorporate");
    const badge = document.getElementById("activeThemeBadge");

    if (cardLight) cardLight.classList.toggle("active", current === "light");
    if (cardDark) cardDark.classList.toggle("active", current === "dark");
    if (cardWarm) cardWarm.classList.toggle("active", current === "warm");
    if (cardSlate) cardSlate.classList.toggle("active", current === "slate");

    if (badge) {
        if (current === "dark") {
            badge.className = "badge badge-sky";
            badge.innerHTML = '<i class="fa-solid fa-moon"></i> Active: Midnight Dark';
        } else if (current === "warm") {
            badge.className = "badge badge-amber";
            badge.innerHTML = '<i class="fa-solid fa-fire-flame-curved"></i> Active: Warm';
        } else if (current === "slate") {
            badge.className = "badge badge-indigo";
            badge.innerHTML = '<i class="fa-solid fa-briefcase"></i> Active: Professional Slate';
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

