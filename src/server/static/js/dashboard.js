/* ==========================================================
   Face Recognition Attendance System - Client JavaScript
   ========================================================== */

document.addEventListener("DOMContentLoaded", () => {
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
 * Inserts new attendance item into the live feed without full-page reload
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

    // Fade out highlight border after 4 seconds
    setTimeout(() => {
        item.classList.remove("highlight");
    }, 4000);
}

/**
 * Inserts a prominent security warning banner when a spoof attack is blocked
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
 * Filter and Export Handlers
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
    const tableBody = document.getElementById("logsTableBody");

    if (!tableBody) return;

    tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted); font-weight: 500;">Loading attendance records...</td></tr>';

    let url = `/api/v1/attendance/records?limit=100`;
    if (dateInput) url += `&date_str=${encodeURIComponent(dateInput)}`;
    if (rollInput) url += `&roll_number=${encodeURIComponent(rollInput)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        renderLogsTable(data.records);
    } catch (e) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--accent-rose); padding: 24px; font-weight: 600;">Failed to fetch logs from server.</td></tr>';
    }
}

function renderLogsTable(records) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    if (!records || records.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 36px; color: var(--text-muted);">No attendance records found matching filters.</td></tr>';
        return;
    }

    tableBody.innerHTML = records.map(r => `
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
            <td>${r.department}</td>
            <td><span class="badge badge-node">${r.node_id}</span></td>
            <td>${r.timestamp}</td>
            <td><span class="badge badge-present">${r.match_confidence_pct}%</span></td>
        </tr>
    `).join("");
}

function exportData(format) {
    const dateInput = document.getElementById("filterDate")?.value || "";
    let url = `/api/v1/attendance/export?export_format=${format}`;
    if (dateInput) url += `&date_str=${encodeURIComponent(dateInput)}`;
    window.location.href = url;
}

/**
 * Delete Student
 */
async function deleteStudent(studentId, studentName) {
    if (!confirm(`Are you sure you want to delete student "${studentName}" and all associated face embeddings?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok) {
            alert(`Student "${studentName}" deleted successfully.`);
            window.location.reload();
        } else {
            alert(`Error: ${data.detail || 'Could not delete student'}`);
        }
    } catch (e) {
        alert("Failed to delete student.");
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
   Edit Student Profile Modal
   ========================================================== */
function openEditModal(id, name, roll, dept, email) {
    const modal = document.getElementById("editStudentModal");
    if (!modal) return;

    document.getElementById("editStudentId").value = id;
    document.getElementById("editStudentName").value = name;
    document.getElementById("editRollNumber").value = roll;
    document.getElementById("editDepartment").value = dept || "Computer Science";
    document.getElementById("editEmail").value = email || "";

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
    const dept = document.getElementById("editDepartment").value.trim();
    const email = document.getElementById("editEmail").value.trim();

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
                department: dept,
                email: email || null,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> Profile updated successfully!';

            // Update row inline
            const nameEl = document.getElementById(`stdNameLabel${id}`);
            const rollEl = document.getElementById(`stdRollLabel${id}`);
            const deptEl = document.getElementById(`stdDeptLabel${id}`);
            const emailEl = document.getElementById(`stdEmailLabel${id}`);

            if (nameEl) nameEl.innerText = name;
            if (rollEl) rollEl.innerText = roll;
            if (deptEl) deptEl.innerText = dept;
            if (emailEl) emailEl.innerText = email || "No email registered";

            setTimeout(() => {
                closeEditModal();
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
            }, 800);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Failed to update student.'}`;
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.';
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
    const secUpload = document.getElementById("retakeUploadSection");
    const secWebcam = document.getElementById("retakeWebcamSection");

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
    const submitBtn = document.getElementById("btnSubmitRetakePhotos");

    for (let i = 0; i < 3; i++) {
        const imgEl = document.getElementById(`retakePrev${i}`);
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

async function submitPhotoUploadRetake() {
    if (retakeFiles.length !== 3 || !retakeStudentId) {
        alert("Please select exactly 3 photos before submitting.");
        return;
    }

    const submitBtn = document.getElementById("btnSubmitRetakePhotos");
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
                window.location.reload();
            }, 1000);
        } else {
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `<span style="color:var(--badge-rose-text); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Photo update failed.'}</span>`;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-rotate"></i> Try Again';
            }
        }
    } catch (err) {
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<span style="color:var(--badge-rose-text); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.</span>';
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-rotate"></i> Try Again';
        }
    }
}

// Guided Webcam Retake
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

