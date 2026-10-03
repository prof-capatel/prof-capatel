// =========================================================================
// Quick Onboarding Interactive Guide Modal Controller & Step Definitions
// Shared between Landing Page and Tenant Admin Sidebar
// =========================================================================

const ONBOARDING_STEPS = [
    {
        stepNum: 0,
        title: "Step 0: Prerequisite & Administrator Login",
        badge: "Initial Setup",
        time: "1 Min",
        role: "Tenant Admin",
        desc: "Log in to your dedicated company portal (<code>/{tenant_id}</code> or <code>/login</code>) using your administrator credentials.",
        checklist: [
            "Open your organization's custom login URL.",
            "Authenticate with the administrator email and secure password.",
            "Confirm the organization name badge in the top navigation bar."
        ],
        callout: "Administrative login credentials are created and sent during tenant setup.",
        images: [
            { src: "/screenshots/walkthrough/01_login_portal.png", label: "Tenant Administrator Login Portal", caption: "Secure entry point with tenant-specific branding and authentication." }
        ]
    },
    {
        stepNum: 1,
        title: "Step 1: Organization Settings & Branch Locations",
        badge: "Workspace Foundation",
        time: "2 Mins",
        role: "Tenant Admin",
        desc: "Establish corporate identity, upload company logo, and register branch office locations.",
        checklist: [
            "Navigate to Settings -> Organization Profile.",
            "Upload the official corporate logo for live portal branding.",
            "Add branch office locations, street addresses, and local time zones."
        ],
        callout: "Branch locations immediately link with GPS geofencing and multi-location logs.",
        images: [
            { src: "/screenshots/walkthrough/15_settings_organization_profile.png", label: "Organization Profile & Multi-Branch Setup", caption: "Configure tenant profile, corporate identity, and branch offices." }
        ]
    },
    {
        stepNum: 2,
        title: "Step 2: Themes & Appearance Customization",
        badge: "Branding",
        time: "1 Min",
        role: "Tenant Admin",
        desc: "Customize portal branding with corporate colors, themes, and navigation styles.",
        checklist: [
            "Open Settings -> Themes & Appearance.",
            "Choose a curated preset theme or enter custom brand hex colors.",
            "Save to apply changes across all admin and employee screens."
        ],
        callout: "Themes persist across browser sessions and attendance kiosks for uniform branding.",
        images: [
            { src: "/screenshots/walkthrough/16_settings_themes_appearance.png", label: "Themes & Appearance Settings", caption: "Dynamic theme switching and custom corporate color configuration." }
        ]
    },
    {
        stepNum: 3,
        title: "Step 3: Departments & Designation Hierarchy",
        badge: "Master Data",
        time: "2 Mins",
        role: "HR / Operations",
        desc: "Set up departmental structure and job hierarchy for employee categorization.",
        checklist: [
            "Go to Settings -> Departments to add functional teams and assign heads.",
            "Go to Settings -> Designations to establish job roles and hierarchy.",
            "Verify department-designation linkage for smooth employee profile setup."
        ],
        callout: "Departments automatically feed into attendance filtering and payroll batches.",
        images: [
            { src: "/screenshots/walkthrough/17_settings_departments.png", label: "Department Masters Setup", caption: "Create and organize functional departments with team leads." },
            { src: "/screenshots/walkthrough/18_settings_designations.png", label: "Designation & Hierarchy Setup", caption: "Establish corporate hierarchy and title classifications." }
        ]
    },
    {
        stepNum: 4,
        title: "Step 4: Shifts, Timing Rules & GPS Geofencing",
        badge: "Operational Rules",
        time: "2 Mins",
        role: "Operations Admin",
        desc: "Configure work timings, grace windows, and tamper-proof GPS perimeter radiuses.",
        checklist: [
            "Open Settings -> Shift Configuration to define start, end, and grace times.",
            "Configure overtime policies, half-day thresholds, and weekly off rotations.",
            "Set GPS coordinates and authorized check-in radius (50m–500m) for mobile check-ins."
        ],
        callout: "The anti-spoofing engine validates real-time GPS coordinates against authorized perimeters.",
        images: [
            { src: "/screenshots/walkthrough/19_settings_shifts_rules.png", label: "Shift Scheduling & Policy Configuration", caption: "Set flexible work hours, grace periods, and late arrival rules." },
            { src: "/screenshots/walkthrough/21_settings_geofencing_portals.png", label: "GPS Geofencing & Location Portals", caption: "Define office perimeter radiuses for zero-fraud mobile attendance." }
        ]
    },
    {
        stepNum: 5,
        title: "Step 5: Employee Biometric Registration",
        badge: "Enrollment",
        time: "2 Mins",
        role: "HR / Admin",
        desc: "Enroll employees via webcam capture (3 facial angles) or self-onboarding mobile links.",
        checklist: [
            "Admin Enrollment: Go to Employees -> Register Employee and capture 3 face angles.",
            "Self-Onboard Link: Share tokenized magic link (/onboard/...) for smartphone photo upload.",
            "High-precision 128-d face embeddings are indexed for sub-second recognition."
        ],
        callout: "3-angle capture ensures 99.8% match precision across diverse lighting and angles.",
        images: [
            { src: "/screenshots/walkthrough/05_register_new_employee.png", label: "3-Angle Biometric Employee Enrollment", caption: "Guided facial capture with real-time liveness feedback and feature vector extraction." }
        ]
    },
    {
        stepNum: 6,
        title: "Step 6: Employee Directory & Profile Lifecycle",
        badge: "Workforce Management",
        time: "2 Mins",
        role: "HR Admin",
        desc: "Centrally manage employee rosters, salary assignments, and credential resets.",
        checklist: [
            "Search and filter the employee roster by department and biometric status.",
            "Edit employee profiles to update salary templates, assigned shifts, and managers.",
            "Toggle active/inactive status or reset employee self-service portal passwords."
        ],
        callout: "Soft-delete safeguards preserve historical attendance and payroll data.",
        images: [
            { src: "/screenshots/walkthrough/03_employee_directory.png", label: "Master Employee Directory", caption: "Searchable employee roster with biometric status indicators and quick actions." },
            { src: "/screenshots/walkthrough/04_employee_edit_modal.png", label: "Employee Profile Lifecycle Editor", caption: "Manage salary structures, branch locations, and shift policies." }
        ]
    },
    {
        stepNum: 7,
        title: "Step 7: Live Biometric Attendance Scanner",
        badge: "Daily Operations",
        time: "Instant",
        role: "Kiosk / Reception",
        desc: "Launch the browser-based face recognition scanner on any PC, tablet, or kiosk webcam.",
        checklist: [
            "Open Dashboard live scanner (or fullscreen kiosk terminal).",
            "Connect standard USB or built-in HD webcam facing the entrance.",
            "Staff walk past camera; punches are logged in <250ms with live visual feedback."
        ],
        callout: "Zero specialized hardware required—standard 720p/1080p webcams deliver instant recognition.",
        images: [
            { src: "/screenshots/walkthrough/02_dashboard_live.png", label: "Live Face Recognition Terminal", caption: "Sub-250ms recognition HUD with real-time liveness detection and confirmation." }
        ]
    },
    {
        stepNum: 8,
        title: "Step 8: Attendance Logs & Auditing",
        badge: "Compliance",
        time: "1 Min",
        role: "HR / Managers",
        desc: "Review daily attendance punches, filter by branch or date, and make audited adjustments.",
        checklist: [
            "Access Attendance Logs to view real-time entry/exit timestamps and work durations.",
            "Filter records by date range, department, or employee ID.",
            "Perform manual punch adjustments or soft deletions with mandatory audit remarks."
        ],
        callout: "All manual adjustments are permanently logged in the administrator audit trail.",
        images: [
            { src: "/screenshots/walkthrough/06_attendance_logs_active.png", label: "Comprehensive Attendance Log Ledger", caption: "Detailed punch timelines, calculated working hours, and exportable reports." },
            { src: "/screenshots/walkthrough/07_attendance_logs_soft_delete_modal.png", label: "Audited Record Modification & Soft Delete", caption: "Secure modal requiring administrative justification for corrections." }
        ]
    },
    {
        stepNum: 9,
        title: "Step 9: Statutory Leaves & Automated Payroll",
        badge: "Payroll Automation",
        time: "2 Mins",
        role: "Payroll / Finance",
        desc: "Manage statutory leave ledgers and execute 1-click automated salary batches.",
        checklist: [
            "Review and approve employee leave applications in Leave Management.",
            "Run Payroll -> Monthly Batches to sync attendance with automated salary calculation.",
            "Review component breakdown (Basic, HRA, PF, PT, Net) and dispatch digital payslips."
        ],
        callout: "Statutory deduction tables follow standard Indian payroll compliance (26-day basis).",
        images: [
            { src: "/screenshots/walkthrough/14_leave_management.png", label: "Statutory Leave Ledger & Approval System", caption: "Allocate annual leave quotas and process employee leave applications." },
            { src: "/screenshots/walkthrough/09_payroll_monthly_batches.png", label: "Automated Monthly Payroll Batch Execution", caption: "One-click attendance-to-salary reconciliation with statutory deductions." },
            { src: "/screenshots/walkthrough/10_payroll_employee_structures.png", label: "Employee Salary Structure Configuration", caption: "Granular salary component builder supporting multiple compensation models." }
        ]
    }
];

let currentGuideStepIndex = 0;

function openOnboardingModal(stepIndex = 0) {
    const modal = document.getElementById('onboardingGuideModal');
    if (!modal) return;
    currentGuideStepIndex = (typeof stepIndex === 'number' && stepIndex >= 0 && stepIndex < ONBOARDING_STEPS.length) ? stepIndex : 0;
    renderGuideStep(currentGuideStepIndex);
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeOnboardingModal() {
    const modal = document.getElementById('onboardingGuideModal');
    if (modal) {
        modal.style.display = 'none';
    }
    const lightbox = document.getElementById('lightboxModal');
    const demoModal = document.getElementById('freeDemoModal');
    const isLightboxOpen = lightbox && lightbox.style.display === 'flex';
    const isDemoOpen = demoModal && demoModal.style.display === 'flex';
    if (!isLightboxOpen && !isDemoOpen) {
        document.body.style.overflow = '';
    }
}

function handleGuideModalOverlayClick(event) {
    if (event.target && event.target.id === 'onboardingGuideModal') {
        closeOnboardingModal();
    }
}

function nextGuideStep() {
    if (currentGuideStepIndex < ONBOARDING_STEPS.length - 1) {
        currentGuideStepIndex++;
        renderGuideStep(currentGuideStepIndex);
    }
}

function prevGuideStep() {
    if (currentGuideStepIndex > 0) {
        currentGuideStepIndex--;
        renderGuideStep(currentGuideStepIndex);
    }
}

function renderGuideStep(index) {
    if (index < 0 || index >= ONBOARDING_STEPS.length) return;
    currentGuideStepIndex = index;
    const step = ONBOARDING_STEPS[index];

    const progressPercent = Math.round(((index + 1) / ONBOARDING_STEPS.length) * 100);
    const pFill = document.getElementById('guideProgressBar');
    if (pFill) pFill.style.width = progressPercent + '%';

    const select = document.getElementById('guideStepSelect');
    if (select) select.value = index;

    const counter = document.getElementById('guideStepCounter');
    if (counter) counter.textContent = `Step ${index + 1} of ${ONBOARDING_STEPS.length}`;

    const btnPrev = document.getElementById('btnGuidePrev');
    const btnNext = document.getElementById('btnGuideNext');
    if (btnPrev) btnPrev.disabled = (index === 0);
    if (btnNext) btnNext.disabled = (index === ONBOARDING_STEPS.length - 1);

    // Update In-Modal Step Pills
    const pills = document.querySelectorAll('.guide-step-pill');
    pills.forEach((p, i) => {
        if (i === index) {
            p.classList.add('active');
            p.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        } else {
            p.classList.remove('active');
        }
    });

    const body = document.getElementById('guideModalBody');
    if (!body) return;

    let checklistHtml = '';
    step.checklist.forEach(item => {
        checklistHtml += `<li><i class="fa-solid fa-circle-check" style="color: #10B981; margin-top: 3px; flex-shrink: 0;"></i> <span>${item}</span></li>`;
    });

    let imagesHtml = '';
    step.images.forEach(img => {
        imagesHtml += `
            <div style="border: 1px solid var(--border-color, #E2E8F0); border-radius: 12px; overflow: hidden; background: #FFFFFF; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;" onclick="openGuideLightbox('${img.src}', '${img.label.replace(/'/g, "\\'")}')">
                <div style="background: #0F172A; padding: 8px 14px; display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 12px; font-weight: 700; color: #F8FAFC; display: flex; align-items: center; gap: 6px;">
                        <i class="fa-regular fa-image" style="color: #FB923C;"></i> ${img.label}
                    </span>
                    <span style="font-size: 11px; color: #94A3B8; display: flex; align-items: center; gap: 4px;">
                        <i class="fa-solid fa-magnifying-glass-plus"></i> Click to Zoom
                    </span>
                </div>
                <img src="${img.src}" alt="${img.label}" loading="lazy" style="width: 100%; height: auto; display: block; border-bottom: 1px solid var(--border-subtle, #E2E8F0);">
                <div style="padding: 10px 14px; font-size: 12px; color: var(--text-muted, #64748B); background: #F8FAFC; line-height: 1.4;">
                    ${img.caption}
                </div>
            </div>
        `;
    });

    body.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 20px;">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap;">
                <div>
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
                        <span class="step-badge" style="background: rgba(234, 88, 12, 0.12); color: #EA580C; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; border: 1px solid rgba(234, 88, 12, 0.2);">
                            ${step.badge}
                        </span>
                        <span style="font-size: 12px; color: var(--text-muted, #64748B); font-weight: 600; display: flex; align-items: center; gap: 4px;">
                            <i class="fa-regular fa-clock" style="color: #EA580C;"></i> Est. Time: ${step.time}
                        </span>
                        <span style="font-size: 12px; color: var(--text-muted, #64748B); font-weight: 600; display: flex; align-items: center; gap: 4px;">
                            <i class="fa-regular fa-user" style="color: #EA580C;"></i> Role: ${step.role}
                        </span>
                    </div>
                    <h3 style="font-size: 19px; font-weight: 800; color: var(--text-heading, #0F172A); margin: 0 0 8px 0;">
                        ${step.title}
                    </h3>
                    <p style="font-size: 13.5px; color: var(--text-body, #334155); line-height: 1.55; margin: 0;">
                        ${step.desc}
                    </p>
                </div>
            </div>

            <div style="background: #F8FAFC; border: 1px solid var(--border-subtle, #E2E8F0); border-radius: 12px; padding: 16px 18px;">
                <h4 style="font-size: 13px; font-weight: 700; color: var(--text-heading, #0F172A); margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid fa-list-check" style="color: #EA580C;"></i> Required Setup Checklist
                </h4>
                <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--text-body, #334155); line-height: 1.45;">
                    ${checklistHtml}
                </ul>
            </div>

            <div style="background: rgba(234, 88, 12, 0.06); border-left: 4px solid #EA580C; border-radius: 0 8px 8px 0; padding: 10px 16px; font-size: 12.5px; color: #9A3412; line-height: 1.45; display: flex; align-items: flex-start; gap: 10px;">
                <i class="fa-solid fa-lightbulb" style="color: #EA580C; font-size: 14px; margin-top: 2px;"></i>
                <div><strong>Pro Tip:</strong> ${step.callout}</div>
            </div>

            <div>
                <h4 style="font-size: 13px; font-weight: 700; color: var(--text-heading, #0F172A); margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid fa-display" style="color: #EA580C;"></i> Screenshot Walkthrough & UI Reference
                </h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
                    ${imagesHtml}
                </div>
            </div>
        </div>
    `;
    body.scrollTop = 0;
}

function openLightbox(imgSrc, title) {
    const modal = document.getElementById('lightboxModal');
    const img = document.getElementById('lightboxImg');
    const titleEl = document.getElementById('lightboxTitle');
    if (modal && img) {
        img.src = imgSrc;
        if (titleEl) titleEl.textContent = title || 'Module Preview';
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeLightbox(event) {
    const modal = document.getElementById('lightboxModal');
    if (modal) {
        modal.style.display = 'none';
    }
    const guideModal = document.getElementById('onboardingGuideModal');
    if (!guideModal || guideModal.style.display !== 'flex') {
        document.body.style.overflow = '';
    }
}

function openGuideLightbox(imgSrc, title) {
    openLightbox(imgSrc, title);
}

function handleGuideCtaAction() {
    closeOnboardingModal();
    if (typeof openFreeDemoModal === 'function') {
        openFreeDemoModal();
    }
}

// Global Esc & Arrow Key support for Onboarding Modal & Lightbox
window.addEventListener('keydown', function(e) {
    const lightboxModal = document.getElementById('lightboxModal');
    if (lightboxModal && lightboxModal.style.display === 'flex') {
        if (e.key === 'Escape') {
            closeLightbox();
            return;
        }
    }
    const guideModal = document.getElementById('onboardingGuideModal');
    if (guideModal && guideModal.style.display === 'flex') {
        if (e.key === 'Escape') {
            closeOnboardingModal();
        } else if (e.key === 'ArrowRight') {
            nextGuideStep();
        } else if (e.key === 'ArrowLeft') {
            prevGuideStep();
        }
    }
});

// Update CTA button label on load
document.addEventListener('DOMContentLoaded', function() {
    const ctaText = document.getElementById('guideCtaText');
    if (ctaText) {
        ctaText.textContent = (typeof openFreeDemoModal === 'function') ? 'Launch Free Demo' : 'Got it, Continue';
    }
});

// Expose globally on window
window.ONBOARDING_STEPS = ONBOARDING_STEPS;
window.openOnboardingModal = openOnboardingModal;
window.closeOnboardingModal = closeOnboardingModal;
window.handleGuideModalOverlayClick = handleGuideModalOverlayClick;
window.handleGuideCtaAction = handleGuideCtaAction;
window.nextGuideStep = nextGuideStep;
window.prevGuideStep = prevGuideStep;
window.renderGuideStep = renderGuideStep;
window.openLightbox = openLightbox;
window.closeLightbox = closeLightbox;
window.openGuideLightbox = openGuideLightbox;

