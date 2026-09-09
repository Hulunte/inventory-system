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
            <span class="product-button__rate">$${escapeHtml(product.rate_per_kg)}/kg</span>
        </button>`).join("")
        : '<div class="status-message status-message--error">No hay productos activos.</div>';
    return true;
}

function renderSackStatistics(product) {
    const stats = product?.sack_statistics || {};
    const unavailable = "Promedio no disponible";
    sacksStatistics.innerHTML = `<strong>Resumen por arpillas</strong>
        <span>Kg promedio por arpilla: ${escapeHtml(stats.average_kg_per_sack || product?.average_sack_weight_kg || unavailable)}</span>
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
    if (!data.has_assignment || !data.person_name || data.person_name === "Sin nombre") {
        return showSacksMessage("Este cupo no tiene una persona asignada.", true);
    }
    validatedSacksBarcode = code;
    sacksWorker.textContent = `${data.slot_label} — ${data.person_name}`;
    sacksProductButtons.querySelector("button")?.focus();
});

sacksProductButtons.addEventListener("click", async event => {
    const button = event.target.closest(".sacks-product-button[data-product-id]");
    if (!button) return;
    selectedSacksProductId = Number(button.dataset.productId);
    sacksProductButtons.querySelectorAll(".sacks-product-button").forEach(item => {
        item.setAttribute("aria-checked", String(item === button));
    });
    renderSackStatistics(allProducts.find(product => product.id === selectedSacksProductId));
});

sacksForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (sacksBusy) return;
    const count = Number(sacksCount.value);
    if (!validatedSacksBarcode) return showSacksMessage("Valide primero el trabajador.", true);
    if (!Number.isInteger(count) || count <= 0) return showSacksMessage("La cantidad de arpillas debe ser un entero positivo.", true);
    if (!selectedSacksProductId) return showSacksMessage("Seleccione un producto.", true);
    sacksBusy = true;
    sacksSubmit.disabled = true;
    try {
        const response = await fetch("/api/harvest/sack-entries", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": sacksCsrf },
            body: JSON.stringify({ barcode: validatedSacksBarcode, product_id: selectedSacksProductId, sack_count: count }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "No fue posible registrar el movimiento.");
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
});
