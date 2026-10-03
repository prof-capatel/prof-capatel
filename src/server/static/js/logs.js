/**
 * Curiosity HUB - Multi-Tenant Attendance Logs & Real-Time Audit Trail Controller
 * Supports Corporate Shift Punch Tracking (Check-In / Check-Out) and Educational Turnout Logs
 */

// Global State
let currentLogsPreset = "today";
let currentLogsData = [];
let targetDeleteRecordId = null;

// ==============================================================================
// 1. Date Range Presets & Filter Helpers
// ==============================================================================

function selectLogsPreset(preset) {
    currentLogsPreset = preset;
    const now = new Date();
    let startDate = new Date();
    let endDate = new Date();

    const buttons = document.querySelectorAll(".preset-btn");
    buttons.forEach(b => {
        if (b.getAttribute("data-preset") === preset) {
            b.classList.remove("btn-secondary");
            b.classList.add("btn-primary");
        } else {
            b.classList.remove("btn-primary");
            b.classList.add("btn-secondary");
        }
    });

    if (preset === "today") {
        // start and end are today
    } else if (preset === "week") {
        const day = now.getDay();
        const diff = now.getDate() - day + (day === 0 ? -6 : 1); // Monday
        startDate.setDate(diff);
    } else if (preset === "month") {
        startDate.setDate(1); // 1st of current month
    } else if (preset === "last30") {
        startDate.setDate(now.getDate() - 30);
    }

    const startStr = formatDate(startDate);
    const endStr = formatDate(endDate);

    const startInput = document.getElementById("filterStartDate");
    const endInput = document.getElementById("filterEndDate");
    if (startInput) startInput.value = startStr;
    if (endInput) endInput.value = endStr;

    updateDateRangeLabel(startStr, endStr);
    applyLogFilters();
}

function onCustomLogsDateChange() {
    const startStr = document.getElementById("filterStartDate")?.value;
    const endStr = document.getElementById("filterEndDate")?.value;
    
    // Clear preset button active highlight
    const buttons = document.querySelectorAll(".preset-btn");
    buttons.forEach(b => {
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
    });

    updateDateRangeLabel(startStr, endStr);
    applyLogFilters();
}

function updateDateRangeLabel(startStr, endStr) {
    const label = document.getElementById("logsDateLabel");
    if (!label) return;
    if (startStr === endStr) {
        label.textContent = startStr || "Today";
    } else {
        label.textContent = `${startStr} to ${endStr}`;
    }
}

function formatDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

// ==============================================================================
// 2. Attendance Logs Fetching & Table Rendering
// ==============================================================================

async function applyLogFilters() {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    const startDate = document.getElementById("filterStartDate")?.value || "";
    const endDate = document.getElementById("filterEndDate")?.value || "";
    const roll = (document.getElementById("filterRoll")?.value || "").trim();
    const dept = document.getElementById("filterDept")?.value || "";
    const role = document.getElementById("filterRole")?.value || "";
    const overrideVal = document.getElementById("filterOverride")?.value || "";
    const viewMode = document.getElementById("filterViewMode")?.value || "active";

    // Show Loading Skeleton
    tableBody.innerHTML = `
        <tr>
            <td colspan="11" style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
                <i class="fa-solid fa-spinner fa-spin" style="font-size: 24px; color: var(--accent-primary); margin-bottom: 8px;"></i>
                <p style="font-size: 13px; font-weight: 600;">Loading attendance logs...</p>
            </td>
        </tr>
    `;

    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (roll) params.append("roll_number", roll);
    if (dept) params.append("department", dept);
    if (role) params.append("user_role", role);
    if (overrideVal !== "") params.append("is_override", overrideVal);
    params.append("view_mode", viewMode);
    params.append("limit", "300");

    try {
        const res = await fetch(`/api/v1/attendance/records?${params.toString()}`);
        if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = data.records || [];
        currentLogsData = records;
        const isCorporate = data.is_corporate || window.IS_CORPORATE;

        renderLogsTable(records, isCorporate, viewMode);
    } catch (err) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; padding: 40px 20px; color: var(--accent-rose, #dc2626);">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 24px; margin-bottom: 8px;"></i>
                    <p style="font-size: 13px; font-weight: 700;">Failed to fetch attendance logs</p>
                    <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">${escapeHtml(err.message)}</p>
                    <button type="button" class="btn btn-secondary" onclick="applyLogFilters()" style="margin-top: 10px; font-size: 12px;">
                        <i class="fa-solid fa-rotate"></i> Retry
                    </button>
                </td>
            </tr>
        `;
    }
}

function renderLogsTable(records, isCorporate, viewMode) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    if (!records || records.length === 0) {
        const emptyMsg = (viewMode === "deleted" || viewMode === "trash")
            ? "No soft-deleted attendance records in Trash."
            : "No attendance logs found matching the selected filters.";
        tableBody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; padding: 50px 20px; color: var(--text-muted);">
                    <i class="fa-solid fa-clipboard-question" style="font-size: 36px; margin-bottom: 12px; color: var(--text-light);"></i>
                    <p style="font-size: 15px; font-weight: 600; color: var(--text-heading);">${emptyMsg}</p>
                    <p style="font-size: 12.5px; color: var(--text-muted); margin-top: 4px;">Punches ingested via Face Recognition or Manual Overrides will appear here in real-time.</p>
                </td>
            </tr>
        `;
        return;
    }

    let html = "";
    records.forEach(r => {
        const student = r.student || {};
        const studentName = r.student_name || r.name || student.name || "Unknown Member";
        const studentRoll = r.roll_number || student.roll_number || "N/A";
        const studentEmail = r.email || r.student_email || student.email || "";
        const studentDept = r.department || student.department || "General";
        const studentRole = r.user_role || student.user_role || (isCorporate ? "employee" : "student");
        const studentDesig = r.designation || student.designation || "Staff";
        const studentClass = r.class_semester || student.class_semester || "General";
        const initial = studentName.charAt(0).toUpperCase();

        const nodeId = r.node_id || "GATEWAY";
        const isOverride = r.is_manual_override;
        const isDeleted = r.is_deleted;
        const tsFormatted = r.timestamp_formatted || (r.timestamp ? `${r.timestamp} IST` : "N/A");

        if (isCorporate) {
            // Corporate Table Row: 24-hour timestamp with IST indicator
            const checkInFormatted = r.check_in_formatted || (r.check_in_time ? `${r.check_in_time} IST` : (r.timestamp ? `${r.timestamp} IST` : "--"));
            const checkOutFormatted = r.check_out_formatted || (r.check_out_time ? `${r.check_out_time} IST` : "--");
            const activeHours = r.work_duration_formatted || (r.work_duration_minutes ? `${r.work_duration_minutes}m` : "--");

            // Shift Status Badge
            let shiftBadge = `<span class="badge badge-present"><i class="fa-solid fa-circle-check"></i> ${escapeHtml(r.status_badge_label || 'On Time')}</span>`;
            if (r.shift_status === "MISSED_CHECKOUT") {
                shiftBadge = `<span class="badge badge-amber"><i class="fa-solid fa-clock"></i> Missed Checkout</span>`;
            } else if (r.shift_status === "LATE_ARRIVAL") {
                shiftBadge = `<span class="badge badge-amber"><i class="fa-solid fa-clock"></i> Late Arrival</span>`;
            } else if (r.shift_status === "EARLY_DEPARTURE") {
                shiftBadge = `<span class="badge badge-sky"><i class="fa-solid fa-arrow-right-from-bracket"></i> Early Departure</span>`;
            } else if (isOverride) {
                shiftBadge = `<span class="badge badge-node"><i class="fa-solid fa-user-check"></i> Manual Override</span>`;
            }

            html += `
                <tr style="${isDeleted ? 'opacity: 0.65; background: rgba(239, 68, 68, 0.04);' : ''}">
                    <td><code style="font-size: 11.5px;">#${r.id}</code></td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div class="feed-avatar" style="width: 32px; height: 32px; font-size: 12px; ${isDeleted ? 'filter: grayscale(1);' : ''}">
                                <span>${initial}</span>
                            </div>
                            <div>
                                <strong style="color: var(--text-heading); font-size: 13px; ${isDeleted ? 'text-decoration: line-through;' : ''}">${escapeHtml(studentName)}</strong>
                                <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(studentEmail || 'No email')}</div>
                            </div>
                        </div>
                    </td>
                    <td><code style="font-size: 12px; font-weight: 600;">${escapeHtml(studentRoll)}</code></td>
                    <td><span class="badge badge-sky"><i class="fa-solid fa-id-badge"></i> ${escapeHtml(studentDesig)}</span></td>
                    <td><span style="font-weight: 600; font-size: 12.5px; color: var(--text-heading);">${escapeHtml(studentDept)}</span></td>
                    <td>
                        <span class="badge ${isOverride ? 'badge-amber' : 'badge-node'}" style="font-size: 11px;">
                            <i class="fa-solid ${isOverride ? 'fa-pen-to-square' : 'fa-network-wired'}"></i> ${escapeHtml(nodeId)}
                        </span>
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="font-weight: 700; color: var(--accent-emerald, #10b981); font-size: 12.5px;">${escapeHtml(checkInFormatted)}</span>
                            ${r.check_in_photo ? `<img src="${r.check_in_photo}" style="width: 24px; height: 24px; border-radius: 4px; object-fit: cover; cursor: pointer;" onclick="openLightbox('${r.check_in_photo}', 'Check-in: ${escapeHtml(studentName)}')" title="Check-in Photo">` : ''}
                        </div>
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="font-weight: 600; color: ${checkOutFormatted !== '--' ? 'var(--text-heading)' : 'var(--text-light)'}; font-size: 12.5px;">${escapeHtml(checkOutFormatted)}</span>
                            ${r.check_out_photo ? `<img src="${r.check_out_photo}" style="width: 24px; height: 24px; border-radius: 4px; object-fit: cover; cursor: pointer;" onclick="openLightbox('${r.check_out_photo}', 'Check-out: ${escapeHtml(studentName)}')" title="Check-out Photo">` : ''}
                        </div>
                    </td>
                    <td><span style="font-weight: 600; font-size: 12px; color: var(--text-secondary);">${escapeHtml(activeHours)}</span></td>
                    <td>${shiftBadge}</td>
                    <td style="text-align: right;">
                        ${isDeleted ? `
                            <button type="button" class="btn btn-secondary" onclick="restoreAttendanceRecord(${r.id})" style="padding: 4px 8px; font-size: 11px; color: #10b981;" title="Restore Record">
                                <i class="fa-solid fa-rotate-left"></i> Restore
                            </button>
                        ` : `
                            <button type="button" class="btn btn-secondary" onclick="openDeleteAttendanceModal(${r.id}, '${escapeHtml(studentName)}', '${escapeHtml(tsFormatted)}', '${escapeHtml(nodeId)}')" style="padding: 4px 8px; font-size: 11px; color: #ef4444;" title="Soft Delete Attendance Log">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        `}
                    </td>
                </tr>
            `;
        } else {
            // Educational Table Row
            let roleBadge = `<span class="badge badge-present"><i class="fa-solid fa-user"></i> Student</span>`;
            if (studentRole === "teacher" || studentRole === "faculty") {
                roleBadge = `<span class="badge badge-node"><i class="fa-solid fa-chalkboard-user"></i> Faculty</span>`;
            } else if (studentRole === "admin_staff") {
                roleBadge = `<span class="badge badge-amber"><i class="fa-solid fa-user-shield"></i> Admin Staff</span>`;
            }

            let statusBadge = `<span class="badge badge-present"><i class="fa-solid fa-circle-check"></i> Present</span>`;
            if (isOverride) {
                statusBadge = `<span class="badge badge-amber" title="Manual Override: ${escapeHtml(r.override_reason || 'Admin Marked')}"><i class="fa-solid fa-user-check"></i> Manual Override</span>`;
            }

            html += `
                <tr style="${isDeleted ? 'opacity: 0.65; background: rgba(239, 68, 68, 0.04);' : ''}">
                    <td><code style="font-size: 11.5px;">#${r.id}</code></td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div class="feed-avatar" style="width: 32px; height: 32px; font-size: 12px; ${isDeleted ? 'filter: grayscale(1);' : ''}">
                                <span>${initial}</span>
                            </div>
                            <div>
                                <strong style="color: var(--text-heading); font-size: 13px; ${isDeleted ? 'text-decoration: line-through;' : ''}">${escapeHtml(studentName)}</strong>
                                <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(studentEmail || 'No email')}</div>
                            </div>
                        </div>
                    </td>
                    <td><code style="font-size: 12px; font-weight: 600;">${escapeHtml(studentRoll)}</code></td>
                    <td>${roleBadge}</td>
                    <td><span style="font-weight: 600; font-size: 12.5px; color: var(--text-heading);">${escapeHtml(studentDept)}</span></td>
                    <td><span style="font-size: 12px; color: var(--text-secondary);">${escapeHtml(studentClass)}</span></td>
                    <td>
                        <span class="badge ${isOverride ? 'badge-amber' : 'badge-node'}" style="font-size: 11px;">
                            <i class="fa-solid ${isOverride ? 'fa-pen-to-square' : 'fa-network-wired'}"></i> ${escapeHtml(nodeId)}
                        </span>
                    </td>
                    <td>
                        <span style="font-family: monospace; font-size: 12px; color: var(--text-primary);">${escapeHtml(tsFormatted)}</span>
                    </td>
                    <td>${statusBadge}</td>
                    <td style="text-align: right;">
                        ${isDeleted ? `
                            <button type="button" class="btn btn-secondary" onclick="restoreAttendanceRecord(${r.id})" style="padding: 4px 8px; font-size: 11px; color: #10b981;" title="Restore Record">
                                <i class="fa-solid fa-rotate-left"></i> Restore
                            </button>
                        ` : `
                            <button type="button" class="btn btn-secondary" onclick="openDeleteAttendanceModal(${r.id}, '${escapeHtml(studentName)}', '${escapeHtml(tsFormatted)}', '${escapeHtml(nodeId)}')" style="padding: 4px 8px; font-size: 11px; color: #ef4444;" title="Soft Delete Attendance Log">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        `}
                    </td>
                </tr>
            `;
        }
    });

    tableBody.innerHTML = html;
}

// Helper to escape HTML characters safely
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ==============================================================================
// 3. Export Data (CSV / Excel)
// ==============================================================================

function exportData(format) {
    const startDate = document.getElementById("filterStartDate")?.value || "";
    const endDate = document.getElementById("filterEndDate")?.value || "";
    const roll = (document.getElementById("filterRoll")?.value || "").trim();
    const dept = document.getElementById("filterDept")?.value || "";
    const role = document.getElementById("filterRole")?.value || "";
    const overrideVal = document.getElementById("filterOverride")?.value || "";
    const viewMode = document.getElementById("filterViewMode")?.value || "active";

    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (roll) params.append("roll_number", roll);
    if (dept) params.append("department", dept);
    if (role) params.append("user_role", role);
    if (overrideVal !== "") params.append("is_override", overrideVal);
    params.append("view_mode", viewMode);

    const endpoint = (format === "xlsx" || format === "excel")
        ? `/api/v1/attendance/export/xlsx?${params.toString()}`
        : `/api/v1/attendance/export/csv?${params.toString()}`;

    window.open(endpoint, "_blank");
}

// ==============================================================================
// 4. Soft Delete & Restore Attendance Record Modal
// ==============================================================================

function openDeleteAttendanceModal(recordId, name, timestamp, details) {
    targetDeleteRecordId = recordId;
    const modal = document.getElementById("deleteAttendanceModal");
    if (!modal) return;

    const elId = document.getElementById("deleteModalRecordId");
    if (elId) elId.textContent = `#${recordId}`;

    const elName = document.getElementById("deleteModalMemberName");
    if (elName) elName.textContent = name || "Unknown Member";

    const elTs = document.getElementById("deleteModalTimestamp");
    if (elTs) elTs.textContent = timestamp || "--";

    const elDetails = document.getElementById("deleteModalDetails");
    if (elDetails) elDetails.textContent = details || "GATEWAY";

    const targetInput = document.getElementById("deleteTargetRecordId");
    if (targetInput) targetInput.value = recordId;

    const btn = document.getElementById("btnConfirmDeleteAttendance");
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> <span>Confirm Delete</span>';
    }

    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeDeleteAttendanceModal() {
    const modal = document.getElementById("deleteAttendanceModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
    targetDeleteRecordId = null;
}

async function executeDeleteAttendanceRecord() {
    const recordId = targetDeleteRecordId || document.getElementById("deleteTargetRecordId")?.value;
    if (!recordId) return;

    const btn = document.getElementById("btnConfirmDeleteAttendance");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Deleting...</span>';
    }

    try {
        const res = await fetch(`/api/v1/attendance/records/${recordId}`, {
            method: "DELETE",
        });
        const data = await res.json();

        if (res.ok) {
            closeDeleteAttendanceModal();
            applyLogFilters();
        } else {
            alert(data.detail || "Failed to soft-delete attendance record.");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> <span>Confirm Delete</span>';
            }
        }
    } catch (err) {
        alert("Network error while deleting attendance record.");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> <span>Confirm Delete</span>';
        }
    }
}

async function restoreAttendanceRecord(recordId) {
    if (!confirm(`Are you sure you want to restore attendance log #${recordId}?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/attendance/records/${recordId}/restore`, {
            method: "POST",
        });
        const data = await res.json();

        if (res.ok) {
            applyLogFilters();
        } else {
            alert(data.detail || "Failed to restore attendance record.");
        }
    } catch (err) {
        alert("Network error while restoring attendance record.");
    }
}

// ==============================================================================
// 5. Manual Attendance Override Modal
// ==============================================================================

function openManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (!modal) return;

    populateStudentDropdown();

    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const tsInput = document.getElementById("overrideTimestamp");
    if (tsInput) tsInput.value = now.toISOString().slice(0, 16);

    const alertBox = document.getElementById("overrideResultAlert");
    if (alertBox) alertBox.style.display = "none";

    const btn = document.getElementById("btnSaveOverride");
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
    }

    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

async function populateStudentDropdown() {
    const select = document.getElementById("overrideStudentSelect");
    if (!select || select.options.length > 1) return;

    try {
        const res = await fetch("/api/v1/enroll/students");
        if (res.ok) {
            const data = await res.json();
            const students = data.students || [];
            select.innerHTML = '<option value="">-- Choose Member --</option>';
            students.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.id;
                opt.textContent = `${s.name} (${s.roll_number} - ${s.department || 'General'}) [${s.designation || s.user_role || 'Member'}]`;
                select.appendChild(opt);
            });
        }
    } catch (e) {}
}

async function onOverrideStudentChanged() {
    const studentId = document.getElementById("overrideStudentSelect")?.value;
    const banner = document.getElementById("overrideStudentStatusBanner");
    if (!banner) return;

    if (!studentId) {
        banner.style.display = "none";
        return;
    }

    try {
        const res = await fetch(`/api/v1/attendance/employee-status/${studentId}`);
        if (res.ok) {
            const data = await res.json();
            banner.style.display = "flex";
            if (data.status === "CHECKED_IN") {
                banner.style.background = "var(--badge-sky-bg, rgba(56,189,248,0.12))";
                banner.style.color = "var(--badge-sky-text, #0284c7)";
                banner.innerHTML = `<i class="fa-solid fa-circle-arrow-right"></i> Currently <strong>Checked In</strong> at ${data.check_in_time || 'N/A'}`;
            } else if (data.status === "CHECKED_OUT") {
                banner.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                banner.style.color = "var(--badge-emerald-text, #059669)";
                banner.innerHTML = `<i class="fa-solid fa-circle-check"></i> Shift Completed: Checked Out at ${data.check_out_time || 'N/A'}`;
            } else {
                banner.style.background = "var(--bg-subtle)";
                banner.style.color = "var(--text-muted)";
                banner.innerHTML = `<i class="fa-regular fa-clock"></i> Not punched yet today`;
            }
        }
    } catch (e) {
        banner.style.display = "none";
    }
}

function onOverridePunchTypeChanged() {}

function applyReasonPreset() {
    const preset = document.getElementById("overridePresetSelect")?.value;
    const reasonInput = document.getElementById("overrideReasonInput");
    if (reasonInput && preset && preset !== "Custom") {
        reasonInput.value = preset;
    }
}

async function submitManualOverride(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const studentId = document.getElementById("overrideStudentSelect")?.value;
    const punchType = document.getElementById("overridePunchType")?.value || "AUTO";
    const timestamp = document.getElementById("overrideTimestamp")?.value;
    const reason = document.getElementById("overrideReasonInput")?.value;
    const overrideBy = document.getElementById("overrideByInput")?.value || "System Administrator";

    if (!studentId || !timestamp || !reason) {
        alert("Please complete all required manual override fields.");
        return;
    }

    const saveBtn = document.getElementById("btnSaveOverride");
    const alertBox = document.getElementById("overrideResultAlert");

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Recording...';
    }

    try {
        const res = await fetch("/api/v1/attendance/manual-override", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                student_id: parseInt(studentId),
                punch_type: punchType,
                timestamp: timestamp,
                reason: reason,
                override_by: overrideBy,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                alertBox.style.color = "var(--badge-emerald-text, #059669)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Attendance manually recorded!");
            }
            setTimeout(() => {
                closeManualOverrideModal();
                applyLogFilters();
            }, 750);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
                alertBox.style.color = "var(--badge-rose-text, #dc2626)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Manual override failed.");
            }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
            alertBox.style.color = "var(--badge-rose-text, #dc2626)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
        }
    }
}

// Lightbox helper for punch photo enlargement
function openLightbox(imgUrl, caption) {
    let modal = document.getElementById("lightboxModal");
    let img = document.getElementById("lightboxImg");
    let cap = document.getElementById("lightboxCaption");

    if (!modal) {
        modal = document.createElement("div");
        modal.id = "lightboxModal";
        modal.className = "lightbox-overlay";
        modal.onclick = () => { modal.style.display = "none"; };
        modal.innerHTML = `
            <div class="lightbox-img-card" onclick="event.stopPropagation()">
                <img id="lightboxImg" class="lightbox-img" src="" alt="Punch Sample">
                <div class="lightbox-footer">
                    <span id="lightboxCaption" style="font-size: 13px; font-weight: 700; color: var(--text-heading);"></span>
                    <button onclick="document.getElementById('lightboxModal').style.display='none'" class="btn btn-secondary" style="padding: 4px 10px; font-size: 11.5px;">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        img = document.getElementById("lightboxImg");
        cap = document.getElementById("lightboxCaption");
    }

    if (img) img.src = imgUrl;
    if (cap) cap.textContent = caption || "";
    modal.classList.add("active");
    modal.style.display = "flex";
}

// ==============================================================================
// DOM Initialization
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    applyLogFilters();
    populateStudentDropdown();

    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const el = document.getElementById("overrideTimestamp");
    if (el) el.value = now.toISOString().slice(0, 16);
});

// Explicit window bindings
window.selectLogsPreset = selectLogsPreset;
window.onCustomLogsDateChange = onCustomLogsDateChange;
window.applyLogFilters = applyLogFilters;
window.exportData = exportData;

window.openDeleteAttendanceModal = openDeleteAttendanceModal;
window.closeDeleteAttendanceModal = closeDeleteAttendanceModal;
window.executeDeleteAttendanceRecord = executeDeleteAttendanceRecord;
window.restoreAttendanceRecord = restoreAttendanceRecord;

window.openManualOverrideModal = openManualOverrideModal;
window.closeManualOverrideModal = closeManualOverrideModal;
window.populateStudentDropdown = populateStudentDropdown;
window.onOverrideStudentChanged = onOverrideStudentChanged;
window.onOverridePunchTypeChanged = onOverridePunchTypeChanged;
window.applyReasonPreset = applyReasonPreset;
window.submitManualOverride = submitManualOverride;
window.openLightbox = openLightbox;
