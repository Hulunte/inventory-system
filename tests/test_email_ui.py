import pytest


class TestEmailFormPresence:
    def test_email_input_exists_for_admin(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="email-input"' in html
        assert 'type="email"' in html

    def test_send_button_exists_for_admin(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="send-email-btn"' in html
        assert "Enviar por correo" in html

    def test_email_section_hidden_by_default(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="email-section"' in html
        assert 'hidden' in html.split('id="email-section"')[1].split('>')[0]

    def test_email_message_div_exists(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="email-message"' in html

    def test_csrf_meta_tag_present(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'name="csrf-token"' in html

    def test_email_not_shown_for_non_admin(self, client):
        resp = client.get("/reports")
        html = resp.data.decode()
        assert 'id="email-input"' not in html
        assert 'id="send-email-btn"' not in html


class TestExportButtonUnchanged:
    def test_export_button_still_present(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'id="export-btn"' in html
        assert "Exportar inventario" in html

    def test_export_button_not_shown_without_session(self, client):
        resp = client.get("/reports")
        html = resp.data.decode()
        assert 'id="export-btn"' not in html


class TestJsEmailFeatures:
    def test_send_email_handler_present(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "send-email-btn" in js
        assert "sendEmailBtn" in js

    def test_email_input_referenced(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "email-input" in js
        assert "emailInput" in js

    def test_fetch_POST_used(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert 'method: "POST"' in js

    def test_csrf_token_sent(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "X-CSRF-Token" in js

    def test_sending_state_management(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "disabled" in js
        assert "Enviando..." in js

    def test_success_message_shown(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "email-message" in js
        assert "success" in js

    def test_error_message_shown(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "error" in js

    def test_no_password_in_js(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "password" not in js.lower() or "app-password" not in js.lower()

    def test_escape_html_used(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "escapeHtml" in js

    def test_no_internal_details_exposed(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "stack" not in js
        assert "traceback" not in js

    def test_email_endpoint_url(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "/api/reports/harvest/export/email" in js


class TestNoCredentialsInHtml:
    def test_no_password_in_html(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert "app-password" not in html.lower()
        assert "smtp" not in html.lower()
        assert "gmail" not in html.lower()

    def test_no_password_in_css(self, client):
        resp = client.get("/static/css/reports.css")
        css = resp.data.decode()
        assert "password" not in css.lower()

    def test_no_credentials_in_js(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "smtp" not in js.lower()
        assert "gmail" not in js.lower()
        assert "app_password" not in js
        assert "APP_PASSWORD" not in js


class TestEmailMessageHandling:
    def test_email_section_shown_via_js(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "emailSection.hidden = false" in js

    def test_no_duplicate_escapeHtml(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        count = js.count("function escapeHtml")
        assert count == 1

    def test_email_message_uses_textcontent(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert "emailMessage.textContent" in js
        assert "emailMessage.innerHTML" not in js

    def test_email_input_not_cleared_on_error(self, client):
        resp = client.get("/static/js/reports.js")
        js = resp.data.decode()
        assert js.count("emailInput.value = \"\"") == 1
