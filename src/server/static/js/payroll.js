    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    let globalDesignations = [];
    let globalLocations = [];
    let globalTemplates = [];
    let globalEmployees = [];
    let globalBatches = [];

    document.addEventListener("DOMContentLoaded", () => {
        loadPayrollBatches();
        loadEmployeeStructures();
        loadSalaryTemplates();
        loadOrganizationMasters();
        loadPayrollSettings();
    });

    function switchPayrollTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

        const tabBtn = document.getElementById('tabBtn' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
        const tabContent = document.getElementById('tabContent' + tabName.charAt(0).toUpperCase() + tabName.slice(1));

        if (tabBtn) tabBtn.classList.add('active');
        if (tabContent) tabContent.classList.add('active');

        if (tabName === 'realtime') {
            loadPayrollSummary();
        }
    }

    // =========================================================================
    // 1. MONTHLY RUNS & BATCHES
    // =========================================================================

    async function loadPayrollBatches() {
        const tableBody = document.getElementById("batchesTableBody");
        if (!tableBody) return;
        tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading payroll batches...</td></tr>`;

        try {
            const res = await fetch("/api/v1/payroll/batches");
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to load batches");

            globalBatches = data.data || [];
            renderBatchesTable(globalBatches);
            updateBatchesKPIs(globalBatches);
        } catch (e) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--accent-rose); padding: 20px;">Error: ${e.message}</td></tr>`;
        }
    }

    function updateBatchesKPIs(batches) {
        document.getElementById("kpiBatchCount").innerText = batches.length;
        if (batches.length > 0) {
            const latest = batches[0];
            document.getElementById("kpiLatestNetOutlay").innerText = `₹${latest.total_net_outlay.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            document.getElementById("kpiLatestBatchLabel").innerText = `${latest.period_label} (${latest.batch_number})`;
            const statTotal = (latest.total_pf_liability || 0) + (latest.total_esi_liability || 0) + (latest.total_pt_liability || 0);
            document.getElementById("kpiLatestStatutory").innerText = `₹${statTotal.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
            const totalCtc = (latest.total_gross_outlay || 0) + (latest.total_employer_contributions || 0);
            document.getElementById("kpiLatestEmployerCtc").innerText = `₹${totalCtc.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        }
    }

    function renderBatchesTable(batches) {
        const tableBody = document.getElementById("batchesTableBody");
        if (!tableBody) return;

        if (!batches || batches.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 32px; color: var(--text-muted);">No payroll batches processed yet. Click "Generate payroll" above to generate.</td></tr>`;
            return;
        }

        tableBody.innerHTML = batches.map(b => {
            let statusBadge = '<span class="badge badge-node">Draft</span>';
            if (b.status === 'VERIFIED') statusBadge = '<span class="badge badge-sky"><i class="fa-solid fa-clipboard-check"></i> Verified</span>';
            else if (b.status === 'APPROVED') statusBadge = '<span class="badge badge-amber"><i class="fa-solid fa-stamp"></i> Approved</span>';
            else if (b.status === 'DISBURSED') statusBadge = '<span class="badge badge-present"><i class="fa-solid fa-circle-check"></i> Disbursed</span>';

            const statLiab = (b.total_pf_liability || 0) + (b.total_esi_liability || 0) + (b.total_pt_liability || 0);
            const totalCtc = (b.total_gross_outlay || 0) + (b.total_employer_contributions || 0);

            return `
                <tr>
                    <td><code>${b.batch_number}</code></td>
                    <td><strong>${b.period_label}</strong></td>
                    <td><span class="badge badge-indigo">${b.total_employees_count} Employees</span></td>
                    <td><strong style="font-family: monospace;">₹${b.total_gross_outlay.toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                    <td><strong style="color: var(--accent-emerald); font-family: monospace; font-size: 14px;">₹${b.total_net_outlay.toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                    <td><span style="font-family: monospace; font-size: 12px;">₹${statLiab.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></td>
                    <td><span style="font-family: monospace; font-size: 12px; color: var(--text-muted);">₹${totalCtc.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></td>
                    <td>${statusBadge}</td>
                    <td>
                        <div style="display: flex; gap: 6px;">
                            <button onclick="viewBatchDetails(${b.id})" class="btn btn-secondary" style="padding: 6px 10px; font-size: 11.5px;" title="View Statement">
                                <i class="fa-solid fa-eye"></i> View
                            </button>
                            <a href="/api/v1/payroll/batches/${b.id}/export-bank-advice?export_format=xlsx" class="btn btn-secondary" style="padding: 6px 10px; font-size: 11.5px; color: var(--accent-emerald);" title="Bank Advice (.xlsx)">
                                <i class="fa-solid fa-file-excel"></i>
                            </a>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function openGenerateBatchModal() {
        const modal = document.getElementById("generateBatchModal");
        if (modal) modal.classList.add("active");
        const alertBox = document.getElementById("batchGenerateAlert");
        if (alertBox) alertBox.style.display = "none";
    }

    function closeGenerateBatchModal() {
        const modal = document.getElementById("generateBatchModal");
        if (modal) modal.classList.remove("active");
    }

    async function submitGenerateBatch(e) {
        e.preventDefault();
        const month = parseInt(document.getElementById("batchPeriodMonth").value);
        const year = parseInt(document.getElementById("batchPeriodYear").value);
        const workingDays = parseFloat(document.getElementById("batchWorkingDays").value);

        const runBtn = document.getElementById("btnRunBatch");
        const alertBox = document.getElementById("batchGenerateAlert");

        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

        try {
            const res = await fetch("/api/v1/payroll/batches/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    period_year: year,
                    period_month: month,
                    working_days: workingDays,
                }),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;

                setTimeout(() => {
                    closeGenerateBatchModal();
                    runBtn.disabled = false;
                    runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Execute Payroll Run';
                    loadPayrollBatches();
                }, 700);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Generation failed.");
                runBtn.disabled = false;
                runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Execute Payroll Run';
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Execute Payroll Run';
        }
    }

    async function viewBatchDetails(batchId) {
        const modal = document.getElementById("batchDetailsModal");
        if (!modal) return;
        modal.classList.add("active");

        const tableBody = document.getElementById("batchPayslipsTableBody");
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Fetching batch payslips...</td></tr>`;

        try {
            const res = await fetch(`/api/v1/payroll/batches/${batchId}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to load batch");

            const batch = data.batch;
            const payslips = data.payslips || [];

            document.getElementById("batchDetailTitle").innerText = `${batch.period_label} — ${batch.batch_number}`;
            document.getElementById("batchDetailSubtitle").innerText = `Total Gross: ₹${batch.total_gross_outlay.toLocaleString(undefined, {minimumFractionDigits: 2})} | Net Outlay: ₹${batch.total_net_outlay.toLocaleString(undefined, {minimumFractionDigits: 2})} (${payslips.length} Employees)`;

            // Render Lifecycle action buttons
            renderBatchLifecycleButtons(batch);

            // Render Payslips Table
            tableBody.innerHTML = payslips.map(p => {
                return `
                    <tr>
                        <td><strong>${p.student_name}</strong></td>
                        <td><code>${p.roll_number}</code></td>
                        <td><span style="font-family: monospace;">${p.present_days}d / ${p.billable_hours}h</span></td>
                        <td><strong style="font-family: monospace;">₹${p.gross_earnings.toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                        <td><span style="font-family: monospace; font-size: 12px;">₹${p.epf_employee.toFixed(2)}</span></td>
                        <td><span style="font-family: monospace; font-size: 12px;">₹${p.esic_employee.toFixed(2)}</span></td>
                        <td><span style="font-family: monospace; font-size: 12px;">₹${p.professional_tax.toFixed(2)}</span></td>
                        <td><strong style="color: var(--accent-emerald); font-family: monospace; font-size: 13.5px;">₹${p.net_salary.toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                        <td><span class="badge badge-node">${p.payment_status}</span></td>
                        <td>
                            <a href="/payroll/payslip/${p.id}" target="_blank" class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; color: var(--accent-primary);" title="Open Printable Slip">
                                <i class="fa-solid fa-arrow-up-right-from-square"></i> Slip
                            </a>
                        </td>
                    </tr>
                `;
            }).join("");

        } catch (e) {
            tableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--accent-rose); padding: 20px;">Error: ${e.message}</td></tr>`;
        }
    }

    function renderBatchLifecycleButtons(batch) {
        const badgeContainer = document.getElementById("batchStatusBadgeContainer");
        const btnContainer = document.getElementById("batchLifecycleBtns");

        badgeContainer.innerHTML = `<span class="badge badge-indigo" style="font-size: 13px; padding: 6px 12px;">Status: ${batch.status}</span>`;

        let btns = `
            <a href="/api/v1/payroll/batches/${batch.id}/export-bank-advice?export_format=xlsx" class="btn btn-secondary" style="font-size: 12px; padding: 6px 12px;">
                <i class="fa-solid fa-file-excel" style="color: var(--accent-emerald);"></i> Bank Advice (.xlsx)
            </a>
        `;

        if (batch.status === 'DRAFT') {
            btns += `
                <button onclick="transitionBatchStatus(${batch.id}, 'verify')" class="btn btn-primary" style="font-size: 12px; padding: 6px 12px;">
                    <i class="fa-solid fa-check-double"></i> Verify Batch
                </button>
            `;
        } else if (batch.status === 'VERIFIED') {
            btns += `
                <button onclick="transitionBatchStatus(${batch.id}, 'approve')" class="btn btn-primary" style="font-size: 12px; padding: 6px 12px; background: var(--accent-emerald); border-color: var(--accent-emerald);">
                    <i class="fa-solid fa-stamp"></i> Approve Batch
                </button>
            `;
        } else if (batch.status === 'APPROVED') {
            btns += `
                <button onclick="transitionBatchStatus(${batch.id}, 'disburse')" class="btn btn-primary" style="font-size: 12px; padding: 6px 12px; background: #059669; border-color: #059669;">
                    <i class="fa-solid fa-money-bill-transfer"></i> Mark Disbursed & Paid
                </button>
            `;
        }

        btnContainer.innerHTML = btns;
    }

    async function transitionBatchStatus(batchId, action) {
        if (!confirm(`Are you sure you want to ${action.toUpperCase()} this payroll batch?`)) return;

        try {
            const res = await fetch(`/api/v1/payroll/batches/${batchId}/${action}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            const data = await res.json();
            if (res.ok) {
                alert(data.message);
                viewBatchDetails(batchId);
                loadPayrollBatches();
            } else {
                alert("Error: " + (data.detail || "Action failed"));
            }
        } catch (e) {
            alert("Network error.");
        }
    }

    function closeBatchDetailsModal() {
        const modal = document.getElementById("batchDetailsModal");
        if (modal) modal.classList.remove("active");
    }

    // =========================================================================
    // 2. EMPLOYEE SALARY STRUCTURES & REVISIONS
    // =========================================================================

    async function loadEmployeeStructures() {
        const tableBody = document.getElementById("empStructuresTableBody");
        if (!tableBody) return;
        tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading employee profiles...</td></tr>`;

        try {
            const res = await fetch("/api/v1/payroll/structures");
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to load profiles");

            globalEmployees = data.data || [];
            document.getElementById("empStructureCountBadge").innerText = `${globalEmployees.length} Active Profiles`;
            renderEmployeeStructuresTable(globalEmployees);
        } catch (e) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--accent-rose); padding: 20px;">Error: ${e.message}</td></tr>`;
        }
    }

    function filterEmployeeStructuresTable() {
        const query = document.getElementById("empStructureSearchInput")?.value.toLowerCase() || "";
        const filtered = globalEmployees.filter(e =>
            (e.name || "").toLowerCase().includes(query) ||
            (e.roll_number || "").toLowerCase().includes(query) ||
            (e.department || "").toLowerCase().includes(query)
        );
        renderEmployeeStructuresTable(filtered);
    }

    function renderEmployeeStructuresTable(employees) {
        const tableBody = document.getElementById("empStructuresTableBody");
        if (!tableBody) return;

        if (!employees || employees.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 32px; color: var(--text-muted);">No employee records found.</td></tr>`;
            return;
        }

        tableBody.innerHTML = employees.map(emp => {
            const st = emp.active_structure;
            let modelLabel = st ? st.compensation_model.replace('_', ' ') : 'HOURLY / UNSET';
            let grossLabel = st && st.monthly_gross > 0 ? `₹${st.monthly_gross.toLocaleString(undefined, {minimumFractionDigits: 2})}/mo` : (emp.hourly_rate > 0 ? `₹${emp.hourly_rate.toFixed(2)}/hr` : '₹0.00');

            let statBadges = '';
            if (st && st.enable_pf) statBadges += '<span class="badge badge-indigo" style="font-size: 10.5px; margin-right: 4px;">PF</span>';
            if (st && st.enable_esi) statBadges += '<span class="badge badge-sky" style="font-size: 10.5px; margin-right: 4px;">ESIC</span>';
            if (st && st.enable_pt) statBadges += '<span class="badge badge-amber" style="font-size: 10.5px;">PT</span>';
            if (!statBadges) statBadges = '<span style="color: var(--text-muted); font-size: 11px;">None</span>';

            const bankInfo = emp.bank_account_number ? `<code>${emp.bank_account_number}</code>` : '<span style="color: var(--text-muted); font-size: 11px;">Not configured</span>';
            const panInfo = emp.pan_number ? `PAN: <code>${emp.pan_number}</code>` : '';

            return `
                <tr>
                    <td>
                        <strong>${emp.name}</strong>
                    </td>
                    <td><code>${emp.roll_number}</code></td>
                    <td>
                        <span class="badge badge-indigo">${emp.department}</span>
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${emp.location_name}</div>
                    </td>
                    <td><div style="font-size: 12.5px; font-weight: 500;">${emp.designation}</div></td>
                    <td><span class="badge badge-node">${modelLabel}</span></td>
                    <td><strong style="color: var(--accent-emerald); font-family: monospace; font-size: 13.5px;">${grossLabel}</strong></td>
                    <td>${statBadges}</td>
                    <td>
                        <div>${bankInfo}</div>
                        <div style="font-size: 11px; margin-top: 2px;">${panInfo}</div>
                    </td>
                    <td>
                        <div style="display: flex; gap: 6px;">
                            <button onclick="openAssignStructureModal(${emp.id})" class="btn btn-secondary" style="padding: 6px 9px; font-size: 11px;" title="View Compensation Structure">
                                <i class="fa-solid fa-file-invoice-dollar"></i> Structure
                            </button>
                            <button onclick="openStatutoryBankingModal(${emp.id})" class="btn btn-secondary" style="padding: 6px 9px; font-size: 11px; color: var(--accent-primary);" title="Banking Profile">
                                <i class="fa-solid fa-building-columns"></i>
                            </button>
                            <button onclick="openRevisionHistoryModal(${emp.id})" class="btn btn-secondary" style="padding: 6px 9px; font-size: 11px; color: var(--accent-indigo);" title="Revision History">
                                <i class="fa-solid fa-clock-rotate-left"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    async function openAssignStructureModal(studentId) {
        const modal = document.getElementById("assignStructureModal");
        if (!modal) return;

        const emp = globalEmployees.find(e => e.id === studentId);
        if (!emp) return;

        document.getElementById("assignStudentId").value = emp.id;
        document.getElementById("assignEmployeeName").value = `${emp.name} (${emp.roll_number})`;
        document.getElementById("assignRevisionReason").value = "Annual Appraisal / Incremental Revision";

        // Populate template select
        const tplSelect = document.getElementById("assignTemplateSelect");
        tplSelect.innerHTML = '<option value="">-- Custom Individual Structure --</option>' +
            globalTemplates.map(t => `<option value="${t.id}">${t.name} (${t.compensation_model})</option>`).join("");

        const st = emp.active_structure;
        if (st) {
            document.getElementById("assignCompModel").value = st.compensation_model;
            document.getElementById("assignAnnualCtc").value = st.annual_ctc || "";
            document.getElementById("assignMonthlyGross").value = st.monthly_gross || "";
            document.getElementById("assignMonthlyBasic").value = st.monthly_basic || "";
            document.getElementById("assignMonthlyHra").value = st.monthly_hra || "";
            if (document.getElementById("assignMonthlyDa")) document.getElementById("assignMonthlyDa").value = st.monthly_da || 0;
            document.getElementById("assignConveyance").value = st.conveyance_allowance || 1600;
            document.getElementById("assignMedical").value = st.medical_allowance || 1250;
            if (document.getElementById("assignOtherPerks")) document.getElementById("assignOtherPerks").value = st.other_allowances || 0;
            if (document.getElementById("assignHourlyRate")) document.getElementById("assignHourlyRate").value = st.hourly_rate || "";
            if (document.getElementById("assignDailyRate")) document.getElementById("assignDailyRate").value = st.daily_rate || "";
            if (st.template_id) tplSelect.value = st.template_id;
        } else {
            // Option A: Default to mapped designation template blueprint if available
            if (emp.default_template_id) {
                tplSelect.value = emp.default_template_id;
                onSelectTemplateBlueprint();
            } else {
                document.getElementById("assignCompModel").value = "STRUCTURED_SALARY";
            }
            const defaultGross = (emp.monthly_base_salary && emp.monthly_base_salary > 0) ? emp.monthly_base_salary : 35000;
            document.getElementById("assignMonthlyGross").value = defaultGross;
            autoCalculateBreakdown();
        }

        onCompModelChange();
        const alertBox = document.getElementById("assignStructureAlert");
        if (alertBox) alertBox.style.display = "none";

        modal.classList.add("active");
    }

    function closeAssignStructureModal() {
        const modal = document.getElementById("assignStructureModal");
        if (modal) modal.classList.remove("active");
    }

    function onCompModelChange() {
        const model = document.getElementById("assignCompModel").value;
        const structuredBox = document.getElementById("structuredFieldsBox");
        const hourlyBox = document.getElementById("hourlyDailyFieldsBox");

        if (model === "STRUCTURED_SALARY") {
            structuredBox.style.display = "block";
            hourlyBox.style.display = "none";
        } else if (model === "HOURLY" || model === "DAILY_WAGE") {
            structuredBox.style.display = "none";
            hourlyBox.style.display = "block";
        } else {
            structuredBox.style.display = "none";
            hourlyBox.style.display = "none";
        }
    }

    function onSelectTemplateBlueprint() {
        const tplId = parseInt(document.getElementById("assignTemplateSelect").value);
        if (!tplId) return;

        const tpl = globalTemplates.find(t => t.id === tplId);
        if (!tpl) return;

        document.getElementById("assignCompModel").value = tpl.compensation_model;
        onCompModelChange();
        autoCalculateBreakdown();
    }

    function autoCalculateMonthlyGross() {
        const ctc = parseFloat(document.getElementById("assignAnnualCtc").value) || 0;
        if (ctc > 0) {
            document.getElementById("assignMonthlyGross").value = (ctc / 12.0).toFixed(2);
            autoCalculateBreakdown();
        }
    }

    function autoCalculateBreakdown() {
        const gross = parseFloat(document.getElementById("assignMonthlyGross").value) || 0;
        const ctc = parseFloat(document.getElementById("assignAnnualCtc").value) || 0;
        if (gross > 0 && ctc <= 0) {
            document.getElementById("assignAnnualCtc").value = (gross * 12.0).toFixed(2);
        }

        const tplId = parseInt(document.getElementById("assignTemplateSelect")?.value);
        const tpl = (globalTemplates || []).find(t => t.id === tplId);

        const basicPct = tpl && tpl.basic_percentage !== undefined ? tpl.basic_percentage : 50;
        const hraPct = tpl && tpl.hra_percentage !== undefined ? tpl.hra_percentage : 20;
        const daPct = tpl && tpl.da_percentage !== undefined ? tpl.da_percentage : 0;
        const conv = tpl && tpl.conveyance_fixed !== undefined ? tpl.conveyance_fixed : 1600;
        const med = tpl && tpl.medical_fixed !== undefined ? tpl.medical_fixed : 1250;

        const basic = Math.round(gross * (basicPct / 100.0) * 100) / 100;
        const da = Math.round(gross * (daPct / 100.0) * 100) / 100;
        const hra = Math.round(basic * (hraPct / 100.0) * 100) / 100;
        const specified = basic + da + hra + conv + med;
        const special = Math.max(0, Math.round((gross - specified) * 100) / 100);

        document.getElementById("assignMonthlyBasic").value = basic;
        document.getElementById("assignMonthlyHra").value = hra;
        document.getElementById("assignConveyance").value = conv;
        document.getElementById("assignMedical").value = med;
        document.getElementById("assignSpecialAllowance").value = special;

        document.getElementById("assignDailyRate").value = (gross / 26.0).toFixed(2);
        document.getElementById("assignHourlyRate").value = (gross / (26.0 * 8.0)).toFixed(2);
    }

    async function submitAssignStructure(e) {
        e.preventDefault();
        const studentId = parseInt(document.getElementById("assignStudentId").value);
        const tplId = document.getElementById("assignTemplateSelect").value ? parseInt(document.getElementById("assignTemplateSelect").value) : null;
        const model = document.getElementById("assignCompModel").value;
        const ctc = parseFloat(document.getElementById("assignAnnualCtc").value) || 0;
        const gross = parseFloat(document.getElementById("assignMonthlyGross").value) || 0;
        const basic = parseFloat(document.getElementById("assignMonthlyBasic").value) || 0;
        const hra = parseFloat(document.getElementById("assignMonthlyHra").value) || 0;
        const conv = parseFloat(document.getElementById("assignConveyance").value) || 0;
        const med = parseFloat(document.getElementById("assignMedical").value) || 0;
        const special = parseFloat(document.getElementById("assignSpecialAllowance").value) || 0;
        const hourly = parseFloat(document.getElementById("assignHourlyRate").value) || 0;
        const daily = parseFloat(document.getElementById("assignDailyRate").value) || 0;
        let effDate = document.getElementById("assignEffectiveFrom").value;
        if (!effDate || !effDate.trim()) {
            effDate = new Date().toISOString().split('T')[0];
        }
        const reason = document.getElementById("assignRevisionReason").value;

        const saveBtn = document.getElementById("btnSaveStructure");
        const alertBox = document.getElementById("assignStructureAlert");

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        try {
            const res = await fetch("/api/v1/payroll/structure/assign", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_id: studentId,
                    template_id: tplId,
                    compensation_model: model,
                    annual_ctc: ctc,
                    monthly_gross: gross,
                    monthly_basic: basic,
                    monthly_hra: hra,
                    conveyance_allowance: conv,
                    medical_allowance: med,
                    special_allowance: special,
                    hourly_rate: hourly,
                    daily_rate: daily,
                    effective_from_date: effDate,
                    revision_reason: reason,
                }),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;

                setTimeout(() => {
                    closeAssignStructureModal();
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Apply Structure';
                    loadEmployeeStructures();
                }, 600);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Assignment failed.");
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Apply Structure';
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Apply Structure';
        }
    }

    // Statutory & Banking Modal
    function openStatutoryBankingModal(studentId) {
        const modal = document.getElementById("statutoryBankingModal");
        if (!modal) return;

        const emp = globalEmployees.find(e => e.id === studentId);
        if (!emp) return;

        document.getElementById("bankStudentId").value = emp.id;
        document.getElementById("statutoryBankingSubtitle").innerText = `Employee: ${emp.name} (${emp.roll_number})`;
        document.getElementById("bankPanNumber").value = emp.pan_number || "";
        document.getElementById("bankUanNumber").value = emp.uan_number || "";
        document.getElementById("bankEsicNumber").value = emp.esic_number || "";
        document.getElementById("bankNameInput").value = emp.bank_name || "";
        document.getElementById("bankAccountInput").value = emp.bank_account_number || "";
        document.getElementById("bankIfscInput").value = emp.bank_ifsc_code || "";

        const alertBox = document.getElementById("statutoryBankingAlert");
        if (alertBox) alertBox.style.display = "none";

        modal.classList.add("active");
    }

    function closeStatutoryBankingModal() {
        const modal = document.getElementById("statutoryBankingModal");
        if (modal) modal.classList.remove("active");
    }

    async function submitStatutoryBanking(e) {
        e.preventDefault();
        const studentId = parseInt(document.getElementById("bankStudentId").value);
        const pan = document.getElementById("bankPanNumber").value;
        const uan = document.getElementById("bankUanNumber").value;
        const esic = document.getElementById("bankEsicNumber").value;
        const bankName = document.getElementById("bankNameInput").value;
        const acct = document.getElementById("bankAccountInput").value;
        const ifsc = document.getElementById("bankIfscInput").value;

        const saveBtn = document.getElementById("btnSaveBanking");
        const alertBox = document.getElementById("statutoryBankingAlert");

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        try {
            const res = await fetch(`/api/v1/payroll/employee/${studentId}/statutory-banking`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_id: studentId,
                    pan_number: pan,
                    uan_number: uan,
                    esic_number: esic,
                    bank_name: bankName,
                    bank_account_number: acct,
                    bank_ifsc_code: ifsc,
                }),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;

                setTimeout(() => {
                    closeStatutoryBankingModal();
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Update Details';
                    loadEmployeeStructures();
                }, 600);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Update failed.");
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Update Details';
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Update Details';
        }
    }

    // Revision History Timeline Modal
    async function openRevisionHistoryModal(studentId) {
        const modal = document.getElementById("revisionHistoryModal");
        if (!modal) return;
        modal.classList.add("active");

        const timelineBox = document.getElementById("revisionHistoryTimeline");
        timelineBox.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Fetching revision timeline...</div>`;

        try {
            const res = await fetch(`/api/v1/payroll/employee/${studentId}/structure`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to load history");

            document.getElementById("revisionHistorySubtitle").innerText = `Employee: ${data.employee.name} (${data.employee.roll_number})`;
            const history = data.revision_history || [];

            if (history.length === 0) {
                timelineBox.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted);">No revision history recorded yet. Initial structure is active.</div>`;
                return;
            }

            timelineBox.innerHTML = history.map(h => {
                const incBadge = h.increment_percentage > 0 ? `<span class="badge badge-present">+${h.increment_percentage}% Increment</span>` : '';
                return `
                    <div style="border-left: 3px solid var(--accent-primary); padding-left: 14px; margin-bottom: 18px; position: relative;">
                        <div style="font-size: 13px; font-weight: 700; color: var(--text-heading); display: flex; justify-content: space-between; align-items: center;">
                            <span>Effective From: ${h.effective_from_date}</span>
                            ${incBadge}
                        </div>
                        <div style="font-size: 12.5px; margin-top: 4px;">
                            <strong>₹${h.new_monthly_gross.toLocaleString(undefined, {minimumFractionDigits: 2})}/mo</strong>
                            <span style="color: var(--text-muted);"> (Annual CTC: ₹${h.new_annual_ctc.toLocaleString(undefined, {minimumFractionDigits: 2})})</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                            Model: <code>${h.new_model}</code> • Reason: <em>${h.revision_reason || 'N/A'}</em>
                        </div>
                    </div>
                `;
            }).join("");

        } catch (e) {
            timelineBox.innerHTML = `<div style="text-align: center; color: var(--accent-rose); padding: 20px;">Error: ${e.message}</div>`;
        }
    }

    function closeRevisionHistoryModal() {
        const modal = document.getElementById("revisionHistoryModal");
        if (modal) modal.classList.remove("active");
    }

    // =========================================================================
    // 3. SALARY TEMPLATES CRUD
    // =========================================================================

    async function loadSalaryTemplates() {
        const tableBody = document.getElementById("templatesTableBody");
        if (!tableBody) return;

        try {
            const res = await fetch("/api/v1/payroll/masters/templates");
            const data = await res.json();
            if (res.ok) {
                globalTemplates = data.data || [];
                renderSalaryTemplatesTable(globalTemplates);
            }
        } catch (e) {
            tableBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--accent-rose);">Failed to load templates.</td></tr>`;
        }
    }

    function toggleTemplateComponentVisibility() {
        const model = document.getElementById("tplModalModel")?.value;
        const breakdownSec = document.getElementById("tplComponentBreakdownSection");
        const basicInput = document.getElementById("tplModalBasicPct");
        const hraInput = document.getElementById("tplModalHraPct");
        if (!breakdownSec) return;
        if (model === "STRUCTURED_SALARY") {
            breakdownSec.style.display = "block";
            if (basicInput) basicInput.required = true;
            if (hraInput) hraInput.required = true;
        } else {
            breakdownSec.style.display = "none";
            if (basicInput) basicInput.required = false;
            if (hraInput) hraInput.required = false;
        }
    }

    function renderSalaryTemplatesTable(templates) {
        const tableBody = document.getElementById("templatesTableBody");
        if (!tableBody) return;

        if (!templates || templates.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 24px; color: var(--text-muted);">No salary templates created yet. Click "Create Template" to add one.</td></tr>`;
            return;
        }

        tableBody.innerHTML = templates.map(t => {
            const safeName = (t.name || "").replace(/'/g, "\\'");
            const isStructured = (t.compensation_model === 'STRUCTURED_SALARY');
            const statusBadge = (t.is_active !== false) ? '<span class="badge badge-present">Active</span>' : '<span class="badge badge-node">Inactive</span>';
            const breakdownStr = isStructured 
                ? `HRA: ${t.hra_percentage}%${t.da_percentage > 0 ? ' • DA: ' + t.da_percentage + '%' : ''}`
                : '<span style="color: var(--text-muted); font-size: 11px;">Standard Base</span>';
            const fixedStr = isStructured
                ? `TA: ₹${t.conveyance_fixed} • Med: ₹${t.medical_fixed}${t.other_perks_fixed > 0 ? ' • Perks: ₹' + t.other_perks_fixed : ''}`
                : '<span style="color: var(--text-muted); font-size: 11px;">--</span>';

            return `
                <tr>
                    <td>
                        <strong>${t.name}</strong>
                        <div style="margin-top: 3px;">${statusBadge}</div>
                    </td>
                    <td><code>${t.code}</code></td>
                    <td><span class="badge badge-node">${(t.compensation_model || 'STRUCTURED_SALARY').replace('_', ' ')}</span></td>
                    <td>${breakdownStr}</td>
                    <td>${fixedStr}</td>
                    <td>
                        ${t.enable_pf ? '<span class="badge badge-indigo" style="font-size: 10px;">PF</span> ' : ''}
                        ${t.enable_esi ? '<span class="badge badge-sky" style="font-size: 10px;">ESI</span> ' : ''}
                        ${t.enable_pt ? '<span class="badge badge-amber" style="font-size: 10px;">PT</span>' : ''}
                    </td>
                    <td><span class="badge ${t.assigned_count > 0 ? 'badge-present' : 'badge-node'}">${t.assigned_count} Assigned</span></td>
                    <td>
                        <div style="display: flex; gap: 6px;">
                            <button onclick="openEditTemplateModal(${t.id})" class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" title="Edit Template">
                                <i class="fa-solid fa-pen-to-square"></i> Edit
                            </button>
                            <button onclick="deleteTemplate(${t.id}, '${safeName}')" class="btn btn-danger" style="padding: 4px 8px; font-size: 11px;" title="Delete Template">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function openCreateTemplateModal() {
        document.getElementById("tplModalId").value = "";
        document.getElementById("salaryTemplateModalTitle").innerHTML = '<i class="fa-solid fa-layer-group" style="color: var(--accent-primary);"></i> <span>Create Salary Template</span>';
        document.getElementById("salaryTemplateForm").reset();
        document.getElementById("tplModalModel").value = "STRUCTURED_SALARY";
        document.getElementById("tplModalHraPct").value = "20";
        document.getElementById("tplModalDaPct").value = "0";
        document.getElementById("tplModalConvFixed").value = "1600";
        document.getElementById("tplModalMedFixed").value = "1250";
        if (document.getElementById("tplModalOtherPerksFixed")) document.getElementById("tplModalOtherPerksFixed").value = "0";
        document.getElementById("tplModalEnablePf").checked = true;
        document.getElementById("tplModalPfCeiling").checked = true;
        document.getElementById("tplModalEnableEsi").checked = true;
        document.getElementById("tplModalEnablePt").checked = true;
        document.getElementById("tplModalIsActive").value = "true";

        toggleTemplateComponentVisibility();

        const alertBox = document.getElementById("salaryTemplateModalAlert");
        if (alertBox) alertBox.style.display = "none";

        const modal = document.getElementById("salaryTemplateModal");
        if (modal) modal.classList.add("active");
    }

    async function openEditTemplateModal(tplId) {
        let tpl = globalTemplates.find(t => t.id === tplId);
        if (!tpl) {
            try {
                const res = await fetch(`/api/v1/payroll/masters/templates/${tplId}`);
                const data = await res.json();
                if (res.ok && data.data) tpl = data.data;
            } catch (e) {}
        }
        if (!tpl) {
            alert("Could not load salary template details.");
            return;
        }

        document.getElementById("tplModalId").value = tpl.id;
        document.getElementById("salaryTemplateModalTitle").innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Salary Template</span>';
        document.getElementById("tplModalName").value = tpl.name || "";
        document.getElementById("tplModalCode").value = tpl.code || "";
        document.getElementById("tplModalModel").value = tpl.compensation_model || "STRUCTURED_SALARY";
        document.getElementById("tplModalHraPct").value = tpl.hra_percentage !== undefined ? tpl.hra_percentage : 20;
        document.getElementById("tplModalDaPct").value = tpl.da_percentage !== undefined ? tpl.da_percentage : 0;
        document.getElementById("tplModalConvFixed").value = tpl.conveyance_fixed !== undefined ? tpl.conveyance_fixed : 1600;
        document.getElementById("tplModalMedFixed").value = tpl.medical_fixed !== undefined ? tpl.medical_fixed : 1250;
        if (document.getElementById("tplModalOtherPerksFixed")) document.getElementById("tplModalOtherPerksFixed").value = tpl.other_perks_fixed !== undefined ? tpl.other_perks_fixed : 0;
        document.getElementById("tplModalEnablePf").checked = Boolean(tpl.enable_pf);
        document.getElementById("tplModalPfCeiling").checked = Boolean(tpl.pf_capped_at_ceiling);
        document.getElementById("tplModalEnableEsi").checked = Boolean(tpl.enable_esi);
        document.getElementById("tplModalEnablePt").checked = Boolean(tpl.enable_pt);
        document.getElementById("tplModalDescription").value = tpl.description || "";
        document.getElementById("tplModalIsActive").value = (tpl.is_active !== false) ? "true" : "false";

        toggleTemplateComponentVisibility();

        const alertBox = document.getElementById("salaryTemplateModalAlert");
        if (alertBox) alertBox.style.display = "none";

        const modal = document.getElementById("salaryTemplateModal");
        if (modal) modal.classList.add("active");
    }

    function closeTemplateModal() {
        const modal = document.getElementById("salaryTemplateModal");
        if (modal) modal.classList.remove("active");
    }

    async function submitTemplateForm(e) {
        e.preventDefault();
        const tplId = document.getElementById("tplModalId").value;
        const name = document.getElementById("tplModalName").value.trim();
        const code = document.getElementById("tplModalCode").value.trim().toUpperCase();
        const model = document.getElementById("tplModalModel").value;
        const isStructured = (model === "STRUCTURED_SALARY");
        const hraPct = isStructured ? (parseFloat(document.getElementById("tplModalHraPct").value) || 0) : 0;
        const daPct = isStructured ? (parseFloat(document.getElementById("tplModalDaPct").value) || 0) : 0;
        const convFixed = isStructured ? (parseFloat(document.getElementById("tplModalConvFixed").value) || 0) : 0;
        const medFixed = isStructured ? (parseFloat(document.getElementById("tplModalMedFixed").value) || 0) : 0;
        const otherPerksFixed = isStructured && document.getElementById("tplModalOtherPerksFixed") ? (parseFloat(document.getElementById("tplModalOtherPerksFixed").value) || 0) : 0;
        const enablePf = document.getElementById("tplModalEnablePf").checked;
        const pfCeiling = document.getElementById("tplModalPfCeiling").checked;
        const enableEsi = document.getElementById("tplModalEnableEsi").checked;
        const enablePt = document.getElementById("tplModalEnablePt").checked;
        const desc = document.getElementById("tplModalDescription").value.trim();
        const isActive = document.getElementById("tplModalIsActive").value === "true";

        const payload = {
            name: name,
            code: code,
            compensation_model: model,
            description: desc || null,
            hra_percentage: hraPct,
            da_percentage: daPct,
            conveyance_fixed: convFixed,
            medical_fixed: medFixed,
            other_perks_fixed: otherPerksFixed,
            enable_pf: enablePf,
            pf_capped_at_ceiling: pfCeiling,
            enable_esi: enableEsi,
            enable_pt: enablePt,
            is_active: isActive,
        };

        const saveBtn = document.getElementById("btnSaveTemplate");
        const alertBox = document.getElementById("salaryTemplateModalAlert");

        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const url = tplId ? `/api/v1/payroll/masters/templates/${tplId}` : "/api/v1/payroll/masters/templates";
        const method = tplId ? "PUT" : "POST";

        try {
            const res = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (res.ok) {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-emerald-bg)";
                alertBox.style.color = "var(--badge-emerald-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Template saved successfully!");

                setTimeout(() => {
                    closeTemplateModal();
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Template';
                    loadSalaryTemplates();
                }, 600);
            } else {
                alertBox.style.display = "block";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Save failed.");
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Template';
            }
        } catch (e) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Template';
        }
    }

    async function deleteTemplate(tplId, name) {
        if (!confirm(`Are you sure you want to delete salary template '${name}'?`)) return;

        try {
            const res = await fetch(`/api/v1/payroll/masters/templates/${tplId}`, {
                method: "DELETE",
            });
            const data = await res.json();

            if (res.ok) {
                alert(data.message || "Template deleted successfully.");
                loadSalaryTemplates();
            } else {
                alert("Cannot delete template: " + (data.detail || "Action failed"));
            }
        } catch (e) {
            alert("Network error deleting template.");
        }
    }

    // =========================================================================
    // 4. ORGANIZATION MASTERS (LOCATIONS, DESIGNATIONS) & STATUTORY SETTINGS
    // =========================================================================

    async function loadOrganizationMasters() {
        try {
            const desigRes = await fetch("/api/v1/payroll/masters/designations");
            const desigData = await desigRes.json();
            if (desigRes.ok) {
                globalDesignations = desigData.data || [];
                const desigBody = document.getElementById("designationsTableBody");
                if (desigBody) {
                    if (globalDesignations.length === 0) {
                        desigBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 16px; color: var(--text-muted);">No designations found. Register designations in Settings &gt; Designations.</td></tr>';
                    } else {
                        desigBody.innerHTML = globalDesignations.map(d => {
                            const statusBadge = d.is_active ? '<span class="badge badge-present">Active</span>' : '<span class="badge badge-node">Inactive</span>';
                            const tplBadge = d.salary_template_name 
                                ? `<span class="badge badge-indigo" title="Template Code: ${escapeHtml(d.salary_template_code || 'N/A')}"><i class="fa-solid fa-layer-group"></i> ${escapeHtml(d.salary_template_name)}</span>` 
                                : '<span class="badge badge-node">No Template</span>';
                            return `
                                <tr>
                                    <td>
                                        <strong>${escapeHtml(d.title)}</strong>
                                        <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">Code: ${escapeHtml(d.code || 'N/A')}</div>
                                    </td>
                                    <td>${tplBadge}</td>
                                    <td><span class="badge ${d.assigned_employees_count > 0 ? 'badge-indigo' : 'badge-node'}">${d.assigned_employees_count} Employees</span></td>
                                    <td>
                                        <div style="display: flex; gap: 6px; align-items: center;">
                                            ${statusBadge}
                                            <button onclick="openEditDesignationModal(${d.id})" class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" title="Edit Salary Structure Mapping">
                                                <i class="fa-solid fa-pen-to-square"></i> Map Structure
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }).join("");
                    }
                }
            }
        } catch (e) {
            console.error("Failed to load masters", e);
        }
    }

    // --- Designations & Salary Structure Mapping Handlers ---
    function populateDesignationSelectOptions(selectedDesigId) {
        const sel = document.getElementById("desigModalSelect");
        if (!sel) return;
        let html = '<option value="">-- Choose Designation from Settings --</option>';
        (globalDesignations || []).forEach(d => {
            const isSelected = selectedDesigId && parseInt(selectedDesigId) === parseInt(d.id) ? ' selected' : '';
            html += `<option value="${d.id}" data-code="${escapeHtml(d.code || '')}" data-dept="${escapeHtml(d.department_name || 'All Departments')}" data-template-id="${d.salary_template_id || ''}" data-active="${d.is_active ? 'true' : 'false'}"${isSelected}>${escapeHtml(d.title)} (${escapeHtml(d.code || 'N/A')})</option>`;
        });
        sel.innerHTML = html;
        if (selectedDesigId) {
            sel.value = selectedDesigId;
        }
    }

    function onMappingDesignationSelected() {
        const sel = document.getElementById("desigModalSelect");
        if (!sel) return;
        const desigId = parseInt(sel.value);
        const codeInput = document.getElementById("desigModalCode");
        const deptInput = document.getElementById("desigModalDeptName");
        const tplSelect = document.getElementById("desigModalSalaryTemplate");
        const statusInput = document.getElementById("desigModalStatusDisplay");
        const idHidden = document.getElementById("desigModalId");

        if (!desigId) {
            if (idHidden) idHidden.value = "";
            if (codeInput) codeInput.value = "";
            if (deptInput) deptInput.value = "";
            if (tplSelect) tplSelect.value = "";
            if (statusInput) statusInput.value = "Active";
            return;
        }

        if (idHidden) idHidden.value = desigId;
        const desig = (globalDesignations || []).find(d => d.id === desigId);
        if (desig) {
            if (codeInput) codeInput.value = desig.code || "";
            if (deptInput) deptInput.value = desig.department_name || "All Departments";
            if (tplSelect) tplSelect.value = desig.salary_template_id || "";
            if (statusInput) statusInput.value = desig.is_active ? "Active" : "Inactive";
        } else {
            const opt = sel.options[sel.selectedIndex];
            if (opt) {
                if (codeInput) codeInput.value = opt.getAttribute("data-code") || "";
                if (deptInput) deptInput.value = opt.getAttribute("data-dept") || "All Departments";
                if (tplSelect) tplSelect.value = opt.getAttribute("data-template-id") || "";
                if (statusInput) statusInput.value = opt.getAttribute("data-active") === "false" ? "Inactive" : "Active";
            }
        }
    }

    function populateDesignationTemplateSelect(selectedId) {
        const sel = document.getElementById("desigModalSalaryTemplate");
        if (!sel) return;
        let html = '<option value="">-- No Default Template / Clear Mapping --</option>';
        (globalTemplates || []).forEach(t => {
            const isSelected = selectedId && parseInt(selectedId) === parseInt(t.id) ? ' selected' : '';
            const modelLabel = (t.compensation_model || '').replace(/_/g, ' ');
            html += `<option value="${t.id}"${isSelected}>${escapeHtml(t.name)} (${escapeHtml(t.code || '')}) - ${escapeHtml(modelLabel)}</option>`;
        });
        sel.innerHTML = html;
        if (selectedId !== undefined && selectedId !== null) {
            sel.value = selectedId;
        }
    }

    function openCreateDesignationModal() {
        const idHidden = document.getElementById("desigModalId");
        if (idHidden) idHidden.value = "";
        
        const titleEl = document.getElementById("designationModalTitle");
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-user-tag" style="color: var(--accent-primary);"></i> <span>Map Designation to Salary Structure</span>';
        
        const form = document.getElementById("designationForm");
        if (form) form.reset();

        const desigSelect = document.getElementById("desigModalSelect");
        if (desigSelect) {
            desigSelect.disabled = false;
            populateDesignationSelectOptions("");
        }
        populateDesignationTemplateSelect("");

        const codeInput = document.getElementById("desigModalCode");
        if (codeInput) codeInput.value = "";
        const deptInput = document.getElementById("desigModalDeptName");
        if (deptInput) deptInput.value = "";
        const statusInput = document.getElementById("desigModalStatusDisplay");
        if (statusInput) statusInput.value = "Active";

        const alertBox = document.getElementById("designationModalAlert");
        if (alertBox) alertBox.style.display = "none";
        const saveBtn = document.getElementById("btnSaveDesignation");
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Salary Mapping';
        }
        const modal = document.getElementById("designationModal");
        if (modal) modal.classList.add("active");
    }

    async function openEditDesignationModal(desigId) {
        let desig = (globalDesignations || []).find(d => d.id === desigId);
        if (!desig) {
            try {
                const res = await fetch(`/api/v1/payroll/masters/designations/${desigId}`);
                const data = await res.json();
                if (res.ok && data.data) desig = data.data;
            } catch (e) {}
        }
        if (!desig) {
            alert("Designation details could not be loaded.");
            return;
        }

        const idHidden = document.getElementById("desigModalId");
        if (idHidden) idHidden.value = desig.id;
        
        const titleEl = document.getElementById("designationModalTitle");
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Designation Salary Mapping</span>';

        populateDesignationSelectOptions(desig.id);
        const desigSelect = document.getElementById("desigModalSelect");
        if (desigSelect) {
            desigSelect.value = desig.id;
            desigSelect.disabled = true;
        }

        const codeInput = document.getElementById("desigModalCode");
        if (codeInput) codeInput.value = desig.code || "";
        const deptInput = document.getElementById("desigModalDeptName");
        if (deptInput) deptInput.value = desig.department_name || "All Departments";
        populateDesignationTemplateSelect(desig.salary_template_id || "");
        const statusInput = document.getElementById("desigModalStatusDisplay");
        if (statusInput) statusInput.value = desig.is_active ? "Active" : "Inactive";

        const alertBox = document.getElementById("designationModalAlert");
        if (alertBox) alertBox.style.display = "none";
        const saveBtn = document.getElementById("btnSaveDesignation");
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Salary Mapping';
        }
        const modal = document.getElementById("designationModal");
        if (modal) modal.classList.add("active");
    }

    function closeDesignationModal() {
        const modal = document.getElementById("designationModal");
        if (modal) modal.classList.remove("active");
    }

    async function submitDesignationForm(e) {
        e.preventDefault();
        const idHiddenVal = document.getElementById("desigModalId")?.value;
        const selectVal = document.getElementById("desigModalSelect")?.value;
        const desigId = parseInt(idHiddenVal) || parseInt(selectVal);
        if (!desigId) {
            alert("Please select a designation to map.");
            return;
        }

        const tplVal = document.getElementById("desigModalSalaryTemplate")?.value;
        const tplId = tplVal ? parseInt(tplVal) : null;

        const payload = {
            salary_template_id: tplId
        };

        const saveBtn = document.getElementById("btnSaveDesignation");
        const alertBox = document.getElementById("designationModalAlert");

        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        }

        const url = `/api/v1/payroll/masters/designations/${desigId}`;

        try {
            const res = await fetch(url, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (res.ok) {
                if (alertBox) {
                    alertBox.style.display = "block";
                    alertBox.style.background = "var(--badge-emerald-bg)";
                    alertBox.style.color = "var(--badge-emerald-text)";
                    alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Salary structure mapping saved successfully!");
                }

                setTimeout(() => {
                    closeDesignationModal();
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Salary Mapping';
                    }
                    loadOrganizationMasters();
                }, 600);
            } else {
                if (alertBox) {
                    alertBox.style.display = "block";
                    alertBox.style.background = "var(--badge-rose-bg)";
                    alertBox.style.color = "var(--badge-rose-text)";
                    alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Save failed.");
                }
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Salary Mapping';
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
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Salary Mapping';
            }
        }
    }

    // =========================================================================
    // 5. REAL-TIME ESTIMATOR
    // =========================================================================

    let searchDebounceTimer = null;
    function debouncePayrollSearch() {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(loadPayrollSummary, 300);
    }

    async function loadPayrollSummary() {
        const startDate = document.getElementById("payrollStartDate")?.value || "";
        const endDate = document.getElementById("payrollEndDate")?.value || "";
        const deptId = document.getElementById("payrollDeptFilter")?.value || "";
        const search = document.getElementById("payrollSearchInput")?.value || "";
        const tableBody = document.getElementById("payrollTableBody");

        if (!tableBody) return;
        tableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Calculating attendance...</td></tr>`;

        let url = `/api/v1/payroll/summary?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
        if (deptId) url += `&department_id=${encodeURIComponent(deptId)}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;

        try {
            const res = await fetch(url);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to load summary");

            tableBody.innerHTML = (data.items || []).map(emp => `
                <tr>
                    <td><strong>${emp.name}</strong></td>
                    <td><code>${emp.roll_number}</code></td>
                    <td><span class="badge badge-indigo">${emp.department || 'General'}</span></td>
                    <td><span style="font-family: monospace;">${emp.days_worked}</span></td>
                    <td><strong style="color: var(--accent-primary); font-family: monospace;">${emp.total_active_hours} hrs</strong></td>
                    <td><span style="font-family: monospace;">₹${emp.hourly_rate.toFixed(2)}</span></td>
                    <td><strong style="font-family: monospace;">₹${emp.gross_pay.toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                    <td><strong style="color: var(--accent-emerald); font-family: monospace;">₹${(emp.net_pay || emp.gross_pay).toLocaleString(undefined, {minimumFractionDigits: 2})}</strong></td>
                    <td><span class="badge badge-present">Compliant</span></td>
                </tr>
            `).join("") || '<tr><td colspan="9" style="text-align:center; padding: 24px; color: var(--text-muted);">No records found.</td></tr>';
        } catch (e) {
            tableBody.innerHTML = `<tr><td colspan="9" style="text-align:center; color: var(--accent-rose); padding: 20px;">Error: ${e.message}</td></tr>`;
        }
    }

    function exportPayroll(format) {
        const startDate = document.getElementById("payrollStartDate")?.value || "";
        const endDate = document.getElementById("payrollEndDate")?.value || "";
        const deptId = document.getElementById("payrollDeptFilter")?.value || "";
        const search = document.getElementById("payrollSearchInput")?.value || "";

        let url = `/api/v1/payroll/export?export_format=${format}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
        if (deptId) url += `&department_id=${encodeURIComponent(deptId)}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;

        window.location.href = url;
    }

    function openPayrollSettingsModal() {
        switchPayrollTab('masters');
    }

    async function loadPayrollSettings() {
        try {
            const res = await fetch("/api/v1/payroll/settings");
            const data = await res.json();
            if (res.ok && data.data) {
                const s = data.data;
                const setVal = (id, val) => {
                    const el = document.getElementById(id);
                    if (el && val !== undefined && val !== null) el.value = val;
                };
                setVal("cfgEpfEePct", s.epf_employee_pct);
                setVal("cfgEpfErPct", s.epf_employer_pct);
                setVal("cfgEpfCeiling", s.epf_wage_ceiling);
                setVal("cfgPfCeilingToggle", s.enable_pf_ceiling ? "true" : "false");
                setVal("cfgEsiEePct", s.esi_employee_pct);
                setVal("cfgEsiErPct", s.esi_employer_pct);
                setVal("cfgEsiThreshold", s.esi_gross_threshold);
                setVal("cfgPtMonthly", s.pt_monthly_default);
                setVal("cfgOtMultiplier", s.overtime_rate_multiplier);
                setVal("cfgHolidayOtMultiplier", s.holiday_ot_multiplier);
            }
        } catch (e) {
            console.error("Failed to load statutory settings", e);
        }
    }

    async function submitStatutorySettings(e) {
        e.preventDefault();
        const payload = {
            epf_employee_pct: parseFloat(document.getElementById("cfgEpfEePct")?.value) || 12.0,
            epf_employer_pct: parseFloat(document.getElementById("cfgEpfErPct")?.value) || 12.0,
            epf_wage_ceiling: parseFloat(document.getElementById("cfgEpfCeiling")?.value) || 15000.0,
            enable_pf_ceiling: document.getElementById("cfgPfCeilingToggle")?.value === "true",
            esi_employee_pct: parseFloat(document.getElementById("cfgEsiEePct")?.value) || 0.75,
            esi_employer_pct: parseFloat(document.getElementById("cfgEsiErPct")?.value) || 3.25,
            esi_gross_threshold: parseFloat(document.getElementById("cfgEsiThreshold")?.value) || 21000.0,
            pt_monthly_default: parseFloat(document.getElementById("cfgPtMonthly")?.value) || 200.0,
            overtime_rate_multiplier: parseFloat(document.getElementById("cfgOtMultiplier")?.value) || 1.5,
            holiday_ot_multiplier: parseFloat(document.getElementById("cfgHolidayOtMultiplier")?.value) || 2.0,
        };

        const saveBtn = document.getElementById("btnSaveStatutorySettings");
        const alertBox = document.getElementById("statutorySettingsAlert");

        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        }

        try {
            const res = await fetch("/api/v1/payroll/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (res.ok) {
                if (alertBox) {
                    alertBox.style.display = "inline-flex";
                    alertBox.style.background = "var(--badge-emerald-bg)";
                    alertBox.style.color = "var(--badge-emerald-text)";
                    alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || "Settings updated successfully!");
                }
                setTimeout(() => {
                    if (alertBox) alertBox.style.display = "none";
                    if (saveBtn) {
                        saveBtn.disabled = false;
                        saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Statutory & OT Settings';
                    }
                }, 3000);
            } else {
                if (alertBox) {
                    alertBox.style.display = "inline-flex";
                    alertBox.style.background = "var(--badge-rose-bg)";
                    alertBox.style.color = "var(--badge-rose-text)";
                    alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || "Update failed.");
                }
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Statutory & OT Settings';
                }
            }
        } catch (e) {
            if (alertBox) {
                alertBox.style.display = "inline-flex";
                alertBox.style.background = "var(--badge-rose-bg)";
                alertBox.style.color = "var(--badge-rose-text)";
                alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error.';
            }
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Statutory & OT Settings';
            }
        }
    }
