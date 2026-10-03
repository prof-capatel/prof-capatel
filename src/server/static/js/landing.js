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
        // Quick Onboarding Interactive Guide Modal Keyboard Listeners
        // (Full step definitions and rendering logic loaded from onboarding_guide.js)
        // =========================================================================
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
