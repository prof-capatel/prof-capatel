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
        if (!sidebar) return;
        sidebar.classList.remove("open");
        if (backdrop) backdrop.classList.remove("active");
    }

    // Close drawer & modals on Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeMobileMenu();
            if (typeof closeLightbox === "function") closeLightbox();
            if (typeof closeEditModal === "function") closeEditModal();
            if (typeof closeRetakeModal === "function") closeRetakeModal();
            if (typeof closeManualOverrideModal === "function") closeManualOverrideModal();
        }
    });

    /* ==========================================================
       Multi-Theme Engine Handlers
       ========================================================== */
    function initThemeSwitcher() {
        const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
        if (typeof updateQuickThemeButton === "function") {
            updateQuickThemeButton(currentTheme);
        }
        updateThemeSelectionCards(currentTheme);
        updateThemeDropdown(currentTheme);
    }

    function setAppTheme(themeName) {
        let normalized = themeName;
        if (normalized === "academic") normalized = "warm";
        if (normalized === "corporate" || normalized === "slate") normalized = "warm";
        if (!["light", "dark", "warm"].includes(normalized)) {
            normalized = "light";
        }
        document.documentElement.setAttribute("data-theme", normalized);
        try {
            localStorage.setItem("app_theme", normalized);
        } catch (e) {}

        updateThemeSelectionCards(normalized);
        updateThemeDropdown(normalized);
    }

    function cycleAppTheme() {
        const currentTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
        let nextTheme = "light";
        if (currentTheme === "light") nextTheme = "dark";
        else if (currentTheme === "dark") nextTheme = "warm";
        else nextTheme = "light";

        setAppTheme(nextTheme);
    }

    function updateThemeDropdown(theme) {
        let current = theme || document.documentElement.getAttribute("data-theme") || localStorage.getItem("app_theme") || "light";
        if (current === "academic" || current === "corporate" || current === "slate") current = "warm";
        const select = document.getElementById("appThemeSelect");
        const mobileSelect = document.getElementById("mobileAppThemeSelect");
        const icon = document.getElementById("themeIconIndicator");
        if (select) select.value = current;
        if (mobileSelect) mobileSelect.value = current;
        if (icon) {
            if (current === "dark") {
                icon.className = "fa-solid fa-moon";
                icon.style.color = "#38bdf8";
            } else if (current === "warm") {
                icon.className = "fa-solid fa-fire-flame-curved";
                icon.style.color = "#ea580c";
            } else {
                icon.className = "fa-solid fa-sun";
                icon.style.color = "#f59e0b";
            }
        }
    }

    function updateThemeSelectionCards(theme) {
        let current = theme || document.documentElement.getAttribute("data-theme") || "light";
        if (current === "academic" || current === "corporate" || current === "slate") current = "warm";
        const cardLight = document.getElementById("themeCardLight");
        const cardDark = document.getElementById("themeCardDark");
        const cardWarm = document.getElementById("themeCardWarm") || document.getElementById("themeCardAcademic");
        const badge = document.getElementById("activeThemeBadge");

        if (cardLight) cardLight.classList.toggle("active", current === "light");
        if (cardDark) cardDark.classList.toggle("active", current === "dark");
        if (cardWarm) cardWarm.classList.toggle("active", current === "warm");

        if (badge) {
            if (current === "dark") {
                badge.className = "badge badge-sky";
                badge.innerHTML = '<i class="fa-solid fa-moon"></i> Active: Midnight Dark';
            } else if (current === "warm") {
                badge.className = "badge badge-amber";
                badge.innerHTML = '<i class="fa-solid fa-fire-flame-curved"></i> Active: Warm';
            } else {
                badge.className = "badge badge-present";
                badge.innerHTML = '<i class="fa-solid fa-sun"></i> Active: Clean Light';
            }
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        initThemeSwitcher();
    });

    window.setAppTheme = setAppTheme;
    window.cycleAppTheme = cycleAppTheme;
    window.updateThemeDropdown = updateThemeDropdown;
    window.updateThemeSelectionCards = updateThemeSelectionCards;
    window.initThemeSwitcher = initThemeSwitcher;
    window.toggleMobileMenu = toggleMobileMenu;
    window.closeMobileMenu = closeMobileMenu;

    // ==========================================================
    // Collapsible Biometric Terminal Gateway Handler
    // ==========================================================
    function toggleBiometricGateway(e) {
        if (e && e.preventDefault) {
            // Prevent default if triggered from an anchor or button click
        }
        const body = document.getElementById("biometricGatewayBody");
        const chevron = document.getElementById("gatewayChevron");
        const toggleText = document.getElementById("gatewayToggleText");
        if (!body) return;

        const isCurrentlyHidden = body.style.display === "none" || (!body.style.display && window.getComputedStyle(body).display === "none");
        if (isCurrentlyHidden) {
            body.style.display = "block";
            if (chevron) chevron.style.transform = "rotate(90deg)";
            if (toggleText) toggleText.textContent = "Hide Details";
        } else {
            body.style.display = "none";
            if (chevron) chevron.style.transform = "rotate(0deg)";
            if (toggleText) toggleText.textContent = "Show Details";
        }
    }
    window.toggleBiometricGateway = toggleBiometricGateway;

    // ==========================================================
    // Dashboard Stats Loader
    // ==========================================================
    async function loadStats() {
        try {
            const res = await fetch('/api/v1/attendance/stats');
            const data = await res.json();
            if (data) {
                if (data.present_today !== undefined && document.getElementById('statPresentCount')) document.getElementById('statPresentCount').innerText = data.present_today;
                if (data.total_students !== undefined && document.getElementById('statTotalStudents')) document.getElementById('statTotalStudents').innerText = data.total_students;
                if (data.checked_out_today !== undefined && document.getElementById('statCheckedOutCount')) document.getElementById('statCheckedOutCount').innerText = data.checked_out_today;
                if (data.absent_today !== undefined && document.getElementById('statAbsentCount')) document.getElementById('statAbsentCount').innerText = data.absent_today;
                if (data.today_leaves_count !== undefined && document.getElementById('statTodayLeavesCount')) document.getElementById('statTodayLeavesCount').innerText = data.today_leaves_count;
                if (data.pending_leaves_count !== undefined && document.getElementById('statPendingLeavesCount')) document.getElementById('statPendingLeavesCount').innerText = data.pending_leaves_count;
                if (data.shift_hours_display && document.getElementById('statShiftHours')) document.getElementById('statShiftHours').innerText = data.shift_hours_display;
            }
        } catch (e) {}

        try {
            const bRes = await fetch('/api/v1/branding');
            const bData = await bRes.json();
            if (bData && bData.branding && bData.branding.cooldown_minutes) {
                const el = document.getElementById('statCooldownWindow');
                if (el) el.innerText = `${bData.branding.cooldown_minutes} Mins`;
            }
        } catch (e) {}
    }
    loadStats();

    // Copy Gateway Links with Full Origin
    function copyDashLink(inputId, btn) {
        const input = document.getElementById(inputId);
        if (!input) return;
        let fullUrl = input.value;
        if (fullUrl.startsWith('/')) {
            fullUrl = window.location.origin + fullUrl;
        }
        navigator.clipboard.writeText(fullUrl).then(() => {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-check" style="color: #10b981;"></i>';
            setTimeout(() => {
                btn.innerHTML = originalHtml;
            }, 1800);
        }).catch(err => {
            console.error('Failed to copy link:', err);
        });
    }

    // Format input fields with origin on load
    document.addEventListener('DOMContentLoaded', () => {
        ['dashPortalUrl', 'dashOnboardUrl'].forEach(id => {
            const el = document.getElementById(id);
            if (el && el.value.startsWith('/')) {
                el.value = window.location.origin + el.value;
            }
        });
        initDraggableCameraCard();
        enumerateCaptureDevices();
    });

    // ==========================================================
    // INLINE CONTINUOUS BIOMETRIC SCANNER ENGINE
    // ==========================================================
    let captureMediaStream = null;
    let captureIntervalTimer = null;
    let isCaptureIngesting = false;
    let isContinuousActive = false;
    let isInitializingCapture = false;
    let isInterruptedState = false;
    let pausedForSecondaryCamera = false;
    let consecutiveIngestErrors = 0;
    let captureToastTimer = null;
    let soundEnabled = true;

    // Expose on window for arbitration & modal integration
    window.isContinuousActive = false;
    window.isInterruptedState = false;

    // Configurable client-side debounce cooldown (3 seconds per employee)
    const CLIENT_DEBOUNCE_MS = 3000;
    const lastRecognitionTimes = new Map(); // student_id -> timestamp ms

    // Background-resilient Web Worker timer to avoid tab throttling / pausing
    function createBackgroundWorkerTimer(callback, intervalMs) {
        if (typeof Worker !== "undefined" && typeof Blob !== "undefined") {
            try {
                const workerScript = `
                    let timer = null;
                    self.onmessage = function(e) {
                        if (e.data === 'start') {
                            if (timer) clearInterval(timer);
                            timer = setInterval(function() { self.postMessage('tick'); }, ${intervalMs});
                        } else if (e.data === 'stop') {
                            if (timer) clearInterval(timer);
                            timer = null;
                        }
                    };
                `;
                const blob = new Blob([workerScript], { type: "application/javascript" });
                const worker = new Worker(URL.createObjectURL(blob));
                worker.onmessage = function(e) {
                    if (e.data === 'tick') callback();
                };
                return {
                    start: function() { worker.postMessage('start'); },
                    stop: function() { worker.postMessage('stop'); },
                    terminate: function() {
                        try {
                            worker.postMessage('stop');
                            worker.terminate();
                        } catch(e) {}
                    }
                };
            } catch (err) {
                console.warn("[Camera] Web Worker timer creation failed, using fallback:", err);
            }
        }
        let fallbackTimer = null;
        return {
            start: function() {
                if (fallbackTimer) clearInterval(fallbackTimer);
                fallbackTimer = setInterval(callback, intervalMs);
            },
            stop: function() {
                if (fallbackTimer) clearInterval(fallbackTimer);
                fallbackTimer = null;
            },
            terminate: function() {
                if (fallbackTimer) clearInterval(fallbackTimer);
                fallbackTimer = null;
            }
        };
    }

    function toggleScannerSound() {
        soundEnabled = !soundEnabled;
        const icon = document.getElementById("soundIcon");
        if (icon) {
            icon.className = soundEnabled ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
            icon.style.color = soundEnabled ? "var(--accent-primary)" : "var(--text-muted)";
        }
    }

    function playSuccessChime() {
        if (!soundEnabled) return;
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
            osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.1); // A5
            
            gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
            
            osc.start();
            osc.stop(audioCtx.currentTime + 0.35);
        } catch (e) {}
    }

    async function toggleContinuousCapture() {
        if (isContinuousActive) {
            stopContinuousCapture();
        } else {
            await startContinuousCapture();
        }
    }

    async function startContinuousCapture() {
        if (isContinuousActive || isInitializingCapture) return;
        isInitializingCapture = true;

        try {
            isInterruptedState = false;
            window.isInterruptedState = false;
            consecutiveIngestErrors = 0;

            const success = await initCaptureCamera();
            if (!success) return;

            isContinuousActive = true;
            window.isContinuousActive = true;
            updateScannerUIState(true);

            // Resilient background capture loop at ~2.5 FPS (every 400ms) with in-flight ingestion guard
            if (captureIntervalTimer) {
                if (typeof captureIntervalTimer.terminate === "function") captureIntervalTimer.terminate();
                else clearInterval(captureIntervalTimer);
                captureIntervalTimer = null;
            }
            captureIntervalTimer = createBackgroundWorkerTimer(() => {
                if (isContinuousActive && !isCaptureIngesting) {
                    captureAndIngestFrame(false);
                }
            }, 400);
            captureIntervalTimer.start();
        } finally {
            isInitializingCapture = false;
        }
    }

    function stopContinuousCapture() {
        isContinuousActive = false;
        window.isContinuousActive = false;
        if (captureIntervalTimer) {
            if (typeof captureIntervalTimer.terminate === "function") captureIntervalTimer.terminate();
            else clearInterval(captureIntervalTimer);
            captureIntervalTimer = null;
        }

        if (captureMediaStream) {
            try {
                captureMediaStream.getTracks().forEach(t => t.stop());
            } catch(e) {}
            captureMediaStream = null;
        }

        const canvas = document.getElementById("captureCanvas");
        if (canvas) {
            const ctx = canvas.getContext("2d");
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }

        updateScannerUIState(false);
    }

    function pauseForSecondaryCamera() {
        if (isContinuousActive) {
            pausedForSecondaryCamera = true;
            isContinuousActive = false;
            window.isContinuousActive = false;
            if (captureIntervalTimer) {
                if (typeof captureIntervalTimer.terminate === "function") captureIntervalTimer.terminate();
                else clearInterval(captureIntervalTimer);
                captureIntervalTimer = null;
            }
            if (captureMediaStream) {
                try {
                    captureMediaStream.getTracks().forEach(t => t.stop());
                } catch(e) {}
                captureMediaStream = null;
            }
            updateScannerUIState(false, false, "", true);
            return true;
        }
        return false;
    }

    async function resumeFromSecondaryCamera() {
        if (pausedForSecondaryCamera) {
            pausedForSecondaryCamera = false;
            await startContinuousCapture();
        }
    }

    // Expose control functions globally
    window.startContinuousCapture = startContinuousCapture;
    window.stopContinuousCapture = stopContinuousCapture;
    window.pauseForSecondaryCamera = pauseForSecondaryCamera;
    window.resumeFromSecondaryCamera = resumeFromSecondaryCamera;

    function handleCaptureInterrupted(reason) {
        if (!isContinuousActive && isInterruptedState) return;
        isContinuousActive = false;
        window.isContinuousActive = false;
        isInterruptedState = true;
        window.isInterruptedState = true;

        if (captureIntervalTimer) {
            if (typeof captureIntervalTimer.terminate === "function") captureIntervalTimer.terminate();
            else clearInterval(captureIntervalTimer);
            captureIntervalTimer = null;
        }

        if (captureMediaStream) {
            try {
                captureMediaStream.getTracks().forEach(t => t.stop());
            } catch (e) {}
            captureMediaStream = null;
            captureMediaStream = null;
        }

        const canvas = document.getElementById("captureCanvas");
        if (canvas) {
            const ctx = canvas.getContext("2d");
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }

        updateScannerUIState(false, true, reason);
    }

    function updateScannerUIState(isActive, isInterrupted = false, interruptReason = "", isPaused = false) {
        const card = document.getElementById("inlineCameraCard");
        const standbyOverlay = document.getElementById("captureStandbyOverlay");
        const standbyTitle = document.getElementById("captureStandbyTitle");
        const standbyDesc = document.getElementById("captureStandbyDesc");
        const radarLine = document.getElementById("scannerRadarLine");
        const hudTag = document.getElementById("hudLiveTag");
        const pill = document.getElementById("cameraStatusPill");

        // Card button
        const cardBtn = document.getElementById("btnCardToggleCapture");
        const cardIcon = document.getElementById("btnCardIcon");
        const cardText = document.getElementById("btnCardText");

        if (isActive) {
            if (card) {
                card.classList.add("scanner-active-glow");
                card.style.borderColor = "var(--accent-primary)";
            }
            if (standbyOverlay) standbyOverlay.style.display = "none";
            if (radarLine) radarLine.style.display = "block";
            if (hudTag) hudTag.style.display = "flex";

            if (pill) {
                pill.className = "badge badge-present";
                pill.innerHTML = '<span class="pulse-dot"></span> SCANNING';
            }

            if (cardBtn) {
                cardBtn.className = "btn btn-danger";
                if (cardIcon) cardIcon.className = "fa-solid fa-stop";
                if (cardText) cardText.innerText = "Stop Attendance Capture";
            }
        } else if (isInterrupted) {
            if (card) {
                card.classList.remove("scanner-active-glow");
                card.style.borderColor = "var(--accent-rose, #ef4444)";
            }
            if (standbyOverlay) standbyOverlay.style.display = "flex";
            if (standbyTitle) {
                standbyTitle.innerHTML = '<span style="color: #ef4444; display: flex; align-items: center; justify-content: center; gap: 6px;"><i class="fa-solid fa-triangle-exclamation"></i> Feed Interrupted</span>';
            }
            if (standbyDesc) {
                standbyDesc.innerText = interruptReason || "Camera capture was interrupted. Click below to restart.";
            }
            if (radarLine) radarLine.style.display = "none";
            if (hudTag) hudTag.style.display = "none";

            if (pill) {
                pill.className = "badge badge-absent";
                pill.innerHTML = '<span class="pulse-dot" style="background: #ef4444;"></span> ⚠️ INTERRUPTED';
            }

            if (cardBtn) {
                cardBtn.className = "btn btn-primary";
                if (cardIcon) cardIcon.className = "fa-solid fa-rotate-right";
                if (cardText) cardText.innerText = "Restart Attendance Feed";
            }
        } else if (isPaused) {
            if (card) {
                card.classList.remove("scanner-active-glow");
                card.style.borderColor = "var(--accent-amber, #f59e0b)";
            }
            if (standbyOverlay) standbyOverlay.style.display = "flex";
            if (standbyTitle) {
                standbyTitle.innerHTML = '<span style="color: #f59e0b; display: flex; align-items: center; justify-content: center; gap: 6px;"><i class="fa-solid fa-pause"></i> Feed Paused</span>';
            }
            if (standbyDesc) {
                standbyDesc.innerText = "Camera in use for photo capture. Will resume automatically when completed.";
            }
            if (radarLine) radarLine.style.display = "none";
            if (hudTag) hudTag.style.display = "none";

            if (pill) {
                pill.className = "badge badge-amber";
                pill.innerHTML = '● PAUSED';
            }

            if (cardBtn) {
                cardBtn.className = "btn btn-primary";
                if (cardIcon) cardIcon.className = "fa-solid fa-play";
                if (cardText) cardText.innerText = "Resume Attendance Feed";
            }
        } else {
            if (card) {
                card.classList.remove("scanner-active-glow");
                card.style.borderColor = "var(--border-color)";
            }
            if (standbyOverlay) standbyOverlay.style.display = "flex";
            if (standbyTitle) {
                standbyTitle.innerText = "Camera Scanner Standby";
            }
            if (standbyDesc) {
                standbyDesc.innerText = "Click below to activate continuous face recognition for employee check-ins.";
            }
            if (radarLine) radarLine.style.display = "none";
            if (hudTag) hudTag.style.display = "none";

            if (pill) {
                pill.className = "badge badge-unknown";
                pill.innerHTML = "● IDLE";
            }

            if (cardBtn) {
                cardBtn.className = "btn btn-primary";
                if (cardIcon) cardIcon.className = "fa-solid fa-play";
                if (cardText) cardText.innerText = "Start Attendance Capture";
            }
        }
    }

    async function initCaptureCamera(deviceId = null) {
        const standbyOverlay = document.getElementById("captureStandbyOverlay");
        const standbyTitle = document.getElementById("captureStandbyTitle");
        const standbyDesc = document.getElementById("captureStandbyDesc");
        const video = document.getElementById("captureVideo");

        if (captureMediaStream) {
            try {
                captureMediaStream.getTracks().forEach(t => t.stop());
            } catch(e) {}
            captureMediaStream = null;
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            if (standbyTitle) standbyTitle.innerText = "Camera API Not Supported";
            if (standbyDesc) standbyDesc.innerText = "Your browser does not support mediaDevices or HTTPS/localhost is required.";
            return false;
        }

        try {
            const constraints = {
                video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
                audio: false
            };
            captureMediaStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = captureMediaStream;
            await video.play();

            // Track hardware interruption / disconnect events
            const videoTrack = captureMediaStream.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.onended = () => {
                    console.warn("[Camera] Live capture video track ended / disconnected.");
                    handleCaptureInterrupted("Camera connection was closed or disconnected by the system.");
                };
                videoTrack.onmute = () => {
                    console.warn("[Camera] Live capture video track muted/occluded (background or minimized); maintaining active capture stream.");
                };
                videoTrack.onunmute = () => {
                    console.log("[Camera] Live capture video track unmuted / active in foreground.");
                };
            }

            if (standbyOverlay) standbyOverlay.style.display = "none";
            await enumerateCaptureDevices();
            return true;
        } catch (err) {
            console.error("Camera access failed:", err);
            handleCaptureInterrupted("Webcam access failed or permission was denied.");
            return false;
        }
    }

    async function enumerateCaptureDevices() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(d => d.kind === "videoinput");
            const select = document.getElementById("captureCameraSelect");
            if (!select) return;

            const currentVal = select.value;
            select.innerHTML = "";
            videoDevices.forEach((dev, idx) => {
                const opt = document.createElement("option");
                opt.value = dev.deviceId;
                opt.text = dev.label || `Camera ${idx + 1}`;
                if (dev.deviceId === currentVal) opt.selected = true;
                select.appendChild(opt);
            });
        } catch (e) {}
    }

    function switchCaptureCamera(devId) {
        if (devId && isContinuousActive) {
            initCaptureCamera(devId);
        }
    }

    function captureManualSingleShot() {
        if (isCaptureIngesting) return;
        captureAndIngestFrame(true);
    }

    async function captureAndIngestFrame(isSingleShot = false) {
        if (!captureMediaStream || isCaptureIngesting) return;
        const video = document.getElementById("captureVideo");
        const canvas = document.getElementById("captureCanvas");
        if (!video || !canvas || video.videoWidth === 0) return;

        isCaptureIngesting = true;

        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
        }

        const tempCanvas = document.createElement("canvas");
        tempCanvas.width = Math.min(640, video.videoWidth);
        tempCanvas.height = Math.round(tempCanvas.width * (video.videoHeight / video.videoWidth));
        const ctx = tempCanvas.getContext("2d");
        ctx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

        tempCanvas.toBlob(async (blob) => {
            if (!blob) {
                isCaptureIngesting = false;
                return;
            }

            const formData = new FormData();
            formData.append("frame", blob, "dash_frame.jpg");
            formData.append("node_id", "DASHBOARD-CAMERA");
            formData.append("location", "Live Terminal");
            if (isSingleShot) formData.append("is_single_shot", "true");

            try {
                const res = await fetch("/api/v1/nodes/frame", {
                    method: "POST",
                    body: formData
                });

                if (res.ok) {
                    consecutiveIngestErrors = 0;
                    const data = await res.json();
                    renderCaptureDetections(data.detections || [], canvas, tempCanvas.width, tempCanvas.height);
                } else {
                    consecutiveIngestErrors++;
                    if (consecutiveIngestErrors >= 8) {
                        handleCaptureInterrupted("Recognition backend server error.");
                    }
                }
            } catch (err) {
                console.warn("Frame transmission error:", err);
                consecutiveIngestErrors++;
                if (consecutiveIngestErrors >= 8) {
                    handleCaptureInterrupted("Network connection to recognition server interrupted.");
                }
            } finally {
                isCaptureIngesting = false;
            }
        }, "image/jpeg", 0.75);
    }

    function renderCaptureDetections(detections, canvas, frameW = 640, frameH = 480) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!detections || detections.length === 0) return;

        const now = Date.now();

        detections.forEach(det => {
            const isMatch = Boolean(det.is_match);
            const name = det.name || "Unknown";
            const roll = det.roll_number || "";
            const studentId = det.student_id;
            const conf = Math.round((1.0 - Math.min(1.0, det.distance || 0.6)) * 100);

            // Safe bounding box extraction supporting both Object and Array structures
            let top = 0, right = 0, bottom = 0, left = 0, hasBox = false;
            if (det.box) {
                if (Array.isArray(det.box) && det.box.length >= 4) {
                    [top, right, bottom, left] = det.box;
                    hasBox = true;
                } else if (typeof det.box === "object") {
                    top = Number(det.box.top) || 0;
                    right = Number(det.box.right) || 0;
                    bottom = Number(det.box.bottom) || 0;
                    left = Number(det.box.left) || 0;
                    hasBox = true;
                }
            }

            if (hasBox) {
                try {
                    const sentW = det.frame_width || frameW || 640;
                    const sentH = det.frame_height || frameH || 480;
                    const scaleX = canvas.width / sentW;
                    const scaleY = canvas.height / sentH;

                    const x = left * scaleX;
                    const y = top * scaleY;
                    const w = Math.max(10, (right - left) * scaleX);
                    const h = Math.max(10, (bottom - top) * scaleY);

                    // Mirrored canvas coordinates
                    const mirroredX = canvas.width - (x + w);

                    ctx.strokeStyle = isMatch ? "#10b981" : "#f59e0b";
                    ctx.lineWidth = 3;
                    ctx.beginPath();
                    if (typeof ctx.roundRect === "function") {
                        ctx.roundRect(mirroredX, y, w, h, 8);
                    } else {
                        ctx.rect(mirroredX, y, w, h);
                    }
                    ctx.stroke();

                    // Draw Label Pill
                    ctx.fillStyle = isMatch ? "rgba(16, 185, 129, 0.9)" : "rgba(245, 158, 11, 0.9)";
                    const labelW = Math.max(110, w);
                    ctx.fillRect(mirroredX, Math.max(0, y - 24), labelW, 24);

                    ctx.fillStyle = "#ffffff";
                    ctx.font = "bold 12px sans-serif";
                    ctx.fillText(`${name} (${conf}%)`, mirroredX + 6, Math.max(16, y - 7));
                } catch (drawErr) {
                    console.warn("Canvas box draw notice:", drawErr);
                }
            }

            // Trigger recognition toast & chime ONLY when attendance is successfully logged
            if (isMatch && det.attendance_logged) {
                try {
                    const idKey = String(studentId || name || roll || "matched_face");
                    const lastSeen = lastRecognitionTimes.get(idKey) || 0;
                    if (now - lastSeen >= CLIENT_DEBOUNCE_MS) {
                        lastRecognitionTimes.set(idKey, now);
                        showCaptureToast(name, roll, conf, det.punch_type || "Attendance Recorded", det.department || "");
                        playSuccessChime();
                    }
                } catch (toastErr) {
                    console.error("Toast trigger notice:", toastErr);
                }
            }
        });
    }

    const FLASH_DURATION_MS = 2500; // 2.5 seconds display duration before smooth fade

    function showCaptureToast(name, roll, conf, punchType, dept = "") {
        const toast = document.getElementById("captureMatchToast");
        const container = document.getElementById("cameraViewportContainer");
        const actionBadge = document.getElementById("toastActionBadge");
        const nameEl = document.getElementById("toastMatchName");
        const subEl = document.getElementById("toastMatchSub");
        const confEl = document.getElementById("toastMatchConfidence");
        const timeEl = document.getElementById("toastMatchTime");
        const iconWrapper = document.getElementById("toastIconWrapper");
        const statusIcon = document.getElementById("toastStatusIcon");

        if (!toast) return;

        // Trigger perimeter container flash glow
        if (container) {
            container.classList.remove("camera-flash-active");
            void container.offsetWidth; // Force reflow
            container.classList.add("camera-flash-active");
        }

        const pType = (punchType || "CHECK_IN").toUpperCase();
        const isCheckOut = pType.includes("OUT") || pType === "CHECK_OUT";

        // Format headline: "Checked In: Jane Smith" or "Checked Out: Jane Smith"
        let headlineText = "";
        let badgeText = "";
        let iconClass = "fa-solid fa-check";
        let gradientBg = "linear-gradient(135deg, #10b981 0%, #059669 100%)";
        let badgeColor = "#34d399";
        let badgeBg = "rgba(16, 185, 129, 0.25)";
        let borderTint = "rgba(16, 185, 129, 0.85)";
        let shadowTint = "rgba(16, 185, 129, 0.45)";

        if (isCheckOut) {
            headlineText = `Checked Out: ${name}`;
            badgeText = "CHECKED OUT";
            iconClass = "fa-solid fa-arrow-right-from-bracket";
            gradientBg = "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)";
            badgeColor = "#38bdf8";
            badgeBg = "rgba(14, 165, 233, 0.25)";
            borderTint = "rgba(14, 165, 233, 0.85)";
            shadowTint = "rgba(14, 165, 233, 0.45)";
        } else {
            headlineText = `Checked In: ${name}`;
            badgeText = "CHECKED IN";
            iconClass = "fa-solid fa-check";
            gradientBg = "linear-gradient(135deg, #10b981 0%, #059669 100%)";
            badgeColor = "#34d399";
            badgeBg = "rgba(16, 185, 129, 0.25)";
            borderTint = "rgba(16, 185, 129, 0.85)";
            shadowTint = "rgba(16, 185, 129, 0.45)";
        }

        if (nameEl) nameEl.innerText = headlineText;
        if (actionBadge) {
            actionBadge.innerText = badgeText;
            actionBadge.style.color = badgeColor;
            actionBadge.style.background = badgeBg;
            actionBadge.style.borderColor = borderTint;
        }
        if (subEl) {
            const idText = roll ? `ID: ${roll}` : 'Enrolled';
            const deptText = dept ? ` • ${dept}` : '';
            subEl.innerText = `${idText}${deptText}`;
        }
        if (confEl) confEl.innerText = `${conf}% MATCH`;
        if (timeEl) {
            const d = new Date();
            timeEl.innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        }
        if (iconWrapper) {
            iconWrapper.style.background = gradientBg;
        }
        if (statusIcon) {
            statusIcon.className = iconClass;
        }

        toast.style.borderColor = borderTint;
        toast.style.boxShadow = `0 12px 35px rgba(0,0,0,0.7), 0 0 25px ${shadowTint}`;

        // Reset and re-trigger entry animation
        if (captureToastTimer) {
            clearTimeout(captureToastTimer);
            captureToastTimer = null;
        }

        toast.classList.remove("toast-anim-out");
        toast.classList.remove("toast-anim-in");
        toast.style.display = "block";
        void toast.offsetWidth; // Force reflow
        toast.classList.add("toast-anim-in");

        captureToastTimer = setTimeout(() => {
            toast.classList.remove("toast-anim-in");
            void toast.offsetWidth;
            toast.classList.add("toast-anim-out");
            setTimeout(() => {
                if (toast.classList.contains("toast-anim-out")) {
                    toast.style.display = "none";
                    toast.classList.remove("toast-anim-out");
                }
            }, 250);
        }, FLASH_DURATION_MS);
    }

    // Expose on window for external triggers
    window.showCaptureToast = showCaptureToast;

    // ==========================================================
    // DRAGGABLE CAMERA CARD IMPLEMENTATION (Desktop-Only Dragging)
    // ==========================================================
    function initDraggableCameraCard() {
        const card = document.getElementById("inlineCameraCard");
        const header = document.getElementById("cameraCardHeader");
        const resetBtn = document.getElementById("btnResetDock");
        if (!card || !header) return;

        let isDragging = false;
        let startX, startY, initialLeft, initialTop;

        const isTouchOrMobile = () => window.innerWidth <= 1024 || ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

        header.addEventListener("mousedown", (e) => {
            // Disable dragging on mobile/tablet/touch screens
            if (isTouchOrMobile()) return;

            // Don't drag if clicking buttons or controls
            if (e.target.closest("button") || e.target.closest("select") || e.target.closest("input")) {
                return;
            }

            isDragging = true;
            header.style.cursor = "grabbing";

            const rect = card.getBoundingClientRect();
            startX = e.clientX;
            startY = e.clientY;
            initialLeft = rect.left;
            initialTop = rect.top;

            // Make card fixed position on first drag
            card.style.position = "fixed";
            card.style.zIndex = "9999";
            card.style.left = `${initialLeft}px`;
            card.style.top = `${initialTop}px`;
            card.style.margin = "0";
            card.style.width = `${rect.width}px`;

            if (resetBtn) resetBtn.style.display = "inline-flex";

            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        });

        function onMouseMove(e) {
            if (!isDragging) return;
            e.preventDefault();

            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            let newLeft = initialLeft + dx;
            let newTop = initialTop + dy;

            // Boundary containment
            const maxLeft = window.innerWidth - card.offsetWidth - 10;
            const maxTop = window.innerHeight - card.offsetHeight - 10;

            newLeft = Math.max(10, Math.min(newLeft, maxLeft));
            newTop = Math.max(10, Math.min(newTop, maxTop));

            card.style.left = `${newLeft}px`;
            card.style.top = `${newTop}px`;
        }

        function onMouseUp() {
            isDragging = false;
            header.style.cursor = "grab";
            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup", onMouseUp);
        }

        window.addEventListener("resize", () => {
            if (isTouchOrMobile()) {
                resetCameraCardDock();
            }
        });
    }

    function resetCameraCardDock() {
        const card = document.getElementById("inlineCameraCard");
        const resetBtn = document.getElementById("btnResetDock");
        if (!card) return;

        card.style.position = "relative";
        card.style.left = "auto";
        card.style.top = "auto";
        card.style.margin = "0 auto";
        card.style.width = "100%";
        card.style.zIndex = "auto";

        if (resetBtn) resetBtn.style.display = "none";
    }

    // Continuous Background Attendance Feed Lifecycle:
    // Live attendance feed continues running seamlessly across window focus, blur, and tab switching.
    // Cleanup is only triggered when navigating away from the page or closing the window.
    window.addEventListener("pagehide", () => {
        stopContinuousCapture();
    });

    window.addEventListener("beforeunload", () => {
        stopContinuousCapture();
    });

    // Expose on window for arbitration & modal integration
    window.isContinuousActive = false;
    window.isInterruptedState = false;

    window.pauseForSecondaryCamera = function() {
        if (typeof isContinuousCapturing !== "undefined" && isContinuousCapturing) {
            pausedForSecondaryCamera = true;
            stopContinuousCapture();
        }
    };

    window.resumeFromSecondaryCamera = function() {
        if (typeof pausedForSecondaryCamera !== "undefined" && pausedForSecondaryCamera) {
            pausedForSecondaryCamera = false;
            startContinuousCapture();
        }
    };

    function closeRetakeModal() {
        const modal = document.getElementById("retakePhotosModal");
        if (modal) {
            modal.classList.remove("active");
            modal.style.display = "none";
        }
        if (typeof stopRetakeWebcam === "function") stopRetakeWebcam();
        if (typeof window.resumeFromSecondaryCamera === "function") {
            window.resumeFromSecondaryCamera();
        }
    }

    async function switchRetakeMode(mode) {
        const tabUpload = document.getElementById("tabRetakeUpload");
        const tabWebcam = document.getElementById("tabRetakeWebcam");
        const secUpload = document.getElementById("secRetakeUpload");
        const secWebcam = document.getElementById("secRetakeWebcam");

        if (mode === "upload") {
            if (tabUpload) tabUpload.classList.add("active");
            if (tabWebcam) tabWebcam.classList.remove("active");
            if (secUpload) secUpload.style.display = "block";
            if (secWebcam) secWebcam.style.display = "none";
            if (typeof stopRetakeWebcam === "function") stopRetakeWebcam();
            if (typeof window.resumeFromSecondaryCamera === "function") {
                window.resumeFromSecondaryCamera();
            }
        } else {
            // Camera Arbitration: Prompt admin if live attendance feed is active
            if (window.isContinuousActive && typeof window.pauseForSecondaryCamera === "function") {
                const proceed = confirm("Live Attendance Feed is currently capturing attendance.\n\nWould you like to temporarily pause the live attendance feed to use the webcam for taking reference photos?");
                if (!proceed) {
                    if (tabUpload) tabUpload.classList.add("active");
                    if (tabWebcam) tabWebcam.classList.remove("active");
                    if (secUpload) secUpload.style.display = "block";
                    if (secWebcam) secWebcam.style.display = "none";
                    return;
                }
                window.pauseForSecondaryCamera();
            }

            if (tabWebcam) tabWebcam.classList.add("active");
            if (tabUpload) tabUpload.classList.remove("active");
            if (secWebcam) secWebcam.style.display = "block";
            if (secUpload) secUpload.style.display = "none";
            if (typeof startRetakeWebcam === "function") startRetakeWebcam();
        }
    }
    window.closeRetakeModal = closeRetakeModal;
    window.switchRetakeMode = switchRetakeMode;

    function formatAttendanceDateTime(dtStr) {
        if (!dtStr) return null;
        const s = String(dtStr).trim();
        const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/);
        if (m) {
            const year = m[1];
            const month = m[2];
            const day = m[3];
            const hour = m[4];
            const min = m[5];
            const sec = m[6] || "00";
            return `${day}-${month}-${year} ${hour}:${min}:${sec}`;
        }
        const d = new Date(s);
        if (!isNaN(d.getTime())) {
            const day = String(d.getDate()).padStart(2, '0');
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const year = d.getFullYear();
            const hour = String(d.getHours()).padStart(2, '0');
            const min = String(d.getMinutes()).padStart(2, '0');
            const sec = String(d.getSeconds()).padStart(2, '0');
            return `${day}-${month}-${year} ${hour}:${min}:${sec}`;
        }
        return s;
    }
    window.formatAttendanceDateTime = formatAttendanceDateTime;


