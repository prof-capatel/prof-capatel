    let globalTenantsData = [];
    let globalPlansData = [];

    document.addEventListener("DOMContentLoaded", () => {
        refreshAllSuperAdminData();
    });

    async function refreshAllSuperAdminData() {
        await Promise.all([
            loadSubscriptionPlans(),
            loadSuperAdminMetrics(),
            loadTenantsList(),
            loadSeoData(),
        ]);
    }

    // --- Subscription Plans Logic ---
    async function loadSubscriptionPlans() {
        try {
            const res = await fetch("/api/v1/super-admin/plans");
            const data = await res.json();
            if (res.ok && data.plans) {
                globalPlansData = data.plans;
                populatePlanSelectDropdowns();
                renderPlansTable();
            }
        } catch (e) {
            console.error("Error loading subscription plans:", e);
        }
    }

    function populatePlanSelectDropdowns() {
        const createSelect = document.getElementById("newTenantPlan");
        const editSelect = document.getElementById("editTenantPlan");

        const optionsHtml = globalPlansData.map(p => `
            <option value="${p.plan_code}" data-faces="${p.max_face_encodings}" data-nodes="${p.max_nodes}">
                ${p.name} (${p.max_face_encodings} Faces, ${p.max_nodes} Nodes)
            </option>
        `).join("");

        if (createSelect) {
            createSelect.innerHTML = optionsHtml;
            // Set initial defaults
            if (globalPlansData.length > 0) {
                onPlanSelectionChanged(globalPlansData[0].plan_code);
            }
        }
        if (editSelect) {
            editSelect.innerHTML = optionsHtml;
        }
    }

    function renderPlansTable() {
        const tbody = document.getElementById("plansTableBody");
        if (!tbody) return;

        if (globalPlansData.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 16px;">No plans configured.</td></tr>`;
            return;
        }

        tbody.innerHTML = globalPlansData.map(p => `
            <tr>
                <td>
                    <div style="font-weight: 700; font-size: 13px;">${p.name}</div>
                    <div style="font-size: 11px; font-family: monospace; color: var(--accent-primary);">${p.plan_code}</div>
                </td>
                <td style="font-weight: 700;">${p.max_face_encodings.toLocaleString()}</td>
                <td style="font-weight: 700;">${p.max_nodes}</td>
                <td style="font-family: monospace; font-weight: 600;">₹${p.price_monthly.toLocaleString()}</td>
                <td style="text-align: right;">
                    <span class="badge ${p.is_active ? 'badge-present' : 'badge-slate'}" style="font-size: 10px;">
                        ${p.is_active ? 'Active' : 'Inactive'}
                    </span>
                </td>
            </tr>
        `).join("");
    }

    function onPlanSelectionChanged(planCode) {
        const plan = globalPlansData.find(p => p.plan_code === planCode);
        if (plan) {
            document.getElementById("newTenantMaxFaces").value = plan.max_face_encodings;
            document.getElementById("newTenantMaxNodes").value = plan.max_nodes;
        }
    }

    function onEditPlanChanged(planCode) {
        const isCustom = document.getElementById("editCustomQuotaToggle").checked;
        if (!isCustom) {
            const plan = globalPlansData.find(p => p.plan_code === planCode);
            if (plan) {
                document.getElementById("editTenantMaxFaces").value = plan.max_face_encodings;
                document.getElementById("editTenantMaxNodes").value = plan.max_nodes;
            }
        }
    }

    function toggleCustomQuotaEditing(enabled) {
        document.getElementById("editTenantMaxFaces").disabled = !enabled;
        document.getElementById("editTenantMaxNodes").disabled = !enabled;
    }

    function openPlansModal() {
        document.getElementById("plansModal").style.display = "flex";
        renderPlansTable();
    }

    function closePlansModal() {
        document.getElementById("plansModal").style.display = "none";
        document.getElementById("newPlanFormContainer").style.display = "none";
    }

    function toggleNewPlanForm() {
        const container = document.getElementById("newPlanFormContainer");
        container.style.display = (container.style.display === "none") ? "block" : "none";
    }

    async function submitNewSubscriptionPlan(e) {
        e.preventDefault();
        const payload = {
            plan_code: document.getElementById("newPlanCode").value.trim().toUpperCase(),
            name: document.getElementById("newPlanDisplayName").value.trim(),
            max_face_encodings: parseInt(document.getElementById("newPlanMaxFaces").value) || 500,
            max_nodes: parseInt(document.getElementById("newPlanMaxNodes").value) || 10,
            price_monthly: parseFloat(document.getElementById("newPlanPrice").value) || 0.0,
        };

        try {
            const res = await fetch("/api/v1/super-admin/plans", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok) {
                await loadSubscriptionPlans();
                toggleNewPlanForm();
                document.getElementById("newPlanForm").reset();
            } else {
                alert("Error: " + (data.detail || "Could not create plan."));
            }
        } catch (err) {
            alert("Network error creating plan.");
        }
    }

    // --- Metrics Logic ---
    async function loadSuperAdminMetrics() {
        try {
            const res = await fetch("/api/v1/super-admin/metrics");
            const data = await res.json();
            if (res.ok && data.metrics) {
                const m = data.metrics;
                document.getElementById("statTotalTenants").innerText = m.total_tenants;
                document.getElementById("statActiveTenantsBadge").innerText = `${m.active_tenants} Active`;
                document.getElementById("statSuspendedTenantsBadge").innerText = `${m.suspended_tenants} Suspended / ${m.deleted_tenants || 0} Deleted`;
                document.getElementById("statTotalVectors").innerText = m.total_face_vectors.toLocaleString();
                document.getElementById("statTotalStudentsBadge").innerText = `${m.total_students} Profiles`;
                document.getElementById("statTotalNodes").innerText = m.total_nodes;
                document.getElementById("statOnlineNodesBadge").innerText = `${m.online_nodes} Online`;
                document.getElementById("statTotalLogs").innerText = m.total_attendance_logs.toLocaleString();
                document.getElementById("statTodayLogsBadge").innerText = `${m.today_attendances} Today`;
            }
        } catch (e) {
            console.error("Metrics load error:", e);
        }
    }

    // --- Tenants Management Table & Filtering ---
    async function loadTenantsList() {
        try {
            const res = await fetch("/api/v1/super-admin/tenants?include_deleted=true");
            const data = await res.json();
            if (res.ok && data.tenants) {
                globalTenantsData = data.tenants;
                renderTenantsTable(globalTenantsData);
            }
        } catch (e) {
            console.error("Tenants load error:", e);
        }
    }

    function filterTenantsGrid() {
        const query = (document.getElementById("tenantSearchInput").value || "").toLowerCase().trim();
        const statusFilter = document.getElementById("tenantStatusFilter").value;
        const planFilter = document.getElementById("tenantPlanFilter").value;

        const filtered = globalTenantsData.filter(t => {
            const matchesSearch = !query || t.name.toLowerCase().includes(query) || t.slug.toLowerCase().includes(query);
            
            let matchesStatus = true;
            if (statusFilter === "ACTIVE") matchesStatus = (t.subscription_status === "ACTIVE" && !t.is_deleted);
            else if (statusFilter === "SUSPENDED") matchesStatus = (t.subscription_status === "SUSPENDED" && !t.is_deleted);
            else if (statusFilter === "DELETED") matchesStatus = t.is_deleted || t.subscription_status === "DELETED";

            let matchesPlan = true;
            if (planFilter !== "ALL") matchesPlan = (t.subscription_plan === planFilter);

            return matchesSearch && matchesStatus && matchesPlan;
        });

        renderTenantsTable(filtered);
    }

    function renderTenantsTable(tenants) {
        const tbody = document.getElementById("tenantsTableBody");
        const countLabel = document.getElementById("tenantsCountLabel");

        countLabel.innerText = `Showing ${tenants.length} of ${globalTenantsData.length} tenants`;

        if (tenants.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">No tenants match the filter criteria.</td></tr>`;
            return;
        }

        tbody.innerHTML = tenants.map(t => {
            const isDeleted = Boolean(t.is_deleted || t.subscription_status === 'DELETED');
            const isSuspended = (t.subscription_status === 'SUSPENDED' && !isDeleted);

            // Tier styling
            let planBadgeClass = 'badge-sky';
            if (t.subscription_plan === 'ENTERPRISE' || t.subscription_plan === 'PRO') planBadgeClass = 'badge-emerald';
            else if (t.subscription_plan === 'SMART') planBadgeClass = 'badge-indigo';
            else if (t.subscription_plan === 'FREE' || t.subscription_plan === 'BASIC') planBadgeClass = 'badge-slate';

            // Lifecycle Badge
            let statusPillHtml = '';
            if (isDeleted) {
                statusPillHtml = `<span class="badge badge-absent" style="font-size: 11px; font-weight: 700;"><i class="fa-solid fa-trash-can"></i> Deleted</span>`;
            } else if (isSuspended) {
                statusPillHtml = `<span class="badge badge-unknown" style="font-size: 11px; font-weight: 700;"><i class="fa-solid fa-pause"></i> Suspended (Read-Only)</span>`;
            } else {
                statusPillHtml = `<span class="badge badge-present" style="font-size: 11px; font-weight: 700;"><i class="fa-solid fa-circle-check"></i> Active</span>`;
            }

            // Quota bar colors
            const facePct = t.face_quota_pct || 0;
            const nodePct = t.node_quota_pct || 0;
            const faceColor = facePct > 90 ? 'var(--accent-rose)' : (facePct > 75 ? 'var(--accent-amber)' : 'var(--accent-emerald)');
            const nodeColor = nodePct > 90 ? 'var(--accent-rose)' : (nodePct > 75 ? 'var(--accent-amber)' : 'var(--accent-cyan)');

            const isCorporate = (t.tenant_type === 'corporate');
            const typeBadgeHtml = isCorporate
                ? `<span class="badge badge-emerald" style="font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><i class="fa-solid fa-building"></i> Company</span>`
                : `<span class="badge badge-sky" style="font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><i class="fa-solid fa-graduation-cap"></i> School / College</span>`;

            const rowStyle = isDeleted ? 'background: rgba(244, 63, 94, 0.04); opacity: 0.75;' : (isSuspended ? 'background: rgba(245, 158, 11, 0.03);' : '');

            return `
                <tr style="${rowStyle} border-bottom: 1px solid var(--border-subtle); transition: background 0.15s ease;">
                    <td style="padding: 14px 16px;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="width: 34px; height: 34px; border-radius: 8px; background: var(--bg-subtle); border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; color: ${isCorporate ? 'var(--accent-emerald)' : 'var(--accent-primary)'};">
                                ${t.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <span style="font-weight: 700; color: var(--text-heading); font-size: 13.5px;">${t.name}</span>
                                    ${typeBadgeHtml}
                                </div>
                                <div style="font-size: 11px; font-family: monospace; color: var(--text-muted); margin-top: 2px;">
                                    ID #${t.id} &bull; <span style="color: var(--accent-primary); font-weight: 600;">${t.slug}</span>
                                </div>
                            </div>
                        </div>
                    </td>

                    <td style="padding: 14px 16px;">
                        <span class="badge ${planBadgeClass}" style="font-size: 11px; font-weight: 800; letter-spacing: 0.3px;">
                            ${t.subscription_plan || 'STANDARD'}
                        </span>
                    </td>

                    <td style="padding: 14px 16px;">
                        ${statusPillHtml}
                    </td>

                    <td style="padding: 14px 16px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; margin-bottom: 4px;">
                            <span>${t.enrolled_faces_count} / ${t.max_face_encodings}</span>
                            <span style="color: ${faceColor}; font-size: 11px;">${facePct}%</span>
                        </div>
                        <div style="background: var(--border-color); height: 6px; border-radius: 3px; overflow: hidden; width: 120px;">
                            <div style="background: ${faceColor}; height: 100%; width: ${Math.min(100, facePct)}%; transition: width 0.3s ease;"></div>
                        </div>
                    </td>

                    <td style="padding: 14px 16px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 700; margin-bottom: 4px;">
                            <span>${t.active_nodes_count} / ${t.max_nodes}</span>
                            <span style="color: ${nodeColor}; font-size: 11px;">${nodePct}%</span>
                        </div>
                        <div style="background: var(--border-color); height: 6px; border-radius: 3px; overflow: hidden; width: 90px;">
                            <div style="background: ${nodeColor}; height: 100%; width: ${Math.min(100, nodePct)}%; transition: width 0.3s ease;"></div>
                        </div>
                    </td>

                    <td style="padding: 14px 16px;">
                        <div style="font-size: 12px; font-weight: 700; color: var(--text-heading);">${t.admin_username}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${t.admin_email}</div>
                    </td>

                    <td style="padding: 14px 16px; text-align: right;">
                        <div style="display: inline-flex; gap: 6px; align-items: center;">
                            <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-emerald);" onclick="openTenantLinksModal(${t.id})" title="View Tokenized Access Links">
                                <i class="fa-solid fa-link"></i> Links
                            </button>
                            ${isDeleted ? `
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-emerald);" onclick="restoreSoftDeletedTenant(${t.id}, '${t.name}')" title="Restore Tenant to ACTIVE">
                                    <i class="fa-solid fa-rotate-left"></i> Restore
                                </button>
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px;" onclick='openEditTenantModal(${JSON.stringify(t)})' title="Edit Tenant Details">
                                    <i class="fa-solid fa-pen"></i>
                                </button>
                            ` : `
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px;" onclick='openEditTenantModal(${JSON.stringify(t)})' title="Edit Tenant Details">
                                    <i class="fa-solid fa-pen"></i> Edit
                                </button>
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-amber);" onclick='openResetPasswordModal(${t.id}, "${t.name.replace(/"/g, '&quot;')}", "${t.admin_username}")' title="Reset Tenant Admin Password">
                                    <i class="fa-solid fa-key"></i> Password
                                </button>
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: ${isSuspended ? 'var(--accent-emerald)' : 'var(--accent-amber)'};" onclick="toggleTenantStatus(${t.id}, '${isSuspended ? 'ACTIVE' : 'SUSPENDED'}', '${t.name}')" title="${isSuspended ? 'Reactivate Tenant' : 'Suspend Tenant (Read-Only Mode)'}">
                                    <i class="fa-solid ${isSuspended ? 'fa-play' : 'fa-pause'}"></i> ${isSuspended ? 'Activate' : 'Suspend'}
                                </button>
                                <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; color: var(--accent-rose);" onclick="softDeleteTenant(${t.id}, '${t.name}')" title="Soft Delete Tenant">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            `}
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // --- Action Handlers: Suspend, Soft Delete, Restore ---
    async function toggleTenantStatus(tenantId, newStatus, tenantName) {
        const actionLabel = (newStatus === "SUSPENDED") 
            ? `SUSPEND '${tenantName}'?\n\nThis locks out operational features (attendance ingestion, new enrollments) while preserving read-only historical viewing.`
            : `REACTIVATE '${tenantName}' to ACTIVE operational state?`;

        if (!confirm(actionLabel)) return;

        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}/status`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus }),
            });
            const data = await res.json();
            if (res.ok) {
                refreshAllSuperAdminData();
            } else {
                alert("Error: " + (data.detail || "Could not update status."));
            }
        } catch (e) {
            alert("Network error updating status.");
        }
    }

    async function softDeleteTenant(tenantId, tenantName) {
        if (!confirm(`Are you sure you want to SOFT DELETE tenant '${tenantName}' (ID #${tenantId})?\n\nThis will deactivate user access immediately without wiping database rows. You can restore it anytime.`)) {
            return;
        }

        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}`, {
                method: "DELETE",
            });
            const data = await res.json();
            if (res.ok) {
                refreshAllSuperAdminData();
            } else {
                alert("Error: " + (data.detail || "Could not delete tenant."));
            }
        } catch (e) {
            alert("Network error soft deleting tenant.");
        }
    }

    async function restoreSoftDeletedTenant(tenantId, tenantName) {
        if (!confirm(`Restore '${tenantName}' (ID #${tenantId}) back to ACTIVE status?`)) return;

        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}/restore`, {
                method: "POST",
            });
            const data = await res.json();
            if (res.ok) {
                refreshAllSuperAdminData();
            } else {
                alert("Error: " + (data.detail || "Could not restore tenant."));
            }
        } catch (e) {
            alert("Network error restoring tenant.");
        }
    }

    // --- Modal: Provision New Tenant ---
    function openCreateTenantModal() {
        document.getElementById("createTenantModal").style.display = "flex";
        document.getElementById("createTenantAlert").style.display = "none";
        document.getElementById("createTenantForm").reset();
        document.getElementById("newTenantType").value = "educational";
        if (globalPlansData.length > 0) {
            onPlanSelectionChanged(globalPlansData[0].plan_code);
        }
    }

    function closeCreateTenantModal() {
        document.getElementById("createTenantModal").style.display = "none";
    }

    function autoGenerateSlug(name) {
        const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
        document.getElementById("newTenantSlug").value = slug;
    }

    async function submitCreateTenant(e) {
        e.preventDefault();
        const alertEl = document.getElementById("createTenantAlert");
        const btn = document.getElementById("btnSubmitTenant");
        alertEl.style.display = "none";
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Provisioning...`;

        const payload = {
            name: document.getElementById("newTenantName").value.trim(),
            slug: document.getElementById("newTenantSlug").value.trim(),
            tenant_type: document.getElementById("newTenantType").value,
            contact_email: document.getElementById("newTenantEmail").value.trim() || null,
            subscription_plan: document.getElementById("newTenantPlan").value,
            admin_full_name: document.getElementById("newAdminFullName").value.trim(),
            admin_username: document.getElementById("newAdminUsername").value.trim(),
            admin_password: document.getElementById("newAdminPassword").value,
        };

        try {
            const res = await fetch("/api/v1/super-admin/tenants", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();

            if (res.ok) {
                closeCreateTenantModal();
                refreshAllSuperAdminData();
                // Immediately display the generated tokenized URLs modal for the new tenant
                openTenantLinksModalFromData(data);
            } else {
                alertEl.style.display = "block";
                alertEl.style.background = "rgba(239, 68, 68, 0.1)";
                alertEl.style.border = "1px solid var(--accent-rose)";
                alertEl.style.color = "var(--accent-rose)";
                alertEl.innerText = data.detail || "Error provisioning tenant organization.";
            }
        } catch (err) {
            alertEl.style.display = "block";
            alertEl.style.background = "rgba(239, 68, 68, 0.1)";
            alertEl.style.border = "1px solid var(--accent-rose)";
            alertEl.style.color = "var(--accent-rose)";
            alertEl.innerText = "Network failure while provisioning tenant.";
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-check"></i> Provision Tenant`;
        }
    }

    // --- Modal: Edit Tenant Details ---
    function openEditTenantModal(tenant) {
        document.getElementById("editTenantId").value = tenant.id;
        document.getElementById("editTenantModalTitle").innerText = `Edit Tenant: ${tenant.name}`;
        document.getElementById("editTenantName").value = tenant.name;
        document.getElementById("editTenantType").value = tenant.tenant_type || "educational";
        document.getElementById("editTenantEmail").value = tenant.contact_email || "";
        document.getElementById("editTenantPlan").value = tenant.subscription_plan || "STANDARD";
        document.getElementById("editTenantStatus").value = tenant.is_deleted ? "DELETED" : (tenant.subscription_status || "ACTIVE");
        document.getElementById("editTenantMaxFaces").value = tenant.max_face_encodings || 500;
        document.getElementById("editTenantMaxNodes").value = tenant.max_nodes || 10;

        document.getElementById("editCustomQuotaToggle").checked = false;
        toggleCustomQuotaEditing(false);

        document.getElementById("editTenantAlert").style.display = "none";
        document.getElementById("editTenantModal").style.display = "flex";
    }

    function closeEditTenantModal() {
        document.getElementById("editTenantModal").style.display = "none";
    }

    async function submitEditTenantDetails(e) {
        e.preventDefault();
        const tenantId = document.getElementById("editTenantId").value;
        const alertEl = document.getElementById("editTenantAlert");
        const btn = document.getElementById("btnSubmitEditTenant");
        alertEl.style.display = "none";
        btn.disabled = true;

        const payload = {
            name: document.getElementById("editTenantName").value.trim(),
            tenant_type: document.getElementById("editTenantType").value,
            contact_email: document.getElementById("editTenantEmail").value.trim() || null,
            subscription_plan: document.getElementById("editTenantPlan").value,
            subscription_status: document.getElementById("editTenantStatus").value,
            max_face_encodings: parseInt(document.getElementById("editTenantMaxFaces").value),
            max_nodes: parseInt(document.getElementById("editTenantMaxNodes").value),
        };

        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok) {
                closeEditTenantModal();
                refreshAllSuperAdminData();
            } else {
                alertEl.style.display = "block";
                alertEl.style.background = "rgba(239, 68, 68, 0.1)";
                alertEl.style.border = "1px solid var(--accent-rose)";
                alertEl.style.color = "var(--accent-rose)";
                alertEl.innerText = data.detail || "Error updating tenant details.";
            }
        } catch (err) {
            alertEl.style.display = "block";
            alertEl.style.background = "rgba(239, 68, 68, 0.1)";
            alertEl.style.border = "1px solid var(--accent-rose)";
            alertEl.style.color = "var(--accent-rose)";
            alertEl.innerText = "Network failure updating tenant.";
        } finally {
            btn.disabled = false;
        }
    }

    // --- Modal: Reset Tenant Admin Password ---
    function openResetPasswordModal(tenantId, tenantName, adminUsername) {
        document.getElementById("resetTenantId").value = tenantId;
        document.getElementById("resetTenantName").innerText = tenantName;
        document.getElementById("resetAdminUsername").innerText = adminUsername;
        document.getElementById("resetNewPassword").value = "";
        document.getElementById("resetPasswordAlert").style.display = "none";
        document.getElementById("resetPasswordModal").style.display = "flex";
    }

    function closeResetPasswordModal() {
        document.getElementById("resetPasswordModal").style.display = "none";
    }

    function generateRandomAdminPassword() {
        const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";
        let pass = "";
        for (let i = 0; i < 12; i++) {
            pass += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        document.getElementById("resetNewPassword").value = pass;
    }

    async function submitResetTenantPassword(e) {
        e.preventDefault();
        const tenantId = document.getElementById("resetTenantId").value;
        const newPassword = document.getElementById("resetNewPassword").value.trim();
        const alertEl = document.getElementById("resetPasswordAlert");
        const btn = document.getElementById("btnSubmitResetPassword");

        alertEl.style.display = "none";
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Resetting...`;

        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}/admin-password`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ new_password: newPassword }),
            });
            const data = await res.json();

            if (res.ok) {
                alert(`SUCCESS:\n\nPassword for tenant administrator '${data.admin_username}' has been updated to:\n${newPassword}`);
                closeResetPasswordModal();
                refreshAllSuperAdminData();
            } else {
                alertEl.style.display = "block";
                alertEl.style.background = "rgba(239, 68, 68, 0.1)";
                alertEl.style.border = "1px solid var(--accent-rose)";
                alertEl.style.color = "var(--accent-rose)";
                alertEl.innerText = data.detail || "Error resetting password.";
            }
        } catch (err) {
            alertEl.style.display = "block";
            alertEl.style.background = "rgba(239, 68, 68, 0.1)";
            alertEl.style.border = "1px solid var(--accent-rose)";
            alertEl.style.color = "var(--accent-rose)";
            alertEl.innerText = "Network failure resetting password.";
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-lock"></i> Set New Password`;
        }
    }

    // --- Modal: Tokenized Corporate & Direct Access Links ---
    async function openTenantLinksModal(tenantId) {
        document.getElementById("currentLinksTenantId").value = tenantId;
        document.getElementById("linksModalAlert").style.display = "none";
        
        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}/links`);
            const data = await res.json();
            if (res.ok && data.links) {
                const origin = window.location.origin;
                const tenantLoginUrl = origin + (data.links.portal_url || data.links.tenant_login_url || `/portal/${data.tenant_name}`);
                const adminUrl = origin + data.links.admin_login_url;
                const onboardUrl = origin + data.links.onboarding_url;
                const checkinUrl = origin + data.links.checkin_url;

                document.getElementById("linksTenantSubtitle").innerText = `${data.tenant_name} (${data.uuid || 'Standard'})`;
                document.getElementById("linksTenantTypeBadge").innerText = (data.tenant_type === 'corporate') ? 'Corporate' : 'Educational';
                document.getElementById("linksTenantTypeBadge").className = (data.tenant_type === 'corporate') ? 'badge badge-emerald' : 'badge badge-sky';

                document.getElementById("linkTenantLoginInput").value = tenantLoginUrl;
                document.getElementById("linkTenantLoginLaunch").href = tenantLoginUrl;

                document.getElementById("linkAdminLoginInput").value = adminUrl;
                document.getElementById("linkAdminLoginLaunch").href = adminUrl;

                document.getElementById("linkOnboardingInput").value = onboardUrl;
                document.getElementById("linkOnboardingLaunch").href = onboardUrl;

                document.getElementById("linkCheckinInput").value = checkinUrl;
                document.getElementById("linkCheckinLaunch").href = checkinUrl;

                document.getElementById("tenantLinksModal").style.display = "flex";
            } else {
                alert("Error loading tenant links: " + (data.detail || "Unknown error"));
            }
        } catch (e) {
            alert("Network error fetching access links.");
        }
    }

    function openTenantLinksModalFromData(data) {
        const origin = window.location.origin;
        const tenant = data.tenant || {};
        const links = data.links || {};

        document.getElementById("currentLinksTenantId").value = tenant.id;
        document.getElementById("linksModalAlert").style.display = "none";

        document.getElementById("linksTenantSubtitle").innerText = `${tenant.name} (${tenant.uuid || 'Standard'})`;
        document.getElementById("linksTenantTypeBadge").innerText = (tenant.tenant_type === 'corporate') ? 'Corporate' : 'Educational';
        document.getElementById("linksTenantTypeBadge").className = (tenant.tenant_type === 'corporate') ? 'badge badge-emerald' : 'badge badge-sky';

        const tenantLoginUrl = origin + (links.portal_url || links.tenant_login_url || tenant.portal_url || tenant.tenant_login_url || `/portal/${tenant.slug || tenant.id}`);
        const adminUrl = origin + (links.admin_login_url || tenant.admin_login_url || "");
        const onboardUrl = origin + (links.onboarding_url || tenant.onboarding_url || "");
        const checkinUrl = origin + (links.checkin_url || tenant.checkin_url || "");

        document.getElementById("linkTenantLoginInput").value = tenantLoginUrl;
        document.getElementById("linkTenantLoginLaunch").href = tenantLoginUrl;

        document.getElementById("linkAdminLoginInput").value = adminUrl;
        document.getElementById("linkAdminLoginLaunch").href = adminUrl;

        document.getElementById("linkOnboardingInput").value = onboardUrl;
        document.getElementById("linkOnboardingLaunch").href = onboardUrl;

        document.getElementById("linkCheckinInput").value = checkinUrl;
        document.getElementById("linkCheckinLaunch").href = checkinUrl;

        document.getElementById("tenantLinksModal").style.display = "flex";
    }

    function closeTenantLinksModal() {
        document.getElementById("tenantLinksModal").style.display = "none";
    }

    function copyLinkInput(inputId, btnEl) {
        const input = document.getElementById(inputId);
        input.select();
        navigator.clipboard.writeText(input.value).then(() => {
            const origHtml = btnEl.innerHTML;
            btnEl.innerHTML = `<i class="fa-solid fa-check" style="color: var(--accent-emerald);"></i> Copied!`;
            setTimeout(() => {
                btnEl.innerHTML = origHtml;
            }, 1800);
        }).catch(() => {
            alert("Copied to clipboard!");
        });
    }

    async function triggerRegenerateTokens() {
        const tenantId = document.getElementById("currentLinksTenantId").value;
        if (!confirm("Are you sure you want to ROTATE the security tokens for this organization?\n\nAny previously shared admin or onboarding links will be invalidated immediately.")) {
            return;
        }

        const alertEl = document.getElementById("linksModalAlert");
        try {
            const res = await fetch(`/api/v1/super-admin/tenants/${tenantId}/regenerate-tokens`, {
                method: "POST"
            });
            const data = await res.json();
            if (res.ok) {
                alertEl.style.display = "block";
                alertEl.style.background = "rgba(16, 185, 129, 0.15)";
                alertEl.style.border = "1px solid var(--accent-emerald)";
                alertEl.style.color = "var(--accent-emerald)";
                alertEl.innerText = data.message || "Security tokens rotated successfully.";
                await openTenantLinksModal(tenantId);
            } else {
                alert("Error: " + (data.detail || "Could not rotate tokens."));
            }
        } catch (e) {
            alert("Network error rotating tokens.");
        }
    }

    // --- Audit Accordion Logic ---
    function toggleAuditAccordion() {
        const body = document.getElementById("auditAccordionBody");
        const icon = document.getElementById("auditAccordionIcon");
        const isClosed = (body.style.display === "none");

        if (isClosed) {
            body.style.display = "block";
            icon.style.transform = "rotate(180deg)";
            loadAuditLogs();
        } else {
            body.style.display = "none";
            icon.style.transform = "rotate(0deg)";
        }
    }

    async function loadAuditLogs() {
        try {
            const res = await fetch("/api/v1/super-admin/audit-logs?limit=50");
            const data = await res.json();
            const tbody = document.getElementById("auditLogsTableBody");
            const badge = document.getElementById("auditTrailBadge");

            if (!res.ok || !data.logs || data.logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-muted);">No audit events recorded yet.</td></tr>`;
                return;
            }

            badge.innerText = `${data.logs.length} Recent Events`;

            tbody.innerHTML = data.logs.map(l => `
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="font-family: monospace; font-size: 11px; padding: 10px 14px;">${l.timestamp}</td>
                    <td style="padding: 10px 14px;">
                        <div style="font-weight: 700; font-size: 12px;">${l.actor_name}</div>
                        <span class="badge badge-sky" style="font-size: 9px;">${l.actor_role}</span>
                    </td>
                    <td style="font-size: 12px; font-weight: 600; padding: 10px 14px;">${l.tenant_name}</td>
                    <td style="padding: 10px 14px;"><span class="badge badge-indigo" style="font-size: 10px; font-weight: 700;">${l.action_type}</span></td>
                    <td style="font-size: 12px; max-width: 320px; padding: 10px 14px;">${l.description}</td>
                    <td style="font-family: monospace; font-size: 11px; color: var(--text-muted); padding: 10px 14px;">${l.ip_address || '127.0.0.1'}</td>
                </tr>
            `).join("");
        } catch (e) {
            console.error("Audit log error:", e);
        }
    }

    // --- SEO Hub Logic ---
    function toggleSeoAccordion() {
        const body = document.getElementById("seoAccordionBody");
        const icon = document.getElementById("seoAccordionIcon");
        if (!body) return;
        const isClosed = (body.style.display === "none");
        if (isClosed) {
            body.style.display = "block";
            if (icon) icon.style.transform = "rotate(180deg)";
        } else {
            body.style.display = "none";
            if (icon) icon.style.transform = "rotate(0deg)";
        }
    }

    let globalSeoData = null;

    async function loadSeoData() {
        try {
            const res = await fetch("/api/v1/super-admin/seo");
            if (!res.ok) return;
            const data = await res.json();
            globalSeoData = data;
            populateSeoForm(data.settings);
            renderSeoHealth(data);
        } catch (e) {
            console.error("Error loading SEO data:", e);
        }
    }

    function populateSeoForm(s) {
        if (!s) return;
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val || "";
        };

        setVal("seoSiteTitle", s.site_title);
        setVal("seoCanonicalUrl", s.canonical_url);
        setVal("seoMetaDescription", s.meta_description);
        setVal("seoMetaKeywords", s.meta_keywords);
        setVal("seoOgImage", s.og_image);
        setVal("seoRobotsDirectives", s.robots_directives);

        updateLiveSeoPreviews();
    }

    function updateLiveSeoPreviews() {
        const title = document.getElementById("seoSiteTitle")?.value || "";
        const canonical = document.getElementById("seoCanonicalUrl")?.value || "https://curiosityhub.co.in/";
        const desc = document.getElementById("seoMetaDescription")?.value || "";
        const ogImage = document.getElementById("seoOgImage")?.value || "/screenshots/walkthrough/02_dashboard_live.png";

        // Counters
        const titleCounter = document.getElementById("seoTitleCounter");
        if (titleCounter) {
            titleCounter.innerText = `${title.length} / 65`;
            titleCounter.style.color = (title.length >= 45 && title.length <= 65) ? "var(--accent-emerald)" : (title.length > 70 ? "var(--accent-rose, #f43f5e)" : "var(--text-muted)");
        }

        const descCounter = document.getElementById("seoDescCounter");
        if (descCounter) {
            descCounter.innerText = `${desc.length} / 170`;
            descCounter.style.color = (desc.length >= 130 && desc.length <= 170) ? "var(--accent-emerald)" : (desc.length > 180 ? "var(--accent-rose, #f43f5e)" : "var(--text-muted)");
        }

        const titleLenDisplay = document.getElementById("seoTitleLenDisplay");
        if (titleLenDisplay) titleLenDisplay.innerText = `${title.length} chars`;

        const descLenDisplay = document.getElementById("seoDescLenDisplay");
        if (descLenDisplay) descLenDisplay.innerText = `${desc.length} chars`;

        // SERP Preview
        const serpTitle = document.getElementById("serpTitlePreview");
        if (serpTitle) {
            serpTitle.innerText = title.length > 60 ? title.substring(0, 60) + "..." : (title || "Curiosity HUB — Face Recognition Attendance & Payroll SaaS");
        }

        const serpUrl = document.getElementById("serpUrlPreview");
        if (serpUrl) serpUrl.innerText = canonical.replace(/\/$/, "");

        const serpSnippet = document.getElementById("serpSnippetPreview");
        if (serpSnippet) {
            serpSnippet.innerText = desc.length > 160 ? desc.substring(0, 160) + "..." : (desc || "AI facial recognition employee management SaaS for modern companies.");
        }

        // Social Preview
        const ogTitle = document.getElementById("ogTitlePreview");
        if (ogTitle) ogTitle.innerText = title.length > 65 ? title.substring(0, 65) + "..." : (title || "Curiosity HUB");

        const ogDesc = document.getElementById("ogDescPreview");
        if (ogDesc) ogDesc.innerText = desc.length > 120 ? desc.substring(0, 120) + "..." : (desc || "Enterprise AI facial recognition attendance & payroll SaaS.");

        const ogImg = document.getElementById("ogImagePreview");
        if (ogImg && ogImage) {
            ogImg.src = ogImage;
        }

        try {
            const parsedUrl = new URL(canonical);
            const serpDomain = document.getElementById("serpDomainPreview");
            if (serpDomain) serpDomain.innerText = parsedUrl.hostname;
            const ogDomain = document.getElementById("ogDomainPreview");
            if (ogDomain) ogDomain.innerText = parsedUrl.hostname;
        } catch (_) {}
    }

    function renderSeoHealth(data) {
        const score = data.score || 0;
        const scoreDisplay = document.getElementById("seoScoreDisplay");
        if (scoreDisplay) scoreDisplay.innerText = `${score} / 100`;

        const badge = document.getElementById("seoHealthBadge");
        if (badge) {
            badge.innerText = `Score: ${score} / 100`;
            if (score >= 90) {
                badge.style.background = "var(--badge-emerald-bg)";
                badge.style.color = "var(--accent-emerald)";
            } else if (score >= 70) {
                badge.style.background = "var(--badge-amber-bg)";
                badge.style.color = "var(--accent-amber)";
            } else {
                badge.style.background = "rgba(239, 68, 68, 0.15)";
                badge.style.color = "#ef4444";
            }
        }

        const statusLabel = document.getElementById("seoScoreStatus");
        if (statusLabel) {
            if (score >= 90) statusLabel.innerText = "Excellent Health • Search Ready";
            else if (score >= 70) statusLabel.innerText = "Good Health • Minor Adjustments Advised";
            else statusLabel.innerText = "Action Required • Optimization Needed";
        }

        const sitemapIndexed = document.getElementById("seoSitemapIndexedDisplay");
        if (sitemapIndexed) {
            sitemapIndexed.innerText = `${data.indexed_urls_count || 3} Indexed URLs`;
        }

        renderSeoChecklist(data.audit_items || []);
    }

    function renderSeoChecklist(items) {
        const tbody = document.getElementById("seoChecklistTableBody");
        if (!tbody) return;

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 16px;">No audit checks evaluated.</td></tr>`;
            return;
        }

        tbody.innerHTML = items.map(item => {
            let statusBadge = "";
            if (item.status === "EXCELLENT") {
                statusBadge = `<span class="badge" style="background: var(--badge-emerald-bg); color: var(--accent-emerald); font-size: 10px; font-weight: 700;"><i class="fa-solid fa-check"></i> EXCELLENT</span>`;
            } else if (item.status === "GOOD") {
                statusBadge = `<span class="badge badge-sky" style="font-size: 10px; font-weight: 700;"><i class="fa-solid fa-circle-info"></i> GOOD</span>`;
            } else {
                statusBadge = `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #b45309; font-size: 10px; font-weight: 700;"><i class="fa-solid fa-triangle-exclamation"></i> ATTENTION</span>`;
            }

            return `
                <tr style="border-bottom: 1px solid var(--border-subtle);">
                    <td style="padding: 10px 14px; font-weight: 600; font-size: 12.5px;">${item.param}</td>
                    <td style="padding: 10px 14px;">${statusBadge}</td>
                    <td style="padding: 10px 14px; font-size: 12px; color: var(--text-muted);">${item.detail}</td>
                </tr>
            `;
        }).join("");
    }

    async function submitSeoSettings(e) {
        if (e) e.preventDefault();
        const btn = document.getElementById("btnSaveSeo");
        const statusSpan = document.getElementById("seoSaveStatus");

        const payload = {
            site_title: document.getElementById("seoSiteTitle")?.value?.trim() || "",
            meta_description: document.getElementById("seoMetaDescription")?.value?.trim() || "",
            meta_keywords: document.getElementById("seoMetaKeywords")?.value?.trim() || "",
            canonical_url: document.getElementById("seoCanonicalUrl")?.value?.trim() || "",
            og_image: document.getElementById("seoOgImage")?.value?.trim() || "",
            robots_directives: document.getElementById("seoRobotsDirectives")?.value || "",
            og_title: document.getElementById("seoSiteTitle")?.value?.trim() || "",
            og_description: document.getElementById("seoMetaDescription")?.value?.trim() || "",
        };

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
        }

        try {
            const res = await fetch("/api/v1/super-admin/seo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok) {
                if (statusSpan) {
                    statusSpan.style.display = "inline-flex";
                    statusSpan.innerHTML = `<i class="fa-solid fa-circle-check" style="margin-right: 4px;"></i> Changes published successfully!`;
                    setTimeout(() => { statusSpan.style.display = "none"; }, 4000);
                }
                if (data.seo) {
                    renderSeoHealth(data.seo);
                }
            } else {
                alert(`Failed to save SEO settings: ${data.detail || "Unknown error"}`);
            }
        } catch (err) {
            console.error("Save SEO error:", err);
            alert("Network error while saving SEO settings.");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Save & Publish SEO Settings`;
            }
        }
    }

    async function triggerRegenerateSitemap() {
        const btn = document.getElementById("btnRegenSitemap");
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating...`;
        }

        try {
            const res = await fetch("/api/v1/super-admin/seo/sitemap-regenerate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
            });
            const data = await res.json();
            if (res.ok) {
                alert(`Sitemap XML regenerated successfully!\nCanonical URL: ${data.sitemap_url}`);
                await loadSeoData();
            } else {
                alert(`Error regenerating sitemap: ${data.detail || "Server error"}`);
            }
        } catch (err) {
            console.error("Regenerate sitemap error:", err);
            alert("Failed to regenerate sitemap due to network error.");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-sitemap"></i> Re-generate XML Sitemap`;
            }
        }
    }
