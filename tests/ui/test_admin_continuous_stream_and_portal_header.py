"""
Unit tests for continuous background admin attendance camera stream & employee portal header cleanup.
Verifies:
1. Admin live attendance stream lifecycle (runs in background across window blur/focus).
2. Stream interruption & hardware disconnect handlers and UI badge states.
3. Camera arbitration and auto-resume logic.
4. Employee portal header cleanup (removal of triple duplicate company branding).
"""
import unittest
from pathlib import Path


class TestAdminContinuousStreamAndPortalHeader(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent.parent
        self.dashboard_template = self.root / "src" / "server" / "templates" / "dashboard.html"
        self.dashboard_js = self.root / "src" / "server" / "static" / "js" / "dashboard.js"
        self.portal_template = self.root / "src" / "server" / "templates" / "employee_portal.html"

    def test_dashboard_continuous_background_stream_lifecycle(self):
        """Verify dashboard has continuous streaming without visibilitychange or blur shutdown."""
        self.assertTrue(self.dashboard_template.exists())
        content = self.dashboard_template.read_text(encoding="utf-8")

        # Must not contain blur or visibilitychange auto-shutdown handlers
        self.assertNotIn('window.addEventListener("blur"', content)
        self.assertNotIn('document.addEventListener("visibilitychange"', content)

        # Must contain continuous background lifecycle comment and unload cleanup
        self.assertIn("Continuous Background Attendance Feed Lifecycle", content)
        self.assertIn('window.addEventListener("pagehide"', content)
        self.assertIn('window.addEventListener("beforeunload"', content)

    def test_dashboard_stream_interruption_and_arbitration_handlers(self):
        """Verify dashboard has interruption detection, warning badge states, and arbitration methods."""
        content = self.dashboard_template.read_text(encoding="utf-8")

        # State and handlers
        self.assertIn("isInterruptedState", content)
        self.assertIn("handleCaptureInterrupted", content)
        self.assertIn("pauseForSecondaryCamera", content)
        self.assertIn("resumeFromSecondaryCamera", content)
        self.assertIn("window.pauseForSecondaryCamera", content)
        self.assertIn("window.resumeFromSecondaryCamera", content)

        # Track event listeners
        self.assertIn("videoTrack.onended", content)
        self.assertIn("videoTrack.onmute", content)

        # Interrupted UI badge & restart trigger
        self.assertIn("⚠️ INTERRUPTED", content)
        self.assertIn("Feed Interrupted", content)
        self.assertIn("Restart Attendance Feed", content)

    def test_dashboard_js_retake_arbitration(self):
        """Verify dashboard.js has arbitration prompt before camera takeover and auto-resume on close."""
        self.assertTrue(self.dashboard_js.exists())
        content = self.dashboard_js.read_text(encoding="utf-8")

        self.assertIn("window.isContinuousActive", content)
        self.assertIn("window.pauseForSecondaryCamera", content)
        self.assertIn("window.resumeFromSecondaryCamera", content)
        self.assertIn("Live Attendance Feed is currently capturing attendance", content)

    def test_employee_portal_header_no_triple_branding(self):
        """Verify employee portal header and hero profile card do not repeat the company name 3 times."""
        self.assertTrue(self.portal_template.exists())
        content = self.portal_template.read_text(encoding="utf-8")

        # Topbar subtitle must be clean 'Employee Portal', not repeating tenant.slug
        self.assertIn("Employee Portal", content)
        self.assertNotIn("<code>{{ tenant.slug }}</code>", content)

        # Profile card must not have duplicate tenant name badge (<i class="fa-solid fa-building"></i> {{ tenant.name }})
        self.assertNotIn('<i class="fa-solid fa-building"></i> {{ tenant.name }}', content)

        # Profile card should contain clean employee designation, biometric, and department badges
        self.assertIn("employee.designation", content)
        self.assertIn("Biometric Active", content)
        self.assertIn("employee.department", content)


if __name__ == "__main__":
    unittest.main()
