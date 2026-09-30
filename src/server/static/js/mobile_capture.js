        let currentFacingMode = "user";
        let mediaStream = null;
        let isStreaming = false;
        let streamTimer = null;
        let isProcessing = false;
        const TARGET_FPS = 2.5;
        const FRAME_INTERVAL_MS = 1000 / TARGET_FPS; // 400ms
        const NODE_ID = "NODE-MOBILE-CAMERA";
        const SERVER_ENDPOINT = "/api/v1/nodes/frame";
        const MAX_CAPTURE_DIMENSION = 640;

        let lastCaptureW = 640;
        let lastCaptureH = 480;
        let isSnapshotMode = false;
        let toastTimeout = null;
        const videoEl = document.getElementById("mobileVideo");
        const snapshotPreviewImg = document.getElementById("snapshotPreviewImg");
        const standbyOverlay = document.getElementById("standbyOverlay");
        const overlayCanvas = document.getElementById("overlayCanvas");
        const captureCanvas = document.getElementById("captureCanvas");
        const cameraContainer = document.getElementById("cameraContainer");
        const overlayCtx = overlayCanvas.getContext("2d");
        const successToast = document.getElementById("attendanceSuccessToast");

        document.addEventListener("DOMContentLoaded", () => {
            initCamera();
            window.addEventListener("resize", resizeCanvas);
        });

        function changeMobileTenant(tId) {
            currentTenantId = tId;
            document.cookie = "active_tenant_id=" + tId + "; path=/; max-age=31536000";
            localStorage.setItem("active_tenant_id", tId);
            window.location.reload();
        }

        let wasStreamingBeforeHidden = false;

        function stopCameraStream() {
            if (isStreaming) {
                wasStreamingBeforeHidden = true;
                stopStreaming();
            }
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => {
                    try {
                        track.stop();
                    } catch (e) {}
                });
                mediaStream = null;
            }
            if (videoEl) {
                videoEl.srcObject = null;
            }
        }

        async function resumeCameraStream() {
            if (!document.hidden && !mediaStream) {
                await initCamera();
                if (wasStreamingBeforeHidden) {
                    wasStreamingBeforeHidden = false;
                    startStreaming();
                }
            }
        }

        async function initCamera() {
            stopCameraStream();

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.warn("[!] WebRTC getUserMedia is not supported or blocked by Insecure Context (HTTP LAN).");
                handleInsecureOrBlockedContext("Browser blocked live stream on HTTP. Tap Take Photo below to mark attendance.");
                return;
            }

            document.getElementById("statusText").innerText = "Requesting Cam...";

            const constraintSets = [
                { audio: false, video: { facingMode: { ideal: currentFacingMode }, width: { ideal: 640 }, height: { ideal: 480 } } },
                { audio: false, video: { width: { ideal: 640 }, height: { ideal: 480 } } },
                { audio: false, video: true }
            ];

            let streamSuccess = false;

            for (const constraints of constraintSets) {
                try {
                    mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
                    videoEl.muted = true;
                    videoEl.playsInline = true;
                    videoEl.autoplay = true;
                    videoEl.srcObject = mediaStream;
                    videoEl.style.transform = (currentFacingMode === "user") ? "scaleX(-1)" : "scaleX(1)";
                    videoEl.style.display = "block";
                    snapshotPreviewImg.style.display = "none";
                    standbyOverlay.classList.add("hidden");

                    try {
                        await videoEl.play();
                    } catch (playErr) {
                        console.warn("[*] video.play() wait:", playErr);
                    }

                    videoEl.onloadedmetadata = () => {
                        videoEl.play();
                        resizeCanvas();
                    };

                    resizeCanvas();
                    document.getElementById("statusText").innerText = "Camera Active";
                    document.getElementById("permBanner").style.display = "none";
                    document.getElementById("btnDirectShutter").style.display = "none";
                    document.getElementById("standardButtonsRow").style.display = "grid";
                    streamSuccess = true;
                    break;
                } catch (err) {
                    console.warn("[*] Constraint failed, trying next tier:", constraints, err);
                }
            }

            if (!streamSuccess) {
                handleInsecureOrBlockedContext("Camera access was blocked or denied. Tap Take Photo to proceed.");
            }
        }

        function handleInsecureOrBlockedContext(reason) {
            standbyOverlay.classList.remove("hidden");
            document.getElementById("standbyHeading").innerText = "Live Stream Unavailable";
            document.getElementById("standbySub").innerText = reason || "Tap below to capture a live photo and mark attendance.";
            document.getElementById("btnStandbyDirectShot").style.display = "flex";

            document.getElementById("statusText").innerText = "Direct Photo Mode";
            document.getElementById("permBanner").style.display = "block";
            document.getElementById("btnDirectShutter").style.display = "flex";
            document.getElementById("btnSnapshot").innerHTML = `<i class="fa-solid fa-camera-retro"></i> <span>Take Photo</span>`;
        }

        function triggerNativeShutter() {
            const input = document.getElementById("nativeCameraInput");
            input.setAttribute("capture", currentFacingMode === "user" ? "user" : "environment");
            input.click();
        }

        async function handleNativePhotoCapture(event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;

            document.getElementById("statusText").innerText = "Analyzing Photo...";
            document.getElementById("detName").innerText = "Processing Biometrics...";
            document.getElementById("detStatusBadge").innerText = "ANALYZING";
            document.getElementById("detStatusBadge").className = "badge badge-node";

            const reader = new FileReader();
            reader.onload = async (e) => {
                const img = new Image();
                img.onload = async () => {
                    snapshotPreviewImg.src = e.target.result;
                    snapshotPreviewImg.style.display = "block";
                    videoEl.style.display = "none";
                    standbyOverlay.classList.add("hidden");
                    isSnapshotMode = true;

                    let targetW = img.width;
                    let targetH = img.height;
                    if (targetW > MAX_CAPTURE_DIMENSION || targetH > MAX_CAPTURE_DIMENSION) {
                        if (targetW >= targetH) {
                            targetH = Math.round((img.height / img.width) * MAX_CAPTURE_DIMENSION);
                            targetW = MAX_CAPTURE_DIMENSION;
                        } else {
                            targetW = Math.round((img.width / img.height) * MAX_CAPTURE_DIMENSION);
                            targetH = MAX_CAPTURE_DIMENSION;
                        }
                    }

                    lastCaptureW = targetW;
                    lastCaptureH = targetH;

                    captureCanvas.width = targetW;
                    captureCanvas.height = targetH;
                    const ctx = captureCanvas.getContext("2d");
                    ctx.drawImage(img, 0, 0, targetW, targetH);

                    captureCanvas.toBlob(async (blob) => {
                        if (!blob) return;

                        const formData = new FormData();
                        formData.append("node_id", NODE_ID);
                        formData.append("tenant_id", currentTenantId);
                        formData.append("is_single_shot", "true");
                        formData.append("location", "Mobile Smartphone Node");
                        formData.append("frame", blob, "mobile_photo.jpg");

                        const t0 = performance.now();
                        try {
                            const res = await fetch(SERVER_ENDPOINT, {
                                method: "POST",
                                body: formData,
                            });
                            const latency = Math.round(performance.now() - t0);
                            document.getElementById("latencyLabel").innerText = `${latency} ms`;
                            document.getElementById("statusText").innerText = "Processed";

                            if (res.ok) {
                                const data = await res.json();
                                handleServerResults(data);
                            } else {
                                document.getElementById("detName").innerText = "Server Error";
                                document.getElementById("detStatusBadge").innerText = `HTTP ${res.status}`;
                            }
                        } catch (err) {
                            console.error("[!] Photo transmission error:", err);
                            document.getElementById("detName").innerText = "Network Error";
                            document.getElementById("detStatusBadge").innerText = "OFFLINE";
                        }
                    }, "image/jpeg", 0.80);
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        function resizeCanvas() {
            if (!cameraContainer) return;
            overlayCanvas.width = cameraContainer.clientWidth || 640;
            overlayCanvas.height = cameraContainer.clientHeight || 480;
        }

        function flipCamera() {
            currentFacingMode = (currentFacingMode === "user") ? "environment" : "user";
            initCamera();
        }

        function toggleStreaming() {
            if (isStreaming) {
                stopStreaming();
            } else {
                startStreaming();
            }
        }

        let streamTimer = null;

        function createMobileWorkerTimer(callback, intervalMs) {
            if (typeof Worker !== "undefined" && typeof Blob !== "undefined") {
                try {
                    const script = `
                        let t = null;
                        self.onmessage = function(e) {
                            if (e.data === 'start') {
                                if (t) clearInterval(t);
                                t = setInterval(function() { self.postMessage('tick'); }, ${intervalMs});
                            } else if (e.data === 'stop') {
                                if (t) clearInterval(t);
                                t = null;
                            }
                        };
                    `;
                    const blob = new Blob([script], { type: "application/javascript" });
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
                } catch (e) {
                    console.warn("[MobileCam] Worker timer fallback:", e);
                }
            }
            let fb = null;
            return {
                start: function() {
                    if (fb) clearInterval(fb);
                    fb = setInterval(callback, intervalMs);
                },
                stop: function() {
                    if (fb) clearInterval(fb);
                    fb = null;
                },
                terminate: function() {
                    if (fb) clearInterval(fb);
                    fb = null;
                }
            };
        }

        function startStreaming() {
            if (!mediaStream || !videoEl.srcObject) {
                initCamera();
                return;
            }
            isStreaming = true;
            isSnapshotMode = false;
            snapshotPreviewImg.style.display = "none";
            videoEl.style.display = "block";
            standbyOverlay.classList.add("hidden");

            const btn = document.getElementById("btnToggleStream");
            btn.className = "btn-stream active";
            document.getElementById("streamBtnText").innerText = "Stop Stream";
            btn.querySelector("i").className = "fa-solid fa-stop";
            document.getElementById("statusText").innerText = "Streaming (2 FPS)";

            transmitFrame();
            if (streamTimer) {
                if (typeof streamTimer.terminate === "function") streamTimer.terminate();
                else clearInterval(streamTimer);
                streamTimer = null;
            }
            streamTimer = createMobileWorkerTimer(transmitFrame, FRAME_INTERVAL_MS);
            streamTimer.start();
        }

        function stopStreaming() {
            isStreaming = false;
            if (streamTimer) {
                if (typeof streamTimer.terminate === "function") streamTimer.terminate();
                else clearInterval(streamTimer);
                streamTimer = null;
            }
            const btn = document.getElementById("btnToggleStream");
            btn.className = "btn-stream inactive";
            document.getElementById("streamBtnText").innerText = "Start Attendance Stream";
            btn.querySelector("i").className = "fa-solid fa-play";
            document.getElementById("statusText").innerText = "Camera Active";
            clearOverlay();
        }

        async function captureSingleFrame() {
            if (!mediaStream || videoEl.videoWidth === 0 || videoEl.style.display === "none") {
                triggerNativeShutter();
                return;
            }
            document.getElementById("statusText").innerText = "Analyzing Frame...";
            await transmitFrame(true);
        }

        async function transmitFrame(isSingle = false) {
            if (isProcessing) return;
            if (!videoEl || videoEl.videoWidth === 0 || videoEl.paused) return;

            isProcessing = true;

            const vw = videoEl.videoWidth;
            const vh = videoEl.videoHeight;

            let targetW = vw;
            let targetH = vh;
            if (vw > MAX_CAPTURE_DIMENSION || vh > MAX_CAPTURE_DIMENSION) {
                if (vw >= vh) {
                    targetW = MAX_CAPTURE_DIMENSION;
                    targetH = Math.round((vh / vw) * MAX_CAPTURE_DIMENSION);
                } else {
                    targetH = MAX_CAPTURE_DIMENSION;
                    targetW = Math.round((vw / vh) * MAX_CAPTURE_DIMENSION);
                }
            }

            lastCaptureW = targetW;
            lastCaptureH = targetH;

            captureCanvas.width = targetW;
            captureCanvas.height = targetH;
            const ctx = captureCanvas.getContext("2d");
            ctx.drawImage(videoEl, 0, 0, targetW, targetH);

            captureCanvas.toBlob(async (blob) => {
                if (!blob) {
                    isProcessing = false;
                    return;
                }

                const formData = new FormData();
                formData.append("node_id", NODE_ID);
                formData.append("tenant_id", currentTenantId);
                if (isSingle) {
                    formData.append("is_single_shot", "true");
                }
                formData.append("location", "Mobile Smartphone Node");
                formData.append("frame", blob, "mobile_frame.jpg");

                const t0 = performance.now();
                try {
                    const res = await fetch(SERVER_ENDPOINT, {
                        method: "POST",
                        body: formData,
                    });
                    const latency = Math.round(performance.now() - t0);
                    document.getElementById("latencyLabel").innerText = `${latency} ms`;

                    if (res.ok) {
                        const data = await res.json();
                        handleServerResults(data);
                    }
                } catch (e) {
                    console.warn("[!] Server transmission error:", e);
                } finally {
                    isProcessing = false;
                }
            }, "image/jpeg", 0.78);
        }

        function getDisplayedVideoRect() {
            const containerW = cameraContainer.clientWidth || overlayCanvas.width || 640;
            const containerH = cameraContainer.clientHeight || overlayCanvas.height || 480;
            
            let videoW = 640;
            let videoH = 480;
            if (!isSnapshotMode && videoEl && videoEl.videoWidth && videoEl.videoHeight) {
                videoW = videoEl.videoWidth;
                videoH = videoEl.videoHeight;
            } else if (lastCaptureW && lastCaptureH) {
                videoW = lastCaptureW;
                videoH = lastCaptureH;
            }

            const videoAspect = videoW / videoH;
            const containerAspect = containerW / containerH;
            let renderW, renderH, offsetX, offsetY;

            if (containerAspect > videoAspect) {
                renderW = containerW;
                renderH = containerW / videoAspect;
                offsetX = 0;
                offsetY = (containerH - renderH) / 2;
            } else {
                renderH = containerH;
                renderW = containerH * videoAspect;
                offsetX = (containerW - renderW) / 2;
                offsetY = 0;
            }

            return { renderW, renderH, offsetX, offsetY };
        }

        function drawSafeRoundedRect(ctx, x, y, width, height, radius) {
            if (isNaN(x) || isNaN(y) || isNaN(width) || isNaN(height) || width <= 0 || height <= 0) return;
            const r = Math.max(0, Math.min(radius, width / 2, height / 2));
            ctx.beginPath();
            ctx.moveTo(x + r, y);
            ctx.lineTo(x + width - r, y);
            ctx.quadraticCurveTo(x + width, y, x + width, y + r);
            ctx.lineTo(x + width, y + height - r);
            ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
            ctx.lineTo(x + r, y + height);
            ctx.quadraticCurveTo(x, y + height, x, y + height - r);
            ctx.lineTo(x, y + r);
            ctx.quadraticCurveTo(x, y, x + r, y);
            ctx.closePath();
        }

        function playAttendanceChime(punchType = "CHECK_IN") {
            if (!ENABLE_AUDIO_CHIME) return;
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                const ctx = new AudioContext();
                const now = ctx.currentTime;
                
                if (punchType === "CHECK_OUT") {
                    // Check-Out 3-Tone Completion Chime (A5 -> E5 -> C5)
                    const osc1 = ctx.createOscillator();
                    const gain1 = ctx.createGain();
                    osc1.type = "sine";
                    osc1.frequency.setValueAtTime(880.00, now);
                    gain1.gain.setValueAtTime(0.28, now);
                    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
                    osc1.connect(gain1);
                    gain1.connect(ctx.destination);
                    osc1.start(now);
                    osc1.stop(now + 0.18);

                    const osc2 = ctx.createOscillator();
                    const gain2 = ctx.createGain();
                    osc2.type = "sine";
                    osc2.frequency.setValueAtTime(659.25, now + 0.10);
                    gain2.gain.setValueAtTime(0.30, now + 0.10);
                    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.30);
                    osc2.connect(gain2);
                    gain2.connect(ctx.destination);
                    osc2.start(now + 0.10);
                    osc2.stop(now + 0.30);

                    const osc3 = ctx.createOscillator();
                    const gain3 = ctx.createGain();
                    osc3.type = "sine";
                    osc3.frequency.setValueAtTime(523.25, now + 0.22);
                    gain3.gain.setValueAtTime(0.35, now + 0.22);
                    gain3.gain.exponentialRampToValueAtTime(0.001, now + 0.50);
                    osc3.connect(gain3);
                    gain3.connect(ctx.destination);
                    osc3.start(now + 0.22);
                    osc3.stop(now + 0.50);
                } else {
                    // Check-In / Attendance 2-Tone Rising Chime (D5 -> A5)
                    const osc1 = ctx.createOscillator();
                    const gain1 = ctx.createGain();
                    osc1.type = "sine";
                    osc1.frequency.setValueAtTime(587.33, now);
                    gain1.gain.setValueAtTime(0.25, now);
                    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
                    osc1.connect(gain1);
                    gain1.connect(ctx.destination);
                    osc1.start(now);
                    osc1.stop(now + 0.22);

                    const osc2 = ctx.createOscillator();
                    const gain2 = ctx.createGain();
                    osc2.type = "sine";
                    osc2.frequency.setValueAtTime(880.00, now + 0.10);
                    gain2.gain.setValueAtTime(0.32, now + 0.10);
                    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.42);
                    osc2.connect(gain2);
                    gain2.connect(ctx.destination);
                    osc2.start(now + 0.10);
                    osc2.stop(now + 0.42);
                }
            } catch (e) {
                console.warn("[*] Audio context note:", e);
            }
        }

        function triggerSuccessFeedback(student) {
            cameraContainer.classList.remove("flash-success");
            void cameraContainer.offsetWidth;
            cameraContainer.classList.add("flash-success");

            const punchType = student.punch_type || (student.log_data && student.log_data.punch_type) || "CHECK_IN";
            playAttendanceChime(punchType);

            if (ENABLE_HAPTIC && navigator.vibrate) {
                if (punchType === "CHECK_OUT") {
                    navigator.vibrate([80, 40, 80, 40, 160]);
                } else {
                    navigator.vibrate([120, 50, 120]);
                }
            }

            if (student) {
                const name = student.name || "Student";
                const roll = student.roll_number || "N/A";
                const conf = student.confidence_pct || 0;
                
                const avatarEl = document.getElementById("toastAvatar");
                const titleEl = successToast.querySelector(".toast-title");
                const nameEl = document.getElementById("toastStudentName");
                const metaEl = document.getElementById("toastMeta");

                nameEl.innerText = name;

                if (punchType === "CHECK_OUT") {
                    successToast.className = "attendance-success-toast toast-checkout active";
                    if (avatarEl) {
                        avatarEl.className = "toast-avatar avatar-checkout";
                        avatarEl.innerHTML = '<i class="fa-solid fa-arrow-right-from-bracket"></i>';
                    }
                    if (titleEl) {
                        titleEl.className = "toast-title title-checkout";
                        titleEl.innerHTML = '<i class="fa-solid fa-circle-check"></i> Shift Check-Out Recorded!';
                    }
                    if (metaEl) {
                        metaEl.className = "toast-meta meta-checkout";
                        const durStr = student.work_duration_formatted || (student.work_duration_minutes ? (student.work_duration_minutes + ' mins') : 'Completed');
                        const statusStr = student.shift_status || 'COMPLETED';
                        metaEl.innerText = `Session: ${durStr} • Status: ${statusStr} • Roll: ${roll}`;
                    }
                } else {
                    successToast.className = "attendance-success-toast toast-checkin active";
                    if (avatarEl) {
                        avatarEl.className = "toast-avatar";
                        avatarEl.innerText = name.charAt(0).toUpperCase();
                    }
                    if (titleEl) {
                        titleEl.className = "toast-title";
                        titleEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${punchType === 'CHECK_IN' ? 'Shift Check-In Recorded!' : 'Attendance Committed!'}`;
                    }
                    if (metaEl) {
                        metaEl.className = "toast-meta";
                        const inTime = student.check_in_short || 'Now';
                        const statusStr = student.shift_status || 'ON_TIME';
                        metaEl.innerText = `In: ${inTime} • Status: ${statusStr} • Roll: ${roll} (${conf}% Match)`;
                    }
                }

                if (toastTimeout) clearTimeout(toastTimeout);
                toastTimeout = setTimeout(() => {
                    successToast.classList.remove("active");
                }, 3800);
            }
        }

        function handleServerResults(data) {
            try {
                clearOverlay();
                const detections = data.detections || data.results || [];

                // 1. Update bottom card FIRST so UI status updates immediately
                const badge = document.getElementById("detStatusBadge");
                if (!detections || detections.length === 0) {
                    document.getElementById("detName").innerText = "No Face Detected";
                    document.getElementById("detSub").innerText = "Point camera steadily or take closer shot";
                    if (badge) {
                        badge.innerText = "NO FACE";
                        badge.className = "badge badge-unknown";
                    }
                    const avatar = document.getElementById("detAvatar");
                    if (avatar) avatar.innerHTML = '<i class="fa-solid fa-user"></i>';
                    return;
                }

                let hasNewAttendanceLogged = false;
                let loggedStudent = null;

                if (detections.length === 1) {
                    const primary = detections[0];
                    if (primary.is_match) {
                        document.getElementById("detName").innerText = primary.name || "Enrolled Profile";
                        let subText = `Roll: ${primary.roll_number || 'N/A'} • Dept: ${primary.department || 'General'}`;
                        
                        const initial = (primary.name && primary.name !== "Unknown") ? primary.name.charAt(0).toUpperCase() : "✓";
                        const avatar = document.getElementById("detAvatar");
                        if (avatar) avatar.innerText = initial;

                        if (primary.attendance_logged) {
                            hasNewAttendanceLogged = true;
                            loggedStudent = primary;
                        }

                        if (badge) {
                            if (!primary.is_live || primary.temporal_status === "SPOOF_DETECTED") {
                                badge.innerText = "SPOOF BLOCKED";
                                badge.className = "badge badge-unknown";
                            } else if (primary.attendance_logged) {
                                if (primary.punch_type === "CHECK_OUT") {
                                    const dur = primary.work_duration_formatted || (primary.work_duration_minutes ? primary.work_duration_minutes + 'm' : 'DONE');
                                    badge.innerText = `✓ CHECKED OUT (${dur})`;
                                    badge.className = "badge badge-sky";
                                    subText = `Check-Out recorded • Session: ${primary.work_duration_formatted || dur} • Dept: ${primary.department || 'General'}`;
                                } else if (primary.punch_type === "CHECK_IN") {
                                    const inStatus = primary.shift_status || 'ON_TIME';
                                    badge.innerText = `✓ CHECKED IN (${inStatus})`;
                                    badge.className = "badge badge-present";
                                    subText = `Check-In recorded at ${primary.check_in_short || 'Now'} • Dept: ${primary.department || 'General'}`;
                                } else {
                                    badge.innerText = "✓ ATTENDANCE LOGGED";
                                    badge.className = "badge badge-present";
                                }
                            } else if (primary.cooldown_active) {
                                badge.innerText = `✓ COOLDOWN (${primary.cooldown_remaining_minutes}m)`;
                                badge.className = "badge badge-sky";
                                if (primary.message) {
                                    subText = primary.message;
                                }
                            } else {
                                badge.innerText = `${primary.confidence_pct || 0}% MATCH`;
                                badge.className = "badge badge-node";
                            }
                        }
                        document.getElementById("detSub").innerText = subText;
                    } else {
                        document.getElementById("detName").innerText = "Unregistered Face";
                        const closestInfo = primary.closest_candidate_name 
                            ? `Closest Vector: '${primary.closest_candidate_name}' (Roll: ${primary.closest_candidate_roll || 'N/A'}, Dist: ${primary.distance} > Thresh: ${primary.threshold || 0.55})`
                            : `No employee/student vectors registered under Tenant #${currentTenantId} (Dist: ${primary.distance})`;
                        document.getElementById("detSub").innerText = closestInfo;
                        const avatar = document.getElementById("detAvatar");
                        if (avatar) avatar.innerHTML = '<i class="fa-solid fa-user-xmark" style="color: #94a3b8;"></i>';
                        if (badge) {
                            badge.innerText = `DIST ${primary.distance !== undefined ? primary.distance : 'N/A'}`;
                            badge.className = "badge badge-unknown";
                        }
                    }
                } else {
                    const namesList = detections.map(d => d.name || "Unknown").join(", ");
                    const recognizedCount = detections.filter(d => d.is_match).length;
                    const loggedCount = detections.filter(d => d.attendance_logged).length;

                    const avatar = document.getElementById("detAvatar");
                    if (avatar) avatar.innerHTML = `<i class="fa-solid fa-users" style="color: #38bdf8;"></i>`;
                    document.getElementById("detName").innerText = `${detections.length} Faces Detected`;
                    document.getElementById("detSub").innerText = namesList;

                    if (badge) {
                        if (loggedCount > 0) {
                            badge.innerText = `✓ LOGGED (${loggedCount}/${detections.length})`;
                            badge.className = "badge badge-present";
                        } else if (recognizedCount > 0) {
                            badge.innerText = `RECOGNIZED (${recognizedCount}/${detections.length})`;
                            badge.className = "badge badge-node";
                        } else {
                            badge.innerText = `GROUP (${detections.length})`;
                            badge.className = "badge badge-unknown";
                        }
                    }
                }

                // 2. Draw overlay bounding boxes and name pills
                const { renderW, renderH, offsetX, offsetY } = getDisplayedVideoRect();

                detections.forEach((r) => {
                    const box = r.box;
                    if (!box) return;

                    const normTop = box.top / lastCaptureH;
                    const normBottom = box.bottom / lastCaptureH;
                    const normLeft = box.left / lastCaptureW;
                    const normRight = box.right / lastCaptureW;

                    let boxY = offsetY + (normTop * renderH);
                    let boxH = (normBottom - normTop) * renderH;
                    let boxX, boxW;

                    if (!isSnapshotMode && currentFacingMode === "user") {
                        boxX = offsetX + ((1.0 - normRight) * renderW);
                        boxW = (normRight - normLeft) * renderW;
                    } else {
                        boxX = offsetX + (normLeft * renderW);
                        boxW = (normRight - normLeft) * renderW;
                    }

                    const isLive = r.is_live !== false;
                    const isMatch = r.is_match;
                    const attendLogged = r.attendance_logged;
                    const cooldownActive = r.cooldown_active;
                    const cooldownRemaining = r.cooldown_remaining_minutes || 0;
                    const tempStatus = r.temporal_status || "REAL";

                    let strokeColor = "#38bdf8";
                    let labelText = "";

                    if (isMatch) {
                        if (attendLogged) {
                            if (r.punch_type === "CHECK_OUT") {
                                strokeColor = "#818cf8";
                                const dur = r.work_duration_formatted || (r.work_duration_minutes ? r.work_duration_minutes + 'm' : 'DONE');
                                labelText = `✓ ${r.name} [CHECK-OUT: ${dur}]`;
                            } else if (r.punch_type === "CHECK_IN") {
                                strokeColor = "#10b981";
                                labelText = `✓ ${r.name} [CHECK-IN: ${r.shift_status || 'ON_TIME'}]`;
                            } else {
                                strokeColor = "#10b981";
                                labelText = `✓ ${r.name} [LOGGED]`;
                            }
                            hasNewAttendanceLogged = true;
                            loggedStudent = r;
                        } else if (cooldownActive) {
                            strokeColor = "#06b6d4";
                            labelText = `✓ ${r.name} [COOLDOWN ${cooldownRemaining}m]`;
                        } else if (!isLive || tempStatus === "SPOOF_DETECTED") {
                            strokeColor = "#f97316";
                            labelText = `⚠️ ${r.name} [SPOOF SUSPECTED]`;
                        } else if (tempStatus.startsWith("VERIFYING")) {
                            strokeColor = "#06b6d4";
                            labelText = `⏳ ${r.name} [${tempStatus}]`;
                        } else {
                            strokeColor = "#10b981";
                            labelText = `✓ ${r.name} [VERIFIED]`;
                        }
                    } else {
                        strokeColor = "#94a3b8";
                        if (r.closest_candidate_name) {
                            labelText = `Unknown (Closest: ${r.closest_candidate_name} • Dist: ${r.distance})`;
                        } else {
                            labelText = `Unknown Face (Dist: ${r.distance})`;
                        }
                    }

                    // Render Bounding Box with glow
                    overlayCtx.save();
                    overlayCtx.shadowColor = strokeColor;
                    overlayCtx.shadowBlur = 12;
                    overlayCtx.strokeStyle = strokeColor;
                    overlayCtx.lineWidth = 3.5;
                    drawSafeRoundedRect(overlayCtx, boxX, boxY, boxW, boxH, 10);
                    overlayCtx.stroke();
                    overlayCtx.restore();

                    // Corner Accents
                    const cornerLen = Math.min(18, Math.max(6, boxW * 0.22));
                    overlayCtx.strokeStyle = "#ffffff";
                    overlayCtx.lineWidth = 2.5;

                    // Top-Left
                    overlayCtx.beginPath();
                    overlayCtx.moveTo(boxX, boxY + cornerLen);
                    overlayCtx.lineTo(boxX, boxY);
                    overlayCtx.lineTo(boxX + cornerLen, boxY);
                    overlayCtx.stroke();

                    // Top-Right
                    overlayCtx.beginPath();
                    overlayCtx.moveTo(boxX + boxW - cornerLen, boxY);
                    overlayCtx.lineTo(boxX + boxW);
                    overlayCtx.lineTo(boxX + boxW, boxY + cornerLen);
                    overlayCtx.stroke();

                    // Bottom-Left
                    overlayCtx.beginPath();
                    overlayCtx.moveTo(boxX, boxY + boxH - cornerLen);
                    overlayCtx.lineTo(boxX, boxY + boxH);
                    overlayCtx.lineTo(boxX + cornerLen, boxY + boxH);
                    overlayCtx.stroke();

                    // Bottom-Right
                    overlayCtx.beginPath();
                    overlayCtx.moveTo(boxX + boxW - cornerLen, boxY + boxH);
                    overlayCtx.lineTo(boxX + boxW);
                    overlayCtx.lineTo(boxX + boxW - cornerLen, boxY + boxH);
                    overlayCtx.stroke();

                    // Label Pill: If box is near top of screen (boxY < 36), place pill INSIDE top of box
                    overlayCtx.font = "bold 12px 'Plus Jakarta Sans', sans-serif";
                    const textWidth = overlayCtx.measureText(labelText).width;
                    const pillW = textWidth + 18;
                    const pillH = 24;
                    let pillY = (boxY < 36) ? (boxY + 8) : (boxY - pillH - 5);
                    let pillX = Math.max(6, Math.min(boxX, overlayCanvas.width - pillW - 6));

                    overlayCtx.fillStyle = "rgba(11, 15, 25, 0.94)";
                    drawSafeRoundedRect(overlayCtx, pillX, pillY, pillW, pillH, 7);
                    overlayCtx.fill();

                    overlayCtx.strokeStyle = strokeColor;
                    overlayCtx.lineWidth = 1.5;
                    overlayCtx.stroke();

                    overlayCtx.fillStyle = strokeColor;
                    overlayCtx.fillText(labelText, pillX + 9, pillY + 16);
                });

                if (hasNewAttendanceLogged && loggedStudent) {
                    triggerSuccessFeedback(loggedStudent);
                }
            } catch (err) {
                console.error("[!] Mobile overlay draw error:", err);
            }
        }

        function clearOverlay() {
            if (overlayCanvas) {
                overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            }
        }

        function copyOriginFlag() {
            const flagUrl = `chrome://flags/#unsafely-treat-insecure-origin-as-secure`;
            navigator.clipboard.writeText(`${window.location.protocol}//${window.location.host}`).then(() => {
                alert(`Copied origin: ${window.location.protocol}//${window.location.host}\n\n1. Open ${flagUrl}\n2. Paste this origin and set to Enabled\n3. Relaunch Chrome`);
            });
        }

        // Background-resilient camera lifecycle: maintain stream during window blur and tab switches
        window.addEventListener("pagehide", () => {
            stopCameraStream();
        });

        window.addEventListener("beforeunload", () => {
            stopCameraStream();
        });
