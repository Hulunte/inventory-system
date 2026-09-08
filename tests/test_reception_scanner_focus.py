from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "app" / "static" / "js" / "reception.js"
TEMPLATE_PATH = ROOT / "app" / "templates" / "reception.html"


def _script():
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_valid_barcode_enter_runs_worker_flow():
    script = _script()
    assert 'barcodeInput.addEventListener("keydown"' in script
    assert 'event.key !== "Enter"' in script
    assert 'await showWorker(worker)' in script
    assert 'scannerDebug("scanner enter recibido")' in script
    assert 'scannerDebug("trabajador validado")' in script
    assert 'scannerDebug("scroll ejecutado")' in script
    assert 'get("scannerDebug") === "1"' in script


def test_successful_worker_flow_scrolls_real_weight_control():
    script = _script()
    assert 'document.getElementById("weight_kg")' in script
    assert 'behavior: "smooth"' in script
    assert "const elementRect = element.getBoundingClientRect()" in script
    assert "window.scrollY + elementRect.top" in script
    assert "scrollableParent.scrollTop +=" in script
    assert "scrollToWeightControl(weightInput)" in script
    assert 'id="weight-entry-section"' in script


def test_reception_template_versions_scanner_javascript():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "filename='js/reception.js', v='20260907-8'" in template


def test_successful_worker_flow_focuses_weight_control():
    script = _script()
    assert 'element.focus({ preventScroll: true })' in script


def test_selecting_required_product_continues_to_weight_control():
    script = _script()
    select_product = script.split("function selectProduct(productId)", 1)[1].split(
        "function restoreSelection", 1
    )[0]
    assert 'document.getElementById("weight_kg")' in select_product
    assert "scrollToWeightControl(weightInput)" in select_product


def test_identifies_real_scrollable_ancestor_before_window_fallback():
    script = _script()
    helper = script.split("function findScrollableAncestor(element)", 1)[1].split(
        "function debugScrollAncestors", 1
    )[0]
    assert "parent.scrollHeight > parent.clientHeight" in helper
    assert '["auto", "scroll"].includes(style.overflowY)' in helper
    assert "return parent" in helper


def test_scroll_runs_after_weight_is_rendered():
    script = _script()
    show_worker = script.split("async function showWorker(worker)", 1)[1].split(
        "// --- Recent Movements ---", 1
    )[0]
    render_position = show_worker.index('id="weight_kg"')
    lookup_position = show_worker.index('document.getElementById("weight_kg")')
    scroll_position = show_worker.index(
        "scrollToWeightControl(weightInput)", lookup_position
    )
    assert render_position < lookup_position < scroll_position
    helper = script.split("async function scrollToWeightControl(element)", 1)[1].split(
        'barcodeInput.addEventListener("keydown"', 1
    )[0]
    assert "if (!element || !element.isConnected)" in helper
    assert "requestAnimationFrame" in helper
    assert "window.setTimeout(() =>" in helper
    assert "}, 300)" in helper
    assert "element.isConnected" in helper


def test_invalid_barcode_returns_before_scroll():
    script = _script()
    handler = script.split('barcodeInput.addEventListener("keydown"', 1)[1].split(
        "async function showWorker", 1
    )[0]
    not_found = handler.split("response.status === 404", 1)[1].split(
        "if (!response.ok)", 1
    )[0]
    assert "return;" in not_found
    assert "focusNextHarvestControl" not in not_found
    assert "scrollIntoView" not in not_found


def test_unassigned_worker_returns_before_scroll():
    script = _script()
    handler = script.split('barcodeInput.addEventListener("keydown"', 1)[1].split(
        "async function showWorker", 1
    )[0]
    unassigned = handler.split("if (!worker.has_assignment)", 1)[1].split(
        "await showWorker(worker)", 1
    )[0]
    assert "return;" in unassigned
    assert "focusNextHarvestControl" not in unassigned
    assert "scrollIntoView" not in unassigned


def test_manual_capture_and_registration_behavior_remains_available():
    script = _script()
    assert "const barcode = barcodeInput.value.trim()" in script
    assert 'weightInput.addEventListener("keydown"' in script
    assert "registerButton.click()" in script
    assert 'registerButton.addEventListener("click"' in script
    assert 'fetch("/api/harvest/entries"' in script
