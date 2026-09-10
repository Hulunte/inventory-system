const openSacksMode = document.getElementById("open-sacks-mode");
const closeSacksMode = document.getElementById("close-sacks-mode");
const sacksMode = document.getElementById("sacks-mode");
const receptionMain = document.querySelector(".reception-main");
const sacksForm = document.getElementById("sacks-form");
const sacksBarcode = document.getElementById("sacks-barcode");
const sacksWorker = document.getElementById("sacks-worker");
const sacksProductButtons = document.getElementById("sacks-product-buttons");
const sacksCount = document.getElementById("sacks-count");
const sacksStatistics = document.getElementById("sacks-statistics");
const sacksSubmit = document.getElementById("sacks-submit");
const sacksMessage = document.getElementById("sacks-message");
let sacksCsrf = "";
let sacksBusy = false;
let validatedSacksBarcode = "";
let selectedSacksProductId = null;
const SACKS_PRODUCT_STORAGE_KEY = "inventory.sacksProductId";

function showSacksMessage(text, error = false) {
    sacksMessage.hidden = false;
    sacksMessage.textContent = text;
    sacksMessage.className = `status-message status-message--${error ? "error" : "success"}`;
}

async function initializeSacksMode() {
    const sessionResponse = await fetch("/api/admin/session");
    const sessionData = await sessionResponse.json();
    if (!sessionData.authenticated) {
        showSacksMessage("Se requiere sesión administrativa para registrar por arpillas.", true);
        return false;
    }
    sacksCsrf = sessionData.csrf_token || "";
    await window.receptionProductsReady;
    const products = allProducts;
    sacksProductButtons.innerHTML = products.length
        ? products.map(product => `<button type="button" class="product-button sacks-product-button"
            role="radio" aria-checked="false" data-product-id="${product.id}">
            <span class="product-button__name">${escapeHtml(product.name)}</span>
            <span class="product-button__rate">${product.rate_per_sack !== null ? `$${escapeHtml(product.rate_per_sack)}/arpilla` : "Precio por arpilla no configurado"}</span>
        </button>`).join("")
        : '<div class="status-message status-message--error">No hay productos activos.</div>';
    const storedProductId = Number(localStorage.getItem(SACKS_PRODUCT_STORAGE_KEY));
    const productToRestore = products.find(product => product.id === storedProductId);
    if (productToRestore) {
        selectSacksProduct(productToRestore.id, false);
    } else {
        selectedSacksProductId = null;
        renderSackStatistics(null);
    }
    return true;
}

function selectSacksProduct(productId, persist = true) {
    const product = allProducts.find(item => item.id === productId);
    if (!product) return false;
    selectedSacksProductId = productId;
    sacksProductButtons.querySelectorAll(".sacks-product-button").forEach(item => {
        item.setAttribute("aria-checked", String(Number(item.dataset.productId) === productId));
    });
    if (persist) localStorage.setItem(SACKS_PRODUCT_STORAGE_KEY, String(productId));
    renderSackStatistics(product);
    return true;
}

function renderSackStatistics(product) {
    const stats = product?.sack_statistics || {};
    const unavailable = "Promedio no disponible";
    sacksStatistics.innerHTML = `<strong>Resumen por arpillas</strong>
        <span>Kg promedio por arpilla configurado: ${escapeHtml(product?.average_sack_weight_kg || unavailable)}</span>
        <span>Kg promedio por movimiento: ${escapeHtml(stats.average_kg_per_movement || unavailable)}</span>
        <span>Total de arpillas: ${Number(stats.total_sacks || 0)}</span>
        <span>Total de movimientos: ${Number(stats.total_movements || 0)}</span>
        <span>Total de kg: ${escapeHtml(stats.total_kg || "0.000")}</span>
        <span>Importe calculado: $${escapeHtml(stats.total_amount_mxn || "0.00")}</span>
        ${stats.period ? `<span>Período: ${escapeHtml(stats.period)}</span>` : ""}`;
}

openSacksMode.addEventListener("click", async () => {
    receptionMain.hidden = true;
    sacksMode.hidden = false;
    await initializeSacksMode();
    sacksBarcode.focus();
});

closeSacksMode.addEventListener("click", () => {
    sacksMode.hidden = true;
    receptionMain.hidden = false;
    barcodeInput.focus({ preventScroll: true });
});

sacksBarcode.addEventListener("keydown", async event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    validatedSacksBarcode = "";
    const code = sacksBarcode.value.trim();
    if (!code) return showSacksMessage("Ingrese un código válido.", true);
    const response = await fetch(`/api/workers/${encodeURIComponent(code)}`);
    const data = await response.json();
    if (!response.ok) return showSacksMessage(data.error || "Trabajador no encontrado.", true);
    validatedSacksBarcode = code;
    sacksWorker.textContent = `${data.slot_label} — ${data.person_name || "Sin nombre"}`;
    sacksCount.focus({ preventScroll: true });
});

sacksProductButtons.addEventListener("click", async event => {
    const button = event.target.closest(".sacks-product-button[data-product-id]");
    if (!button) return;
    selectSacksProduct(Number(button.dataset.productId));
});

async function submitSackEntry() {
    if (sacksBusy) return;
    const count = Number(sacksCount.value);
    const selectedProduct = allProducts.find(product => product.id === selectedSacksProductId);
    if (!validatedSacksBarcode) return showSacksMessage("Valide primero el trabajador.", true);
    if (!Number.isInteger(count) || count <= 0) return showSacksMessage("La cantidad de arpillas debe ser un entero positivo.", true);
    if (!selectedSacksProductId) return showSacksMessage("Seleccione un producto.", true);
    if (!selectedProduct?.average_sack_weight_kg) {
        return showSacksMessage(
            "Falta configurar el promedio kg/arpilla de este producto en Productos.",
            true,
        );
    }
    if (selectedProduct?.rate_per_sack === null || selectedProduct?.rate_per_sack === undefined) {
        return showSacksMessage("Falta configurar el precio por arpilla de este producto en Productos.", true);
    }
    if (!sacksCsrf) {
        return showSacksMessage("La sesión administrativa no tiene un token CSRF válido.", true);
    }
    sacksBusy = true;
    sacksSubmit.disabled = true;
    try {
        const response = await fetch("/api/harvest/sack-entries", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": sacksCsrf },
            body: JSON.stringify({ barcode: validatedSacksBarcode, product_id: selectedSacksProductId, sack_count: count }),
        });
        const contentType = response.headers.get("content-type") || "";
        const result = contentType.includes("application/json")
            ? await response.json()
            : { error: await response.text() };
        if (!response.ok) throw new Error(result.error || `No fue posible registrar el movimiento (HTTP ${response.status}).`);
        showSacksMessage(`Registrado: ${result.sack_count} arpillas, ${result.weight_kg} kg estimados, promedio ${result.average_sack_weight_kg} kg/arpilla, importe $${result.amount_mxn}.`);
        sacksCount.value = "";
        await loadRecentMovements();
        sacksBarcode.focus();
        sacksBarcode.select();
    } catch (error) {
        showSacksMessage(error.message, true);
    } finally {
        sacksBusy = false;
        sacksSubmit.disabled = false;
    }
}

sacksForm.addEventListener("submit", event => {
    event.preventDefault();
    submitSackEntry();
});

sacksCount.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    sacksForm.requestSubmit();
});

sacksSubmit.addEventListener("click", () => {
    sacksForm.requestSubmit();
});
