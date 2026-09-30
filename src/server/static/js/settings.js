function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
    handleInitialTabFromHash();
    if (typeof updateThemeSelectionCards === "function") {
        updateThemeSelectionCards();
    }
    loadSavedSystemPreferences();

    // Initialize Employee Portal full URL and QR
    const empPortalSpan = document.getElementById("universalEmployeePortalUrlSpan");
    const empPortalOpenBtn = document.getElementById("btnUniversalEmpPortalOpen");
    const empPortalQrImg = document.getElementById("universalEmpPortalQrImg");
    if (empPortalSpan) {
        const slug = window.currentTenantSlug || "default";
        const relativeUrl = `/employee/${slug}`;
        const fullUrl = window.location.origin + relativeUrl;
        empPortalSpan.innerText = fullUrl;
        if (empPortalOpenBtn) empPortalOpenBtn.href = relativeUrl;
        if (empPortalQrImg) {
            empPortalQrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encodeURIComponent(fullUrl)}`;
        }
    }
});

// Tab Switcher with Deep Linking - Strict Sequence:
// 1. Organization Settings (branding)
// 2. Themes & Appearance (themes)
// 3. Departments & Teams (departments)
// 4. Designations & Roles (designations)
// 5. Shifts & Rules (shifts)
// 6. Attendance & Security (security)
// 7. Geofencing & Portals (geofencing)
function switchSettingsTab(tabName) {
    const validTabs = ['branding', 'themes', 'departments', 'designations', 'shifts', 'security', 'geofencing'];
    if (!validTabs.includes(tabName)) tabName = 'branding';

    validTabs.forEach(t => {
        const btn = document.getElementById(`tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const pane = document.getElementById(`tabContent${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (btn) btn.classList.remove("active");
        if (pane) pane.classList.remove("active");
    });

    const activeBtn = document.getElementById(`tabBtn${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
    const activePane = document.getElementById(`tabContent${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
    if (activeBtn) activeBtn.classList.add("active");
    if (activePane) activePane.classList.add("active");

    // Leaflet Map Invalidation on Geofencing tab display
    if (tabName === 'geofencing') {
        setTimeout(() => {
            if (officeMap) {
                officeMap.invalidateSize();
            } else {
                initOfficeMap();
            }
        }, 150);
    }

    // Update URL hash without jumping page
    if (history.replaceState) {
        history.replaceState(null, null, `#${tabName}`);
    }
}

function handleInitialTabFromHash() {
    const hash = (window.location.hash || '').toLowerCase().replace('#', '');
    if (hash === 'departments' || hash === 'departmentssection') {
        switchSettingsTab('departments');
    } else if (hash === 'designations' || hash === 'roles' || hash === 'designation') {
        switchSettingsTab('designations');
    } else if (hash === 'shifts' || hash === 'shiftssection') {
        switchSettingsTab('shifts');
    } else if (hash === 'themes' || hash === 'theme') {
        switchSettingsTab('themes');
    } else if (hash === 'security' || hash === 'liveness' || hash === 'spoofing') {
        switchSettingsTab('security');
    } else if (hash === 'geofencing' || hash === 'geofence' || hash === 'portals') {
        switchSettingsTab('geofencing');
    } else {
        switchSettingsTab('branding');
    }
}

function updateBrandingLivePreview() {
    const instName = document.getElementById("brandInstName").value || "FaceAttendance Campus";
    const badgeText = document.getElementById("brandBadgeText").value || "Thin-Client Hub";

    const nameEl = document.getElementById("livePreviewName");
    const badgeEl = document.getElementById("livePreviewBadge");

    if (nameEl) nameEl.innerText = instName;
    if (badgeEl) badgeEl.innerText = badgeText;
}

function syncColorInput(val) {
    document.getElementById("brandAccentColorText").value = val;
}

function syncColorPicker(val) {
    if (/^#[0-9A-F]{6}$/i.test(val)) {
        document.getElementById("brandAccentColorPicker").value = val;
    }
}

function setCooldownPreset(mins) {
    mins = Math.max(1, Math.min(1440, parseInt(mins) || 1));
    document.getElementById("brandCooldownMinutes").value = mins;
    document.getElementById("cooldownSlider").value = Math.min(720, mins);
    const minCheckoutEl = document.getElementById("brandMinCheckoutInterval");
    if (minCheckoutEl) minCheckoutEl.value = mins;
    const hrs = (mins / 60).toFixed(1);
    document.getElementById("cooldownLabel").innerText = `${mins} Minutes (${hrs} Hours)`;
}

function updateCooldownDisplay(val) {
    const mins = Math.max(1, parseInt(val) || 1);
    document.getElementById("brandCooldownMinutes").value = mins;
    const minCheckoutEl = document.getElementById("brandMinCheckoutInterval");
    if (minCheckoutEl) minCheckoutEl.value = mins;
    const hrs = (mins / 60).toFixed(1);
    document.getElementById("cooldownLabel").innerText = `${mins} Minutes (${hrs} Hours)`;
}

function updateCooldownFromInput(val) {
    let mins = parseInt(val) || 1;
    mins = Math.max(1, Math.min(1440, mins));
    document.getElementById("cooldownSlider").value = Math.min(720, mins);
    const minCheckoutEl = document.getElementById("brandMinCheckoutInterval");
    if (minCheckoutEl) minCheckoutEl.value = mins;
    const hrs = (mins / 60).toFixed(1);
    document.getElementById("cooldownLabel").innerText = `${mins} Minutes (${hrs} Hours)`;
}

function setLivenessPreset(mode, frames) {
    document.getElementById("brandLivenessMode").value = mode;
    document.getElementById("livenessModeBadge").innerText = mode;
    document.getElementById("temporalFramesSlider").value = frames;
    document.getElementById("brandTemporalFrames").value = frames;

    document.querySelectorAll(".liveness-preset-btn").forEach(b => {
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
    });

    const activeMap = {
        "STRICT": "btnLiveStrict",
        "BALANCED": "btnLiveBalanced",
        "FAST": "btnLiveFast",
        "DISABLED": "btnLiveDisabled"
    };
    const activeBtn = document.getElementById(activeMap[mode]);
    if (activeBtn) {
        activeBtn.classList.remove("btn-secondary");
        activeBtn.classList.add("btn-primary");
    }
}

function updateTemporalFramesDisplay(val) {
    const frames = parseInt(val) || 3;
    document.getElementById("brandTemporalFrames").value = frames;
}

function updateTemporalFramesFromInput(val) {
    let frames = parseInt(val) || 3;
    frames = Math.max(1, Math.min(10, frames));
    document.getElementById("temporalFramesSlider").value = frames;
}

function toggleAntiSpoofingControls(isEnabled) {
    const badge = document.getElementById("antiSpoofStatusBadge");
    const container = document.getElementById("antiSpoofConfigContainer");
    const notice = document.getElementById("antiSpoofDisabledNotice");
    const track = document.getElementById("toggleTrack");
    const knob = document.getElementById("toggleKnob");

    if (isEnabled) {
        if (badge) {
            badge.innerText = "ENABLED";
            badge.className = "badge badge-present";
        }
        if (track) track.style.backgroundColor = "var(--accent-emerald)";
        if (knob) knob.style.left = "22px";
        if (container) {
            container.style.opacity = "1";
            container.style.pointerEvents = "auto";
        }
        if (notice) notice.style.display = "none";
    } else {
        if (badge) {
            badge.innerText = "DISABLED";
            badge.className = "badge badge-unknown";
        }
        if (track) track.style.backgroundColor = "var(--border-color)";
        if (knob) knob.style.left = "3px";
        if (container) {
            container.style.opacity = "0.45";
            container.style.pointerEvents = "none";
        }
        if (notice) notice.style.display = "block";
    }
}

function toggleSelfAttendanceControls(isEnabled) {
    const badge = document.getElementById("selfAttendanceStatusBadge");
    const container = document.getElementById("selfAttendanceConfigContainer");
    const track = document.getElementById("selfToggleTrack");
    const knob = document.getElementById("selfToggleKnob");

    if (isEnabled) {
        if (badge) {
            badge.innerText = "ENABLED";
            badge.className = "badge badge-present";
        }
        if (track) track.style.backgroundColor = "var(--accent-emerald)";
        if (knob) knob.style.left = "22px";
        if (container) {
            container.style.opacity = "1";
            container.style.pointerEvents = "auto";
        }
        if (officeMap) {
            setTimeout(() => officeMap.invalidateSize(), 200);
        }
    } else {
        if (badge) {
            badge.innerText = "DISABLED";
            badge.className = "badge badge-unknown";
        }
        if (track) track.style.backgroundColor = "var(--border-color)";
        if (knob) knob.style.left = "3px";
        if (container) {
            container.style.opacity = "0.45";
            container.style.pointerEvents = "none";
        }
    }
}

// --- Interactive Leaflet Map Office Locator & Geofencing ---
let officeMap = null;
let officeMarker = null;
let officeCircle = null;

const DEFAULT_FALLBACK_LAT = 23.022505;
const DEFAULT_FALLBACK_LON = 72.571362;

function setMapPinBadge(text, badgeClass = "badge-subtle", iconHtml = '<i class="fa-solid fa-location-dot"></i>') {
    const badge = document.getElementById("mapPinStatusBadge");
    if (!badge) return;
    badge.className = `badge ${badgeClass}`;
    badge.innerHTML = `${iconHtml} <span>${text}</span>`;
}

function initOfficeMap() {
    const mapContainer = document.getElementById("officeMapPicker");
    if (!mapContainer || typeof L === "undefined") return;

    if (officeMap) {
        officeMap.remove();
        officeMap = null;
    }

    const latInput = document.getElementById("brandGeoLatitude");
    const lonInput = document.getElementById("brandGeoLongitude");
    const radiusInput = document.getElementById("brandGeoRadius");

    const rawLat = parseFloat(latInput ? latInput.value : "");
    const rawLon = parseFloat(lonInput ? lonInput.value : "");
    const radius = parseFloat(radiusInput ? radiusInput.value : "") || 150;

    const hasSavedCoords = !isNaN(rawLat) && !isNaN(rawLon) && rawLat !== 0 && rawLon !== 0;

    if (hasSavedCoords) {
        const initLat = rawLat;
        const initLon = rawLon;

        officeMap = L.map('officeMapPicker').setView([initLat, initLon], 16);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(officeMap);

        officeMarker = L.marker([initLat, initLon], {
            draggable: true,
            title: "Office Geofence Center"
        }).addTo(officeMap);

        officeCircle = L.circle([initLat, initLon], {
            radius: radius,
            color: '#10b981',
            fillColor: '#10b981',
            fillOpacity: 0.18,
            weight: 2
        }).addTo(officeMap);

        bindMapEvents();
        setMapPinBadge("Saved Office Coordinates", "badge-present", '<i class="fa-solid fa-building"></i>');
    } else {
        officeMap = L.map('officeMapPicker').setView([DEFAULT_FALLBACK_LAT, DEFAULT_FALLBACK_LON], 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(officeMap);

        officeMarker = L.marker([DEFAULT_FALLBACK_LAT, DEFAULT_FALLBACK_LON], {
            draggable: true,
            title: "Office Geofence Center"
        }).addTo(officeMap);

        officeCircle = L.circle([DEFAULT_FALLBACK_LAT, DEFAULT_FALLBACK_LON], {
            radius: radius,
            color: '#10b981',
            fillColor: '#10b981',
            fillOpacity: 0.18,
            weight: 2
        }).addTo(officeMap);

        bindMapEvents();
        setMapPinBadge("Detecting Live GPS...", "badge-node", '<i class="fa-solid fa-spinner fa-spin"></i>');

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = parseFloat(pos.coords.latitude.toFixed(6));
                    const lon = parseFloat(pos.coords.longitude.toFixed(6));
                    const acc = parseFloat(pos.coords.accuracy.toFixed(1));

                    if (latInput) latInput.value = lat;
                    if (lonInput) lonInput.value = lon;

                    if (officeMarker) officeMarker.setLatLng([lat, lon]);
                    if (officeCircle) officeCircle.setLatLng([lat, lon]);
                    if (officeMap) officeMap.flyTo([lat, lon], 16, { animate: true, duration: 1.2 });

                    setMapPinBadge(`Auto-Centered to Live GPS (±${acc}m)`, "badge-present", '<i class="fa-solid fa-crosshairs" style="color: #10b981;"></i>');
                    
                    const statusEl = document.getElementById("gpsDetectStatus");
                    if (statusEl) {
                        statusEl.innerHTML = `<span style="color: var(--accent-emerald); font-weight: 600;"><i class="fa-solid fa-check"></i> Live GPS locked: ${lat}, ${lon} (±${acc}m)</span>`;
                    }
                },
                (err) => {
                    if (latInput && !latInput.value) latInput.value = DEFAULT_FALLBACK_LAT.toFixed(6);
                    if (lonInput && !lonInput.value) lonInput.value = DEFAULT_FALLBACK_LON.toFixed(6);

                    setMapPinBadge("Gujarat, India (Fallback Default)", "badge-unknown", '<i class="fa-solid fa-location-dot"></i>');
                    
                    const statusEl = document.getElementById("gpsDetectStatus");
                    if (statusEl) {
                        statusEl.innerHTML = `<span style="color: var(--text-muted); font-size: 11px;">GPS permission denied/unavailable. Using regional center default.</span>`;
                    }
                },
                { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
            );
        } else {
            if (latInput && !latInput.value) latInput.value = DEFAULT_FALLBACK_LAT.toFixed(6);
            if (lonInput && !lonInput.value) lonInput.value = DEFAULT_FALLBACK_LON.toFixed(6);
            setMapPinBadge("Gujarat, India (Geolocation Unsupported)", "badge-unknown", '<i class="fa-solid fa-location-dot"></i>');
        }
    }

    setTimeout(() => {
        if (officeMap) officeMap.invalidateSize();
    }, 250);
}

function bindMapEvents() {
    if (!officeMarker || !officeMap) return;

    officeMarker.on('drag', (e) => {
        const pos = e.target.getLatLng();
        updateCoordinatesFromMap(pos.lat, pos.lng);
        setMapPinBadge("Pin Position Selected", "badge-node", '<i class="fa-solid fa-hand-pointer"></i>');
    });

    officeMap.on('click', (e) => {
        officeMarker.setLatLng(e.latlng);
        updateCoordinatesFromMap(e.latlng.lat, e.latlng.lng);
        setMapPinBadge("Pin Position Selected", "badge-node", '<i class="fa-solid fa-hand-pointer"></i>');
    });
}

function updateCoordinatesFromMap(lat, lon) {
    const latInput = document.getElementById("brandGeoLatitude");
    const lonInput = document.getElementById("brandGeoLongitude");
    if (latInput) latInput.value = lat.toFixed(6);
    if (lonInput) lonInput.value = lon.toFixed(6);
    if (officeCircle) {
        officeCircle.setLatLng([lat, lon]);
    }
}

function onManualCoordinateChange() {
    const latInput = document.getElementById("brandGeoLatitude");
    const lonInput = document.getElementById("brandGeoLongitude");
    if (!latInput || !lonInput) return;

    const lat = parseFloat(latInput.value);
    const lon = parseFloat(lonInput.value);

    if (!isNaN(lat) && !isNaN(lon) && officeMap && officeMarker && officeCircle) {
        officeMarker.setLatLng([lat, lon]);
        officeCircle.setLatLng([lat, lon]);
        officeMap.panTo([lat, lon]);
        setMapPinBadge("Coordinates Manually Entered", "badge-node", '<i class="fa-solid fa-pen"></i>');
    }
}

function updateGeoRadiusDisplay(val) {
    const radius = Math.max(10, parseInt(val) || 150);
    const brandGeoRadius = document.getElementById("brandGeoRadius");
    const geoRadiusBadge = document.getElementById("geoRadiusBadge");
    if (brandGeoRadius) brandGeoRadius.value = radius;
    if (geoRadiusBadge) geoRadiusBadge.innerText = `${radius} Meters`;
    if (officeCircle) {
        officeCircle.setRadius(radius);
    }
}

function updateGeoRadiusFromInput(val) {
    let radius = parseInt(val) || 150;
    radius = Math.max(10, Math.min(50000, radius));
    const geoRadiusSlider = document.getElementById("geoRadiusSlider");
    const geoRadiusBadge = document.getElementById("geoRadiusBadge");
    if (geoRadiusSlider) geoRadiusSlider.value = Math.min(2000, radius);
    if (geoRadiusBadge) geoRadiusBadge.innerText = `${radius} Meters`;
    if (officeCircle) {
        officeCircle.setRadius(radius);
    }
}

async function searchMapLocation() {
    const searchInput = document.getElementById("mapSearchInput");
    if (!searchInput) return;
    const query = searchInput.value.trim();
    if (!query) return;

    setMapPinBadge("Searching location...", "badge-node", '<i class="fa-solid fa-spinner fa-spin"></i>');

    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data && data.length > 0) {
            const first = data[0];
            const lat = parseFloat(first.lat);
            const lon = parseFloat(first.lon);

            const latInput = document.getElementById("brandGeoLatitude");
            const lonInput = document.getElementById("brandGeoLongitude");
            if (latInput) latInput.value = lat.toFixed(6);
            if (lonInput) lonInput.value = lon.toFixed(6);

            if (officeMap && officeMarker && officeCircle) {
                officeMarker.setLatLng([lat, lon]);
                officeCircle.setLatLng([lat, lon]);
                officeMap.flyTo([lat, lon], 16, { animate: true, duration: 1.2 });
            }
            setMapPinBadge(`Found: ${query.substring(0, 24)}...`, "badge-present", '<i class="fa-solid fa-location-crosshairs"></i>');
        } else {
            setMapPinBadge("Location Not Found", "badge-unknown", '<i class="fa-solid fa-triangle-exclamation"></i>');
            alert("No geographic locations found for: " + query);
        }
    } catch (err) {
        setMapPinBadge("Search Service Unavailable", "badge-unknown", '<i class="fa-solid fa-triangle-exclamation"></i>');
        alert("Location search failed. Please enter coordinates manually.");
    }
}

function fetchAdminGpsLocation() {
    const statusEl = document.getElementById("gpsDetectStatus");
    if (!navigator.geolocation) {
        if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger-color);">Geolocation not supported by browser.</span>';
        return;
    }

    if (statusEl) statusEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Fetching high-accuracy GPS coordinates...';
    setMapPinBadge("Locating Live GPS...", "badge-node", '<i class="fa-solid fa-spinner fa-spin"></i>');

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const lat = parseFloat(pos.coords.latitude.toFixed(6));
            const lon = parseFloat(pos.coords.longitude.toFixed(6));
            const acc = parseFloat(pos.coords.accuracy.toFixed(1));

            const latInput = document.getElementById("brandGeoLatitude");
            const lonInput = document.getElementById("brandGeoLongitude");
            if (latInput) latInput.value = lat;
            if (lonInput) lonInput.value = lon;

            if (officeMap && officeMarker && officeCircle) {
                officeMarker.setLatLng([lat, lon]);
                officeCircle.setLatLng([lat, lon]);
                officeMap.flyTo([lat, lon], 16, { animate: true, duration: 1.0 });
            }

            setMapPinBadge(`Live GPS Locked (±${acc}m)`, "badge-present", '<i class="fa-solid fa-crosshairs" style="color: #10b981;"></i>');

            if (statusEl) {
                statusEl.innerHTML = `<span style="color: var(--accent-emerald); font-weight: 600;"><i class="fa-solid fa-check"></i> Lat: ${lat}, Lon: ${lon} (±${acc}m)</span>`;
            }
        },
        (err) => {
            setMapPinBadge("GPS Request Failed", "badge-unknown", '<i class="fa-solid fa-triangle-exclamation"></i>');
            if (statusEl) {
                statusEl.innerHTML = `<span style="color: var(--danger-color);">GPS Error: ${err.message}. Please check browser location permissions.</span>`;
            }
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
}

function showCopyFeedback(btn) {
    if (!btn) return;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-check" style="color: var(--accent-emerald);"></i> <span style="color: var(--accent-emerald);">Copied!</span>';
    setTimeout(() => {
        btn.innerHTML = origHtml;
    }, 2000);
}

function copyToClipboardWithFallback(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showCopyFeedback(btn);
        }).catch(() => {
            fallbackExecCopy(text, btn);
        });
    } else {
        fallbackExecCopy(text, btn);
    }
}

function fallbackExecCopy(text, btn) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand("copy");
        showCopyFeedback(btn);
    } catch (e) {
        prompt("Copy URL to clipboard:", text);
    }
    document.body.removeChild(ta);
}

function copyUniversalEmployeePortalLink(btn) {
    const span = document.getElementById("universalEmployeePortalUrlSpan");
    if (!span) return;
    const text = span.innerText.trim();
    const fullUrl = text.startsWith("http") ? text : (window.location.origin + text);
    copyToClipboardWithFallback(fullUrl, btn);
}

function copyPermanentCheckinLink(btn) {
    const span = document.getElementById("selfAttendanceUrlSpan");
    if (!span) return;
    const fullUrl = window.location.origin + span.innerText.trim();
    copyToClipboardWithFallback(fullUrl, btn);
}

function copyEmployeeOnboardLink(btn) {
    const span = document.getElementById("employeeOnboardingUrlSpan");
    if (!span) return;
    const fullUrl = window.location.origin + span.innerText.trim();
    copyToClipboardWithFallback(fullUrl, btn);
}

function resetBrandColor() {
    document.getElementById("brandAccentColorPicker").value = "#6366f1";
    document.getElementById("brandAccentColorText").value = "#6366f1";
}

async function saveBrandingDetails(e) {
    e.preventDefault();
    const instName = document.getElementById("brandInstName").value.trim();
    const shortCode = document.getElementById("brandShortCode").value.trim();
    const tagline = document.getElementById("brandTagline").value.trim();
    const badgeText = document.getElementById("brandBadgeText").value.trim();
    const email = document.getElementById("brandContactEmail").value.trim();
    const color = document.getElementById("brandAccentColorText").value.trim();
    const rawCooldown = parseInt(document.getElementById("brandCooldownMinutes").value);
    const cooldownMins = isNaN(rawCooldown) ? 60 : Math.max(1, rawCooldown);
    const antiSpoofing = document.getElementById("brandAntiSpoofingToggle").checked;
    const livenessMode = document.getElementById("brandLivenessMode").value || "BALANCED";
    const temporalFrames = parseInt(document.getElementById("brandTemporalFrames").value) || 3;
    const audioChime = document.getElementById("brandAudioChime").checked;
    const hapticFeedback = document.getElementById("brandHapticFeedback").checked;
    const enableSelfAttendance = document.getElementById("brandSelfAttendanceToggle").checked;
    const rawLat = document.getElementById("brandGeoLatitude").value.trim();
    const rawLon = document.getElementById("brandGeoLongitude").value.trim();
    const geoLat = rawLat ? parseFloat(rawLat) : null;
    const geoLon = rawLon ? parseFloat(rawLon) : null;
    const geoRadius = parseFloat(document.getElementById("brandGeoRadius").value) || 150.0;
    const gpsAccuracy = parseFloat(document.getElementById("brandGpsAccuracy").value) || 50.0;
    const faceThreshold = parseFloat(document.getElementById("brandFaceThreshold").value) || 0.52;

    const shiftCheckIn = document.getElementById("brandShiftCheckIn") ? document.getElementById("brandShiftCheckIn").value.trim() : "10:30";
    const shiftCheckOut = document.getElementById("brandShiftCheckOut") ? document.getElementById("brandShiftCheckOut").value.trim() : "18:00";
    const shiftGrace = document.getElementById("brandShiftGrace") ? parseInt(document.getElementById("brandShiftGrace").value) || 15 : 15;
    const minCheckoutInterval = document.getElementById("brandMinCheckoutInterval") ? parseInt(document.getElementById("brandMinCheckoutInterval").value) || 15 : 15;

    const alertBox = document.getElementById("brandingSaveAlert");

    try {
        const res = await fetch("/api/v1/branding", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                institution_name: instName,
                short_code: shortCode,
                tagline: tagline,
                header_badge_text: badgeText,
                contact_email: email || null,
                primary_accent_color: color,
                cooldown_minutes: cooldownMins,
                enable_anti_spoofing: antiSpoofing,
                liveness_mode: livenessMode,
                temporal_frames_required: temporalFrames,
                enable_audio_chime: audioChime,
                enable_haptic_feedback: hapticFeedback,
                enable_self_attendance: enableSelfAttendance,
                geo_latitude: geoLat,
                geo_longitude: geoLon,
                geo_radius_meters: geoRadius,
                max_gps_accuracy_meters: gpsAccuracy,
                self_attendance_face_threshold: faceThreshold,
                shift_check_in_time: shiftCheckIn,
                shift_check_out_time: shiftCheckOut,
                shift_grace_minutes: shiftGrace,
                min_checkout_interval_minutes: minCheckoutInterval,
            }),
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || 'Settings saved successfully!');

            // Update live UI
            const sideName = document.getElementById("sidebarBrandName");
            const sideBadge = document.getElementById("sidebarBrandBadge");
            const sideCode = document.getElementById("footerShortCode");
            const tagEl = document.getElementById("topBarTagline");

            if (sideName) sideName.innerText = instName;
            if (sideBadge) sideBadge.innerText = badgeText;
            if (sideCode) sideCode.innerText = `${shortCode} Online`;
            if (tagEl) tagEl.innerText = tagline;

            setTimeout(() => {
                alertBox.style.display = "none";
            }, 3000);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || 'Failed to save.');
            setTimeout(() => {
                alertBox.style.display = "none";
            }, 4000);
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to backend.';
        setTimeout(() => {
            alertBox.style.display = "none";
        }, 4000);
    }
}

async function handleLogoFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    const alertBox = document.getElementById("logoUploadAlert");
    alertBox.style.display = "block";
    alertBox.style.background = "var(--badge-indigo-bg)";
    alertBox.style.color = "var(--accent-primary)";
    alertBox.style.border = "1px solid var(--badge-indigo-border)";
    alertBox.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading & resizing logo...';

    const formData = new FormData();
    formData.append("logo", file);

    try {
        const res = await fetch("/api/v1/branding/logo", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + data.message;
            setTimeout(() => window.location.reload(), 900);
        } else {
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || 'Upload failed.');
        }
    } catch (err) {
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error uploading logo.';
    }
}

async function resetInstituteLogo() {
    if (!confirm("Are you sure you want to reset the institute logo to default?")) return;

    try {
        const res = await fetch("/api/v1/branding/logo", {
            method: "DELETE",
        });
        if (res.ok) {
            window.location.reload();
        } else {
            alert("Failed to reset logo.");
        }
    } catch (e) {
        alert("Network error.");
    }
}

function loadSavedSystemPreferences() {
    const savedThreshold = localStorage.getItem("app_defaulter_threshold") || "75";
    const savedTolerance = localStorage.getItem("app_match_tolerance") || "0.60";

    const thresholdInput = document.getElementById("prefDefaulterThreshold");
    const toleranceSelect = document.getElementById("prefMatchTolerance");

    if (thresholdInput) thresholdInput.value = savedThreshold;
    if (toleranceSelect) toleranceSelect.value = savedTolerance;
}

function saveSystemPreferences(e) {
    if (e && e.preventDefault) e.preventDefault();
    const threshold = document.getElementById("prefDefaulterThreshold").value;
    const tolerance = document.getElementById("prefMatchTolerance").value;

    localStorage.setItem("app_defaulter_threshold", threshold);
    localStorage.setItem("app_match_tolerance", tolerance);

    const alertBox = document.getElementById("prefsSaveAlert");
    if (alertBox) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-emerald-bg)";
        alertBox.style.color = "var(--badge-emerald-text)";
        alertBox.style.border = "1px solid var(--badge-emerald-border)";
        alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> System parameters saved successfully!';
        setTimeout(() => {
            alertBox.style.display = "none";
        }, 3000);
    }
}

// --- Consolidated Departments Modal & Live Async CRUD Functions ---
async function fetchAndRenderDepartmentsTable() {
    try {
        const res = await fetch("/api/v1/academic/departments");
        if (!res.ok) return;
        const data = await res.json();
        const depts = data.departments || [];
        renderDepartmentsTable(depts);
        updateDepartmentDropdowns(depts);
    } catch (err) {
        console.error("Failed to fetch departments:", err);
    }
}

function renderDepartmentsTable(depts) {
    const tbody = document.getElementById("departmentsTableBody");
    if (!tbody) return;

    if (!depts || depts.length === 0) {
        tbody.innerHTML = `
            <tr id="emptyDeptsRow">
                <td colspan="5" style="text-align: center; padding: 32px 16px; color: var(--text-muted);">
                    <i class="fa-solid fa-diagram-project" style="font-size: 28px; margin-bottom: 8px; opacity: 0.5;"></i>
                    <p style="font-weight: 600; margin: 0; color: var(--text-heading);">No departments created yet.</p>
                    <span style="font-size: 12px;">Click "Add Department / Team" above to create your organizational hierarchy.</span>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = depts.map(dept => {
        const deptJson = JSON.stringify(dept).replace(/'/g, "&#39;");
        const empCount = dept.employee_count != null ? dept.employee_count : (dept.students_count || 0);
        return `
            <tr style="border-bottom: 1px solid var(--border-subtle); font-size: 13px;" id="deptRow-${dept.id}">
                <td style="padding: 12px; font-weight: 700; color: var(--text-heading);">
                    <i class="fa-solid fa-building" style="color: var(--accent-primary); margin-right: 8px;"></i>
                    ${escapeHtml(dept.name)}
                </td>
                <td style="padding: 12px; font-family: monospace; font-size: 12px; color: var(--text-secondary);">
                    ${escapeHtml(dept.code || (dept.name ? dept.name.slice(0, 4).toUpperCase() : 'DEPT'))}
                </td>
                <td style="padding: 12px;">
                    <span class="badge badge-sky" style="font-size: 11px;">
                        <i class="fa-solid fa-users"></i> ${empCount} Members
                    </span>
                </td>
                <td style="padding: 12px; color: var(--text-muted); font-size: 12px; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    ${escapeHtml(dept.description || '—')}
                </td>
                <td style="padding: 12px; text-align: right;">
                    <div style="display: flex; gap: 6px; justify-content: flex-end;">
                        <button type="button" class="btn btn-secondary" style="padding: 5px 9px; font-size: 11.5px;" onclick='openEditDeptModal(${deptJson})' title="Edit Department">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button type="button" class="btn btn-secondary" style="padding: 5px 9px; font-size: 11.5px; color: var(--accent-rose);" onclick="deleteDepartment(${dept.id}, '${escapeHtml(dept.name).replace(/'/g, "\\'")}')" title="Delete Department">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function updateDepartmentDropdowns(depts) {
    const desigDeptSelect = document.getElementById("modalSettingsDesigDept");
    if (desigDeptSelect) {
        const curVal = desigDeptSelect.value;
        let html = '<option value="">-- All / General Department --</option>';
        depts.forEach(d => {
            html += `<option value="${d.id}">${escapeHtml(d.name)}</option>`;
        });
        desigDeptSelect.innerHTML = html;
        desigDeptSelect.value = curVal;
    }
}

function openAddDepartmentModal() {
    document.getElementById("modalDeptId").value = "";
    document.getElementById("modalDeptName").value = "";
    document.getElementById("modalDeptCode").value = "";
    document.getElementById("modalDeptDesc").value = "";
    document.getElementById("deptModalTitle").innerHTML = '<i class="fa-solid fa-building" style="color: var(--accent-primary);"></i> <span>Add Department / Team</span>';
    document.getElementById("deptModalAlert").style.display = "none";
    document.getElementById("deptModal").style.display = "flex";
}

function openEditDeptModal(deptOrId) {
    let dept = deptOrId;
    if (typeof deptOrId === "number" || typeof deptOrId === "string") {
        dept = (window.allTenantDepartments || []).find(d => Number(d.id) === Number(deptOrId)) || { id: deptOrId };
    }
    if (!dept) return;
    document.getElementById("modalDeptId").value = dept.id || "";
    document.getElementById("modalDeptName").value = dept.name || "";
    document.getElementById("modalDeptCode").value = dept.code || "";
    document.getElementById("modalDeptDesc").value = dept.description || "";
    document.getElementById("deptModalTitle").innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Department: ' + escapeHtml(dept.name || '') + '</span>';
    document.getElementById("deptModalAlert").style.display = "none";
    document.getElementById("deptModal").style.display = "flex";
}

function closeDeptModal() {
    document.getElementById("deptModal").style.display = "none";
}

async function saveDepartmentModal(e) {
    e.preventDefault();
    const deptId = document.getElementById("modalDeptId").value;
    const name = document.getElementById("modalDeptName").value.trim();
    const code = document.getElementById("modalDeptCode").value.trim();
    const description = document.getElementById("modalDeptDesc").value.trim();
    const alertBox = document.getElementById("deptModalAlert");
    const saveBtn = document.getElementById("btnSaveDeptModal");

    if (!name) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(239, 68, 68, 0.1)";
        alertBox.style.color = "#f87171";
        alertBox.innerText = "Department name is required.";
        return;
    }

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    }

    const isEdit = !!deptId;
    const url = isEdit ? `/api/v1/academic/departments/${deptId}` : "/api/v1/academic/departments";
    const method = isEdit ? "PUT" : "POST";

    try {
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, code, description })
        });
        const data = await res.json();
        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.innerText = data.message || "Department saved successfully!";

            // Live asynchronous refresh of department table and dropdowns
            await fetchAndRenderDepartmentsTable();

            setTimeout(() => {
                closeDeptModal();
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Department';
                }
            }, 400);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(239, 68, 68, 0.1)";
            alertBox.style.color = "#f87171";
            alertBox.innerText = data.detail || "Failed to save department.";
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Department';
            }
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(239, 68, 68, 0.1)";
        alertBox.style.color = "#f87171";
        alertBox.innerText = "Network error: " + err.message;
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Department';
        }
    }
}

async function deleteDepartment(deptId, deptName) {
    if (!confirm(`Are you sure you want to delete department "${deptName}"?`)) return;
    try {
        const res = await fetch(`/api/v1/academic/departments/${deptId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            await fetchAndRenderDepartmentsTable();
        } else {
            alert(data.detail || "Failed to delete department.");
        }
    } catch (e) {
        alert("Network error while deleting department.");
    }
}

// ----------------------------------------------------
// WORK SHIFT MANAGEMENT MODAL & CRUD
// ----------------------------------------------------
function openAddShiftModal() {
    document.getElementById("shiftModalTitle").innerHTML = '<i class="fa-solid fa-clock" style="color: var(--accent-primary);"></i> <span>Add Work Shift</span>';
    document.getElementById("modalShiftId").value = "";
    document.getElementById("modalShiftName").value = "";
    document.getElementById("modalShiftCode").value = "";
    document.getElementById("modalShiftStartTime").value = "09:00";
    document.getElementById("modalShiftEndTime").value = "17:30";
    document.getElementById("modalShiftGrace").value = "15";
    document.getElementById("modalShiftBreak").value = "0";
    document.getElementById("modalShiftHalfDay").value = "4.0";
    document.getElementById("modalShiftIsDefault").checked = false;
    document.getElementById("shiftModalAlert").style.display = "none";
    document.getElementById("shiftModal").style.display = "flex";
}

function openEditShiftModal(shiftOrId) {
    let shift = shiftOrId;
    if (typeof shiftOrId === "number" || typeof shiftOrId === "string") {
        shift = (window.allTenantShifts || []).find(s => Number(s.id) === Number(shiftOrId)) || { id: shiftOrId };
    }
    if (!shift) return;
    document.getElementById("shiftModalTitle").innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Work Shift</span>';
    document.getElementById("modalShiftId").value = shift.id || "";
    document.getElementById("modalShiftName").value = shift.name || "";
    document.getElementById("modalShiftCode").value = shift.code || "";
    document.getElementById("modalShiftStartTime").value = shift.start_time || "10:30";
    document.getElementById("modalShiftEndTime").value = shift.end_time || "18:00";
    document.getElementById("modalShiftGrace").value = shift.grace_period_minutes != null ? shift.grace_period_minutes : 15;
    document.getElementById("modalShiftBreak").value = shift.break_duration_minutes != null ? shift.break_duration_minutes : 0;
    document.getElementById("modalShiftHalfDay").value = shift.half_day_hours != null ? shift.half_day_hours : 4.0;
    document.getElementById("modalShiftIsDefault").checked = !!shift.is_default;
    document.getElementById("shiftModalAlert").style.display = "none";
    document.getElementById("shiftModal").style.display = "flex";
}

function closeShiftModal() {
    document.getElementById("shiftModal").style.display = "none";
}

async function saveShiftModal(event) {
    event.preventDefault();
    const shiftId = document.getElementById("modalShiftId").value;
    const name = document.getElementById("modalShiftName").value.trim();
    const code = document.getElementById("modalShiftCode").value.trim();
    const start_time = document.getElementById("modalShiftStartTime").value.trim();
    const end_time = document.getElementById("modalShiftEndTime").value.trim();
    const grace_period_minutes = parseInt(document.getElementById("modalShiftGrace").value) || 15;
    const break_duration_minutes = parseInt(document.getElementById("modalShiftBreak").value) || 0;
    const half_day_hours = parseFloat(document.getElementById("modalShiftHalfDay").value) || 4.0;
    const is_default = document.getElementById("modalShiftIsDefault").checked;
    const alertBox = document.getElementById("shiftModalAlert");

    if (!name || !start_time || !end_time) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(239, 68, 68, 0.1)";
        alertBox.style.color = "#f87171";
        alertBox.innerText = "Shift Name, Start Time, and End Time are required.";
        return;
    }

    const isEdit = !!shiftId;
    const url = isEdit ? `/api/v1/shifts/${shiftId}` : "/api/v1/shifts";
    const method = isEdit ? "PUT" : "POST";

    try {
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name,
                code,
                start_time,
                end_time,
                grace_period_minutes,
                break_duration_minutes,
                half_day_hours,
                is_default
            })
        });
        const data = await res.json();
        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.innerText = data.message || "Shift saved successfully!";
            setTimeout(() => {
                closeShiftModal();
                window.location.reload();
            }, 500);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(239, 68, 68, 0.1)";
            alertBox.style.color = "#f87171";
            alertBox.innerText = data.detail || "Failed to save shift.";
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(239, 68, 68, 0.1)";
        alertBox.style.color = "#f87171";
        alertBox.innerText = "Network error: " + err.message;
    }
}

async function setDefaultShift(shiftId, shiftName) {
    try {
        const res = await fetch(`/api/v1/shifts/${shiftId}/set-default`, {
            method: "POST"
        });
        const data = await res.json();
        if (res.ok) {
            window.location.reload();
        } else {
            alert(data.detail || "Failed to set default shift.");
        }
    } catch (e) {
        alert("Network error while updating default shift.");
    }
}

async function deleteShift(shiftId, shiftName) {
    if (!confirm(`Are you sure you want to delete shift "${shiftName}"?`)) return;
    try {
        const res = await fetch(`/api/v1/shifts/${shiftId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            const row = document.getElementById(`shiftRow-${shiftId}`);
            if (row) row.remove();
            window.location.reload();
        } else {
            alert(data.detail || "Failed to delete shift.");
        }
    } catch (e) {
        alert("Network error while deleting shift.");
    }
}

// Designation Modal Handlers (Settings - General Title & Role Creation)
function openAddDesignationModal() {
    document.getElementById("settingsDesigModalTitle").innerHTML = '<i class="fa-solid fa-user-tag" style="color: var(--accent-primary);"></i> <span>Add Designation</span>';
    document.getElementById("modalSettingsDesigId").value = "";
    document.getElementById("modalSettingsDesigTitle").value = "";
    document.getElementById("modalSettingsDesigCode").value = "";
    document.getElementById("modalSettingsDesigDept").value = "";
    document.getElementById("modalSettingsDesigDesc").value = "";
    document.getElementById("modalSettingsDesigIsActive").value = "true";
    document.getElementById("settingsDesigModalAlert").style.display = "none";
    document.getElementById("settingsDesignationModal").style.display = "flex";
}

function openEditDesignationModal(desigOrId) {
    let desig = desigOrId;
    if (typeof desigOrId === "number" || typeof desigOrId === "string") {
        desig = (window.allTenantDesignations || []).find(d => Number(d.id) === Number(desigOrId)) || { id: desigOrId };
    }
    if (!desig) return;
    document.getElementById("settingsDesigModalTitle").innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Designation</span>';
    document.getElementById("modalSettingsDesigId").value = desig.id || "";
    document.getElementById("modalSettingsDesigTitle").value = desig.title || "";
    document.getElementById("modalSettingsDesigCode").value = desig.code || "";
    document.getElementById("modalSettingsDesigDept").value = desig.department_id || "";
    document.getElementById("modalSettingsDesigDesc").value = desig.description || "";
    document.getElementById("modalSettingsDesigIsActive").value = desig.is_active ? "true" : "false";
    document.getElementById("settingsDesigModalAlert").style.display = "none";
    document.getElementById("settingsDesignationModal").style.display = "flex";
}

function closeSettingsDesignationModal() {
    document.getElementById("settingsDesignationModal").style.display = "none";
}

async function saveSettingsDesignationModal(e) {
    e.preventDefault();
    const id = document.getElementById("modalSettingsDesigId").value;
    const title = document.getElementById("modalSettingsDesigTitle").value.trim();
    const code = document.getElementById("modalSettingsDesigCode").value.trim();
    const deptId = document.getElementById("modalSettingsDesigDept").value;
    const desc = document.getElementById("modalSettingsDesigDesc").value.trim();
    const isActive = document.getElementById("modalSettingsDesigIsActive").value === "true";
    const alertBox = document.getElementById("settingsDesigModalAlert");
    const saveBtn = document.getElementById("btnSaveSettingsDesigModal");

    if (!title) return;

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    const payload = {
        title: title,
        code: code || null,
        department_id: deptId ? parseInt(deptId) : null,
        description: desc || null,
        is_active: isActive
    };

    try {
        const url = id ? `/api/v1/payroll/masters/designations/${id}` : "/api/v1/payroll/masters/designations";
        const method = id ? "PUT" : "POST";
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || 'Designation saved successfully.');
            setTimeout(() => {
                closeSettingsDesignationModal();
                window.location.hash = "designations";
                window.location.reload();
            }, 600);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || 'Failed to save designation.');
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Designation';
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Designation';
    }
}

async function deleteSettingsDesignation(desigId, title) {
    if (!confirm(`Are you sure you want to delete designation "${title}"?`)) return;
    try {
        const res = await fetch(`/api/v1/payroll/masters/designations/${desigId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            const row = document.getElementById(`settingsDesigRow-${desigId}`);
            if (row) row.remove();
            window.location.hash = "designations";
            window.location.reload();
        } else {
            alert(data.detail || "Failed to delete designation.");
        }
    } catch (e) {
        alert("Network error while deleting designation.");
    }
}
// =========================================================================
// OFFICE LOCATIONS & BRANCHES HANDLERS (Organization Settings)
// =========================================================================
function openAddLocationModal() {
    document.getElementById("modalSettingsLocId").value = "";
    document.getElementById("settingsLocModalTitle").innerHTML = '<i class="fa-solid fa-map-location-dot" style="color: var(--accent-primary);"></i> <span>Add Office Location</span>';
    document.getElementById("settingsLocModalForm").reset();
    document.getElementById("modalSettingsLocState").value = "Maharashtra";
    document.getElementById("modalSettingsLocIsActive").value = "true";
    const alertBox = document.getElementById("settingsLocModalAlert");
    if (alertBox) alertBox.style.display = "none";
    const modal = document.getElementById("settingsLocationModal");
    if (modal) modal.style.display = "flex";
}

function openEditLocationModal(locId) {
    document.getElementById("modalSettingsLocId").value = locId;
    document.getElementById("settingsLocModalTitle").innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--accent-primary);"></i> <span>Edit Office Location</span>';
    const alertBox = document.getElementById("settingsLocModalAlert");
    if (alertBox) alertBox.style.display = "none";

    fetch(`/api/v1/payroll/masters/locations/${locId}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success" && data.data) {
                const loc = data.data;
                document.getElementById("modalSettingsLocName").value = loc.name || "";
                document.getElementById("modalSettingsLocCode").value = loc.code || "";
                document.getElementById("modalSettingsLocCity").value = loc.city || "";
                document.getElementById("modalSettingsLocState").value = loc.state || "Maharashtra";
                document.getElementById("modalSettingsLocContact").value = loc.contact_number || "";
                document.getElementById("modalSettingsLocAddress").value = loc.address || "";
                document.getElementById("modalSettingsLocIsActive").value = loc.is_active ? "true" : "false";
                const modal = document.getElementById("settingsLocationModal");
                if (modal) modal.style.display = "flex";
            }
        })
        .catch(err => {
            alert("Failed to load location details.");
        });
}

function closeSettingsLocationModal() {
    const modal = document.getElementById("settingsLocationModal");
    if (modal) modal.style.display = "none";
}

async function saveSettingsLocationModal(e) {
    e.preventDefault();
    const id = document.getElementById("modalSettingsLocId").value;
    const name = document.getElementById("modalSettingsLocName").value.trim();
    const code = document.getElementById("modalSettingsLocCode").value.trim().toUpperCase();
    const city = document.getElementById("modalSettingsLocCity").value.trim();
    const state = document.getElementById("modalSettingsLocState").value.trim();
    const contact = document.getElementById("modalSettingsLocContact").value.trim();
    const address = document.getElementById("modalSettingsLocAddress").value.trim();
    const isActive = document.getElementById("modalSettingsLocIsActive").value === "true";

    const saveBtn = document.getElementById("btnSaveSettingsLocModal");
    const alertBox = document.getElementById("settingsLocModalAlert");

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    const payload = {
        name: name,
        code: code || null,
        city: city || null,
        state: state || "Maharashtra",
        contact_number: contact || null,
        address: address || null,
        is_active: isActive
    };

    try {
        const url = id ? `/api/v1/payroll/masters/locations/${id}` : "/api/v1/payroll/masters/locations";
        const method = id ? "PUT" : "POST";
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-emerald-bg)";
            alertBox.style.border = "1px solid var(--badge-emerald-border)";
            alertBox.style.color = "var(--badge-emerald-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-circle-check"></i> ' + (data.message || 'Office location saved successfully.');
            setTimeout(() => {
                closeSettingsLocationModal();
                window.location.hash = "branding";
                window.location.reload();
            }, 600);
        } else {
            alertBox.style.display = "block";
            alertBox.style.background = "var(--badge-rose-bg)";
            alertBox.style.border = "1px solid var(--badge-rose-border)";
            alertBox.style.color = "var(--badge-rose-text)";
            alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + (data.detail || 'Failed to save location.');
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Location';
        }
    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "var(--badge-rose-bg)";
        alertBox.style.border = "1px solid var(--badge-rose-border)";
        alertBox.style.color = "var(--badge-rose-text)";
        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Network error connecting to server.';
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save Location';
    }
}

async function deleteSettingsLocation(locId, name) {
    if (!confirm(`Are you sure you want to delete office location "${name}"?`)) return;
    try {
        const res = await fetch(`/api/v1/payroll/masters/locations/${locId}`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (res.ok) {
            const row = document.getElementById(`settingsLocRow-${locId}`);
            if (row) row.remove();
            window.location.hash = "branding";
            window.location.reload();
        } else {
            alert(data.detail || "Failed to delete office location.");
        }
    } catch (e) {
        alert("Network error while deleting location.");
    }
}

// Explicit window bindings for inline HTML handlers
window.switchSettingsTab = switchSettingsTab;
window.handleInitialTabFromHash = handleInitialTabFromHash;
window.updateBrandingLivePreview = updateBrandingLivePreview;
window.syncColorInput = syncColorInput;
window.syncColorPicker = syncColorPicker;
window.setCooldownPreset = setCooldownPreset;
window.updateThresholdDisplay = updateThresholdDisplay;
window.updateToleranceDisplay = updateToleranceDisplay;
window.setLivenessPreset = setLivenessPreset;
window.saveBrandingDetails = saveBrandingDetails;
window.resetBrandColor = resetBrandColor;
window.resetInstituteLogo = resetInstituteLogo;
window.copyUniversalEmployeePortalLink = copyUniversalEmployeePortalLink;
window.copyPermanentCheckinLink = copyPermanentCheckinLink;
window.copyEmployeeOnboardLink = copyEmployeeOnboardLink;
window.initOfficeMap = initOfficeMap;
window.searchMapLocation = searchMapLocation;
window.fetchAdminGpsLocation = fetchAdminGpsLocation;
window.openAddLocationModal = openAddLocationModal;
window.openEditLocationModal = openEditLocationModal;
window.closeSettingsLocationModal = closeSettingsLocationModal;
window.submitSettingsLocationModal = submitSettingsLocationModal;
window.deleteSettingsLocation = deleteSettingsLocation;
window.openAddDepartmentModal = openAddDepartmentModal;
window.openEditDeptModal = openEditDeptModal;
window.closeDeptModal = closeDeptModal;
window.submitDeptModal = submitDeptModal;
window.deleteDepartment = deleteDepartment;
window.openAddDesignationModal = openAddDesignationModal;
window.openEditDesignationModal = openEditDesignationModal;
window.closeDesignationModal = closeDesignationModal;
window.submitDesignationModal = submitDesignationModal;
window.deleteSettingsDesignation = deleteSettingsDesignation;
window.openAddShiftModal = openAddShiftModal;
window.openEditShiftModal = openEditShiftModal;
window.closeShiftModal = closeShiftModal;
window.submitShiftModal = submitShiftModal;
window.deleteShift = deleteShift;
window.setDefaultShift = setDefaultShift;
window.saveSystemPreferences = saveSystemPreferences;

