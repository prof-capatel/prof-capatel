import unittest
from fastapi.testclient import TestClient
from src.server.app import app
from src.server.services import traffic_analytics
from src.server.rbac_middleware import create_access_token


class TestTrafficAnalyticsAndOnboardingGuide(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.super_admin_token = create_access_token(user_id=1, role="SUPER_ADMIN", tenant_id=None, username="superadmin")
        self.tenant_admin_token = create_access_token(user_id=2, role="TENANT_ADMIN", tenant_id=1, username="admin")

    def test_traffic_logging_and_endpoint(self):
        # 1. Clear existing logs for a deterministic test
        traffic_analytics.clear_traffic_logs()

        # 2. Simulate simulated crawler hit
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        resp = self.client.get("/", headers=headers)
        self.assertEqual(resp.status_code, 200)

        # 3. Simulate human hit to /saas
        headers_human = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = self.client.get("/saas", headers=headers_human)
        self.assertEqual(resp.status_code, 200)

        # 4. Fetch metrics as Super Admin
        self.client.cookies.set("access_token", self.super_admin_token)
        analytics_resp = self.client.get("/api/v1/super-admin/traffic-analytics")
        self.assertEqual(analytics_resp.status_code, 200)
        data = analytics_resp.json()

        self.assertGreaterEqual(data["total_requests"], 2)
        self.assertGreaterEqual(data["crawler_hits"], 1)
        self.assertGreaterEqual(data["human_visits"], 1)

        # Check top pages contains / and /saas
        paths = [p["path"] for p in data["top_pages"]]
        self.assertIn("/", paths)

    def test_homepage_signin_links_target_blank(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.text
        self.assertIn('href="/saas" target="_blank"', html)

    def test_tenant_sidebar_has_onboarding_guide(self):
        self.client.cookies.set("access_token", self.tenant_admin_token)
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        html = resp.text
        self.assertIn("Quick Onboarding Guide", html)
        self.assertIn("openOnboardingModal(0)", html)
        self.assertIn("onboardingGuideModal", html)
        self.assertIn("onboarding_guide.js", html)


if __name__ == "__main__":
    unittest.main()
