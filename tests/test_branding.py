"""Tests for brand identity, logo, splash, visual refresh, and CSS branding."""
import os
import re
import struct

import pytest


LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "app", "static", "img", "branding",
    "logo-agricola-vita-santa-fe.png",
)

PLACEHOLDER_MAX_SIZE = 5000


def _read_png_dimensions(path):
    with open(path, "rb") as f:
        header = f.read(24)
    if header[:4] != b"\x89PNG":
        return None, None
    if b"IHDR" not in header:
        return None, None
    ihdr_start = header.index(b"IHDR") + 4
    w, h = struct.unpack(">II", header[ihdr_start : ihdr_start + 8])
    return w, h


class TestLogoFile:
    def test_logo_file_exists(self):
        assert os.path.isfile(LOGO_PATH), f"Logo not found: {LOGO_PATH}"

    def test_logo_is_valid_png(self):
        with open(LOGO_PATH, "rb") as f:
            header = f.read(8)
        assert header[:4] == b"\x89PNG", "Logo is not a valid PNG file"

    def test_logo_file_size(self):
        size = os.path.getsize(LOGO_PATH)
        assert size > 1000, f"Logo file too small ({size} bytes) - likely placeholder"
        assert size < 5000000, f"Logo file too large ({size} bytes)"

    def test_logo_dimensions_are_real(self):
        w, h = _read_png_dimensions(LOGO_PATH)
        assert w is not None, "Could not read PNG dimensions"
        assert h is not None, "Could not read PNG dimensions"
        assert w > 400, f"Logo width {w}px too small for real logo"
        assert h > 400, f"Logo height {h}px too small for real logo"

    def test_logo_not_placeholder_400x120(self):
        w, h = _read_png_dimensions(LOGO_PATH)
        assert (w, h) != (400, 120), "Logo is still the 400x120 placeholder"

    def test_logo_not_placeholder_tiny(self):
        size = os.path.getsize(LOGO_PATH)
        assert size > PLACEHOLDER_MAX_SIZE, (
            f"Logo file is {size} bytes, likely still a placeholder"
        )

    def test_logo_no_external_url(self):
        with open(LOGO_PATH, "rb") as f:
            content = f.read()
        assert b"http://" not in content
        assert b"https://" not in content


class TestBrandCssExists:
    def test_brand_css_file_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        assert os.path.isfile(path)

    def test_brand_css_has_brand_variables(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert "--brand-green:" in css
        assert "--brand-green-dark:" in css
        assert "--brand-lime:" in css
        assert "--brand-cream:" in css
        assert "--brand-soft-green:" in css
        assert "--brand-white:" in css
        assert "--brand-text:" in css
        assert "--brand-border:" in css

    def test_brand_css_overrides_clr_variables(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert "--clr-primary: #147a38" in css
        assert "--clr-primary-hover: #0d5f2b" in css
        assert "--clr-text: #183321" in css
        assert "--clr-border: #b7d8bd" in css

    def test_brand_css_has_reusable_classes(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert ".brand-logo" in css
        assert ".brand-logo--compact" in css
        assert ".brand-header" in css
        assert ".app-splash" in css
        assert ".app-splash__logo" in css
        assert ".app-splash--hidden" in css

    def test_brand_css_logo_size_desktop(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert "height: 80px" in css
        assert "height: 64px" in css

    def test_brand_css_splash_size(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert "width: 300px" in css

    def test_brand_css_has_institutional_headers(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "css", "brand.css",
        )
        with open(path, encoding="utf-8") as f:
            css = f.read()
        assert "brand-green-dark" in css


class TestSplashJsExists:
    def test_splash_js_file_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "js", "splash.js",
        )
        assert os.path.isfile(path)

    def test_splash_js_uses_session_storage(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "js", "splash.js",
        )
        with open(path, encoding="utf-8") as f:
            js = f.read()
        assert "sessionStorage" in js

    def test_splash_js_respects_reduced_motion(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "js", "splash.js",
        )
        with open(path, encoding="utf-8") as f:
            js = f.read()
        assert "prefers-reduced-motion" in js

    def test_splash_js_no_external_references(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "static", "js", "splash.js",
        )
        with open(path, encoding="utf-8") as f:
            js = f.read()
        assert "http://" not in js
        assert "https://" not in js


class TestReceptionPageBranding:
    def test_reception_loads_brand_css(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_reception_brand_css_after_page_css(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        brand_pos = html.find("brand.css")
        reception_pos = html.find("reception.css")
        assert brand_pos > reception_pos, "brand.css must load after reception.css"

    def test_reception_has_splash_div(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_reception_has_splash_js(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "splash.js" in html

    def test_reception_has_real_logo(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo--header" in html

    def test_reception_has_institutional_header(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "reception-header" in html
        assert "reception-header__logo" in html
        assert "reception-header__content" in html

    def test_reception_has_accessible_alt(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "Logo de Agr" in html and "cola Vita Santa Fe" in html

    def test_reception_has_single_logo(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        count = html.count("logo-agricola-vita-santa-fe.png")
        assert count == 2, f"Expected 2 logo refs (splash + header), got {count}"

    def test_reception_no_compact_logo(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "brand-logo--compact" not in html

    def test_reception_has_brand_name(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "Agr" in html and "cola Vita Santa Fe" in html


class TestAdminPageBranding:
    def test_admin_loads_brand_css(self, admin_client):
        resp = admin_client.get("/admin")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_admin_brand_css_after_page_css(self, admin_client):
        resp = admin_client.get("/admin")
        html = resp.data.decode()
        brand_pos = html.find("brand.css")
        admin_pos = html.find("admin.css")
        assert brand_pos > admin_pos, "brand.css must load after admin.css"

    def test_admin_has_splash_div(self, admin_client):
        resp = admin_client.get("/admin")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_admin_has_real_logo(self, admin_client):
        resp = admin_client.get("/admin")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestProductsPageBranding:
    def test_products_loads_brand_css(self, admin_client):
        resp = admin_client.get("/admin/products")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_products_has_splash_div(self, admin_client):
        resp = admin_client.get("/admin/products")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_products_has_real_logo(self, admin_client):
        resp = admin_client.get("/admin/products")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestHistoryPageBranding:
    def test_history_loads_brand_css(self, admin_client):
        resp = admin_client.get("/history")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_history_brand_css_after_page_css(self, admin_client):
        resp = admin_client.get("/history")
        html = resp.data.decode()
        brand_pos = html.find("brand.css")
        history_pos = html.find("history.css")
        assert brand_pos > history_pos, "brand.css must load after history.css"

    def test_history_has_splash_div(self, admin_client):
        resp = admin_client.get("/history")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_history_has_real_logo(self, admin_client):
        resp = admin_client.get("/history")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestReportsPageBranding:
    def test_reports_loads_brand_css(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_reports_brand_css_after_page_css(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        brand_pos = html.find("brand.css")
        reports_pos = html.find("reports.css")
        assert brand_pos > reports_pos, "brand.css must load after reports.css"

    def test_reports_has_splash_div(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_reports_has_real_logo(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestTicketsPageBranding:
    def test_tickets_loads_brand_css(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_tickets_brand_css_after_page_css(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        brand_pos = html.find("brand.css")
        tickets_pos = html.find("tickets.css")
        assert brand_pos > tickets_pos, "brand.css must load after tickets.css"

    def test_tickets_has_splash_div(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_tickets_has_real_logo(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestLoginPageBranding:
    def test_login_loads_brand_css(self, client):
        resp = client.get("/admin/login")
        html = resp.data.decode()
        assert "brand.css" in html

    def test_login_has_splash_div(self, client):
        resp = client.get("/admin/login")
        html = resp.data.decode()
        assert 'id="app-splash"' in html

    def test_login_has_real_logo(self, client):
        resp = client.get("/admin/login")
        html = resp.data.decode()
        assert "logo-agricola-vita-santa-fe.png" in html
        assert "brand-logo" in html


class TestNoExternalImages:
    def _check_page(self, html, page_name):
        img_tags = re.findall(r"<img[^>]+>", html, re.IGNORECASE)
        for tag in img_tags:
            assert "http://" not in tag, f"External image on {page_name}: {tag}"
            assert "https://" not in tag, f"External image on {page_name}: {tag}"

    def test_reception_no_external_images(self, admin_client):
        html = admin_client.get("/").data.decode()
        self._check_page(html, "reception")

    def test_admin_no_external_images(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        self._check_page(html, "admin")

    def test_products_no_external_images(self, admin_client):
        html = admin_client.get("/admin/products").data.decode()
        self._check_page(html, "products")

    def test_history_no_external_images(self, admin_client):
        html = admin_client.get("/history").data.decode()
        self._check_page(html, "history")

    def test_reports_no_external_images(self, admin_client):
        html = admin_client.get("/reports").data.decode()
        self._check_page(html, "reports")

    def test_tickets_no_external_images(self, admin_client):
        html = admin_client.get("/tickets").data.decode()
        self._check_page(html, "tickets")

    def test_login_no_external_images(self, client):
        html = client.get("/admin/login").data.decode()
        self._check_page(html, "login")


class TestNoSensitiveData:
    def test_reception_no_secrets(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert ".env" not in html.lower()

    def test_admin_no_secrets(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert ".env" not in html.lower()


class TestNoBrokenRoutes:
    def test_logo_serves_200(self, admin_client):
        resp = admin_client.get(
            "/static/img/branding/logo-agricola-vita-santa-fe.png"
        )
        assert resp.status_code == 200

    def test_brand_css_serves_200(self, admin_client):
        resp = admin_client.get("/static/css/brand.css")
        assert resp.status_code == 200

    def test_splash_js_serves_200(self, admin_client):
        resp = admin_client.get("/static/js/splash.js")
        assert resp.status_code == 200

    def test_logo_content_is_png(self, admin_client):
        resp = admin_client.get(
            "/static/img/branding/logo-agricola-vita-santa-fe.png"
        )
        assert resp.data[:4] == b"\x89PNG"


class TestFunctionalityPreserved:
    def test_reception_still_has_barcode_input(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert 'id="barcode"' in html

    def test_reception_still_has_product_selector(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "product-selector" in html

    def test_reception_still_has_scale_section(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "scale-section" in html

    def test_reception_still_has_recent_movements(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "recent-movements" in html

    def test_reception_still_loads_reception_js(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "reception.js" in html

    def test_reception_still_loads_scale_js(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "scale.js" in html

    def test_admin_still_has_slot_section(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert "slots-section" in html

    def test_admin_still_loads_admin_js(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert "admin.js" in html

    def test_products_still_has_product_form(self, admin_client):
        html = admin_client.get("/admin/products").data.decode()
        assert "product-form" in html

    def test_history_still_has_date_input(self, admin_client):
        html = admin_client.get("/history").data.decode()
        assert 'id="date-input"' in html

    def test_reports_still_has_date_range(self, admin_client):
        html = admin_client.get("/reports").data.decode()
        assert "start-date" in html

    def test_tickets_still_has_ticket_list(self, admin_client):
        html = admin_client.get("/tickets").data.decode()
        assert "ticket-list" in html

    def test_login_still_has_password_field(self, client):
        html = client.get("/admin/login").data.decode()
        assert 'type="password"' in html

    def test_login_still_has_submit_button(self, client):
        html = client.get("/admin/login").data.decode()
        assert "login-submit" in html
