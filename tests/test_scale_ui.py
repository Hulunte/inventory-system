"""Tests for scale UI elements in reception page and scale.js."""
import pytest


class TestReceptionPageScaleSection:
    def test_scale_section_exists(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-section"' in html

    def test_scale_port_select(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-port-select"' in html

    def test_scale_connect_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-connect-btn"' in html
        assert "Conectar" in html

    def test_scale_disconnect_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-disconnect-btn"' in html
        assert "Desconectar" in html

    def test_scale_refresh_ports_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-refresh-ports"' in html
        assert "Actualizar" in html

    def test_scale_weight_value(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-weight-value"' in html

    def test_scale_stability_indicator(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-stability-indicator"' in html

    def test_scale_reading_error(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-reading-error"' in html

    def test_scale_use_weight_button(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-use-weight-btn"' in html
        assert "Usar peso" in html

    def test_scale_connection_status(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert 'id="scale-connection-status"' in html

    def test_scale_autofill_is_visible_and_disabled_initially(self, admin_client):
        html = admin_client.get("/").data.decode()
        assert "Autorrellenar peso de b" in html
        assert 'id="scale-autofill-weight"' in html
        assert 'id="scale-autofill-weight" class="scale-select" disabled' in html
        assert '<option value="on" selected>Activado</option>' in html


class TestScaleJs:
    def test_js_file_loads(self, client):
        resp = client.get("/static/js/scale.js")
        assert resp.status_code == 200

    def test_js_uses_fetch(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "fetch(" in js

    def test_js_uses_csrf_token(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "X-CSRF-Token" in js
        assert "csrf-token" in js

    def test_js_uses_textcontent(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "textContent" in js

    def test_js_no_webusb(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "webusb" not in js.lower()
        assert "WebUSB" not in js

    def test_js_no_web_serial(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "Web Serial" not in js
        assert "navigator.serial" not in js

    def test_js_no_window_print(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "window.print()" not in js

    def test_js_no_subprocess(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "subprocess" not in js
        assert "powershell" not in js.lower()
        assert "exec(" not in js

    def test_js_references_scale_api(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "/api/scale/ports" in js
        assert "/api/scale/status" in js
        assert "/api/scale/connect" in js
        assert "/api/scale/disconnect" in js

    def test_js_handles_visibility(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "visibilitychange" in js

    def test_js_has_polling(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "setInterval" in js
        assert "clearInterval" in js

    def test_js_weight_input_target(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "weight_kg" in js

    def test_js_no_numeric_float_conversion(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "parseFloat" not in js

    def test_autofill_targets_only_weight_after_valid_worker(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        reception_js = client.get("/static/js/reception.js").data.decode()
        assert 'document.getElementById("weight_kg")' in js
        assert 'getElementById("barcode")' not in js
        assert 'window.addEventListener("inventory:worker-validated"' in js
        assert 'new CustomEvent("inventory:worker-validated")' in reception_js

    def test_autofill_requires_stable_fresh_reading(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        assert "lastStable" in js
        assert "MAX_AUTOFILL_AGE_MS" in js
        assert "Date.now() - lastReadingAt.getTime()" in js
        assert "!autofillEnabled" in js

    def test_realtime_updates_reuse_single_polling_loop(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        assert "if (pollInterval) return" in js
        assert js.count('window.addEventListener("inventory:worker-validated"') == 1
        assert "fillWeightIfEnabled();" in js

    def test_successful_registration_clears_weight_and_preserves_autofill(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        reception_js = client.get("/static/js/reception.js").data.decode()
        assert 'new CustomEvent("inventory:movement-registered")' in reception_js
        handler = js[js.index("function handleMovementRegistered()"):
                     js.index("function changeAutofillPreference()")]
        assert 'weightInput.value = ""' in handler
        assert 'autofillSelect.value = "off"' not in handler
        assert "resetAutofill();" in handler

    def test_autofill_preference_persists_for_next_worker_in_session(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        assert 'var AUTOFILL_STORAGE_KEY = "inventory.scaleAutofillWeight"' in js
        assert "sessionStorage.getItem(AUTOFILL_STORAGE_KEY)" in js
        assert "sessionStorage.setItem(AUTOFILL_STORAGE_KEY" in js
        assert 'autofillEnabled = autofillSelect.value === "on"' in js
        assert js.count('window.addEventListener("inventory:worker-validated"') == 1
        assert js.count('autofillSelect.addEventListener("change"') == 1

    def test_autofill_defaults_on_but_respects_manual_session_choice(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        assert "storedAutofillPreference === null" in js
        assert '? true' in js
        assert 'storedAutofillPreference === "on"' in js
        assert 'autofillSelect.value = autofillEnabled ? "on" : "off"' in js

    def test_invalid_worker_disables_control_without_changing_preference(self, client):
        js = client.get("/static/js/scale.js").data.decode()
        reset = js[js.index("function resetAutofill()"):
                   js.index("function readingIsFreshAndStable()")]
        assert "workerIsValid = false" in reset
        assert "autofillSelect.disabled = true" in reset
        assert "autofillEnabled = false" not in reset
        assert "sessionStorage.setItem" not in reset
        assert "autofillSelect.value" not in reset


class TestReceptionPageHasScaleScript:
    def test_scale_script_included(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "scale.js" in html

    def test_reception_script_still_included(self, admin_client):
        resp = admin_client.get("/")
        html = resp.data.decode()
        assert "reception.js" in html


class TestScaleJsMessages:
    def test_js_has_message_map(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "MESSAGES" in js

    def test_pyserial_unavailable_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "pyserial_unavailable" in js
        assert "PySerial no disponible" in js

    def test_no_serial_ports_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "no_serial_ports" in js
        assert "No hay puertos disponibles" in js

    def test_scale_not_connected_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "scale_not_connected" in js
        assert "no se ha conectado" in js.lower()

    def test_port_in_use_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "port_in_use" in js
        assert "otra aplicacion" in js.lower() or "utilizada" in js.lower()

    def test_connected_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "connected" in js
        assert "conectada" in js.lower()

    def test_serial_read_error_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "serial_read_error" in js
        assert "no se reconoce" in js.lower() or "formato" in js.lower()

    def test_invalid_configuration_message(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "invalid_configuration" in js

    def test_messageForCode_function(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "messageForCode" in js

    def test_load_ports_uses_code(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "data.code" in js or "code" in js

    def test_updateUiFromStatus_uses_code(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert "updateUiFromStatus" in js
        assert "status.code" in js or "code" in js

    def test_pyserial_message_is_only_used_for_503_or_unavailable_code(self, client):
        resp = client.get("/static/js/scale.js")
        js = resp.data.decode()
        assert 'result.status === 503' in js
        assert 'opt.textContent = MESSAGES.pyserial_unavailable' in js
