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
            "/tools/attendance-roi-calculator",
            "/resources/attendance-policy-template",
            "/resources/holiday-calendar-2026",
        ]

    def test_01_all_new_routes_return_200(self):
        """Verify each of the 9 targeted SEO landing and resource pages returns HTTP 200 OK."""
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
        """Verify title tags are between 45-65 chars and meta descriptions are between 140-170 chars."""
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
                self.assertTrue(45 <= title_len <= 65, f"Route {route} title length {title_len} out of 45-65 range: '{title}'")

                # Meta description check
                desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
                self.assertIsNotNone(desc_match, f"Missing meta description in {route}")
                desc = desc_match.group(1).strip()
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

    def test_07_sitemap_xml_contains_all_routes(self):
        """Verify /sitemap.xml dynamically serves valid XML containing all public routes."""
        res = self.client.get("/sitemap.xml")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/xml", res.headers.get("content-type", ""))
        xml = res.text
        self.assertIn("<urlset", xml)
        self.assertIn("https://curiosityhub.co.in/</loc>", xml)
        for route in self.new_routes:
            self.assertIn(f"https://curiosityhub.co.in{route}</loc>", xml, f"Missing {route} in sitemap.xml")

    def test_08_robots_txt_allows_new_routes(self):
        """Verify /robots.txt includes Allow directives for all public marketing paths."""
        res = self.client.get("/robots.txt")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("Allow: /cloud-face-recognition-attendance", content)
        self.assertIn("Allow: /tablet-mobile-attendance-kiosk", content)
        self.assertIn("Allow: /zero-hardware-time-tracking", content)
        self.assertIn("Allow: /leave-management-software", content)
        self.assertIn("Allow: /automated-payroll-software", content)
        self.assertIn("Allow: /saas-vs-hardware-attendance", content)
        self.assertIn("Allow: /tools/", content)
        self.assertIn("Allow: /resources/", content)
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


if __name__ == "__main__":
    unittest.main()
