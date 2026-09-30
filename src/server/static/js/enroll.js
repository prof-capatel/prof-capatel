// ==========================================================
// Employee Code Auto-Generation & Refresh
// ==========================================================
function generateRandomEmployeeCode() {
    const prefix = isCorporateTenant ? "EMP" : "STU";
    const num = Math.floor(1000 + Math.random() * 9000);
    return `${prefix}-${num}`;
}

function regenerateEmployeeCode(mode) {
    const code = generateRandomEmployeeCode();
    const input = document.getElementById(mode === "batch" ? "batchRollNumber" : "rollNumber");
    if (input) {
        input.value = code;
    }
}

// ==========================================================
// Cascading Dropdown Handlers
// ==========================================================
function onEnrollDeptChanged(mode) {
    const isBatch = mode === "batch";
    const deptSelect = document.getElementById(isBatch ? "batchEnrollDeptSelect" : "enrollDeptSelect");
    const classSelect = document.getElementById(isBatch ? "batchEnrollClassSelect" : "enrollClassSelect");
    const divSelect = document.getElementById(isBatch ? "batchEnrollDivSelect" : "enrollDivSelect");
    const desigSelect = document.getElementById(isBatch ? "batchEnrollDesignationSelect" : "enrollDesignationSelect");

    const deptId = deptSelect && deptSelect.value ? parseInt(deptSelect.value) : null;

    // Filter Classes
    if (classSelect) {
        const filteredClasses = deptId ? ENROLL_CLASSES.filter(c => c.department_id === deptId) : ENROLL_CLASSES;

        let classHtml = '<option value="">-- Select Class --</option>';
        filteredClasses.forEach(c => {
            classHtml += `<option value="${c.id}" data-dept-id="${c.department_id || ''}" data-name="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`;
        });
        classSelect.innerHTML = classHtml;
    }

    // Reset Division
    if (divSelect) {
        divSelect.innerHTML = '<option value="">-- Select Division (Optional) --</option>';
    }

    // Filter Designations (Mapped to department or unassigned/global)
    if (desigSelect && typeof ENROLL_DESIGNATIONS !== "undefined" && Array.isArray(ENROLL_DESIGNATIONS)) {
        const currentDesigVal = desigSelect.value ? parseInt(desigSelect.value) : null;
        const filteredDesigs = deptId
            ? ENROLL_DESIGNATIONS.filter(d => !d.department_id || d.department_id === deptId)
            : ENROLL_DESIGNATIONS;

        let desigHtml = '<option value="">-- Select Designation (Optional) --</option>';
        let stillValid = false;
        filteredDesigs.forEach(d => {
            const isSel = currentDesigVal && d.id === currentDesigVal;
            if (isSel) stillValid = true;
            const codeStr = d.code ? ` (${escapeHtml(d.code)})` : '';
            desigHtml += `<option value="${d.id}" data-dept-id="${d.department_id || ''}" data-title="${escapeHtml(d.title)}" data-template-id="${d.salary_template_id || ''}" ${isSel ? 'selected' : ''}>${escapeHtml(d.title)}${codeStr}</option>`;
        });
        desigSelect.innerHTML = desigHtml;
        if (!stillValid) {
            desigSelect.value = "";
        }
        onDesignationChanged(mode);
    }
}

function onEnrollClassChanged(mode) {
    const isBatch = mode === "batch";
    const classSelect = document.getElementById(isBatch ? "batchEnrollClassSelect" : "enrollClassSelect");
    const divSelect = document.getElementById(isBatch ? "batchEnrollDivSelect" : "enrollDivSelect");

    const classId = classSelect.value ? parseInt(classSelect.value) : null;

    // Filter Divisions
    const filteredDivs = classId ? ENROLL_DIVISIONS.filter(d => d.class_id === classId) : ENROLL_DIVISIONS;

    let divHtml = '<option value="">-- Select Division (Optional) --</option>';
    filteredDivs.forEach(dv => {
        divHtml += `<option value="${dv.id}" data-class-id="${dv.class_id}" data-name="${escapeHtml(dv.name)}">${escapeHtml(dv.name)}</option>`;
    });
    divSelect.innerHTML = divHtml;
}

function onEnrollRoleChanged(mode) {
    const isBatch = mode === "batch";
    const roleSelect = document.getElementById(isBatch ? "batchUserRole" : "userRole");
    const classSelect = document.getElementById(isBatch ? "batchEnrollClassSelect" : "enrollClassSelect");
    const reqStar = document.getElementById(isBatch ? "batchEnrollClassReqStar" : "enrollClassReqStar");
    const role = roleSelect.value;

    if (role === "student") {
        classSelect.required = true;
        if (reqStar) reqStar.style.display = "inline";
    } else {
        classSelect.required = false;
        if (reqStar) reqStar.style.display = "none";
    }
}

function onDesignationChanged(mode) {
    const isBatch = mode === "batch";
    const desigSelect = document.getElementById(isBatch ? "batchEnrollDesignationSelect" : "enrollDesignationSelect");
    const tplSelect = document.getElementById(isBatch ? "batchEnrollSalaryTemplateSelect" : "enrollSalaryTemplateSelect");
    if (!desigSelect || !tplSelect) return;

    const opt = desigSelect.options[desigSelect.selectedIndex];
    if (opt) {
        const tplId = opt.getAttribute("data-template-id");
        if (tplId) {
            tplSelect.value = tplId;
        }
    }
    updateEnrollRateInputVisibility(mode);
}

function onEnrollTemplateChanged(mode) {
    updateEnrollRateInputVisibility(mode);
}

function updateEnrollRateInputVisibility(mode) {
    const isBatch = mode === "batch";
    const tplSelect = document.getElementById(isBatch ? "batchEnrollSalaryTemplateSelect" : "enrollSalaryTemplateSelect");
    const desigSelect = document.getElementById(isBatch ? "batchEnrollDesignationSelect" : "enrollDesignationSelect");
    
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

    const monthlyGrp = document.getElementById(isBatch ? "batchMonthlySalaryGroup" : "enrollMonthlySalaryGroup");
    const dailyGrp = document.getElementById(isBatch ? "batchDailyRateGroup" : "enrollDailyRateGroup");
    const hourlyGrp = document.getElementById(isBatch ? "batchHourlyRateGroup" : "enrollHourlyRateGroup");

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

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ==========================================================
// Mode Switching (Webcam vs Batch Upload)
// ==========================================================
function switchEnrollMode(mode) {
    const secWebcam = document.getElementById("modeWebcamSection");
    const secBatch = document.getElementById("modeBatchSection");

    if (mode === "webcam") {
        secWebcam.style.display = "grid";
        secBatch.style.display = "none";
    } else {
        secBatch.style.display = "block";
        secWebcam.style.display = "none";
        stopWebcam();
    }
}

// Auto-fill today's date for Date of Joining & Auto-fill Employee Code on Load
document.addEventListener("DOMContentLoaded", () => {
    const todayStr = new Date().toISOString().split('T')[0];
    const doj1 = document.getElementById("dateOfJoining");
    const doj2 = document.getElementById("batchDateOfJoining");
    if (doj1 && !doj1.value) doj1.value = todayStr;
    if (doj2 && !doj2.value) doj2.value = todayStr;

    // Auto-populate employee codes on load if empty
    const rollInput = document.getElementById("rollNumber");
    const batchRollInput = document.getElementById("batchRollNumber");
    if (rollInput && !rollInput.value) {
        rollInput.value = generateRandomEmployeeCode();
    }
    if (batchRollInput && !batchRollInput.value) {
        batchRollInput.value = generateRandomEmployeeCode();
    }

    // Initialize rate visibility
    updateEnrollRateInputVisibility('webcam');
    updateEnrollRateInputVisibility('batch');
});

// ==========================================================
// Webcam Stream & Enrollment Logic (Mobile-Optimized)
// ==========================================================
let currentStudentId = null;
let videoStream = null;
let selectedCameraDeviceId = null;
let currentActiveAngle = "frontal";

async function populateCameraDevices() {
    const selector = document.getElementById("cameraSourceSelect");
    if (!selector || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;

    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === "videoinput");
        
        if (videoDevices.length > 1) {
            selector.style.display = "inline-block";
            selector.innerHTML = "";
            videoDevices.forEach((dev, idx) => {
                const opt = document.createElement("option");
                opt.value = dev.deviceId;
                opt.text = dev.label || `Camera ${idx + 1} (${idx === 0 ? 'Front' : 'Back'})`;
                selector.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn("[*] Camera device enumeration note:", e);
    }
}

async function startWebcam(deviceId = null) {
    if (videoStream) stopWebcam();
    const video = document.getElementById("webcamVideo");
    const feedbackText = document.getElementById("camFeedbackText");
    const troubleshooting = document.getElementById("mobileCamTroubleshooting");
    const nativeBtn = document.getElementById("btnNativeCameraFallback");

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        document.getElementById("camStatusBadge").innerText = "WebRTC Unavailable";
        document.getElementById("camStatusBadge").className = "badge badge-unknown";
        if (feedbackText) feedbackText.innerHTML = `<span style="color:var(--accent-amber);"><i class="fa-solid fa-triangle-exclamation"></i> Live video streaming requires HTTPS or supported mobile browser.</span>`;
        if (troubleshooting) troubleshooting.style.display = "block";
        if (nativeBtn) nativeBtn.style.display = "inline-flex";
        return;
    }

    // Constraint Fallback Ladder (Ideal -> FacingMode -> Unconstrained)
    const constraintLadder = [];
    if (deviceId) {
        constraintLadder.push({ video: { deviceId: { exact: deviceId }, width: { ideal: 640 }, height: { ideal: 480 } } });
        constraintLadder.push({ video: { deviceId: { exact: deviceId } } });
    }
    constraintLadder.push({
        video: {
            facingMode: { ideal: "user" },
            width: { ideal: 640, max: 1280 },
            height: { ideal: 480, max: 720 }
        }
    });
    constraintLadder.push({ video: { facingMode: "user" } });
    constraintLadder.push({ video: true });

    let stream = null;
    let lastError = null;

    for (const constraints of constraintLadder) {
        try {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (stream) break;
        } catch (err) {
            lastError = err;
        }
    }

    if (stream) {
        videoStream = stream;
        video.srcObject = stream;
        video.setAttribute("playsinline", "true");
        video.setAttribute("webkit-playsinline", "true");
        video.muted = true;
        try {
            await video.play();
        } catch (playErr) {
            console.warn("[*] Video play notice:", playErr);
        }

        document.getElementById("camStatusBadge").innerText = "Streaming";
        document.getElementById("camStatusBadge").className = "badge badge-present";
        document.getElementById("btnToggleCam").innerHTML = '<i class="fa-solid fa-stop"></i> Release Camera';
        document.getElementById("btnToggleCam").className = "btn btn-danger";
        if (troubleshooting) troubleshooting.style.display = "none";
        if (nativeBtn) nativeBtn.style.display = "none";
        if (feedbackText) feedbackText.innerHTML = `<span style="color:var(--badge-emerald-text);"><i class="fa-solid fa-camera"></i> Camera active. Align face inside frame.</span>`;
        await populateCameraDevices();
    } else {
        document.getElementById("camStatusBadge").innerText = "Access Denied / Busy";
        document.getElementById("camStatusBadge").className = "badge badge-unknown";
        if (feedbackText) feedbackText.innerHTML = `<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Camera unavailable: ${lastError ? (lastError.message || lastError.name) : 'Permission denied'}.</span>`;
        if (troubleshooting) troubleshooting.style.display = "block";
        if (nativeBtn) nativeBtn.style.display = "inline-flex";
    }
}

function onCameraSourceChanged(deviceId) {
    selectedCameraDeviceId = deviceId;
    startWebcam(deviceId);
}

function stopWebcam() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
        const video = document.getElementById("webcamVideo");
        if (video) video.srcObject = null;
        
        const badge = document.getElementById("camStatusBadge");
        if (badge) {
            badge.innerText = "Camera Released";
            badge.className = "badge badge-node";
        }
        const btn = document.getElementById("btnToggleCam");
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-video"></i> Start Camera';
            btn.className = "btn btn-secondary";
        }
    }
}

function toggleWebcam() {
    if (videoStream) stopWebcam();
    else startWebcam(selectedCameraDeviceId);
}

// Mobile Native Shutter Fallback
function triggerNativeMobileCapture() {
    if (!currentStudentId) {
        alert("Please register the member profile first.");
        return;
    }
    const input = document.getElementById("mobileNativeCaptureInput");
    if (input) input.click();
}

async function handleNativeCapturedFile(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    await uploadSampleBlob(file, currentActiveAngle);
    input.value = "";
}

window.addEventListener("beforeunload", stopWebcam);
window.addEventListener("pagehide", stopWebcam);

document.getElementById("enrollStudentForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const rollNumber = document.getElementById("rollNumber").value.trim();
    const name = document.getElementById("studentName").value.trim();
    const userRole = document.getElementById("userRole").value.trim();
    
    const deptSelect = document.getElementById("enrollDeptSelect");
    const deptId = deptSelect.value ? parseInt(deptSelect.value) : null;
    const deptOption = deptSelect.options[deptSelect.selectedIndex];
    const deptName = deptOption ? (deptOption.dataset.name || deptOption.text) : "Computer Science";

    const classSelect = document.getElementById("enrollClassSelect");
    const classId = classSelect ? (classSelect.value ? parseInt(classSelect.value) : null) : null;
    const classOption = classSelect ? classSelect.options[classSelect.selectedIndex] : null;
    const className = classOption ? (classOption.dataset.name || classOption.text) : "";

    const divSelect = document.getElementById("enrollDivSelect");
    const divId = divSelect ? (divSelect.value ? parseInt(divSelect.value) : null) : null;

    const email = document.getElementById("email").value.trim();
    const dateOfJoining = document.getElementById("dateOfJoining")?.value || null;
    const shiftSelect = document.getElementById("enrollShiftSelect");
    const shiftId = shiftSelect && shiftSelect.value ? parseInt(shiftSelect.value) : null;

    const locSelect = document.getElementById("enrollLocationSelect");
    const locId = locSelect && locSelect.value ? parseInt(locSelect.value) : null;

    const desigSelect = document.getElementById("enrollDesignationSelect");
    const desigId = desigSelect && desigSelect.value ? parseInt(desigSelect.value) : null;
    const desigOption = desigSelect && desigSelect.selectedIndex >= 0 ? desigSelect.options[desigSelect.selectedIndex] : null;
    const desigTitle = desigOption ? (desigOption.dataset.title || desigOption.text) : null;

    const tplSelect = document.getElementById("enrollSalaryTemplateSelect");
    const tplId = tplSelect && tplSelect.value ? parseInt(tplSelect.value) : null;
    const monthlySalary = parseFloat(document.getElementById("enrollMonthlySalary")?.value) || null;
    const dailyRate = parseFloat(document.getElementById("enrollDailyRate")?.value) || null;
    const hourlyRate = parseFloat(document.getElementById("enrollHourlyRate")?.value) || null;

    if (userRole === "student" && !classId) {
        alert("Please select a valid Class/Semester for the student.");
        return;
    }

    try {
        const res = await fetch("/api/v1/enroll/student", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                roll_number: rollNumber,
                name: name,
                department_id: deptId,
                department: deptName,
                class_id: classId,
                class_semester: className || "General",
                division_id: divId,
                email: email || null,
                user_role: userRole,
                shift_id: shiftId,
                date_of_joining: dateOfJoining || null,
                location_id: locId,
                designation_id: desigId,
                designation: desigTitle,
                salary_template_id: tplId,
                monthly_base_salary: monthlySalary,
                daily_rate: dailyRate,
                hourly_rate: hourlyRate,
            })
        });
        const data = await res.json();

        if (res.ok) {
            currentStudentId = data.student.id;
            document.getElementById("btnRegisterProfile").disabled = true;
            document.getElementById("btnRegisterProfile").innerHTML = '<i class="fa-solid fa-check"></i> Profile Registered';
            document.getElementById("enrollProgressSection").style.display = "block";
            document.getElementById("camFeedbackText").innerHTML = `<span style="color:var(--badge-emerald-text); font-weight:600;"><i class="fa-solid fa-check"></i> Registered ${name}. Initializing camera...</span>`;
            if (typeof showFloatingToast === "function") {
                showFloatingToast(`Employee '${name}' registered successfully! Starting face capture...`, "success");
            }
            await startWebcam(selectedCameraDeviceId);
        } else {
            alert(`Error: ${data.detail || 'Could not register student.'}`);
        }
    } catch (err) {
        alert("Failed to connect to server.");
    }
});

async function captureSample(angle) {
    if (!currentStudentId) {
        alert("Please register the member profile first.");
        return;
    }
    currentActiveAngle = angle;

    if (!videoStream) {
        await startWebcam(selectedCameraDeviceId);
        await new Promise(r => setTimeout(r, 400));
    }

    const video = document.getElementById("webcamVideo");
    if (!videoStream || video.videoWidth === 0) {
        triggerNativeMobileCapture();
        return;
    }

    const canvas = document.getElementById("captureCanvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(async (blob) => {
        if (blob) {
            await uploadSampleBlob(blob, angle);
        }
    }, "image/jpeg", 0.92);
}

async function uploadSampleBlob(blobOrFile, angle) {
    const formData = new FormData();
    formData.append("student_id", currentStudentId);
    formData.append("sample_angle", angle);
    formData.append("image", blobOrFile, `sample_${angle}.jpg`);

    const feedbackEl = document.getElementById("camFeedbackText");
    feedbackEl.innerHTML = `<span style="color:var(--accent-primary); font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Extracting face embedding for ${angle} pose...</span>`;

    try {
        const res = await fetch("/api/v1/enroll/capture-sample", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            feedbackEl.innerHTML = `<span style="color:var(--badge-emerald-text); font-weight:600;"><i class="fa-solid fa-check"></i> ${data.message}</span>`;
            if (angle === 'frontal') {
                document.getElementById("btnCapFrontal").disabled = true;
                document.getElementById("btnCapFrontal").className = "btn btn-primary";
                document.getElementById("btnCapFrontal").innerText = "✓ Done";
                document.getElementById("btnCapLeft").disabled = false;
                currentActiveAngle = "left";
            } else if (angle === 'left') {
                document.getElementById("btnCapLeft").disabled = true;
                document.getElementById("btnCapLeft").className = "btn btn-primary";
                document.getElementById("btnCapLeft").innerText = "✓ Done";
                document.getElementById("btnCapRight").disabled = false;
                currentActiveAngle = "right";
            } else if (angle === 'right') {
                document.getElementById("btnCapRight").disabled = true;
                document.getElementById("btnCapRight").className = "btn btn-primary";
                document.getElementById("btnCapRight").innerText = "✓ Done";
                document.getElementById("enrollmentCompleteBox").style.display = "block";
                stopWebcam();
                feedbackEl.innerHTML = `<span style="color:var(--badge-emerald-text); font-weight:600;"><i class="fa-solid fa-circle-check"></i> Enrollment finished! Camera released.</span>`;
                if (typeof showFloatingToast === "function") {
                    showFloatingToast(`Face capture completed successfully for '${document.getElementById("studentName")?.value || "employee"}'!`, "success");
                }
            }
        } else {
            feedbackEl.innerHTML = `<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> ${data.detail}</span>`;
        }
    } catch (err) {
        feedbackEl.innerHTML = `<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Upload failed. Try again.</span>`;
    }
}

// ==========================================================
// Batch 3-Photo File Upload Logic
// ==========================================================
let batchFiles = [];

const fileInput = document.getElementById("fileInputBatch");
const dropzone = document.getElementById("dropzone");

dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    handleSelectedFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", (e) => {
    handleSelectedFiles(e.target.files);
});

function handleSelectedFiles(filesList) {
    const newFiles = Array.from(filesList).filter(f => f.type.startsWith("image/"));
    for (const f of newFiles) {
        if (batchFiles.length < 3) {
            batchFiles.push(f);
        }
    }
    updateBatchPreviews();
}

function updateBatchPreviews() {
    const badge = document.getElementById("photoCountBadge");
    const hint = document.getElementById("batchValidationHint");
    const submitBtn = document.getElementById("btnSubmitBatch");
    const clearBtn = document.getElementById("btnClearFiles");

    badge.innerText = `${batchFiles.length} / 3 Selected`;
    badge.className = batchFiles.length === 3 ? "badge badge-present" : "badge badge-node";

    for (let i = 0; i < 3; i++) {
        const imgEl = document.getElementById(`prevImg${i}`);
        const phEl = document.getElementById(`prevPlaceholder${i}`);

        if (batchFiles[i]) {
            const url = URL.createObjectURL(batchFiles[i]);
            imgEl.src = url;
            imgEl.style.display = "block";
            phEl.style.display = "none";
        } else {
            imgEl.src = "";
            imgEl.style.display = "none";
            phEl.style.display = "flex";
        }
    }

    if (batchFiles.length === 3) {
        hint.innerHTML = '<span style="color:var(--badge-emerald-text); font-weight:700;"><i class="fa-solid fa-circle-check"></i> Exactly 3 photos selected. Ready for upload!</span>';
        submitBtn.disabled = false;
        clearBtn.style.display = "inline-flex";
    } else {
        hint.innerHTML = `<span style="color:var(--accent-amber); font-weight:600;"><i class="fa-solid fa-circle-exclamation"></i> Please select exactly 3 photos (${3 - batchFiles.length} more needed).</span>`;
        submitBtn.disabled = true;
        clearBtn.style.display = batchFiles.length > 0 ? "inline-flex" : "none";
    }
}

function clearBatchFiles() {
    batchFiles = [];
    fileInput.value = "";
    updateBatchPreviews();
    const alertBox = document.getElementById("batchResultAlert");
    alertBox.style.display = "none";
}

// Submit Batch Form
document.getElementById("batchUploadForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    if (batchFiles.length !== 3) {
        alert("Please select exactly 3 photos before submitting.");
        return;
    }

    const rollNumber = document.getElementById("batchRollNumber").value.trim();
    const name = document.getElementById("batchStudentName").value.trim();
    const userRole = document.getElementById("batchUserRole").value.trim();
    
    const deptSelect = document.getElementById("batchEnrollDeptSelect");
    const deptId = deptSelect.value ? parseInt(deptSelect.value) : null;
    const deptOption = deptSelect.options[deptSelect.selectedIndex];
    const deptName = deptOption ? (deptOption.dataset.name || deptOption.text) : "Computer Science";

    const classSelect = document.getElementById("batchEnrollClassSelect");
    const classId = classSelect.value ? parseInt(classSelect.value) : null;
    const classOption = classSelect.options[classSelect.selectedIndex];
    const className = classOption ? (classOption.dataset.name || classOption.text) : "";

    const divSelect = document.getElementById("batchEnrollDivSelect");
    const divId = divSelect.value ? parseInt(divSelect.value) : null;

    const email = document.getElementById("batchEmail").value.trim();
    const batchDoj = document.getElementById("batchDateOfJoining")?.value || null;

    if (userRole === "student" && !classId) {
        alert("Please select a valid Class/Semester for the student.");
        return;
    }

    const submitBtn = document.getElementById("btnSubmitBatch");
    const alertBox = document.getElementById("batchResultAlert");

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extracting Vectors & Enrolling...';

    alertBox.style.display = "block";
    alertBox.style.background = "var(--badge-indigo-bg)";
    alertBox.style.border = "1px solid var(--badge-indigo-border)";
    alertBox.innerHTML = '<span style="color:var(--accent-primary); font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Processing 3 images with CPU face recognition engine...</span>';

    const formData = new FormData();
    formData.append("roll_number", rollNumber);
    formData.append("name", name);
    formData.append("user_role", userRole);
    if (deptId) formData.append("department_id", deptId);
    if (deptName) formData.append("department", deptName);
    if (classId) formData.append("class_id", classId);
    if (className) formData.append("class_semester", className);
    if (divId) formData.append("division_id", divId);
    if (email) formData.append("email", email);
    if (batchDoj) formData.append("date_of_joining", batchDoj);
    const batchShiftSelect = document.getElementById("batchEnrollShiftSelect");
    if (batchShiftSelect && batchShiftSelect.value) {
        formData.append("shift_id", batchShiftSelect.value);
    }
    const batchLocSelect = document.getElementById("batchEnrollLocationSelect");
    if (batchLocSelect && batchLocSelect.value) {
        formData.append("location_id", batchLocSelect.value);
    }

    const batchDesigSelect = document.getElementById("batchEnrollDesignationSelect");
    if (batchDesigSelect && batchDesigSelect.value) {
        formData.append("designation_id", batchDesigSelect.value);
        const opt = batchDesigSelect.options[batchDesigSelect.selectedIndex];
        if (opt) {
            formData.append("designation", opt.dataset.title || opt.text);
        }
    }
    const batchTplSelect = document.getElementById("batchEnrollSalaryTemplateSelect");
    if (batchTplSelect && batchTplSelect.value) {
        formData.append("salary_template_id", batchTplSelect.value);
    }
    const batchMonthly = document.getElementById("batchMonthlySalary")?.value;
    if (batchMonthly) {
        formData.append("monthly_base_salary", batchMonthly);
    }
    const batchDaily = document.getElementById("batchDailyRate")?.value;
    if (batchDaily) {
        formData.append("daily_rate", batchDaily);
    }
    const batchHourly = document.getElementById("batchHourlyRate")?.value;
    if (batchHourly) {
        formData.append("hourly_rate", batchHourly);
    }

    // Send exactly 3 distinct named files for API compatibility
    formData.append("photo_front", batchFiles[0]);
    formData.append("photo_left", batchFiles[1]);
    formData.append("photo_right", batchFiles[2]);

    try {
        const res = await fetch("/api/v1/enroll/batch-upload", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            batchFiles = [];
            renderBatchPreviews();
            submitBtn.disabled = true;
            document.getElementById("batchRollNumber").value = generateRandomEmployeeCode();
            document.getElementById("batchStudentName").value = "";
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <i class="fa-solid fa-circle-check" style="color: var(--accent-emerald); font-size: 22px;"></i>
                    <strong style="color: var(--badge-emerald-text); font-size: 14px;">${data.message}</strong>
                </div>
                <div style="font-size: 12.5px; color: var(--text-secondary); margin-bottom: 12px;">
                    Profile <strong>${data.student.name}</strong> (${data.student.roll_number}) enrolled with 3 vectors cached in RAM.
                </div>
                <a href="${isCorporateTenant ? '/employees' : '/students'}" class="btn btn-primary" style="padding: 7px 16px; font-size: 12.5px;">
                    <i class="fa-solid fa-users"></i> View in Directory
                </a>
            `;
            submitBtn.innerHTML = '<i class="fa-solid fa-check"></i> Enrolled Successfully';
            if (typeof showFloatingToast === "function") {
                showFloatingToast(`Employee '${data.student.name}' registered & face embeddings generated successfully!`, "success");
            }
        } else {
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-rose); font-size: 20px;"></i>
                    <strong style="color: var(--badge-rose-text); font-size: 13px;">${data.detail || 'Enrollment failed.'}</strong>
                </div>
            `;
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Try Again';
        }
    } catch (err) {
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<span style="color:var(--accent-rose); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to backend server.</span>';
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-upload"></i> Try Again';
    }
});

function copyEnrollOnboardLink(btn) {
    const span = document.getElementById("enrollSelfOnboardUrl");
    if (!span) return;
    const fullUrl = window.location.origin + span.innerText.trim();
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullUrl).then(() => {
            showEnrollCopyFeedback(btn);
        }).catch(() => {
            fallbackEnrollCopy(fullUrl, btn);
        });
    } else {
        fallbackEnrollCopy(fullUrl, btn);
    }
}

function showEnrollCopyFeedback(btn) {
    if (!btn) return;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-check" style="color: var(--accent-emerald);"></i> <span style="color: var(--accent-emerald);">Copied!</span>';
    setTimeout(() => {
        btn.innerHTML = origHtml;
    }, 2000);
}

function fallbackEnrollCopy(text, btn) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand("copy");
        showEnrollCopyFeedback(btn);
    } catch (e) {
        prompt("Copy URL to clipboard:", text);
    }
    document.body.removeChild(ta);
}

// Visibility-Aware Camera Lifecycle Management
let wasWebcamActiveBeforeHidden = false;

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        if (videoStream) {
            wasWebcamActiveBeforeHidden = true;
            stopWebcam();
        }
    } else {
        if (wasWebcamActiveBeforeHidden) {
            wasWebcamActiveBeforeHidden = false;
            startWebcam(selectedCameraDeviceId);
        }
    }
});

window.addEventListener("blur", () => {
    if (videoStream) {
        wasWebcamActiveBeforeHidden = true;
        stopWebcam();
    }
});

window.addEventListener("focus", () => {
    if (!document.hidden && wasWebcamActiveBeforeHidden) {
        wasWebcamActiveBeforeHidden = false;
        startWebcam(selectedCameraDeviceId);
    }
});

window.addEventListener("pagehide", () => {
    stopWebcam();
});

window.addEventListener("beforeunload", () => {
    stopWebcam();
});
