    document.addEventListener("DOMContentLoaded", () => {
        loadSourceStudents();
        loadFacultyList();
        loadRecentTransferHistory();
    });

    function switchAcademicTab(tab) {
        document.querySelectorAll(".tab-pane").forEach(p => p.style.display = "none");
        document.querySelectorAll(".tab-btn").forEach(b => {
            b.classList.remove("btn-primary");
            b.classList.add("btn-secondary");
        });

        const activePane = document.getElementById("tabContent" + tab.charAt(0).toUpperCase() + tab.slice(1));
        const activeBtn = document.getElementById("tabBtn" + tab.charAt(0).toUpperCase() + tab.slice(1));
        if (activePane) activePane.style.display = "block";
        if (activeBtn) {
            activeBtn.classList.remove("btn-secondary");
            activeBtn.classList.add("btn-primary");
        }
    }

    /* ==========================================================
       Department Lifecycle Actions
       ========================================================== */
    async function submitCreateDepartment(e) {
        e.preventDefault();
        const name = document.getElementById("newDeptName").value.trim();
        const code = document.getElementById("newDeptCode").value.trim();
        const description = document.getElementById("newDeptDesc").value.trim();
        const alertBox = document.getElementById("createDeptAlert");

        try {
            const res = await fetch("/api/v1/academic/departments", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, code, description })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Department created successfully!");
                window.location.reload();
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Error creating department.");
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    function openEditDepartmentModal(id, name, code, desc) {
        document.getElementById("editDeptId").value = id;
        document.getElementById("editDeptName").value = name;
        document.getElementById("editDeptCode").value = code || "";
        document.getElementById("editDeptDesc").value = desc || "";
        document.getElementById("editDeptAlert").style.display = "none";
        document.getElementById("editDepartmentModal").classList.add("active");
    }

    function closeEditDepartmentModal() {
        document.getElementById("editDepartmentModal").classList.remove("active");
    }

    async function submitEditDepartment(e) {
        e.preventDefault();
        const id = document.getElementById("editDeptId").value;
        const name = document.getElementById("editDeptName").value.trim();
        const code = document.getElementById("editDeptCode").value.trim();
        const description = document.getElementById("editDeptDesc").value.trim();
        const alertBox = document.getElementById("editDeptAlert");

        try {
            const res = await fetch(`/api/v1/academic/departments/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, code, description })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Department updated successfully!");
                window.location.reload();
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Error updating department.");
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function deleteDepartment(id, name) {
        if (!confirm(`Are you sure you want to delete department "${name}"?`)) return;

        try {
            const res = await fetch(`/api/v1/academic/departments/${id}`, { method: "DELETE" });
            const data = await res.json();
            if (res.ok) {
                alert(data.message || "Department deleted.");
                window.location.reload();
            } else {
                alert("Cannot Delete Department:\n" + (data.detail || "Deletion restricted due to linked records."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    /* ==========================================================
       Class & Division Actions
       ========================================================== */
    async function submitCreateClass(e) {
        e.preventDefault();
        const deptId = parseInt(document.getElementById("newClassDeptSelect").value);
        const name = document.getElementById("newClassName").value.trim();
        const code = document.getElementById("newClassCode").value.trim();

        try {
            const res = await fetch("/api/v1/academic/classes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, department_id: deptId, code })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Class created successfully!");
                window.location.reload();
            } else {
                alert("Error: " + (data.detail || "Could not create class."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    function openEditClassModal(id, name, deptId, code) {
        document.getElementById("editClassId").value = id;
        document.getElementById("editClassName").value = name;
        if (deptId && document.getElementById("editClassDeptSelect")) {
            document.getElementById("editClassDeptSelect").value = deptId;
        }
        document.getElementById("editClassCode").value = code || "";
        document.getElementById("editClassAlert").style.display = "none";
        document.getElementById("editClassModal").classList.add("active");
    }

    function closeEditClassModal() {
        document.getElementById("editClassModal").classList.remove("active");
    }

    async function submitEditClass(e) {
        e.preventDefault();
        const id = document.getElementById("editClassId").value;
        const deptId = parseInt(document.getElementById("editClassDeptSelect").value);
        const name = document.getElementById("editClassName").value.trim();
        const code = document.getElementById("editClassCode").value.trim();
        const alertBox = document.getElementById("editClassAlert");

        try {
            const res = await fetch(`/api/v1/academic/classes/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, department_id: deptId, code })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Class updated successfully!");
                window.location.reload();
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Error updating class.");
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function deleteClass(id, name) {
        if (!confirm(`Are you sure you want to delete class "${name}"?`)) return;

        try {
            const res = await fetch(`/api/v1/academic/classes/${id}`, { method: "DELETE" });
            const data = await res.json();
            if (res.ok) {
                alert(data.message || "Class deleted.");
                window.location.reload();
            } else {
                alert("Cannot Delete Class:\n" + (data.detail || "Deletion restricted due to enrolled students."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function submitCreateDivision(e) {
        e.preventDefault();
        const classId = parseInt(document.getElementById("divParentClassSelect").value);
        const name = document.getElementById("newDivisionName").value.trim();

        try {
            const res = await fetch("/api/v1/academic/divisions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ class_id: classId, name })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Division created successfully!");
                window.location.reload();
            } else {
                alert("Error: " + (data.detail || "Could not create division."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function deleteDivision(id, name) {
        if (!confirm(`Are you sure you want to delete division "${name}"?`)) return;

        try {
            const res = await fetch(`/api/v1/academic/divisions/${id}`, { method: "DELETE" });
            const data = await res.json();
            if (res.ok) {
                alert(data.message || "Division deleted.");
                window.location.reload();
            } else {
                alert("Cannot Delete Division:\n" + (data.detail || "Deletion restricted due to enrolled students."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    /* ==========================================================
       Cascading Selection & Promotion Engine
       ========================================================== */
    function onSourceDeptChanged() {
        const deptId = document.getElementById("sourceDeptSelect").value;
        const classSelect = document.getElementById("sourceClassSelect");
        
        classSelect.innerHTML = '<option value="">All Classes</option>';
        allTenantClasses.forEach(c => {
            if (!deptId || c.department_id == deptId) {
                classSelect.innerHTML += `<option value="${c.id}" data-dept-id="${c.department_id}">${c.name}</option>`;
            }
        });

        loadSourceDivisions();
        loadSourceStudents();
    }

    function onSourceClassChanged() {
        loadSourceDivisions();
        loadSourceStudents();
    }

    async function loadSourceDivisions() {
        const classId = document.getElementById("sourceClassSelect").value;
        const select = document.getElementById("sourceDivSelect");
        select.innerHTML = '<option value="">All Divisions</option>';
        if (!classId) return;

        try {
            const res = await fetch(`/api/v1/academic/divisions?class_id=${classId}`);
            const data = await res.json();
            if (res.ok && data.divisions) {
                data.divisions.forEach(d => {
                    select.innerHTML += `<option value="${d.id}">${d.name}</option>`;
                });
            }
        } catch (e) {
            console.error("Division load error:", e);
        }
    }

    function onTargetDeptChanged() {
        const deptId = document.getElementById("targetDeptSelect").value;
        const classSelect = document.getElementById("targetClassSelect");
        
        classSelect.innerHTML = '<option value="">Select Target Class</option>';
        allTenantClasses.forEach(c => {
            if (!deptId || c.department_id == deptId) {
                classSelect.innerHTML += `<option value="${c.id}">${c.name}</option>`;
            }
        });
        loadTargetDivisions();
    }

    async function loadTargetDivisions() {
        const classId = document.getElementById("targetClassSelect").value;
        const select = document.getElementById("targetDivSelect");
        select.innerHTML = '<option value="">Default / Unassigned</option>';
        if (!classId) return;

        try {
            const res = await fetch(`/api/v1/academic/divisions?class_id=${classId}`);
            const data = await res.json();
            if (res.ok && data.divisions) {
                data.divisions.forEach(d => {
                    select.innerHTML += `<option value="${d.id}">${d.name}</option>`;
                });
            }
        } catch (e) {
            console.error("Target division load error:", e);
        }
    }

    async function loadSourceStudents() {
        const yearId = document.getElementById("sourceYearSelect")?.value || "";
        const deptId = document.getElementById("sourceDeptSelect")?.value || "";
        const classId = document.getElementById("sourceClassSelect")?.value || "";
        const divId = document.getElementById("sourceDivSelect")?.value || "";
        const tbody = document.getElementById("sourceStudentsTableBody");

        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading students...</td></tr>`;

        let queryParams = [];
        if (deptId) queryParams.push(`department_id=${deptId}`);
        if (classId) queryParams.push(`class_id=${classId}`);
        if (divId) queryParams.push(`division_id=${divId}`);
        if (yearId) queryParams.push(`academic_year_id=${yearId}`);

        const url = `/api/v1/academic/students` + (queryParams.length ? `?${queryParams.join("&")}` : "");

        try {
            const res = await fetch(url);
            const data = await res.json();
            if (res.ok && data.students) {
                sourceStudentsData = data.students;
                document.getElementById("sourceStudentCount").innerText = data.students.length;

                if (data.students.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">No enrolled students found matching the selected filters.</td></tr>`;
                    return;
                }

                tbody.innerHTML = data.students.map(s => `
                    <tr>
                        <td style="text-align: center;">
                            <input type="checkbox" class="student-checkbox" value="${s.id}" checked>
                        </td>
                        <td style="font-family: monospace; font-weight: 700; color: var(--accent-primary);">${s.roll_number}</td>
                        <td style="font-weight: 700; color: var(--text-heading);">${s.name}</td>
                        <td><span class="badge badge-indigo">${s.department || 'General'}</span></td>
                        <td>${s.class_name || 'General'} &bull; ${s.division_name || 'N/A'}</td>
                        <td>
                            <span class="badge badge-present" style="font-size: 11px;">${s.samples_count || 0} Vectors</span>
                        </td>
                        <td style="font-size: 11.5px; color: var(--text-muted);">
                            ${s.last_promoted_at ? s.last_promoted_at.slice(0, 10) : 'Original'}
                        </td>
                    </tr>
                `).join("");
            } else {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--accent-rose);">Could not load student roster.</td></tr>`;
            }
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: var(--accent-rose);">Network error loading students.</td></tr>`;
        }
    }

    function toggleSelectAllStudents(checked) {
        document.querySelectorAll(".student-checkbox").forEach(cb => cb.checked = checked);
        const master = document.getElementById("selectAllCheckbox");
        if (master) master.checked = checked;
    }

    async function executeBatchPromotion() {
        const selectedIds = Array.from(document.querySelectorAll(".student-checkbox:checked")).map(cb => parseInt(cb.value));
        const targetClassSelect = document.getElementById("targetClassSelect");
        const targetClassId = targetClassSelect.value ? parseInt(targetClassSelect.value) : null;
        const targetDivId = document.getElementById("targetDivSelect").value ? parseInt(document.getElementById("targetDivSelect").value) : null;
        const targetYearId = document.getElementById("targetYearSelect").value ? parseInt(document.getElementById("targetYearSelect").value) : null;

        const alertBox = document.getElementById("promotionAlert");

        if (selectedIds.length === 0) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Please select at least one student to promote.';
            return;
        }

        if (!targetClassId) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Please select a valid target class.';
            return;
        }

        if (!confirm(`Are you sure you want to promote ${selectedIds.length} student(s) to target class? Biometric face vectors and attendance records will remain safe.`)) return;

        try {
            const res = await fetch("/api/v1/academic/students/promote", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_ids: selectedIds,
                    target_class_id: targetClassId,
                    target_division_id: targetDivId,
                    target_academic_year_id: targetYearId,
                }),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
                setTimeout(() => loadSourceStudents(), 1000);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Promotion failed.");
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
    }

    async function executeClassRollback() {
        const classId = parseInt(document.getElementById("rollbackClassSelect").value);
        const alertBox = document.getElementById("rollbackAlert");

        if (!confirm("Are you sure you want to rollback/downgrade all students in this class back to their prior academic level?")) return;

        try {
            const res = await fetch("/api/v1/academic/students/rollback-promotion", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ class_id: classId }),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
                setTimeout(() => loadSourceStudents(), 1000);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "No eligible rollback history found.");
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
    }

    async function loadFacultyList() {
        try {
            const res = await fetch("/api/v1/academic/teachers");
            const data = await res.json();
            const teacherSelect = document.getElementById("assignTeacherSelect");
            const tbody = document.getElementById("facultyTableBody");

            if (res.ok && data.teachers) {
                teacherSelect.innerHTML = data.teachers.map(t => `<option value="${t.id}">${t.full_name} (@${t.username})</option>`).join("");

                let rows = [];
                data.teachers.forEach(t => {
                    if (t.assignments && t.assignments.length > 0) {
                        t.assignments.forEach(a => {
                            rows.push(`
                                <tr>
                                    <td style="font-weight: 700; color: var(--text-heading);">${t.full_name}</td>
                                    <td style="font-family: monospace; font-size: 11.5px; color: var(--accent-primary);">@${t.username}</td>
                                    <td style="font-weight: 600;">${a.class_name}</td>
                                    <td><span class="badge badge-indigo" style="font-size: 10.5px;">${a.division_name || 'All'}</span></td>
                                    <td style="font-size: 12px;">${a.subject || 'General'}</td>
                                    <td style="text-align: right;">
                                        <button class="btn btn-secondary" style="font-size: 10.5px; padding: 2px 6px; color: var(--accent-rose);" onclick="removeAssignment(${a.id})">
                                            <i class="fa-solid fa-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            `);
                        });
                    } else {
                        rows.push(`
                            <tr>
                                <td style="font-weight: 700; color: var(--text-heading);">${t.full_name}</td>
                                <td style="font-family: monospace; font-size: 11.5px; color: var(--accent-primary);">@${t.username}</td>
                                <td colspan="3" style="color: var(--text-muted); font-size: 11.5px;">No classrooms assigned yet</td>
                                <td></td>
                            </tr>
                        `);
                    }
                });

                tbody.innerHTML = rows.join("");
            }
        } catch (e) {
            console.error("Faculty load error:", e);
        }
    }

    async function loadAssignDivisions() {
        const classId = document.getElementById("assignClassSelect").value;
        const select = document.getElementById("assignDivSelect");
        select.innerHTML = '<option value="">All Divisions</option>';
        if (!classId) return;

        try {
            const res = await fetch(`/api/v1/academic/divisions?class_id=${classId}`);
            const data = await res.json();
            if (res.ok && data.divisions) {
                data.divisions.forEach(d => {
                    select.innerHTML += `<option value="${d.id}">${d.name}</option>`;
                });
            }
        } catch (e) {}
    }

    async function submitCreateTeacher(e) {
        e.preventDefault();
        const payload = {
            full_name: document.getElementById("newTeacherFullName").value.trim(),
            username: document.getElementById("newTeacherUsername").value.trim(),
            password: document.getElementById("newTeacherPassword").value,
            email: document.getElementById("newTeacherEmail").value.trim(),
        };

        try {
            const res = await fetch("/api/v1/academic/teachers", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                alert("Teacher registered successfully!");
                loadFacultyList();
            } else {
                alert("Error: " + (data.detail || "Could not create teacher account."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function submitAssignTeacher(e) {
        e.preventDefault();
        const teacherId = parseInt(document.getElementById("assignTeacherSelect").value);
        const classId = parseInt(document.getElementById("assignClassSelect").value);
        const divId = document.getElementById("assignDivSelect").value ? parseInt(document.getElementById("assignDivSelect").value) : null;
        const subject = document.getElementById("assignSubject").value.trim() || "General";

        try {
            const res = await fetch("/api/v1/academic/teacher-assignments", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    teacher_id: teacherId,
                    class_id: classId,
                    division_id: divId,
                    subject: subject
                })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Classroom assignment saved!");
                loadFacultyList();
            } else {
                alert("Error: " + (data.detail || "Assignment failed."));
            }
        } catch (err) {
            alert("Network error.");
        }
    }

    async function removeAssignment(id) {
        if (!confirm("Are you sure you want to remove this classroom assignment?")) return;
        try {
            const res = await fetch(`/api/v1/academic/teacher-assignments/${id}`, { method: "DELETE" });
            if (res.ok) {
                loadFacultyList();
            }
        } catch (e) {}
    }

    async function submitCreateYear(e) {
        e.preventDefault();
        const name = document.getElementById("newYearName").value.trim();
        const isCurrent = document.getElementById("newYearIsCurrent").checked;

        try {
            const res = await fetch("/api/v1/academic/years", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, is_current: isCurrent })
            });
            const data = await res.json();
            if (res.ok) {
                alert("Academic year created!");
                window.location.reload();
            } else {
                alert("Error: " + (data.detail || "Could not create academic year."));
            }
        } catch (e) {}
    }

    /* ==========================================================
       Individual Student Transfer Functions
       ========================================================== */
    function onTransferSearchInput(query) {
        clearTimeout(searchDebounceTimer);
        const resultsDiv = document.getElementById("transferStudentSearchResults");
        if (!query || query.trim().length < 1) {
            resultsDiv.style.display = "none";
            return;
        }

        searchDebounceTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/v1/academic/students?search=${encodeURIComponent(query.trim())}`);
                const data = await res.json();
                if (res.ok && data.students && data.students.length > 0) {
                    resultsDiv.innerHTML = data.students.map(s => {
                        const safeJson = JSON.stringify(s).replace(/'/g, "&#39;");
                        return `
                        <div style="padding: 10px 14px; cursor: pointer; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;"
                             onmouseover="this.style.background='var(--bg-subtle)'"
                             onmouseout="this.style.background='transparent'"
                             onclick='selectTransferStudent(${safeJson})'>
                            <div>
                                <div style="font-weight: 700; color: var(--text-heading); font-size: 13.5px;">${s.name}</div>
                                <div style="font-size: 11.5px; color: var(--text-muted);">${s.department || 'No Dept'} &bull; ${s.class_name || s.class_semester || 'General'}</div>
                            </div>
                            <code style="font-weight: 600; color: var(--accent-primary); font-size: 12px;">${s.roll_number}</code>
                        </div>
                    `;
                    }).join("");
                    resultsDiv.style.display = "block";
                } else {
                    resultsDiv.innerHTML = `<div style="padding: 12px; color: var(--text-muted); font-size: 12.5px; text-align: center;">No matching active students found</div>`;
                    resultsDiv.style.display = "block";
                }
            } catch (e) {
                console.error("Student search error:", e);
            }
        }, 250);
    }

    function selectTransferStudent(student) {
        document.getElementById("transferStudentSearchResults").style.display = "none";
        document.getElementById("transferStudentSearchInput").value = `${student.name} (${student.roll_number})`;
        document.getElementById("transferSelectedStudentId").value = student.id;

        // Populate Profile Card
        document.getElementById("transferStdAvatar").innerText = student.name ? student.name[0].toUpperCase() : "?";
        document.getElementById("transferStdName").innerText = student.name;
        document.getElementById("transferStdRoll").innerText = student.roll_number;
        document.getElementById("transferStdGender").innerText = student.gender || "Other";
        document.getElementById("transferStdRole").innerText = student.user_role || "student";
        document.getElementById("transferStdDept").innerText = student.department || "Unassigned";
        document.getElementById("transferStdClassDiv").innerText = (student.class_name || student.class_semester || "General") + (student.division_name && student.division_name !== 'N/A' ? ' • ' + student.division_name : '');
        document.getElementById("transferStdEmail").innerText = student.email || "No email";
        document.getElementById("transferStdSamples").innerText = `${student.samples_count || 0} Biometric Sample(s)`;

        document.getElementById("selectedStudentCard").style.display = "block";
        document.getElementById("noStudentSelectedMsg").style.display = "none";
        document.getElementById("btnExecuteTransfer").disabled = false;

        // Reset target selections
        document.getElementById("transferTargetDeptSelect").value = "";
        onTransferDeptChanged();
    }

    function onTransferDeptChanged() {
        const deptId = document.getElementById("transferTargetDeptSelect").value;
        const classSelect = document.getElementById("transferTargetClassSelect");
        const divSelect = document.getElementById("transferTargetDivSelect");

        classSelect.innerHTML = '<option value="">Select Target Class</option>';
        divSelect.innerHTML = '<option value="">Default / Unassigned</option>';

        if (!deptId) return;

        const filteredClasses = allTenantClasses.filter(c => !c.department_id || c.department_id == deptId);
        filteredClasses.forEach(c => {
            classSelect.innerHTML += `<option value="${c.id}">${c.name}</option>`;
        });
    }

    async function onTransferClassChanged() {
        const classId = document.getElementById("transferTargetClassSelect").value;
        const divSelect = document.getElementById("transferTargetDivSelect");
        divSelect.innerHTML = '<option value="">Default / Unassigned</option>';

        if (!classId) return;

        try {
            const res = await fetch(`/api/v1/academic/divisions?class_id=${classId}`);
            const data = await res.json();
            if (res.ok && data.divisions) {
                data.divisions.forEach(d => {
                    divSelect.innerHTML += `<option value="${d.id}">${d.name}</option>`;
                });
            }
        } catch (e) {
            console.error("Load transfer divisions error:", e);
        }
    }

    async function submitIndividualTransfer(e) {
        e.preventDefault();
        const studentId = parseInt(document.getElementById("transferSelectedStudentId").value);
        const deptId = parseInt(document.getElementById("transferTargetDeptSelect").value);
        const classId = parseInt(document.getElementById("transferTargetClassSelect").value);
        const divId = document.getElementById("transferTargetDivSelect").value ? parseInt(document.getElementById("transferTargetDivSelect").value) : null;
        const yearId = document.getElementById("transferTargetYearSelect").value ? parseInt(document.getElementById("transferTargetYearSelect").value) : null;
        const alertBox = document.getElementById("transferAlert");

        if (!studentId || !deptId || !classId) {
            alert("Please select a student, target department, and target class.");
            return;
        }

        try {
            const res = await fetch("/api/v1/academic/students/transfer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_id: studentId,
                    target_department_id: deptId,
                    target_class_id: classId,
                    target_division_id: divId,
                    target_academic_year_id: yearId,
                })
            });
            const data = await res.json();
            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
                setTimeout(() => {
                    loadRecentTransferHistory();
                    document.getElementById("transferStudentSearchInput").value = "";
                    document.getElementById("selectedStudentCard").style.display = "none";
                    document.getElementById("noStudentSelectedMsg").style.display = "block";
                    document.getElementById("btnExecuteTransfer").disabled = true;
                    alertBox.style.display = "none";
                }, 1500);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Transfer failed.");
            }
        } catch (err) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        }
    }

    async function loadRecentTransferHistory() {
        const tbody = document.getElementById("transferHistoryTableBody");
        if (!tbody) return;

        try {
            const res = await fetch("/api/v1/academic/transfers/recent?limit=50");
            const data = await res.json();
            if (res.ok && data.transfers && data.transfers.length > 0) {
                tbody.innerHTML = data.transfers.map(t => `
                    <tr>
                        <td>
                            <div style="font-weight: 700; color: var(--text-heading);">${t.name}</div>
                            <div style="font-size: 11px; color: var(--text-muted);">${t.email || 'No email'}</div>
                        </td>
                        <td><code style="color: var(--accent-primary); font-weight: 600;">${t.roll_number}</code></td>
                        <td>
                            <span class="badge badge-node" style="font-size: 11px;">${t.previous_department_name} &bull; ${t.previous_class_name}</span>
                        </td>
                        <td>
                            <span class="badge badge-indigo" style="font-size: 11px;">${t.department} &bull; ${t.class_name || t.class_semester}</span>
                        </td>
                        <td style="font-family: monospace; font-size: 11.5px; color: var(--text-muted);">
                            ${t.last_transferred_at ? t.last_transferred_at.replace('T', ' ').slice(0, 19) : 'Recent'}
                        </td>
                        <td style="text-align: right;">
                            <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-rose); border-color: var(--accent-rose);" onclick="rollbackTransfer(${t.id}, '${t.name.replace(/'/g, "\\'")}')">
                                <i class="fa-solid fa-rotate-left"></i> Revert Transfer
                            </button>
                        </td>
                    </tr>
                `).join("");
            } else {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">No transfer audit history recorded yet.</td></tr>`;
            }
        } catch (e) {
            console.error("Load transfer history error:", e);
        }
    }

    async function rollbackTransfer(studentId, studentName) {
        if (!confirm(`Are you sure you want to revert the transfer for ${studentName} back to their previous department and class?`)) return;

        try {
            const res = await fetch("/api/v1/academic/students/rollback-transfer", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ student_id: studentId })
            });
            const data = await res.json();
            if (res.ok) {
                alert(data.message || "Transfer reverted successfully.");
                loadRecentTransferHistory();
            } else {
                alert("Error: " + (data.detail || "Could not revert transfer."));
            }
        } catch (e) {
            alert("Network error.");
        }
    }

    /* ==========================================================
       Excel Bulk Upload & Batch Management Functions
       ========================================================== */
    function handleBulkFileDrop(e) {
        e.preventDefault();
        e.currentTarget.style.borderColor = "var(--border-color)";
        e.currentTarget.style.background = "var(--bg-subtle)";
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setBulkFile(e.dataTransfer.files[0]);
        }
    }

    function handleBulkFileSelect(e) {
        if (e.target.files && e.target.files.length > 0) {
            setBulkFile(e.target.files[0]);
        }
    }

    function setBulkFile(file) {
        selectedBulkFile = file;
        document.getElementById("bulkFileNameText").innerText = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        document.getElementById("bulkSelectedFileName").style.display = "block";
        document.getElementById("btnValidateUpload").disabled = false;
    }

    async function validateBulkUploadFile() {
        if (!selectedBulkFile) {
            alert("Please select an Excel file first.");
            return;
        }

        const btn = document.getElementById("btnValidateUpload");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validating Workbook...';

        const formData = new FormData();
        formData.append("file", selectedBulkFile);

        try {
            const res = await fetch("/api/v1/academic/students/bulk-preview", {
                method: "POST",
                body: formData
            });
            const data = await res.json();

            if (res.ok) {
                renderBulkPreview(data);
            } else {
                alert("Validation Failed: " + (data.detail || "Unknown error parsing Excel file."));
            }
        } catch (e) {
            alert("Network error uploading file.");
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass-chart"></i> Validate & Preview Staging';
        }
    }

    function renderBulkPreview(data) {
        document.getElementById("previewTotalCount").innerText = data.total_rows;
        document.getElementById("previewValidCount").innerText = data.valid_count;
        document.getElementById("previewInvalidCount").innerText = data.invalid_count;
        document.getElementById("btnImportValidCount").innerText = data.valid_count;

        const confirmBtn = document.getElementById("btnConfirmImport");
        confirmBtn.disabled = data.valid_count === 0;

        const tbody = document.getElementById("bulkPreviewTableBody");
        validatedBulkRows = data.preview_data.filter(r => r.is_valid);

        tbody.innerHTML = data.preview_data.map(r => `
            <tr style="background: ${r.is_valid ? 'transparent' : 'rgba(239, 68, 68, 0.04)'};">
                <td style="font-family: monospace; font-size: 12px; color: var(--text-muted);">${r.row_index}</td>
                <td>
                    ${r.is_valid
                        ? '<span class="badge badge-present" style="font-size: 10.5px;"><i class="fa-solid fa-check"></i> Valid</span>'
                        : '<span class="badge badge-absent" style="font-size: 10.5px;"><i class="fa-solid fa-triangle-exclamation"></i> Error</span>'
                    }
                </td>
                <td style="font-weight: 700; color: var(--text-heading);">${r.name || '<em style="color: var(--accent-rose);">Missing</em>'}</td>
                <td><code style="font-weight: 600; color: var(--accent-primary);">${r.roll_number || 'N/A'}</code></td>
                <td>${r.department || 'N/A'}</td>
                <td>${r.class_name || 'N/A'}${r.division_name && r.division_name !== 'N/A' ? ' &bull; ' + r.division_name : ''}</td>
                <td><span class="badge badge-node" style="font-size: 10px;">${r.gender}</span></td>
                <td><span class="badge badge-present" style="font-size: 10px;">${r.user_role}</span></td>
                <td>
                    ${r.is_valid
                        ? '<span style="color: var(--accent-emerald); font-size: 12px;"><i class="fa-solid fa-circle-check"></i> Ready to import</span>'
                        : `<div style="color: var(--accent-rose); font-size: 11.5px; font-weight: 600;">${r.errors.join(' | ')}</div>`
                    }
                </td>
            </tr>
        `).join("");

        document.getElementById("bulkPreviewSection").style.display = "block";
        document.getElementById("bulkPreviewSection").scrollIntoView({ behavior: "smooth" });
    }

    async function confirmBulkImport() {
        if (!validatedBulkRows || validatedBulkRows.length === 0) {
            alert("No valid rows available to import.");
            return;
        }

        if (!confirm(`Are you sure you want to import ${validatedBulkRows.length} valid student(s)? This will create a batch record.`)) {
            return;
        }

        const btn = document.getElementById("btnConfirmImport");
        const alertBox = document.getElementById("bulkImportAlert");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Importing Roster...';

        const payload = {
            filename: selectedBulkFile ? selectedBulkFile.name : "bulk_upload.xlsx",
            rows: validatedBulkRows.map(r => ({
                name: r.name,
                roll_number: r.roll_number,
                department_id: r.department_id,
                class_id: r.class_id,
                division_id: r.division_id,
                gender: r.gender,
                user_role: r.user_role,
                email: r.email || null,
                phone_number: r.phone_number || null,
            }))
        };

        try {
            const res = await fetch("/api/v1/academic/students/bulk-import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message} ${data.skipped_duplicates > 0 ? `(${data.skipped_duplicates} duplicates skipped)` : ''}`;
                loadBatchHistory();
                setTimeout(() => {
                    document.getElementById("bulkPreviewSection").style.display = "none";
                    document.getElementById("bulkSelectedFileName").style.display = "none";
                    selectedBulkFile = null;
                    validatedBulkRows = [];
                }, 3000);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Import failed.");
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-file-import"></i> Import Valid Rows';
        }
    }

    async function loadBatchHistory() {
        const tbody = document.getElementById("batchHistoryTableBody");
        if (!tbody) return;

        try {
            const res = await fetch("/api/v1/academic/batches");
            const data = await res.json();
            if (res.ok && data.batches && data.batches.length > 0) {
                tbody.innerHTML = data.batches.map(b => `
                    <tr>
                        <td style="font-weight: 700; font-family: monospace;">#${b.id}</td>
                        <td>
                            <div style="font-weight: 600; color: var(--text-heading); display: flex; align-items: center; gap: 6px;">
                                <i class="fa-solid fa-file-excel" style="color: var(--accent-emerald);"></i>
                                <span>${b.filename}</span>
                            </div>
                        </td>
                        <td style="font-family: monospace; font-size: 12px; color: var(--text-muted);">
                            ${b.created_at ? b.created_at.replace('T', ' ').slice(0, 19) : 'N/A'}
                        </td>
                        <td style="font-weight: 600;">${b.imported_count} / ${b.total_rows} Rows</td>
                        <td style="font-weight: 700; color: var(--accent-primary);">${b.active_students_count} Active Enrolled</td>
                        <td>
                            ${b.is_active
                                ? '<span class="badge badge-present" style="font-size: 11px;"><i class="fa-solid fa-circle-check"></i> Active</span>'
                                : '<span class="badge badge-absent" style="font-size: 11px;"><i class="fa-solid fa-ban"></i> Soft-Deleted</span>'
                            }
                        </td>
                        <td style="text-align: right;">
                            ${b.is_active
                                ? `<button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-rose); border-color: var(--accent-rose);" onclick="softDeleteBatch(${b.id}, '${b.filename.replace(/'/g, "\\'")}')" title="Soft Delete Batch and deactivate students">
                                       <i class="fa-solid fa-trash"></i> Soft-Delete Batch
                                   </button>`
                                : '<span style="font-size: 11.5px; color: var(--text-muted); font-style: italic;">Rolled Back</span>'
                            }
                        </td>
                    </tr>
                `).join("");
            } else {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">No bulk upload batches recorded yet.</td></tr>`;
            }
        } catch (e) {
            console.error("Load batches error:", e);
        }
    }

    async function softDeleteBatch(batchId, filename) {
        const confirmMsg = `WARNING: Are you sure you want to soft-delete Batch #${batchId} ('${filename}')?\n\nThis will instantly deactivate all students in this batch and remove them from the live facial recognition RAM cache.`;
        if (!confirm(confirmMsg)) return;

        try {
            const res = await fetch(`/api/v1/academic/batches/${batchId}`, {
                method: "DELETE"
            });
            const data = await res.json();
            if (res.ok) {
                alert(data.message || `Batch #${batchId} soft-deleted successfully.`);
                loadBatchHistory();
            } else {
                alert("Error: " + (data.detail || "Could not delete batch."));
            }
        } catch (e) {
            alert("Network error.");
        }
    }
