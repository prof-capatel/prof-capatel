        // Module Filtering Tabs
        function filterModules(category) {
            const cards = document.querySelectorAll('.walkthrough-card');
            const btns = document.querySelectorAll('.demo-filter-btn');
            
            btns.forEach(b => b.classList.remove('active'));
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            }

            cards.forEach(card => {
                if (category === 'all' || card.getAttribute('data-category') === category) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        }

        // Lightbox Modal Handlers
        function openLightbox(imgSrc, title) {
            const modal = document.getElementById('lightboxModal');
            const img = document.getElementById('lightboxImg');
            const titleEl = document.getElementById('lightboxTitle');
            
            img.src = imgSrc;
            titleEl.textContent = title || 'Module Preview';
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeLightbox(event) {
            const modal = document.getElementById('lightboxModal');
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }

        // Keyboard Esc to Close Lightbox
        window.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeLightbox();
            }
        });

        // Mobile Nav Toggle
        function toggleMobileNav() {
            const menu = document.getElementById('navMenu');
            if (menu.style.display === 'flex') {
                menu.style.display = 'none';
            } else {
                menu.style.display = 'flex';
                menu.style.flexDirection = 'column';
                menu.style.position = 'absolute';
                menu.style.top = '100%';
                menu.style.left = '0';
                menu.style.width = '100%';
                menu.style.background = '#FFFFFF';
                menu.style.padding = '24px';
                menu.style.boxShadow = '0 12px 24px rgba(0,0,0,0.15)';
                menu.style.zIndex = '999';
            }
        }

        // Inquiry Form Handler
        function handleInquirySubmit(event) {
            event.preventDefault();
            const btn = document.getElementById('btnSubmitInquiry');
            const fb = document.getElementById('formFeedback');
            const name = document.getElementById('inqName').value.trim();
            const company = document.getElementById('inqCompany').value.trim();
            const email = document.getElementById('inqEmail').value.trim();
            const phone = document.getElementById('inqPhone').value.trim();
            const edition = document.getElementById('inqEdition').value;

            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Sending to Curiosity HUB...</span>';

            setTimeout(() => {
                fb.style.display = 'block';
                fb.style.background = 'var(--success-soft)';
                fb.style.border = '1px solid var(--success-emerald)';
                fb.style.color = 'var(--success-emerald)';
                fb.innerHTML = `<strong><i class="fa-solid fa-circle-check"></i> Thank you, ${name}!</strong><br>Your inquiry for the <strong>${edition} Edition</strong> has been received. Our Ahmedabad team will connect with you at <strong>${email}</strong> or <strong>${phone}</strong> shortly.`;
                
                document.getElementById('inquiryForm').reset();
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Inquiry Submitted Successfully</span>';
                setTimeout(() => {
                    btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> <span>Submit Another Inquiry</span>';
                }, 4000);
            }, 600);
        }

        // =========================================================================
        // Free Demo Self-Service Modal & OTP Controller
        // =========================================================================
        let currentDemoEmail = '';
        let resendInterval = null;

        function openFreeDemoModal() {
            const modal = document.getElementById('freeDemoModal');
            if (modal) {
                modal.style.display = 'flex';
                goToDemoStep1();
                setTimeout(() => {
                    const nameInput = document.getElementById('demoName');
                    if (nameInput) nameInput.focus();
                }, 100);
            }
        }

        function closeFreeDemoModal() {
            const modal = document.getElementById('freeDemoModal');
            if (modal) {
                modal.style.display = 'none';
                if (resendInterval) clearInterval(resendInterval);
            }
        }

        function handleDemoModalOverlayClick(event) {
            if (event.target && event.target.id === 'freeDemoModal') {
                closeFreeDemoModal();
            }
        }

        function goToDemoStep1() {
            document.getElementById('demoStep1').style.display = 'block';
            document.getElementById('demoStep2').style.display = 'none';
            document.getElementById('demoStep1Feedback').style.display = 'none';
            if (resendInterval) clearInterval(resendInterval);
        }

        async function handleDemoRequestOtp(event) {
            event.preventDefault();
            const btn = document.getElementById('btnRequestOtp');
            const fb = document.getElementById('demoStep1Feedback');
            const name = document.getElementById('demoName').value.trim();
            const company = document.getElementById('demoCompany').value.trim();
            const mobile = document.getElementById('demoMobile').value.trim();
            const email = document.getElementById('demoEmail').value.trim().toLowerCase();

            fb.style.display = 'none';
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Sending Verification Code...</span>';

            try {
                const res = await fetch('/api/v1/demo/request-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        company_name: company,
                        mobile: mobile,
                        email: email,
                    }),
                });

                const data = await res.json();
                if (res.ok) {
                    currentDemoEmail = email;
                    document.getElementById('displayTargetEmail').textContent = email;
                    document.getElementById('demoStep1').style.display = 'none';
                    document.getElementById('demoStep2').style.display = 'block';
                    document.getElementById('demoStep2Feedback').style.display = 'none';
                    document.getElementById('demoOtpCode').value = '';
                    setTimeout(() => {
                        document.getElementById('demoOtpCode').focus();
                    }, 100);
                    startResendTimer(60);
                } else {
                    fb.style.display = 'block';
                    fb.className = 'demo-alert demo-alert-error';
                    fb.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Unable to send verification code. Please check details and try again.'}`;
                }
            } catch (err) {
                fb.style.display = 'block';
                fb.className = 'demo-alert demo-alert-error';
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server. Please check your connection.';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> <span>Send Verification Code</span>';
            }
        }

        async function handleDemoVerifyOtp(event) {
            event.preventDefault();
            const btn = document.getElementById('btnVerifyOtp');
            const fb = document.getElementById('demoStep2Feedback');
            const otp = document.getElementById('demoOtpCode').value.trim();

            if (!otp || otp.length !== 6) {
                fb.style.display = 'block';
                fb.className = 'demo-alert demo-alert-error';
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Please enter the complete 6-digit verification code.';
                return;
            }

            fb.style.display = 'none';
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Activating 7-Day Pro Portal...</span>';

            try {
                const res = await fetch('/api/v1/demo/verify-and-provision', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: currentDemoEmail,
                        otp: otp,
                    }),
                });

                const data = await res.json();
                if (res.ok) {
                    fb.style.display = 'block';
                    fb.className = 'demo-alert demo-alert-success';
                    fb.innerHTML = `<strong><i class="fa-solid fa-circle-check"></i> Demo Activated!</strong><br>Credentials emailed to <strong>${currentDemoEmail}</strong>.<br>Launching your workspace in 2 seconds...`;

                    btn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Portal Ready! Redirecting...</span>';
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/dashboard';
                    }, 1800);
                } else {
                    fb.style.display = 'block';
                    fb.className = 'demo-alert demo-alert-error';
                    fb.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Invalid verification code.'}`;
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>Verify & Launch My Demo</span>';
                }
            } catch (err) {
                fb.style.display = 'block';
                fb.className = 'demo-alert demo-alert-error';
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error activating demo. Please try again.';
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> <span>Verify & Launch My Demo</span>';
            }
        }

        function startResendTimer(seconds) {
            if (resendInterval) clearInterval(resendInterval);
            let remaining = seconds;
            const timerSpan = document.getElementById('resendTimer');
            const countdownText = document.getElementById('resendCountdownText');
            const resendBtn = document.getElementById('btnResendOtp');

            countdownText.style.display = 'inline';
            resendBtn.style.display = 'none';
            timerSpan.textContent = remaining;

            resendInterval = setInterval(() => {
                remaining--;
                if (remaining <= 0) {
                    clearInterval(resendInterval);
                    countdownText.style.display = 'none';
                    resendBtn.style.display = 'inline';
                } else {
                    timerSpan.textContent = remaining;
                }
            }, 1000);
        }

        async function handleResendOtp() {
            const fb = document.getElementById('demoStep2Feedback');
            const resendBtn = document.getElementById('btnResendOtp');
            resendBtn.disabled = true;
            resendBtn.textContent = 'Resending...';

            try {
                const name = document.getElementById('demoName').value.trim();
                const company = document.getElementById('demoCompany').value.trim();
                const mobile = document.getElementById('demoMobile').value.trim();

                const res = await fetch('/api/v1/demo/request-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        company_name: company,
                        mobile: mobile,
                        email: currentDemoEmail,
                    }),
                });

                const data = await res.json();
                if (res.ok) {
                    fb.style.display = 'block';
                    fb.className = 'demo-alert demo-alert-success';
                    fb.innerHTML = '<i class="fa-solid fa-paper-plane"></i> A fresh verification code has been dispatched to your email.';
                    startResendTimer(60);
                } else {
                    fb.style.display = 'block';
                    fb.className = 'demo-alert demo-alert-error';
                    fb.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.detail || 'Unable to resend OTP.'}`;
                    resendBtn.disabled = false;
                    resendBtn.textContent = 'Resend Verification Code';
                }
            } catch (err) {
                fb.style.display = 'block';
                fb.className = 'demo-alert demo-alert-error';
                fb.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error. Please try again.';
                resendBtn.disabled = false;
                resendBtn.textContent = 'Resend Verification Code';
            }
        }

        // Expose Free Demo controllers globally on window
        window.openFreeDemoModal = openFreeDemoModal;
        window.closeFreeDemoModal = closeFreeDemoModal;
        window.goToDemoStep1 = goToDemoStep1;
        window.handleDemoModalOverlayClick = handleDemoModalOverlayClick;
        window.handleDemoRequestOtp = handleDemoRequestOtp;
        window.handleDemoVerifyOtp = handleDemoVerifyOtp;
        window.handleResendOtp = handleResendOtp;

        // Defensive event binding for Free Demo CTA buttons
        document.addEventListener('DOMContentLoaded', function() {
            const demoBtn = document.getElementById('btnNavFreeDemo');
            if (demoBtn) {
                demoBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    openFreeDemoModal();
                });
            }
        });

        // =========================================================================
        // Quick Onboarding Interactive Guide Modal Controller
        // =========================================================================
        const ONBOARDING_STEPS = [
            {
                stepNum: 0,
                title: "Step 0: Prerequisite & Administrator Login",
                badge: "Initial Setup",
                time: "1 Min",
                role: "Super Admin / Tenant Admin",
                desc: "Upon tenant provisioning, the administrator accesses the dedicated organizational portal (<code>/{tenant_id}</code> or <code>/login</code>) using the automatically dispatched credentials.",
                checklist: [
                    "Navigate to your company tenant login URL.",
                    "Authenticate using the issued Admin Email and secure password.",
                    "Verify top-right tenant badge confirming your organizational workspace."
                ],
                callout: "Credentials are automatically emailed to your registered administrative address upon registration.",
                images: [
                    { src: "/screenshots/walkthrough/01_login_portal.png", label: "Tenant Administrator Login Portal", caption: "Secure entry point with tenant-specific branding and credential validation." }
                ]
            },
            {
                stepNum: 1,
                title: "Step 1: Organization Settings & Branch Locations",
                badge: "Workspace Foundation",
                time: "2 Mins",
                role: "Tenant Admin",
                desc: "Establish your corporate identity, upload your official company logo, specify legal business entities, and register multi-location branches with physical street addresses.",
                checklist: [
                    "Go to Settings -> Organization Profile.",
                    "Upload company brand logo and verify real-time preview across portal headers.",
                    "Define physical office branch locations, primary contact details, and local time zones."
                ],
                callout: "All registered branch locations are immediately linked to geofencing and multi-location attendance routing.",
                images: [
                    { src: "/screenshots/walkthrough/15_settings_organization_profile.png", label: "Organization Profile & Multi-Branch Setup", caption: "Configure tenant profile, corporate identity, and multi-location branch offices." }
                ]
            },
            {
                stepNum: 2,
                title: "Step 2: Themes & Appearance Customization",
                badge: "Branding",
                time: "1 Min",
                role: "Tenant Admin",
                desc: "Align the platform with your company brand guidelines by configuring custom primary colors, accent gradients, dark/light themes, and dashboard layouts.",
                checklist: [
                    "Navigate to Settings -> Themes & Appearance.",
                    "Select your preferred color theme or customize brand hex codes.",
                    "Save changes to instantly reflect across all administrative and employee interfaces."
                ],
                callout: "Theme preferences persist across all browser sessions and kiosks for consistent branding.",
                images: [
                    { src: "/screenshots/walkthrough/16_settings_themes_appearance.png", label: "Themes & Appearance Settings", caption: "Dynamic theme switching and custom corporate color scheme configuration." }
                ]
            },
            {
                stepNum: 3,
                title: "Step 3: Departments & Designation Hierarchy",
                badge: "Master Data",
                time: "2 Mins",
                role: "HR / Operations",
                desc: "Define organizational structure by configuring department masters (Engineering, Sales, Operations, HR) and tiered designation levels with reporting lines.",
                checklist: [
                    "Go to Settings -> Departments to add functional departments and assign department heads.",
                    "Go to Settings -> Designations to establish organizational hierarchy and job roles.",
                    "Verify department-designation linkage for streamlined employee assignment."
                ],
                callout: "Departmental masters automatically feed into attendance filtering, leave approvals, and payroll categorization.",
                images: [
                    { src: "/screenshots/walkthrough/17_settings_departments.png", label: "Department Masters Setup", caption: "Create and organize functional departments with designated department leads." },
                    { src: "/screenshots/walkthrough/18_settings_designations.png", label: "Designation & Hierarchy Setup", caption: "Establish corporate hierarchy, title classifications, and job levels." }
                ]
            },
            {
                stepNum: 4,
                title: "Step 4: Shifts, Timing Rules & GPS Geofencing",
                badge: "Operational Rules",
                time: "3 Mins",
                role: "Operations Admin",
                desc: "Configure work schedules, flexible timing windows, grace periods, half-day thresholds, and pin tamper-proof GPS coordinates with meter radius geofencing for remote or mobile check-ins.",
                checklist: [
                    "Navigate to Settings -> Shift Configuration to define start time, end time, and grace intervals.",
                    "Configure overtime policies, half-day cutoffs, and weekly off rotations.",
                    "Set GPS Geofencing coordinates and authorized radius (50m - 500m) for mobile attendance portals."
                ],
                callout: "The anti-spoofing engine cross-checks real-time browser GPS coordinates against authorized site perimeters.",
                images: [
                    { src: "/screenshots/walkthrough/19_settings_shifts_rules.png", label: "Shift Scheduling & Policy Configuration", caption: "Set flexible work hours, grace periods, late arrival cutoffs, and overtime rules." },
                    { src: "/screenshots/walkthrough/21_settings_geofencing_portals.png", label: "GPS Geofencing & Location Portals", caption: "Pinpoint authorized office perimeter radiuses for zero-fraud remote and mobile attendance." }
                ]
            },
            {
                stepNum: 5,
                title: "Step 5: Employee Registration & 3-Angle Facial Biometrics",
                badge: "Workforce Enrollment",
                time: "3 Mins",
                role: "HR Admin / Employee",
                desc: "Rapidly enroll your workforce through two flexible methods: direct administrative capture or employee smartphone self-onboarding link. Multi-angle captures (Frontal, Left, Right) ensure 99.8% sub-second match precision.",
                checklist: [
                    "Method A (Admin): Go to Employees -> 'Register Employee', enter profile, and capture 3 facial angles via webcam.",
                    "Method B (Self-Onboard): Share tokenized magic link (/onboard/{uuid}/{token}) with employees for frictionless smartphone photo registration.",
                    "High-precision 128-dimensional embedding vectors are generated and indexed in memory for sub-second recognition."
                ],
                callout: "Multi-angle facial enrollment guarantees lightning-fast identification even under varying lighting conditions, spectacles, or head turns.",
                images: [
                    { src: "/screenshots/walkthrough/05_register_new_employee.png", label: "3-Angle Biometric Employee Enrollment", caption: "Guided facial capture with real-time liveness feedback and instant feature vector extraction." }
                ]
            },
            {
                stepNum: 6,
                title: "Step 6: Employee Directory & Profile Lifecycle",
                badge: "Workforce Management",
                time: "2 Mins",
                role: "HR Admin",
                desc: "Centrally oversee the master employee directory with real-time search, department filtering, biometric status badges, credential resets, and full lifecycle edits.",
                checklist: [
                    "Browse the full employee roster with biometric registration badges.",
                    "Click 'Edit' on any profile to update salary templates, assigned shifts, reporting managers, or personal info.",
                    "Use quick actions to toggle active/inactive status or reset employee self-service portal passwords."
                ],
                callout: "Soft-delete safeguards and audit trails ensure no historical attendance or payroll records are lost.",
                images: [
                    { src: "/screenshots/walkthrough/03_employee_directory.png", label: "Master Employee Directory", caption: "Searchable employee roster with biometric status indicators, department tags, and quick actions." },
                    { src: "/screenshots/walkthrough/04_employee_edit_modal.png", label: "Employee Profile Lifecycle Editor", caption: "Manage salary assignment, branch location, shift policies, and contact information." }
                ]
            },
            {
                stepNum: 7,
                title: "Step 7: Live Biometric Attendance Scanner & Real-Time HUD",
                badge: "Daily Operations",
                time: "Instant",
                role: "Kiosk / Receptionist / Security",
                desc: "Launch the zero-hardware live biometric scanner on any PC, iPad, tablet, or kiosk webcam. Real-time HUD detects faces, runs Euclidean matching in <250ms, and flashes positive confirmation.",
                checklist: [
                    "Open the Dashboard live scanner terminal (or dedicated fullscreen kiosk view).",
                    "Point any USB or built-in webcam toward the entrance.",
                    "Staff walk past the camera; system auto-detects, validates anti-spoof liveness, logs In/Out timestamps, and displays personalized greeting cues."
                ],
                callout: "Zero specialized biometric hardware required. Standard 720p/1080p webcams deliver institutional-grade throughput.",
                images: [
                    { src: "/screenshots/walkthrough/02_dashboard_live.png", label: "Live Face Recognition Terminal", caption: "Sub-250ms recognition HUD with real-time liveness detection, punch confirmation, and occupancy counts." }
                ]
            },
            {
                stepNum: 8,
                title: "Step 8: Daily Attendance Logs, In/Out Tracking & Auditing",
                badge: "Compliance & Auditing",
                time: "1 Min",
                role: "HR / Line Managers",
                desc: "Inspect real-time daily punch records, filter by date ranges, departments, or shifts, review confidence scores, and perform administrative manual adjustments with tamper-proof audit trails.",
                checklist: [
                    "Access Attendance Logs to view real-time entry/exit timestamps, work durations, and status (Present, Late, Half-day).",
                    "Filter by specific date ranges, branch offices, or employee codes.",
                    "Perform manual time adjustments or soft deletions with mandatory audit remarks when authorized."
                ],
                callout: "All manual adjustments are permanently logged with administrator ID and timestamp for statutory audit compliance.",
                images: [
                    { src: "/screenshots/walkthrough/06_attendance_logs_active.png", label: "Comprehensive Attendance Log Ledger", caption: "Detailed punch timelines, calculated working hours, late marks, and exportable CSV reports." },
                    { src: "/screenshots/walkthrough/07_attendance_logs_soft_delete_modal.png", label: "Audited Record Modification & Soft Delete", caption: "Secure modal requiring administrative justification for attendance record corrections." }
                ]
            },
            {
                stepNum: 9,
                title: "Step 9: Statutory Leaves & Automated Indian Payroll",
                badge: "Payroll Automation",
                time: "3 Mins",
                role: "Payroll / Finance Admin",
                desc: "Eliminate spreadsheet chaos with 1-click payroll processing. Automatically syncs monthly attendance data, calculates paid/unpaid leaves, computes Indian statutory deductions (PF, ESIC, PT, TDS), and generates downloadable PDF payslips.",
                checklist: [
                    "Navigate to Leave Management to review leave ledgers, allocate quotas (CL, SL, EL), and approve employee requests.",
                    "Open Payroll -> Monthly Batches to trigger automated salary computation synced with biometric attendance logs.",
                    "Review component breakdown (Basic, HRA, Allowances, PF, PT, Net Payable) and dispatch digital payslips to staff."
                ],
                callout: "Statutory deduction tables follow latest Indian Ministry of Labour compliance guidelines.",
                images: [
                    { src: "/screenshots/walkthrough/14_leave_management.png", label: "Statutory Leave Ledger & Approval System", caption: "Allocate annual leave quotas, track balance consumption, and process leave applications." },
                    { src: "/screenshots/walkthrough/09_payroll_monthly_batches.png", label: "Automated Monthly Payroll Batch Execution", caption: "One-click attendance-to-salary reconciliation with automatic deduction calculations." },
                    { src: "/screenshots/walkthrough/10_payroll_employee_structures.png", label: "Employee Salary Structure Configuration", caption: "Granular salary component builder supporting allowances, reimbursements, and statutory compliance." }
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
                    <div style="border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden; background: #FFFFFF; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;" onclick="openLightbox('${img.src}', '${img.label.replace(/'/g, "\\'")}')">
                        <div style="background: #0F172A; padding: 8px 14px; display: flex; align-items: center; justify-content: space-between;">
                            <span style="font-size: 12px; font-weight: 700; color: #F8FAFC; display: flex; align-items: center; gap: 6px;">
                                <i class="fa-regular fa-image" style="color: #FB923C;"></i> ${img.label}
                            </span>
                            <span style="font-size: 11px; color: #94A3B8; display: flex; align-items: center; gap: 4px;">
                                <i class="fa-solid fa-magnifying-glass-plus"></i> Click to Zoom
                            </span>
                        </div>
                        <img src="${img.src}" alt="${img.label}" loading="lazy" style="width: 100%; height: auto; display: block; border-bottom: 1px solid var(--border-subtle);">
                        <div style="padding: 10px 14px; font-size: 12px; color: var(--text-muted); background: #F8FAFC; line-height: 1.4;">
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
                                <span class="step-badge" style="background: var(--accent-light); color: var(--accent-primary); font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; border: 1px solid rgba(234, 88, 12, 0.2);">
                                    ${step.badge}
                                </span>
                                <span style="font-size: 12px; color: var(--text-muted); font-weight: 600; display: flex; align-items: center; gap: 4px;">
                                    <i class="fa-regular fa-clock" style="color: var(--accent-primary);"></i> Est. Time: ${step.time}
                                </span>
                                <span style="font-size: 12px; color: var(--text-muted); font-weight: 600; display: flex; align-items: center; gap: 4px;">
                                    <i class="fa-regular fa-user" style="color: var(--accent-primary);"></i> Role: ${step.role}
                                </span>
                            </div>
                            <h3 style="font-size: 20px; font-weight: 800; color: var(--text-heading); margin: 0 0 8px 0;">
                                ${step.title}
                            </h3>
                            <p style="font-size: 14px; color: var(--text-body); line-height: 1.6; margin: 0;">
                                ${step.desc}
                            </p>
                        </div>
                    </div>

                    <div style="background: #F8FAFC; border: 1px solid var(--border-subtle); border-radius: 12px; padding: 18px 20px;">
                        <h4 style="font-size: 13.5px; font-weight: 700; color: var(--text-heading); margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-list-check" style="color: var(--accent-primary);"></i> Required Setup Checklist
                        </h4>
                        <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; font-size: 13.5px; color: var(--text-body); line-height: 1.5;">
                            ${checklistHtml}
                        </ul>
                    </div>

                    <div style="background: rgba(234, 88, 12, 0.06); border-left: 4px solid var(--accent-primary); border-radius: 0 10px 10px 0; padding: 12px 18px; font-size: 13px; color: #9A3412; line-height: 1.5; display: flex; align-items: flex-start; gap: 10px;">
                        <i class="fa-solid fa-lightbulb" style="color: var(--accent-primary); font-size: 15px; margin-top: 2px;"></i>
                        <div><strong>Pro Tip:</strong> ${step.callout}</div>
                    </div>

                    <div>
                        <h4 style="font-size: 13.5px; font-weight: 700; color: var(--text-heading); margin: 0 0 14px 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;">
                            <i class="fa-solid fa-display" style="color: var(--accent-primary);"></i> Screenshot Walkthrough & UI Reference
                        </h4>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
                            ${imagesHtml}
                        </div>
                    </div>
                </div>
            `;
            body.scrollTop = 0;
        }

        // Global Esc & Arrow Key support for Onboarding Modal
        window.addEventListener('keydown', function(e) {
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

        // Expose onboarding functions to window
        window.openOnboardingModal = openOnboardingModal;
        window.closeOnboardingModal = closeOnboardingModal;
        window.handleGuideModalOverlayClick = handleGuideModalOverlayClick;
        window.renderGuideStep = renderGuideStep;
        window.nextGuideStep = nextGuideStep;
        window.prevGuideStep = prevGuideStep;

        // =========================================================================
        // PRODUCTS DROPDOWN & MULTI-TIER PRODUCT DETAIL MODAL CONTROLLERS
        // =========================================================================

        function toggleProductsDropdown(event) {
            if (event) {
                event.stopPropagation();
                event.preventDefault();
            }
            const dropdown = document.getElementById('productsDropdownMenu');
            const navItem = document.getElementById('navProductsDropdown');
            const trigger = document.getElementById('productsMenuTrigger');
            if (!dropdown) return;

            const isShown = dropdown.classList.contains('show');
            if (isShown) {
                dropdown.classList.remove('show');
                if (navItem) navItem.classList.remove('active');
                if (trigger) trigger.setAttribute('aria-expanded', 'false');
            } else {
                dropdown.classList.add('show');
                if (navItem) navItem.classList.add('active');
                if (trigger) trigger.setAttribute('aria-expanded', 'true');
            }
        }

        function closeProductsDropdown() {
            const dropdown = document.getElementById('productsDropdownMenu');
            const navItem = document.getElementById('navProductsDropdown');
            const trigger = document.getElementById('productsMenuTrigger');
            if (dropdown) dropdown.classList.remove('show');
            if (navItem) navItem.classList.remove('active');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        }

        // Click outside closes dropdown
        document.addEventListener('click', function(e) {
            const navItem = document.getElementById('navProductsDropdown');
            if (navItem && !navItem.contains(e.target)) {
                closeProductsDropdown();
            }
        });

        function selectProductView(productKey) {
            const validKeys = ['attendance', 'leave', 'payroll'];
            const targetKey = validKeys.includes(productKey) ? productKey : 'attendance';

            // 1. Update Tab Buttons
            validKeys.forEach(k => {
                const btn = document.getElementById(`tabBtn${capitalize(k)}`);
                const panel = document.getElementById(`productPanel${capitalize(k)}`);
                if (btn) {
                    if (k === targetKey) {
                        btn.classList.add('active');
                        btn.setAttribute('aria-selected', 'true');
                    } else {
                        btn.classList.remove('active');
                        btn.setAttribute('aria-selected', 'false');
                    }
                }
                if (panel) {
                    if (k === targetKey) {
                        panel.classList.add('active');
                        panel.style.display = 'block';
                    } else {
                        panel.classList.remove('active');
                        panel.style.display = 'none';
                    }
                }
            });

            // 2. Smoothly scroll to product section
            const productSection = document.getElementById('product');
            if (productSection) {
                productSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        function capitalize(str) {
            if (!str) return '';
            return str.charAt(0).toUpperCase() + str.slice(1);
        }

        // Product Specification Data for Deep-Dive Modal
        const PRODUCT_SPECS_DATA = {
            attendance: {
                title: "Face based Attendance System",
                badge: "Biometrics & Kiosks",
                icon: "fa-face-smile",
                color: "var(--accent-primary)",
                subtitle: "Comparative biometric architecture and feature matrix across Basic, Smart, and Pro editions.",
                specs: [
                    { param: "Face Recognition Biometric Engine", basic: "1:N Euclidean vector match", smart: "1:N Euclidean with liveness checks", pro: "Sub-250ms ResNet 128-d + Temporal Anti-Spoof Liveness" },
                    { param: "Supported Hardware & Terminals", basic: "1 Laptop / USB Webcam Kiosk", smart: "Multi-Location Kiosks + Employee Mobile GPS", pro: "Unlimited Edge Raspberry Pi / PC Nodes + Mobile" },
                    { param: "Branch & Multi-Location Deployment", basic: "Single Physical Office", smart: "Multi-Branch Distributed Offices", pro: "Centralized Enterprise HQ & Unlimited Stores" },
                    { param: "Shift Scheduling & Flexibility", basic: "Standard Daily Shift Hours", smart: "Dynamic Morning, Evening & Overnight Shifts", pro: "Rotational Rosters, Grace Windows & Auto-Half Day" },
                    { param: "Mobile GPS Geofencing Protection", basic: "Not Included (Kiosk Only)", smart: "Haversine Perimeter & Mock GPS Protection", pro: "Reverse-Geocoded Street Verification & Geofences" },
                    { param: "Real-Time Streaming HUD & RAM Cache", basic: "Manual CSV Attendance Log Export", smart: "Daily Sync & Defaulter Attendance Filters", pro: "Live Server-Sent Events (SSE) HUD & RAM Vector Cache" },
                    { param: "Security & Encryption Standard", basic: "Standard Salted Hashes", smart: "Tenant-Isolated Encrypted Vectors", pro: "Bank-Grade 128-d Vector Encryption & Audit Trail" },
                    { param: "Support & SLA", basic: "Standard Email Support", smart: "Priority Business Hours Support", pro: "Dedicated Account Manager & 99.9% Cloud SLA" }
                ]
            },
            leave: {
                title: "Leave Management Software",
                badge: "Absence Governance",
                icon: "fa-calendar-check",
                color: "var(--success-emerald)",
                subtitle: "Comparative absence governance, approval queues, and balance ledgers across Basic, Smart, and Pro editions.",
                specs: [
                    { param: "Leave Application Workflow", basic: "Self-Service Application Submission", smart: "Multi-Tier Approval (Manager &rarr; Admin)", pro: "Custom Hierarchical Approval with Auto-Escalation" },
                    { param: "Leave Categories & Balances", basic: "Static Annual Entitlement Ledger", smart: "Dedicated Casual (CL), Sick (SL), Paid (PL) Ledgers", pro: "Custom Enterprise Policies (Maternity, Paternity, Comp-Off)" },
                    { param: "Automated Accruals Engine", basic: "Manual Annual Allocation", smart: "Automated Monthly Accrual Processing", pro: "Custom Accrual Frequencies, Rollover & Encashment" },
                    { param: "Holiday Management System", basic: "Static Company Holiday Notice", smart: "Centralized Institutional Holiday Master", pro: "Location-Specific Regional & Festival Holiday Calendars" },
                    { param: "Payroll & Loss of Pay (LOP) Sync", basic: "Manual Unpaid Leave Deductions", smart: "Automated Loss of Pay (LOP) Hours Calculation", pro: "Real-Time Biometric Absence to Payroll Net Pay Sync" },
                    { param: "Leave Ledgers & Defaulter Flags", basic: "Basic Request History Log", smart: "Departmental Leave Utilization Reports", pro: "Full Immutable Audit Trail & Defaulter Flagging" },
                    { param: "Notification Triggers", basic: "Basic Email on Status Decision", smart: "Real-time Email to Managers & Staff", pro: "Omni-Channel Email & In-App Status Alerts" },
                    { param: "Support & SLA", basic: "Standard Email Support", smart: "Priority Business Hours Support", pro: "Dedicated Account Manager & 99.9% Cloud SLA" }
                ]
            },
            payroll: {
                title: "Payroll Management System",
                badge: "Automated Compensation",
                icon: "fa-money-check-dollar",
                color: "var(--tech-indigo)",
                subtitle: "Comparative automated compensation, batch processing, and payslip generation across Basic, Smart, and Pro editions.",
                specs: [
                    { param: "Compensation Calculation Model", basic: "Flat Base Monthly Salary Assignment", smart: "Dynamic % Formula Templates (Basic, HRA, DA)", pro: "Custom Multi-Tier CTC Structures & Performance Bonuses" },
                    { param: "Biometric Attendance Hours Sync", basic: "Manual Working Days Input", smart: "Automated Clock-In Hours & LOP Deductions", pro: "Precision Biometric Overtime, Half-Day & LOP Engine" },
                    { param: "Statutory Deductions Compliance", basic: "Fixed Amount Deductions", smart: "Statutory PF, ESIC, Professional Tax (PT), TDS", pro: "Custom Gratuity, Bonus Formulas & Compliance Registers" },
                    { param: "Batch Payroll Processing", basic: "Single Employee Slip Generation", smart: "Departmental Batch Payroll Execution", pro: "1-Click Platform-Wide Batch Payroll Execution" },
                    { param: "PDF Payslips & Distribution", basic: "Printable Browser Payslip View", smart: "Employee Mobile Portal PDF Payslip Downloads", pro: "Company-Branded PDF Payslips with QR & Automated Email" },
                    { param: "Bank Advice & Compliance Reports", basic: "Basic CSV Payroll Export", smart: "Monthly Net Pay Summary & Bank Advices", pro: "Direct NEFT / RTGS Bank Advice Sheet & Tax Ledgers" },
                    { param: "Salary Revisions & Historical Log", basic: "Overwrites Current Rate", smart: "Effective-Dated Salary Revision Log", pro: "Full Versioned Salary History & Compensation Audits" },
                    { param: "Support & SLA", basic: "Standard Email Support", smart: "Priority Business Hours Support", pro: "Dedicated Account Manager & 99.9% Cloud SLA" }
                ]
            }
        };

        function openProductModal(productKey) {
            const data = PRODUCT_SPECS_DATA[productKey] || PRODUCT_SPECS_DATA.attendance;
            const modal = document.getElementById('productDetailModal');
            const titleEl = document.getElementById('modalProductTitle');
            const badgeEl = document.getElementById('modalProductBadge');
            const iconEl = document.getElementById('modalProductIcon');
            const iconContainer = document.getElementById('modalProductIconContainer');
            const subtitleEl = document.getElementById('modalProductSubtitle');
            const tableContainer = document.getElementById('modalComparisonTableContainer');

            if (!modal || !tableContainer) return;

            if (titleEl) titleEl.textContent = data.title;
            if (badgeEl) badgeEl.textContent = data.badge;
            if (subtitleEl) subtitleEl.textContent = data.subtitle;
            if (iconEl) iconEl.className = `fa-solid ${data.icon}`;
            if (iconContainer) {
                iconContainer.style.color = data.color;
                iconContainer.style.background = data.color.replace('var(', '').replace(')', '') === '--accent-primary' ? 'rgba(234, 88, 12, 0.12)' : (data.color.replace('var(', '').replace(')', '') === '--success-emerald' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(79, 70, 229, 0.12)');
            }

            // Render Comparative Specs Table
            let rowsHtml = data.specs.map(row => `
                <tr>
                    <td class="feature-name">${row.param}</td>
                    <td class="tier-cell">
                        <span style="display: block; font-size: 12px; font-weight: 600; color: var(--text-heading);">${row.basic}</span>
                    </td>
                    <td class="tier-cell" style="background: rgba(234, 88, 12, 0.03);">
                        <span style="display: block; font-size: 12px; font-weight: 700; color: var(--accent-primary);">${row.smart}</span>
                    </td>
                    <td class="tier-cell">
                        <span style="display: block; font-size: 12px; font-weight: 700; color: var(--text-heading);">${row.pro}</span>
                    </td>
                </tr>
            `).join('');

            tableContainer.innerHTML = `
                <div class="spec-table-container">
                    <table class="spec-table">
                        <thead>
                            <tr>
                                <th style="width: 32%;">Capability / Feature</th>
                                <th style="width: 22.6%; text-align: center;">
                                    <div style="font-weight: 800; font-size: 13px; color: var(--text-heading);">BASIC EDITION</div>
                                    <div style="font-size: 10.5px; color: var(--text-muted); text-transform: none;">Essential Operations</div>
                                </th>
                                <th style="width: 22.6%; text-align: center; background: #FFF7ED; border-top: 3px solid var(--accent-primary);">
                                    <div style="font-weight: 800; font-size: 13px; color: var(--accent-primary);">SMART EDITION</div>
                                    <div style="font-size: 10.5px; color: var(--accent-primary); text-transform: none; font-weight: 600;">Multi-Location &amp; GPS</div>
                                </th>
                                <th style="width: 22.6%; text-align: center;">
                                    <div style="font-weight: 800; font-size: 13px; color: var(--text-heading);">PRO EDITION</div>
                                    <div style="font-size: 10.5px; color: var(--text-muted); text-transform: none;">Enterprise Automated</div>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                </div>
            `;

            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeProductModal() {
            const modal = document.getElementById('productDetailModal');
            if (modal) {
                modal.style.display = 'none';
                document.body.style.overflow = '';
            }
        }

        // Global Esc key for product detail modal
        window.addEventListener('keydown', function(e) {
            const modal = document.getElementById('productDetailModal');
            if (modal && modal.style.display === 'flex' && e.key === 'Escape') {
                closeProductModal();
            }
        });

        // Expose product functions to window
        window.toggleProductsDropdown = toggleProductsDropdown;
        window.closeProductsDropdown = closeProductsDropdown;
        window.selectProductView = selectProductView;
        window.openProductModal = openProductModal;
        window.closeProductModal = closeProductModal;
