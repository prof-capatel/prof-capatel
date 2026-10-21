import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import unittest
import re
from fastapi.testclient import TestClient
from src.server.app import app


class TestSEOEnhancements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.new_routes = [
            "/cloud-face-recognition-attendance",
            "/tablet-mobile-attendance-kiosk",
            "/zero-hardware-time-tracking",
            "/leave-management-software",
            "/automated-payroll-software",
            "/saas-vs-hardware-attendance",
            "/onboarding-guide",
            "/compare-editions",
            "/face-attendance-for-retail",
            "/face-attendance-for-factories",
            "/face-attendance-for-corporate-offices",
            "/face-attendance-for-field-teams",
            "/face-attendance-software-ahmedabad",
            "/tools/attendance-roi-calculator",
            "/resources/attendance-policy-template",
            "/resources/holiday-calendar-2026",
            "/privacy-policy",
            "/terms",
            "/biometric-data-policy",
        ]

    def test_01_all_new_routes_return_200(self):
        """Verify each of the targeted SEO landing, industry, and resource pages returns HTTP 200 OK."""
        for route in self.new_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")
                self.assertIn("Curiosity HUB", res.text)

    def test_02_single_h1_per_page(self):
        """Verify each page has exactly one single <h1> tag for optimal SEO hierarchy."""
        all_pages = ["/"] + self.new_routes
        for route in all_pages:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200)
                h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', res.text, re.DOTALL | re.IGNORECASE)
                self.assertEqual(len(h1_matches), 1, f"Route {route} expected exactly 1 <h1>, found {len(h1_matches)}: {h1_matches}")

    def test_03_title_and_meta_description_lengths(self):
        """Verify title tags are between 40-65 chars and meta descriptions are between 140-170 chars."""
        for route in self.new_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200)
                html = res.text

                # Title tag check
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                self.assertIsNotNone(title_match, f"Missing <title> in {route}")
                title = title_match.group(1).strip()
                title_len = len(title)
                self.assertTrue(40 <= title_len <= 65, f"Route {route} title length {title_len} out of 40-65 range: '{title}'")

                # Meta description check
                desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=(["\'])(.*?)\1', html, re.IGNORECASE)
                self.assertIsNotNone(desc_match, f"Missing meta description in {route}")
                desc = desc_match.group(2).strip()
                desc_len = len(desc)
                self.assertTrue(140 <= desc_len <= 170, f"Route {route} meta description length {desc_len} out of 140-170 range: '{desc}'")

    def test_04_canonical_and_open_graph_tags(self):
        """Verify self-referencing canonical, Open Graph, and Twitter tags are present on every page."""
        for route in self.new_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200)
                html = res.text
                expected_canonical = f"https://curiosityhub.co.in{route}"
                self.assertIn(f'rel="canonical" href="{expected_canonical}"', html)
                self.assertIn('property="og:title"', html)
                self.assertIn('property="og:description"', html)
                self.assertIn('property="og:image"', html)
                self.assertIn('name="twitter:card" content="summary_large_image"', html)

    def test_05_json_ld_schemas(self):
        """Verify JSON-LD structured data exists on all pages."""
        for route in self.new_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200)
                html = res.text
                self.assertIn('application/ld+json', html)
                self.assertIn('"@context": "https://schema.org"', html)
                self.assertIn('"@type": "BreadcrumbList"', html)

    def test_06_faq_section_and_schema_on_core_pages(self):
        """Verify FAQ section and Schema.org FAQPage JSON-LD are rendered."""
        # Check on root
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn('id="faq"', res_root.text)
        self.assertIn('"@type": "FAQPage"', res_root.text)
        self.assertIn("zero dedicated biometric hardware", res_root.text.lower())

        # Check on cloud face attendance page
        res_cloud = self.client.get("/cloud-face-recognition-attendance")
        self.assertEqual(res_cloud.status_code, 200)
        self.assertIn('id="faq"', res_cloud.text)
        self.assertIn('"@type": "FAQPage"', res_cloud.text)

    def test_07_sitemap_xml_contains_all_routes_and_no_private(self):
        """Verify /sitemap.xml dynamically serves valid XML containing public routes and excluding private ones."""
        res = self.client.get("/sitemap.xml")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/xml", res.headers.get("content-type", ""))
        xml = res.text
        self.assertIn("<urlset", xml)
        self.assertIn("https://curiosityhub.co.in/</loc>", xml)
        for route in self.new_routes:
            self.assertIn(f"https://curiosityhub.co.in{route}</loc>", xml, f"Missing {route} in sitemap.xml")

        # Exclude private paths
        self.assertNotIn("https://curiosityhub.co.in/saas</loc>", xml)
        self.assertNotIn("https://curiosityhub.co.in/login</loc>", xml)
        self.assertNotIn("https://curiosityhub.co.in/super-admin", xml)

    def test_08_robots_txt_allows_new_routes_and_disallows_private(self):
        """Verify /robots.txt includes Allow directives for public marketing paths and disallows private app routes."""
        res = self.client.get("/robots.txt")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("Allow: /cloud-face-recognition-attendance", content)
        self.assertIn("Allow: /onboarding-guide", content)
        self.assertIn("Allow: /compare-editions", content)
        self.assertIn("Allow: /face-attendance-for-retail", content)
        self.assertIn("Allow: /face-attendance-software-ahmedabad", content)
        self.assertIn("Disallow: /saas", content)
        self.assertIn("Disallow: /login", content)
        self.assertIn("Disallow: /super-admin", content)
        self.assertIn("Disallow: /dashboard", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Sitemap: https://curiosityhub.co.in/sitemap.xml", content)

    def test_09_interactive_calculator_assets(self):
        """Verify the Attendance ROI calculator page has required interactive input sliders."""
        res = self.client.get("/tools/attendance-roi-calculator")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('id="sliderEmployees"', html)
        self.assertIn('id="sliderSalary"', html)
        self.assertIn('id="sliderMinutes"', html)
        self.assertIn('id="sliderHardware"', html)
        self.assertIn('calculateSavings()', html)

    def test_10_noindex_headers_on_private_routes(self):
        """Verify X-Robots-Tag: noindex, nofollow is sent for private and app endpoints."""
        private_test_urls = ["/saas", "/login", "/super-admin/login", "/dashboard"]
        for p_url in private_test_urls:
            with self.subTest(url=p_url):
                res = self.client.get(p_url, follow_redirects=False)
                self.assertEqual(res.headers.get("x-robots-tag"), "noindex, nofollow", f"Missing noindex header on {p_url}")

    def test_11_no_deprecated_keywords_meta_tag(self):
        """Verify deprecated <meta name='keywords'> is purged from all public pages."""
        all_pages = ["/"] + self.new_routes
        for route in all_pages:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200)
                self.assertNotIn('name="keywords"', res.text.lower(), f"Found deprecated meta keywords on {route}")


if __name__ == "__main__":
    unittest.main()
