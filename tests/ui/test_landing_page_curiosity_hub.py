import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import unittest
from fastapi.testclient import TestClient
from src.server.app import app


class TestLandingPageCuriosityHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_landing_page_status_and_branding(self):
        """Test root / returns 200 with Curiosity HUB branding."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Curiosity HUB", html)
        self.assertIn("Employee Management SaaS", html)
        self.assertIn("Ahmedabad", html)

    def test_02_four_required_navigation_menus(self):
        """Test the required navigation links, Products dropdown with 3 submenus, and onboarding guide trigger exist in navbar."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('href="#about"', html)
        self.assertIn("About Us", html)
        # Products dropdown and submenus
        self.assertIn("navProductsDropdown", html)
        self.assertIn("Products", html)
        self.assertIn("Face based Attendance System", html)
        self.assertIn("Leave Management Software", html)
        self.assertIn("Payroll Management System", html)
        # Guide & Contact
        self.assertIn("openOnboardingModal", html)
        self.assertIn("Quick Onboarding Guide", html)
        self.assertIn('href="#contact"', html)
        self.assertIn("Contact Us", html)
        # Deep-dive product modal
        self.assertIn('id="productDetailModal"', html)

    def test_03_single_sign_in_header_action(self):
        """Test navbar contains single 'Sign In' action leading to /saas."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('href="/saas"', html)
        self.assertIn("Sign In", html)

    def test_04_about_us_content(self):
        """Test About Us section specifies Ahmedabad, software development & content design."""
        res = self.client.get("/")
        html = res.text
        self.assertIn('id="about"', html)
        self.assertIn("Ahmedabad (AHD), Gujarat", html)
        self.assertIn("software development", html.lower())
        self.assertIn("content design", html.lower())

    def test_05_employee_management_system_and_editions(self):
        """Test EMS section contains roles and edition tiers (Basic, Smart, Pro)."""
        res = self.client.get("/")
        html = res.text
        self.assertIn('id="product"', html)
        # Roles
        self.assertIn("Organization Admin", html)
        self.assertIn("HR / Payroll Manager", html)
        self.assertIn("Shift Supervisor", html)
        self.assertIn("Employee", html)
        # Edition tiers
        self.assertIn("Basic Edition", html)
        self.assertIn("Smart Edition", html)
        self.assertIn("Pro Edition", html)

    def test_06_onboarding_and_demo_modals(self):
        """Test Onboarding Guide and Free Demo modals and lightbox exist in page."""
        res = self.client.get("/")
        html = res.text
        self.assertIn('id="onboardingGuideModal"', html)
        self.assertIn('id="freeDemoModal"', html)
        self.assertIn('id="lightboxModal"', html)
        self.assertIn("/screenshots/walkthrough/02_dashboard_live.png", html)
        self.assertIn("landing.js", html)

    def test_07_contact_us_details(self):
        """Test Contact Us section has Ahmedabad location, email, mobile, and form."""
        res = self.client.get("/")
        html = res.text
        self.assertIn('id="contact"', html)
        self.assertIn("Ahmedabad, Gujarat, India", html)
        self.assertIn("curiosityhubahd@gmail.com", html)
        self.assertIn("8866868245", html)
        self.assertIn('id="inquiryForm"', html)

    def test_08_core_value_pillars(self):
        """Test landing page emphasizes workforce onboarding, all companies, multi-location, secure."""
        res = self.client.get("/")
        html = res.text
        self.assertIn("Workforce Onboarding", html)
        self.assertIn("Suitable to All Companies", html)
        self.assertIn("Multi-Location Offices", html)
        self.assertIn("Bank-Grade", html)
        self.assertIn("Hardware-Agnostic", html)
        self.assertIn("Automated Payroll", html)

    def test_09_seo_metadata_and_structured_data(self):
        """Test landing page contains complete SEO meta tags, Open Graph, Twitter cards, and Schema.org JSON-LD."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        # Meta tags
        self.assertIn('<meta name="robots" content="index, follow">', html)
        self.assertIn('<link rel="canonical" href="https://curiosityhub.co.in/">', html)
        self.assertIn('<meta name="keywords"', html)
        self.assertIn('name="description"', html)
        # Open Graph
        self.assertIn('property="og:type" content="website"', html)
        self.assertIn('property="og:site_name" content="Curiosity HUB"', html)
        self.assertIn('property="og:url" content="https://curiosityhub.co.in/"', html)
        self.assertIn('property="og:image"', html)
        # Twitter Card
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        # JSON-LD Structured Data
        self.assertIn('type="application/ld+json"', html)
        self.assertIn('"@type": "Organization"', html)
        self.assertIn('"@type": "SoftwareApplication"', html)
        self.assertIn("Ahmedabad", html)
        self.assertIn("curiosityhubahd@gmail.com", html)
        self.assertIn("+91-8866868245", html)
        # Semantic Landmark
        self.assertIn('<main id="main-content" role="main">', html)

    def test_10_technical_seo_files(self):
        """Test technical SEO endpoints /robots.txt and /sitemap.xml are served properly."""
        # robots.txt
        res_robots = self.client.get("/robots.txt")
        self.assertEqual(res_robots.status_code, 200)
        self.assertIn("text/plain", res_robots.headers.get("content-type", ""))
        self.assertIn("User-agent: *", res_robots.text)
        self.assertIn("Allow: /$", res_robots.text)
        self.assertIn("Allow: /screenshots/", res_robots.text)
        self.assertIn("Allow: /static/", res_robots.text)
        self.assertIn("Disallow: /saas", res_robots.text)
        self.assertIn("Disallow: /api/", res_robots.text)
        self.assertIn("Sitemap: https://curiosityhub.co.in/sitemap.xml", res_robots.text)

        # sitemap.xml
        res_sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertIn("application/xml", res_sitemap.headers.get("content-type", ""))
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', res_sitemap.text)
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', res_sitemap.text)
        self.assertIn("<loc>https://curiosityhub.co.in/</loc>", res_sitemap.text)
        self.assertIn("<priority>1.0</priority>", res_sitemap.text)


if __name__ == "__main__":
    unittest.main()

