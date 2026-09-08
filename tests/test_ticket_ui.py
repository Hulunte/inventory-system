"""Tests for tickets UI page and JavaScript."""
import pytest


class TestTicketsPageAccess:
    def test_redirects_without_admin(self, client):
        resp = client.get("/tickets")
        assert resp.status_code == 302

    def test_renders_for_admin(self, admin_client):
        resp = admin_client.get("/tickets")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Tickets diarios" in html


class TestTicketsPageContent:
    def test_date_input(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="date-input"' in html
        assert 'type="date"' in html

    def test_search_input(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="search-input"' in html

    def test_query_button(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="query-btn"' in html
        assert "Consultar" in html

    def test_ticket_list_section(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="ticket-list-section"' in html
        assert 'id="ticket-list"' in html

    def test_preview_section(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="preview-section"' in html
        assert 'id="preview-content"' in html

    def test_printer_section(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="printer-section"' in html

    def test_printer_select(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="printer-select"' in html

    def test_refresh_printers_button(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="refresh-printers-btn"' in html
        assert "Actualizar impresoras" in html

    def test_test_print_button(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="test-print-btn"' in html
        assert "Imprimir prueba" in html

    def test_print_all_auto_button(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="print-all-auto-btn"' in html
        assert "automatico" in html.lower()

    def test_print_all_confirm_button(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'id="print-all-confirm-btn"' in html
        assert "confirmacion" in html.lower()

    def test_csrf_meta_tag(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'name="csrf-token"' in html

    def test_operational_today_config(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert "TICKETS_CONFIG" in html
        assert "operationalToday" in html


class TestTicketsNav:
    def test_nav_includes_tickets(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'href="/tickets"' in html
        assert "Tickets" in html

    def test_nav_includes_admin(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'href="/admin"' in html

    def test_nav_includes_reception(self, admin_client):
        resp = admin_client.get("/tickets")
        html = resp.data.decode()
        assert 'href="/"' in html


class TestNavigationAllPages:
    def test_reception_has_tickets_link(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'href="/tickets"' in html

    def test_admin_has_tickets_link(self, admin_client):
        resp = admin_client.get("/admin")
        html = resp.data.decode()
        assert 'href="/tickets"' in html

    def test_history_has_tickets_link(self, admin_client):
        resp = admin_client.get("/history")
        html = resp.data.decode()
        assert 'href="/tickets"' in html

    def test_reports_has_tickets_link(self, admin_client):
        resp = admin_client.get("/reports")
        html = resp.data.decode()
        assert 'href="/tickets"' in html

    def test_products_has_tickets_link(self, admin_client):
        resp = admin_client.get("/admin/products")
        html = resp.data.decode()
        assert 'href="/tickets"' in html


class TestTicketsJs:
    def test_js_file_loads(self, client):
        resp = client.get("/static/js/tickets.js")
        assert resp.status_code == 200

    def test_js_references_date_input(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "date-input" in js
        assert "dateInput" in js

    def test_js_references_search_input(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "search-input" in js

    def test_js_references_ticket_list(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "ticket-list" in js

    def test_js_references_printer_select(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "printer-select" in js

    def test_js_references_preview(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "preview-section" in js
        assert "preview-content" in js

    def test_js_uses_fetch(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "fetch(" in js

    def test_js_uses_csrf_token(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "X-CSRF-Token" in js
        assert "csrf-token" in js

    def test_js_uses_textcontent_for_messages(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "textContent" in js

    def test_js_escape_html_function(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "escapeHtml" in js

    def test_js_print_all_auto_mode(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "printAllAutomatic" in js or "print-all-auto" in js

    def test_js_print_all_confirm_mode(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "printAllWithConfirmation" in js or "print-all-confirm" in js

    def test_js_print_selected_mode(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "print-selected" in js

    def test_js_localstorage_namespace(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "inventory.ticketPrinterName" in js

    def test_js_sequential_not_parallel(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "Promise.all" not in js
        assert "for" in js

    def test_js_progress_reporting(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "progress-text" in js
        assert "progress-fill" in js

    def test_js_confirm_dialog(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "confirm-dialog" in js
        assert "confirm-print-btn" in js
        assert "confirm-skip-btn" in js
        assert "confirm-stop-btn" in js

    def test_js_error_actions(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "error-retry-btn" in js
        assert "error-skip-btn" in js
        assert "error-stop-btn" in js

    def test_js_no_window_print(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "window.print()" not in js

    def test_js_no_webusb(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "webusb" not in js.lower()
        assert "WebUSB" not in js

    def test_js_no_system_commands(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "exec(" not in js
        assert "subprocess" not in js
        assert "powershell" not in js.lower()

    def test_js_printer_message_uses_textcontent(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "printer-message" in js
        assert "showMessage" in js

    def test_js_input_blocking_function(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "setInputsDisabled" in js
        assert "dateInput.disabled" in js
        assert "searchInput.disabled" in js
        assert "printerSelect.disabled" in js

    def test_js_stable_ticket_list_copy(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "stableTickets" in js
        assert "[...tickets]" in js

    def test_js_no_chinese_text(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "再次" not in js
        assert "Error al reintentar" in js

    def test_js_uses_data_tickets(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.tickets" in js

    def test_js_uses_total_workers(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.total_workers" in js

    def test_js_uses_total_day_weight(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.total_day_weight_kg" in js

    def test_js_uses_total_day_amount(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.total_day_amount_mxn" in js

    def test_js_no_old_field_movements(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.movements" not in js

    def test_js_no_old_field_workers(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.workers" not in js

    def test_js_no_old_field_entries(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "data.entries" not in js

    def test_js_uses_worker_name(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "worker_name" in js

    def test_js_uses_worker_barcode(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "worker_barcode" in js

    def test_js_uses_slot_label(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "slot_label" in js

    def test_js_uses_product_lines_not_products(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "product_lines" in js

    def test_js_handles_null_amount_mxn(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "amount_mxn" in js
        assert "N/D" in js

    def test_js_change_event_on_date_input(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert 'dateInput.addEventListener("change"' in js or "dateInput.addEventListener('change'" in js

    def test_js_incomplete_tag(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "PAGO INCOMPLETO" in js

    def test_js_diagnostic_flag(self, client):
        resp = client.get("/static/js/tickets.js")
        js = resp.data.decode()
        assert "__TICKETS_DEBUG__" in js


class TestTicketsCss:
    def test_css_file_loads(self, client):
        resp = client.get("/static/css/tickets.css")
        assert resp.status_code == 200

    def test_css_has_tickets_wrapper(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "tickets-wrapper" in css

    def test_css_has_tickets_header(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "tickets-header" in css

    def test_css_has_preview_styles(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "preview-box" in css
        assert "preview-table" in css

    def test_css_has_printer_styles(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "printer-controls" in css
        assert "printer-message" in css

    def test_css_has_print_modes(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "print-modes" in css
        assert "print-mode" in css

    def test_css_has_confirm_dialog(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "confirm-dialog" in css

    def test_css_has_progress_bar(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "print-progress" in css
        assert "print-progress__fill" in css

    def test_css_has_incomplete_tag(self, client):
        resp = client.get("/static/css/tickets.css")
        css = resp.data.decode()
        assert "incomplete-tag" in css
