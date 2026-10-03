/**
 * Curiosity HUB - Institutional & Corporate Employee Directory Controller
 * Complete Action Handlers: Edit, Transfer, Retake, Relieve, Reinstate, Delete, Override & Filters
 */

// Global State
let currentRetakeStream = null;
let currentEmployeeStatusFilter = "active";
let retakeCapturedBlobs = { frontal: null, left: null, right: null };
let retakeUploadedFiles = [];

// ==============================================================================
// 1. Directory Filtering & Search System
// ==============================================================================

function setEmployeeStatusFilter(status) {
    currentEmployeeStatusFilter = status;
    const btnActive = document.getElementById("pillStatusActive");
    const btnRelieved = document.getElementById("pillStatusRelieved");
    const btnAll = document.getElementById("pillStatusAll");

    if (btnActive) btnActive.classList.toggle("active", status === "active");
    if (btnRelieved) btnRelieved.classList.toggle("active", status === "relieved");
    if (btnAll) btnAll.classList.toggle("active", status === "all");

    applyDirectoryFilters();
}

function applyDirectoryFilters() {
    const searchVal = (document.getElementById("dirSearchInput")?.value || "").trim().toLowerCase();
    const deptIdVal = document.getElementById("dirDeptFilter")?.value || "";
    const shiftIdVal = document.getElementById("dirShiftFilter")?.value || "";
    const classIdVal = document.getElementById("dirClassFilter")?.value || "";
    const divIdVal = document.getElementById("dirDivFilter")?.value || "";
    const desigIdVal = document.getElementById("dirDesigFilter")?.value || "";
    const roleVal = document.getElementById("dirRoleFilter")?.value || "";

    const rows = document.querySelectorAll(".student-row");
    let visibleCount = 0;
    let totalCount = rows.length;

    rows.forEach(row => {
        const name = row.getAttribute("data-name") || "";
        const roll = row.getAttribute("data-roll") || "";
        const rowDeptId = row.getAttribute("data-dept-id") || "";
        const rowDesigId = row.getAttribute("data-desig-id") || "";
        const rowClassId = row.getAttribute("data-class-id") || "";
        const rowDivId = row.getAttribute("data-div-id") || "";
        const rowShiftId = row.getAttribute("data-shift-id") || "";
        const rowRole = row.getAttribute("data-role") || "student";
        const rowStatus = row.getAttribute("data-status") || "active";

        const matchSearch = !searchVal || name.includes(searchVal) || roll.includes(searchVal);
        const matchDept = !deptIdVal || rowDeptId === deptIdVal;
        const matchShift = !shiftIdVal || rowShiftId === shiftIdVal;
        const matchClass = !classIdVal || rowClassId === classIdVal;
        const matchDiv = !divIdVal || rowDivId === divIdVal;
        const matchDesig = !desigIdVal || rowDesigId === desigIdVal;
        const matchRole = !roleVal || rowRole === roleVal;
        const matchStatus = (currentEmployeeStatusFilter === "all") || (rowStatus === currentEmployeeStatusFilter);

        if (matchSearch && matchDept && matchShift && matchClass && matchDiv && matchDesig && matchRole && matchStatus) {
            row.style.display = "";
            visibleCount++;
        } else {
            row.style.display = "none";
        }
    });

    const countLabel = document.getElementById("dirFilterCountLabel");
    if (countLabel) {
        countLabel.textContent = `Showing ${visibleCount} of ${totalCount} profiles`;
    }

    const emptyRow = document.getElementById("emptyDirectoryRow");
    if (emptyRow) {
        emptyRow.style.display = (visibleCount === 0 && totalCount > 0) ? "" : "none";
    }
}

function resetDirectoryFilters() {
    const searchInp = document.getElementById("dirSearchInput");
    if (searchInp) searchInp.value = "";

    const deptSelect = document.getElementById("dirDeptFilter");
    if (deptSelect) deptSelect.value = "";

    const shiftSelect = document.getElementById("dirShiftFilter");
    if (shiftSelect) shiftSelect.value = "";

    const classSelect = document.getElementById("dirClassFilter");
    if (classSelect) classSelect.value = "";

    const divSelect = document.getElementById("dirDivFilter");
    if (divSelect) divSelect.value = "";

    const desigSelect = document.getElementById("dirDesigFilter");
    if (desigSelect) desigSelect.value = "";

    const roleSelect = document.getElementById("dirRoleFilter");
    if (roleSelect) roleSelect.value = "";

    onDirDeptFilterChanged();
    setEmployeeStatusFilter("active");
}

function onDirDeptFilterChanged() {
    const deptId = document.getElementById("dirDeptFilter")?.value;
    
    // Educational: Class cascading
    const classSelect = document.getElementById("dirClassFilter");
    if (classSelect) {
        Array.from(classSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.style.display = (!deptId || !dId || dId === deptId) ? "" : "none";
        });
        if (deptId && classSelect.selectedOptions[0]?.style.display === "none") {
            classSelect.value = "";
        }
    }

    // Corporate: Designation cascading
    const desigSelect = document.getElementById("dirDesigFilter");
    if (desigSelect) {
        Array.from(desigSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.style.display = (!deptId || !dId || dId === deptId) ? "" : "none";
        });
        if (deptId && desigSelect.selectedOptions[0]?.style.display === "none") {
            desigSelect.value = "";
        }
    }

    applyDirectoryFilters();
}

function onDirClassFilterChanged() {
    const classId = document.getElementById("dirClassFilter")?.value;
    const divSelect = document.getElementById("dirDivFilter");
    if (divSelect) {
        Array.from(divSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const cId = opt.getAttribute("data-class-id");
            opt.style.display = (!classId || !cId || cId === classId) ? "" : "none";
        });
        if (classId && divSelect.selectedOptions[0]?.style.display === "none") {
            divSelect.value = "";
        }
    }
    applyDirectoryFilters();
}

// ==============================================================================
// 2. Edit Profile Modal
// ==============================================================================

function getStudentData(id) {
    if (window.allTenantStudents && Array.isArray(window.allTenantStudents)) {
        const found = window.allTenantStudents.find(s => Number(s.id) === Number(id));
        if (found) return found;
    }
    return null;
}

function triggerRetakeFromEdit() {
    const studentId = document.getElementById("editStudentId")?.value;
    if (!studentId) return;
    closeEditModal();
    openRetakeModal(studentId);
}

function openEditModal(studentId) {
    const modal = document.getElementById("editStudentModal");
    if (!modal) return;

    const student = getStudentData(studentId);
    
    document.getElementById("editStudentId").value = studentId;
    
    const nameInput = document.getElementById("editStudentName");
    if (nameInput) nameInput.value = student ? student.name : "";

    const rollInput = document.getElementById("editRollNumber");
    if (rollInput) rollInput.value = student ? student.roll_number : "";

    const emailInput = document.getElementById("editEmail");
    if (emailInput) emailInput.value = (student && student.email) ? student.email : "";

    const dojInput = document.getElementById("editDateOfJoining");
    if (dojInput) dojInput.value = (student && student.date_of_joining) ? student.date_of_joining.slice(0, 10) : "";

    const roleSelect = document.getElementById("editUserRole");
    if (roleSelect && student) {
        roleSelect.value = student.user_role || (window.IS_CORPORATE ? "employee" : "student");
    }

    const deptSelect = document.getElementById("editDepartmentSelect");
    if (deptSelect && student) {
        deptSelect.value = student.department_id || "";
        onEditDeptSelectChanged(false); // don't reset designation on initial open
    }

    const classSelect = document.getElementById("editClassSelect");
    if (classSelect && student) {
        classSelect.value = student.class_id || "";
        onEditClassSelectChanged();
    }

    const divSelect = document.getElementById("editDivisionSelect");
    if (divSelect && student) {
        divSelect.value = student.division_id || "";
    }

    const locSelect = document.getElementById("editLocationSelect");
    if (locSelect && student) {
        locSelect.value = student.location_id || "";
    }

    const desigSelect = document.getElementById("editDesignationSelect");
    if (desigSelect && student) {
        desigSelect.value = student.designation_id || "";
    }

    const shiftSelect = document.getElementById("editShiftSelect");
    if (shiftSelect && student) {
        shiftSelect.value = student.shift_id || "";
    }

    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    if (tplSelect && student) {
        if (student.salary_template_id) {
            tplSelect.value = student.salary_template_id;
            onEditSalaryTemplateChanged();
        } else if (student.designation_id) {
            // Synchronize template from designation metadata
            onEditDesignationChanged();
        } else if (student.daily_rate && !student.monthly_base_salary) {
            const dailyOpt = Array.from(tplSelect.options).find(o => o.getAttribute("data-model") === "DAILY_WAGE");
            if (dailyOpt) tplSelect.value = dailyOpt.value;
            onEditSalaryTemplateChanged();
        } else if (student.hourly_rate && !student.monthly_base_salary) {
            const hourlyOpt = Array.from(tplSelect.options).find(o => o.getAttribute("data-model") === "HOURLY");
            if (hourlyOpt) tplSelect.value = hourlyOpt.value;
            onEditSalaryTemplateChanged();
        } else {
            onEditSalaryTemplateChanged();
        }
    } else {
        onEditSalaryTemplateChanged();
    }

    const baseSalaryInput = document.getElementById("editMonthlyBaseSalary");
    if (baseSalaryInput && student) {
        baseSalaryInput.value = student.monthly_base_salary != null ? student.monthly_base_salary : "";
    }

    const dailyRateInput = document.getElementById("editDailyRate");
    if (dailyRateInput && student) {
        dailyRateInput.value = student.daily_rate != null ? student.daily_rate : "";
    }

    const hourlyRateInput = document.getElementById("editHourlyRate");
    if (hourlyRateInput && student) {
        hourlyRateInput.value = student.hourly_rate != null ? student.hourly_rate : "";
    }

    // Render Enrolled Photo Thumbnails in Edit Modal
    const photosContainer = document.getElementById("editStudentPhotosPreview");
    const countBadge = document.getElementById("editPhotosCountBadge");
    if (photosContainer && student) {
        photosContainer.innerHTML = "";
        if (student.photos && student.photos.length > 0) {
            if (countBadge) countBadge.textContent = `${student.photos.length} Photos`;
            student.photos.forEach(p => {
                const item = document.createElement("div");
                item.className = "photo-preview-card";
                item.innerHTML = `
                    <img src="${p.url}" class="photo-preview-img" style="aspect-ratio: 1/1; object-fit: cover; cursor: pointer;" onclick="openLightbox('${p.url}', '${student.name} (${p.angle})')">
                    <div class="photo-preview-label">${p.angle ? p.angle.toUpperCase() : 'SAMPLE'}</div>
                `;
                photosContainer.appendChild(item);
            });
        } else {
            if (countBadge) countBadge.textContent = "0 Photos";
            photosContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 10px;">No enrolled sample photos found.</div>`;
        }
    }

    const alertBox = document.getElementById("editResultAlert");
    if (alertBox) alertBox.style.display = "none";

    const saveBtn = document.getElementById("btnSaveEdit");
    if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
    }

    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeEditModal() {
    const modal = document.getElementById("editStudentModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

function onEditDeptSelectChanged(shouldResetDesig = true) {
    const deptId = document.getElementById("editDepartmentSelect")?.value;
    
    // Educational: Class options
    const classSelect = document.getElementById("editClassSelect");
    if (classSelect) {
        Array.from(classSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.style.display = (!deptId || !dId || dId === deptId) ? "" : "none";
        });
        if (deptId && classSelect.selectedOptions[0]?.style.display === "none") {
            classSelect.value = "";
            onEditClassSelectChanged();
        }
    }

    // Corporate: Designation options
    const desigSelect = document.getElementById("editDesignationSelect");
    if (desigSelect) {
        let isCurrentDesigValid = false;
        Array.from(desigSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            const visible = (!deptId || !dId || dId === deptId);
            opt.style.display = visible ? "" : "none";
            if (visible && opt.value === desigSelect.value) {
                isCurrentDesigValid = true;
            }
        });
        if (shouldResetDesig && desigSelect.value && !isCurrentDesigValid) {
            desigSelect.value = "";
            onEditDesignationChanged();
        }
    }
}

function onEditClassSelectChanged() {
    const classId = document.getElementById("editClassSelect")?.value;
    const divSelect = document.getElementById("editDivisionSelect");
    if (divSelect) {
        Array.from(divSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const cId = opt.getAttribute("data-class-id");
            opt.style.display = (!classId || !cId || cId === classId) ? "" : "none";
        });
    }
}

function onEditDesignationChanged() {
    const desigSelect = document.getElementById("editDesignationSelect");
    if (!desigSelect) return;
    const selectedOption = desigSelect.options[desigSelect.selectedIndex];
    const tplId = selectedOption?.getAttribute("data-template-id");
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    if (tplSelect) {
        if (tplId) {
            tplSelect.value = tplId;
        } else if (!desigSelect.value) {
            tplSelect.value = "";
        }
        onEditSalaryTemplateChanged();
    }
}

function onEditSalaryTemplateChanged() {
    const tplSelect = document.getElementById("editSalaryTemplateSelect");
    const monthlyGroup = document.getElementById("editMonthlySalaryGroup");
    const dailyGroup = document.getElementById("editDailyRateGroup");
    const hourlyGroup = document.getElementById("editHourlyRateGroup");
    
    const monthlyLabel = document.getElementById("editMonthlySalaryLabel");
    const monthlyHelp = document.getElementById("editMonthlySalaryHelp");
    const monthlyInput = document.getElementById("editMonthlyBaseSalary");
    
    const dailyLabel = document.getElementById("editDailyRateLabel");
    const dailyHelp = document.getElementById("editDailyRateHelp");
    
    const hourlyLabel = document.getElementById("editHourlyRateLabel");
    const hourlyHelp = document.getElementById("editHourlyRateHelp");
    
    if (!tplSelect) return;
    const selectedOption = tplSelect.options[tplSelect.selectedIndex];
    const compModel = selectedOption?.getAttribute("data-model") || "STRUCTURED_SALARY";

    if (compModel === "MONTHLY_FIXED") {
        if (monthlyGroup) monthlyGroup.style.display = "";
        if (dailyGroup) dailyGroup.style.display = "none";
        if (hourlyGroup) hourlyGroup.style.display = "none";
        if (monthlyLabel) monthlyLabel.textContent = "Monthly Fixed Salary (₹) *";
        if (monthlyHelp) monthlyHelp.textContent = "All-inclusive fixed monthly compensation without separate HRA/DA components.";
        if (monthlyInput) monthlyInput.placeholder = "e.g. 40000";
    } else if (compModel === "STIPEND") {
        if (monthlyGroup) monthlyGroup.style.display = "";
        if (dailyGroup) dailyGroup.style.display = "none";
        if (hourlyGroup) hourlyGroup.style.display = "none";
        if (monthlyLabel) monthlyLabel.textContent = "Monthly Fixed Stipend (₹) *";
        if (monthlyHelp) monthlyHelp.textContent = "Fixed monthly stipend for intern or trainee profile.";
        if (monthlyInput) monthlyInput.placeholder = "e.g. 15000";
    } else if (compModel === "DAILY_WAGE") {
        if (monthlyGroup) monthlyGroup.style.display = "none";
        if (dailyGroup) dailyGroup.style.display = "";
        if (hourlyGroup) hourlyGroup.style.display = "none";
        if (dailyLabel) dailyLabel.textContent = "Daily Salary Rate (₹/day) *";
        if (dailyHelp) dailyHelp.textContent = "Daily salary wage rate applied per present day and paid leave.";
    } else if (compModel === "HOURLY") {
        if (monthlyGroup) monthlyGroup.style.display = "none";
        if (dailyGroup) dailyGroup.style.display = "none";
        if (hourlyGroup) hourlyGroup.style.display = "";
        if (hourlyLabel) hourlyLabel.textContent = "Hourly Salary Rate (₹/hr) *";
        if (hourlyHelp) hourlyHelp.textContent = "Hourly rate applied to tracked billed working hours.";
    } else { // STRUCTURED_SALARY (default)
        if (monthlyGroup) monthlyGroup.style.display = "";
        if (dailyGroup) dailyGroup.style.display = "none";
        if (hourlyGroup) hourlyGroup.style.display = "none";
        if (monthlyLabel) monthlyLabel.textContent = "Monthly Basic Salary (₹) *";
        if (monthlyHelp) monthlyHelp.textContent = "Base compensation; components (HRA, DA, etc.) calculate automatically based on designation template.";
        if (monthlyInput) monthlyInput.placeholder = "e.g. 35000";
    }
}

async function submitStudentEdit(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const studentId = document.getElementById("editStudentId")?.value;
    if (!studentId) return;

    const name = document.getElementById("editStudentName")?.value.trim();
    const roll = document.getElementById("editRollNumber")?.value.trim();
    const deptId = document.getElementById("editDepartmentSelect")?.value;
    const email = document.getElementById("editEmail")?.value.trim();
    const doj = document.getElementById("editDateOfJoining")?.value;
    const role = document.getElementById("editUserRole")?.value;
    const classId = document.getElementById("editClassSelect")?.value;
    const divId = document.getElementById("editDivisionSelect")?.value;
    const locId = document.getElementById("editLocationSelect")?.value;
    const desigId = document.getElementById("editDesignationSelect")?.value;
    const shiftId = document.getElementById("editShiftSelect")?.value;
    const tplId = document.getElementById("editSalaryTemplateSelect")?.value;

    const monthlySalary = document.getElementById("editMonthlyBaseSalary")?.value;
    const dailyRate = document.getElementById("editDailyRate")?.value;
    const hourlyRate = document.getElementById("editHourlyRate")?.value;

    const saveBtn = document.getElementById("btnSaveEdit");
    const alertBox = document.getElementById("editResultAlert");

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    }

    const payload = {
        name: name,
        roll_number: roll,
        department_id: deptId ? parseInt(deptId) : null,
        email: email || null,
        date_of_joining: doj || null,
        user_role: role || (window.IS_CORPORATE ? "employee" : "student"),
        class_id: classId ? parseInt(classId) : null,
        division_id: divId ? parseInt(divId) : null,
        location_id: locId ? parseInt(locId) : null,
        designation_id: desigId ? parseInt(desigId) : null,
        shift_id: shiftId ? parseInt(shiftId) : null,
        salary_template_id: tplId ? parseInt(tplId) : null,
        monthly_base_salary: monthlySalary ? parseFloat(monthlySalary) : null,
        daily_rate: dailyRate ? parseFloat(dailyRate) : null,
        hourly_rate: hourlyRate ? parseFloat(hourlyRate) : null,
    };

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                alertBox.style.color = "var(--badge-emerald-text, #059669)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Profile updated successfully!");
            }
            setTimeout(() => {
                closeEditModal();
                window.location.reload();
            }, 600);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
                alertBox.style.color = "var(--badge-rose-text, #dc2626)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Update failed.");
            }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
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
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
        }
    }
}

// ==============================================================================
// 3. Department / Team Transfer Modal
// ==============================================================================

function openTransferDepartmentModal(studentId) {
    const modal = document.getElementById("transferEmployeeModal");
    if (!modal) return;

    const student = getStudentData(studentId);
    document.getElementById("transferStudentId").value = studentId;
    
    const nameInput = document.getElementById("transferStudentName");
    if (nameInput) {
        nameInput.value = student ? `${student.name} (${student.roll_number})` : `#${studentId}`;
    }

    const deptSelect = document.getElementById("transferTargetDept");
    if (deptSelect && student) {
        deptSelect.value = student.department_id || "";
        onTransferDeptChanged();
    }

    const desigSelect = document.getElementById("transferTargetDesignation");
    if (desigSelect && student) {
        desigSelect.value = student.designation_id || "";
    }

    const classSelect = document.getElementById("transferTargetClass");
    if (classSelect && student) {
        classSelect.value = student.class_id || "";
        onTransferClassChanged();
    }

    const divSelect = document.getElementById("transferTargetDiv");
    if (divSelect && student) {
        divSelect.value = student.division_id || "";
    }

    const alertBox = document.getElementById("transferResultAlert");
    if (alertBox) alertBox.style.display = "none";

    const saveBtn = document.getElementById("btnConfirmTransfer");
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

function onTransferDeptChanged() {
    const deptId = document.getElementById("transferTargetDept")?.value;
    
    const classSelect = document.getElementById("transferTargetClass");
    if (classSelect) {
        Array.from(classSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.style.display = (!deptId || !dId || dId === deptId) ? "" : "none";
        });
    }

    const desigSelect = document.getElementById("transferTargetDesignation");
    if (desigSelect) {
        Array.from(desigSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const dId = opt.getAttribute("data-dept-id");
            opt.style.display = (!deptId || !dId || dId === deptId) ? "" : "none";
        });
    }
}

function onTransferClassChanged() {
    const classId = document.getElementById("transferTargetClass")?.value;
    const divSelect = document.getElementById("transferTargetDiv");
    if (divSelect) {
        Array.from(divSelect.options).forEach((opt, idx) => {
            if (idx === 0) return;
            const cId = opt.getAttribute("data-class-id");
            opt.style.display = (!classId || !cId || cId === classId) ? "" : "none";
        });
    }
}

async function submitDepartmentTransfer(e) {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    const studentId = document.getElementById("transferStudentId")?.value;
    const deptId = document.getElementById("transferTargetDept")?.value;
    const desigId = document.getElementById("transferTargetDesignation")?.value;
    const classId = document.getElementById("transferTargetClass")?.value;
    const divId = document.getElementById("transferTargetDiv")?.value;

    if (!studentId || !deptId) {
        alert("Please choose a target department.");
        return;
    }

    const saveBtn = document.getElementById("btnConfirmTransfer");
    const alertBox = document.getElementById("transferResultAlert");

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Transferring...';
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}/transfer-department`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                department_id: parseInt(deptId),
                designation_id: desigId ? parseInt(desigId) : null,
                class_id: classId ? parseInt(classId) : null,
                division_id: divId ? parseInt(divId) : null,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                alertBox.style.color = "var(--badge-emerald-text, #059669)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Transferred successfully!");
            }
            setTimeout(() => {
                closeTransferDepartmentModal();
                window.location.reload();
            }, 600);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
                alertBox.style.color = "var(--badge-rose-text, #dc2626)";
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
            alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
            alertBox.style.color = "var(--badge-rose-text, #dc2626)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-arrow-right-arrow-left"></i> Confirm Transfer';
        }
    }
}

// ==============================================================================
// 4. Retake Photos Modal (Dual-Mode: 3-Photo Upload & Webcam)
// ==============================================================================

function openRetakeModal(studentId) {
    const modal = document.getElementById("retakePhotosModal");
    if (!modal) return;

    const student = getStudentData(studentId);
    document.getElementById("retakeStudentId").value = studentId;

    const titleEl = document.getElementById("retakeModalTitle");
    if (titleEl) {
        titleEl.textContent = student ? `Update Photos: ${student.name}` : "Update Reference Photos";
    }

    const subEl = document.getElementById("retakeModalSubtitle");
    if (subEl) {
        subEl.textContent = student ? `ID: ${student.roll_number} | Department: ${student.department}` : "";
    }

    // Populate existing preview
    const existingPreview = document.getElementById("retakeExistingPhotosPreview");
    if (existingPreview && student) {
        existingPreview.innerHTML = "";
        if (student.photos && student.photos.length > 0) {
            student.photos.forEach(p => {
                const card = document.createElement("div");
                card.className = "photo-preview-card";
                card.innerHTML = `
                    <img src="${p.url}" class="photo-preview-img" style="aspect-ratio: 1/1; object-fit: cover;">
                    <div class="photo-preview-label">${p.angle ? p.angle.toUpperCase() : 'PHOTO'}</div>
                `;
                existingPreview.appendChild(card);
            });
        } else {
            existingPreview.innerHTML = `<span style="font-size: 12px; color: var(--text-muted); font-style: italic;">No current photos registered.</span>`;
        }
    }

    retakeCapturedBlobs = { frontal: null, left: null, right: null };
    retakeUploadedFiles = [null, null, null];
    resetRetakeUploadPreviews();
    switchRetakeMode("upload");

    const alertBox = document.getElementById("retakeResultAlert");
    if (alertBox) alertBox.style.display = "none";

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
        if (tabUpload) tabUpload.classList.remove("active");
        if (tabWebcam) tabWebcam.classList.add("active");
        if (secUpload) secUpload.style.display = "none";
        if (secWebcam) secWebcam.style.display = "block";
    }
    checkRetakeReadiness();
}

function resetRetakeUploadPreviews() {
    for (let i = 0; i < 3; i++) {
        const img = document.getElementById(`retakePrevImg${i}`);
        const ph = document.getElementById(`retakePh${i}`);
        if (img) { img.src = ""; img.style.display = "none"; }
        if (ph) { ph.style.display = "flex"; }

        const camImg = document.getElementById(`retakeCamPrevImg${i}`);
        const camPh = document.getElementById(`retakeCamPh${i}`);
        if (camImg) { camImg.src = ""; camImg.style.display = "none"; }
        if (camPh) { camPh.style.display = "flex"; }
    }
    const feedback = document.getElementById("retakeCamFeedback");
    if (feedback) feedback.style.display = "none";
    checkRetakeReadiness();
}

function checkRetakeReadiness() {
    const submitBtn = document.getElementById("btnSubmitRetakeUpload");
    if (!submitBtn) return;

    const validCount = retakeUploadedFiles.filter(f => f != null).length;
    const isReady = (validCount === 3);

    submitBtn.disabled = !isReady;
    if (isReady) {
        submitBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Save & Replace Face Vectors (3/3 Ready)';
    } else {
        submitBtn.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Save & Replace Face Vectors (${validCount}/3 Ready)`;
    }
}

function handleRetakeFiles(files) {
    if (!files || files.length === 0) return;
    const selectedFiles = Array.from(files).slice(0, 3);
    retakeUploadedFiles = [null, null, null];

    selectedFiles.forEach((f, idx) => {
        retakeUploadedFiles[idx] = f;
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = document.getElementById(`retakePrevImg${idx}`);
            const ph = document.getElementById(`retakePh${idx}`);
            if (img) {
                img.src = e.target.result;
                img.style.display = "block";
            }
            if (ph) ph.style.display = "none";
            checkRetakeReadiness();
        };
        reader.readAsDataURL(f);
    });

    checkRetakeReadiness();
}

async function submitRetakeUpload() {
    const studentId = document.getElementById("retakeStudentId")?.value;
    const validCount = retakeUploadedFiles.filter(f => f != null).length;
    if (!studentId || validCount < 3) {
        alert("Please provide all 3 required reference photos (Frontal, Left, Right).");
        return;
    }

    const submitBtn = document.getElementById("btnSubmitRetakeUpload");
    const alertBox = document.getElementById("retakeResultAlert");

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing Biometrics...';
    }

    const formData = new FormData();
    if (retakeUploadedFiles[0]) formData.append("photo_front", retakeUploadedFiles[0]);
    if (retakeUploadedFiles[1]) formData.append("photo_left", retakeUploadedFiles[1]);
    if (retakeUploadedFiles[2]) formData.append("photo_right", retakeUploadedFiles[2]);

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}/update-photos`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                alertBox.style.color = "var(--badge-emerald-text, #059669)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Photos and vector encodings updated successfully!");
            }
            setTimeout(() => {
                closeRetakeModal();
                window.location.reload();
            }, 750);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
                alertBox.style.color = "var(--badge-rose-text, #dc2626)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Photo update failed.");
            }
            if (submitBtn) {
                submitBtn.disabled = false;
                checkRetakeReadiness();
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
            alertBox.style.color = "var(--badge-rose-text, #dc2626)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (submitBtn) {
            submitBtn.disabled = false;
            checkRetakeReadiness();
        }
    }
}

// Retake Webcam Controls
async function toggleRetakeWebcam() {
    const video = document.getElementById("retakeWebcamVideo");
    const btn = document.getElementById("btnToggleRetakeCam");
    if (!video) return;

    if (currentRetakeStream) {
        stopRetakeWebcam();
        if (btn) btn.innerHTML = '<i class="fa-solid fa-video"></i> Start Camera';
    } else {
        try {
            currentRetakeStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }
            });
            video.srcObject = currentRetakeStream;
            if (btn) btn.innerHTML = '<i class="fa-solid fa-video-slash"></i> Stop Camera';
            enableWebcamCaptureButtons(true);
        } catch (err) {
            alert("Camera access denied or unavailable: " + err.message);
        }
    }
}

function stopRetakeWebcam() {
    if (currentRetakeStream) {
        currentRetakeStream.getTracks().forEach(t => t.stop());
        currentRetakeStream = null;
    }
    const video = document.getElementById("retakeWebcamVideo");
    if (video) video.srcObject = null;
    const btn = document.getElementById("btnToggleRetakeCam");
    if (btn) btn.innerHTML = '<i class="fa-solid fa-video"></i> Start Camera';
    enableWebcamCaptureButtons(false);
}

function enableWebcamCaptureButtons(enabled) {
    const btnFront = document.getElementById("btnRetakeCapFrontal");
    const btnLeft = document.getElementById("btnRetakeCapLeft");
    const btnRight = document.getElementById("btnRetakeCapRight");
    if (btnFront) btnFront.disabled = !enabled;
    if (btnLeft) btnLeft.disabled = !enabled;
    if (btnRight) btnRight.disabled = !enabled;
}

function captureRetakeSample(angle) {
    const video = document.getElementById("retakeWebcamVideo");
    const canvas = document.getElementById("retakeCaptureCanvas");
    if (!video || !canvas || !currentRetakeStream) {
        alert("Please start the camera first.");
        return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
        if (!blob) return;
        retakeCapturedBlobs[angle] = blob;
        const file = new File([blob], `${angle}.jpg`, { type: "image/jpeg" });
        
        const angleIdx = angle === "frontal" ? 0 : (angle === "left" ? 1 : 2);
        retakeUploadedFiles[angleIdx] = file;

        // Update upload tab previews
        const img = document.getElementById(`retakePrevImg${angleIdx}`);
        const ph = document.getElementById(`retakePh${angleIdx}`);
        if (img) {
            img.src = URL.createObjectURL(blob);
            img.style.display = "block";
        }
        if (ph) ph.style.display = "none";

        // Update webcam tab previews
        const camImg = document.getElementById(`retakeCamPrevImg${angleIdx}`);
        const camPh = document.getElementById(`retakeCamPh${angleIdx}`);
        if (camImg) {
            camImg.src = URL.createObjectURL(blob);
            camImg.style.display = "block";
        }
        if (camPh) camPh.style.display = "none";

        const feedback = document.getElementById("retakeCamFeedback");
        if (feedback) {
            feedback.style.display = "block";
            feedback.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
            feedback.style.color = "var(--badge-emerald-text, #059669)";
            feedback.innerHTML = `<i class="fa-solid fa-circle-check"></i> Captured <strong>${angle.toUpperCase()}</strong> frame successfully!`;
        }

        checkRetakeReadiness();
    }, "image/jpeg", 0.92);
}

// ==============================================================================
// 5. Relieve & Reinstate Employee (Offboarding with Full Audit Retention)
// ==============================================================================

function openRelieveModal(studentId) {
    const modal = document.getElementById("relieveEmployeeModal");
    if (!modal) return;

    const student = getStudentData(studentId);
    document.getElementById("relieveStudentId").value = studentId;

    const nameInput = document.getElementById("relieveStudentName");
    if (nameInput) {
        nameInput.value = student ? `${student.name} (${student.roll_number})` : `#${studentId}`;
    }

    const dateInput = document.getElementById("relieveDateInput");
    if (dateInput) {
        dateInput.value = new Date().toISOString().slice(0, 10);
    }

    const reasonInput = document.getElementById("relieveReasonInput");
    if (reasonInput) reasonInput.value = "";

    const alertBox = document.getElementById("relieveResultAlert");
    if (alertBox) alertBox.style.display = "none";

    const submitBtn = document.getElementById("btnConfirmRelieve");
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-user-slash"></i> Confirm Relieving';
    }

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

    const submitBtn = document.getElementById("btnConfirmRelieve");
    const alertBox = document.getElementById("relieveResultAlert");

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Relieving...';
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
                alertBox.style.background = "var(--badge-emerald-bg, rgba(16,185,129,0.12))";
                alertBox.style.color = "var(--badge-emerald-text, #059669)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Employee successfully relieved.");
            }
            setTimeout(() => {
                closeRelieveModal();
                window.location.reload();
            }, 750);
        } else {
            if (alertBox) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
                alertBox.style.color = "var(--badge-rose-text, #dc2626)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Failed to relieve employee.");
            }
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-user-slash"></i> Confirm Relieving';
            }
        }
    } catch (err) {
        if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg, rgba(239,68,68,0.12))";
            alertBox.style.color = "var(--badge-rose-text, #dc2626)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-user-slash"></i> Confirm Relieving';
        }
    }
}

async function reinstateEmployee(studentId) {
    const student = getStudentData(studentId);
    const name = student ? student.name : `#${studentId}`;

    if (!confirm(`Are you sure you want to reinstate "${name}" back to active status?`)) {
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
            alert(data.message || `"${name}" has been reinstated successfully!`);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to reinstate employee.");
        }
    } catch (err) {
        alert("Network error while reinstating employee.");
    }
}

// ==============================================================================
// 6. Delete Profile Action
// ==============================================================================

async function deleteStudent(studentId) {
    const student = getStudentData(studentId);
    const name = student ? student.name : `#${studentId}`;

    if (!confirm(`Are you sure you want to permanently delete profile "${name}"? This removes all face vector encodings and enrolled photos.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/v1/enroll/student/${studentId}`, {
            method: "DELETE",
        });
        const data = await res.json();

        if (res.ok) {
            alert(data.message || `"${name}" deleted successfully.`);
            window.location.reload();
        } else {
            alert(data.detail || "Failed to delete profile.");
        }
    } catch (err) {
        alert("Network error while deleting profile.");
    }
}

// ==============================================================================
// 7. Lightbox Image Viewer
// ==============================================================================

function openLightbox(imgUrl, caption) {
    const modal = document.getElementById("lightboxModal");
    const img = document.getElementById("lightboxImg");
    const cap = document.getElementById("lightboxCaption");
    if (!modal || !img) return;

    img.src = imgUrl;
    if (cap) cap.textContent = caption || "";
    modal.classList.add("active");
    modal.style.display = "flex";
}

function closeLightbox() {
    const modal = document.getElementById("lightboxModal");
    if (modal) {
        modal.classList.remove("active");
        modal.style.display = "none";
    }
}

// ==============================================================================
// 8. Manual Attendance Override Modal
// ==============================================================================

function openManualOverrideModal() {
    const modal = document.getElementById("manualOverrideModal");
    if (!modal) return;

    const select = document.getElementById("overrideStudentSelect");
    if (select && select.value) {
        onOverrideStudentChanged();
    }

    // Default timestamp to now in local time
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const tsInput = document.getElementById("overrideTimestamp");
    if (tsInput) tsInput.value = now.toISOString().slice(0, 16);

    const alertBox = document.getElementById("overrideResultAlert");
    if (alertBox) alertBox.style.display = "none";

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

function applyReasonPreset() {
    const preset = document.getElementById("overridePresetSelect")?.value;
    const reasonInput = document.getElementById("overrideReasonInput");
    if (reasonInput && preset && preset !== "Custom") {
        reasonInput.value = preset;
    }
}

function onOverridePunchTypeChanged() {}

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
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
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
                window.location.reload();
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

// ==============================================================================
// DOM Initialization & Event Listeners
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // Retake File Drag & Drop
    const dropzone = document.getElementById("retakeDropzone");
    const fileInput = document.getElementById("retakeFileInput");

    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            handleRetakeFiles(e.target.files);
        });
    }

    if (dropzone) {
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
            handleRetakeFiles(e.dataTransfer.files);
        });
    }

    // Default status pill
    setEmployeeStatusFilter("active");
});

// Explicit window bindings for inline HTML handlers
window.setEmployeeStatusFilter = setEmployeeStatusFilter;
window.applyDirectoryFilters = applyDirectoryFilters;
window.resetDirectoryFilters = resetDirectoryFilters;
window.onDirDeptFilterChanged = onDirDeptFilterChanged;
window.onDirClassFilterChanged = onDirClassFilterChanged;

window.openEditModal = openEditModal;
window.closeEditModal = closeEditModal;
window.onEditDeptSelectChanged = onEditDeptSelectChanged;
window.onEditClassSelectChanged = onEditClassSelectChanged;
window.onEditDesignationChanged = onEditDesignationChanged;
window.onEditSalaryTemplateChanged = onEditSalaryTemplateChanged;
window.submitStudentEdit = submitStudentEdit;

window.openTransferDepartmentModal = openTransferDepartmentModal;
window.closeTransferDepartmentModal = closeTransferDepartmentModal;
window.onTransferDeptChanged = onTransferDeptChanged;
window.onTransferClassChanged = onTransferClassChanged;
window.submitDepartmentTransfer = submitDepartmentTransfer;

window.openRetakeModal = openRetakeModal;
window.closeRetakeModal = closeRetakeModal;
window.triggerRetakeFromEdit = triggerRetakeFromEdit;
window.switchRetakeMode = switchRetakeMode;
window.handleRetakeFiles = handleRetakeFiles;
window.submitRetakeUpload = submitRetakeUpload;
window.toggleRetakeWebcam = toggleRetakeWebcam;
window.stopRetakeWebcam = stopRetakeWebcam;
window.captureRetakeSample = captureRetakeSample;

window.openRelieveModal = openRelieveModal;
window.closeRelieveModal = closeRelieveModal;
window.submitRelieveEmployee = submitRelieveEmployee;
window.reinstateEmployee = reinstateEmployee;
window.deleteStudent = deleteStudent;

window.openLightbox = openLightbox;
window.closeLightbox = closeLightbox;

window.openManualOverrideModal = openManualOverrideModal;
window.closeManualOverrideModal = closeManualOverrideModal;
window.onOverrideStudentChanged = onOverrideStudentChanged;
window.onOverridePunchTypeChanged = onOverridePunchTypeChanged;
window.applyReasonPreset = applyReasonPreset;
window.submitManualOverride = submitManualOverride;
