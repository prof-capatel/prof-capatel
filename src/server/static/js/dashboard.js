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
                <h4 style="font-size: 14px; font-weight: 700; color: var(--text-heading);">${data.student_name || "Unknown Student"}</h4>
                <div style="font-size: 12px; color: var(--text-muted); display: flex; gap: 10px; margin-top: 2px;">
                    <span>Roll: <strong>${data.roll_number || 'N/A'}</strong></span>
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
            <span class="badge badge-present"><i class="fa-solid fa-shield-check"></i> Manual Override</span>
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

async function applyLogFilters() {
    const dateInput = document.getElementById("filterDate")?.value;
    const rollInput = document.getElementById("filterRoll")?.value;
    const deptInput = document.getElementById("filterDept")?.value;
    const roleInput = document.getElementById("filterRole")?.value;
    const overrideInput = document.getElementById("filterOverride")?.value;
    const tableBody = document.getElementById("logsTableBody");

    if (!tableBody) return;

    tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted); font-weight: 500;"><i class="fa-solid fa-spinner fa-spin"></i> Loading attendance audit records...</td></tr>';

    let url = `/api/v1/attendance/records?limit=150`;
    if (dateInput) url += `&date_str=${encodeURIComponent(dateInput)}`;
    if (rollInput) url += `&roll_number=${encodeURIComponent(rollInput)}`;
    if (deptInput) url += `&department=${encodeURIComponent(deptInput)}`;
    if (roleInput) url += `&user_role=${encodeURIComponent(roleInput)}`;
    if (overrideInput !== undefined && overrideInput !== "") url += `&is_override=${encodeURIComponent(overrideInput)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        renderLogsTable(data.records);
    } catch (e) {
        tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--accent-rose); padding: 24px; font-weight: 600;">Failed to fetch logs from server.</td></tr>';
    }
}

function renderLogsTable(records) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    if (!records || records.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding: 36px; color: var(--text-muted);">No attendance records found matching filters.</td></tr>';
        return;
    }

    tableBody.innerHTML = records.map(r => {
        let roleBadge = '<span class="badge badge-present">Student</span>';
        if (r.user_role === 'teacher') roleBadge = '<span class="badge badge-node">Faculty</span>';
        else if (r.user_role === 'admin_staff') roleBadge = '<span class="badge badge-amber">Admin Staff</span>';
        else if (r.user_role === 'other') roleBadge = '<span class="badge badge-node">Other</span>';

        let verificationBadge = `<span class="badge badge-present">✓ ${r.match_confidence_pct}% Face Match</span>`;
        if (r.is_manual_override) {
            verificationBadge = `<span class="badge badge-amber" title="Override Reason: ${r.override_reason || 'N/A'} (By ${r.override_by || 'Admin'})"><i class="fa-solid fa-shield-check"></i> Manual Override</span>`;
        } else if (r.is_self_attendance) {
            verificationBadge = `<span class="badge badge-emerald" title="GPS Dist: ${r.geo_distance_meters !== null ? r.geo_distance_meters + 'm' : 'Verified'} • Lat: ${r.geo_latitude || 'N/A'}, Lon: ${r.geo_longitude || 'N/A'}"><i class="fa-solid fa-satellite-dish"></i> ${r.match_confidence_pct}% (GPS)</span>`;
        }

        let nodeBadge = `<span class="badge ${r.is_manual_override ? 'badge-amber' : 'badge-node'}">${r.node_id}</span>`;
        if (r.is_self_attendance) {
            nodeBadge = `<span class="badge badge-emerald" title="GPS Geofenced Check-in"><i class="fa-solid fa-mobile-screen"></i> ${r.geo_distance_meters !== null ? r.geo_distance_meters + 'm from Campus' : 'Self-Mobile'}</span>`;
        }

        return `
            <tr>
                <td>#${r.id}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div class="feed-avatar" style="width: 32px; height: 32px; font-size: 12px;">
                            ${r.snapshot_path ? `<img src="/data/${r.snapshot_path}" alt="Face">` : `<span>${r.student_name.charAt(0)}</span>`}
                        </div>
                        <strong style="color: var(--text-heading);">${r.student_name}</strong>
                    </div>
                </td>
                <td><code>${r.roll_number}</code></td>
                <td>${roleBadge}</td>
                <td>${r.department}</td>
                <td><span class="badge badge-node">${r.class_semester || 'General'}</span></td>
                <td>${nodeBadge}</td>
                <td>${r.timestamp}</td>
                <td>${verificationBadge}</td>
            </tr>
        `;
    }).join("");
}

function exportData(format) {
    const dateInput = document.getElementById("filterDate")?.value || "";
    let url = `/api/v1/attendance/export?export_format=${format}`;
    if (dateInput) url += `&date_str=${encodeURIComponent(dateInput)}`;
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

function applyDirectoryFilters() {
    const searchVal = (document.getElementById("dirSearchInput")?.value || "").toLowerCase().trim();
    const deptFilterEl = document.getElementById("dirDeptFilter");
    const deptIdVal = deptFilterEl?.value || "";
    const deptTextVal = deptIdVal && deptFilterEl ? (deptFilterEl.options[deptFilterEl.selectedIndex]?.text || "").toLowerCase().trim() : "";

    const classIdVal = document.getElementById("dirClassFilter")?.value || "";
    const divIdVal = document.getElementById("dirDivFilter")?.value || "";
    const roleVal = document.getElementById("dirRoleFilter")?.value || "";

    const rows = document.querySelectorAll(".student-row");
    let visibleCount = 0;

    rows.forEach(row => {
        const name = (row.getAttribute("data-name") || "").toLowerCase();
        const roll = (row.getAttribute("data-roll") || "").toLowerCase();
        const rowDeptId = row.getAttribute("data-dept-id") || "";
        const rowDept = (row.getAttribute("data-dept") || "").toLowerCase();
        const rowClassId = row.getAttribute("data-class-id") || "";
        const rowDivId = row.getAttribute("data-div-id") || "";
        const rowRole = row.getAttribute("data-role") || "student";

        let matchSearch = !searchVal || name.includes(searchVal) || roll.includes(searchVal);
        let matchDept = !deptIdVal || rowDeptId === deptIdVal || (rowDept && rowDept === deptTextVal);
        let matchClass = !classIdVal || rowClassId === classIdVal;
        let matchDiv = !divIdVal || rowDivId === divIdVal;
        let matchRole = !roleVal || rowRole === roleVal;

        if (matchSearch && matchDept && matchClass && matchDiv && matchRole) {
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

    applyDirectoryFilters();
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

function openEditModal(id, name, roll, dept, email, role, classSem, deptId, classId, divId) {
    const modal = document.getElementById("editStudentModal");
    if (!modal) return;

    document.getElementById("editStudentId").value = id;
    document.getElementById("editStudentName").value = name;
    document.getElementById("editRollNumber").value = roll;
    document.getElementById("editEmail").value = email || "";
    if (document.getElementById("editUserRole")) {
        document.getElementById("editUserRole").value = role || "student";
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
                email: email || null,
                user_role: role,
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
async function populateStudentDropdown() {
    try {
        const res = await fetch("/api/v1/enroll/students");
        const data = await res.json();
        const select = document.getElementById("overrideStudentSelect");
        if (!select || !data.students) return;

        select.innerHTML = '<option value="">-- Choose Member --</option>' +
            data.students.map(s => `<option value="${s.id}">${s.name} (${s.roll_number} - ${s.department}) [${s.user_role || 'student'}]</option>`).join("");
    } catch (e) {}
}

function openManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (modal) modal.classList.add("active");
    const alertBox = document.getElementById("overrideResultAlert");
    if (alertBox) alertBox.style.display = "none";
    populateStudentDropdown();
}

function openManualOverrideForStudent(studentId) {
    openManualOverrideModal();
    setTimeout(() => {
        const select = document.getElementById("overrideStudentSelect");
        if (select) select.value = studentId;
    }, 100);
}

function closeManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (modal) modal.classList.remove("active");
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
                saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
                if (typeof loadAnalyticsData === "function") loadAnalyticsData();
                if (typeof applyLogFilters === "function") applyLogFilters();
            }, 900);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Failed to record override.'}`;
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Force Mark Present';
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
    updateQuickThemeButton(currentTheme);
    updateThemeSelectionCards(currentTheme);
}

function setAppTheme(themeName) {
    if (!["light", "dark", "academic"].includes(themeName)) {
        themeName = "light";
    }
    document.documentElement.setAttribute("data-theme", themeName);
    try {
        localStorage.setItem("app_theme", themeName);
    } catch (e) {}

    updateThemeSelectionCards(themeName);
    updateQuickThemeButton(themeName);
}

function cycleAppTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
    let nextTheme = "light";
    if (currentTheme === "light") nextTheme = "dark";
    else if (currentTheme === "dark") nextTheme = "academic";
    else nextTheme = "light";

    setAppTheme(nextTheme);
}

function updateThemeSelectionCards(theme) {
    const current = theme || document.documentElement.getAttribute("data-theme") || "light";
    const cardLight = document.getElementById("themeCardLight");
    const cardDark = document.getElementById("themeCardDark");
    const cardAcad = document.getElementById("themeCardAcademic");
    const badge = document.getElementById("activeThemeBadge");

    if (cardLight) cardLight.classList.toggle("active", current === "light");
    if (cardDark) cardDark.classList.toggle("active", current === "dark");
    if (cardAcad) cardAcad.classList.toggle("active", current === "academic");

    if (badge) {
        if (current === "dark") {
            badge.className = "badge badge-sky";
            badge.innerHTML = '<i class="fa-solid fa-moon"></i> Active: Midnight Dark';
        } else if (current === "academic") {
            badge.className = "badge badge-amber";
            badge.innerHTML = '<i class="fa-solid fa-graduation-cap"></i> Active: Warm Academic';
        } else {
            badge.className = "badge badge-present";
            badge.innerHTML = '<i class="fa-solid fa-sun"></i> Active: Clean Light';
        }
    }
}

function updateQuickThemeButton(theme) {
    const current = theme || document.documentElement.getAttribute("data-theme") || "light";
    const btn = document.getElementById("btnQuickThemeToggle");
    const label = document.getElementById("quickThemeLabel");
    if (!btn || !label) return;

    if (current === "dark") {
        label.innerText = "Dark";
        btn.querySelector("i").className = "fa-solid fa-moon";
    } else if (current === "academic") {
        label.innerText = "Academic";
        btn.querySelector("i").className = "fa-solid fa-graduation-cap";
    } else {
        label.innerText = "Light";
        btn.querySelector("i").className = "fa-solid fa-sun";
    }
}

