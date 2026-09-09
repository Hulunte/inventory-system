const activeDate = document.getElementById("active-date");
const activeEntriesContent = document.getElementById("active-entries-content");
const voidSearch = document.getElementById("void-search");
const voidsContent = document.getElementById("voids-content");
const voidModal = document.getElementById("void-modal");
const voidModalText = document.getElementById("void-modal-text");
const voidReasonInput = document.getElementById("void-reason-input");
const voidActionMessage = document.getElementById("void-action-message");
const voidCancelBtn = document.getElementById("void-cancel-btn");
const voidConfirmBtn = document.getElementById("void-confirm-btn");
let voidSearchTimer = null;
let currentVoidEntryId = null;

function escapeHtml(value) {
    const node = document.createElement("div");
    node.textContent = value == null ? "" : String(value);
    return node.innerHTML;
}

function csrfHeaders() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return {"Content-Type": "application/json", "X-CSRF-Token": meta ? meta.content : ""};
}

async function readJson(response) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
        window.location.href = "/admin/login";
        throw new Error("Se requiere una sesión de administrador.");
    }
    if (!response.ok) throw new Error(data.error || "No fue posible completar la operación.");
    return data;
}

function renderActiveEntries(entries) {
    const activeEntries = entries.filter(entry => !entry.voided);
    if (!activeEntries.length) {
        activeEntriesContent.innerHTML = '<p class="empty-state">No hay movimientos activos para esta fecha.</p>';
        return;
    }
    activeEntriesContent.innerHTML = `
        <div class="table-scroll"><table class="detail-table">
            <thead><tr><th>Trabajador</th><th>Código</th><th>Cupo</th><th>Producto</th><th>Tipo</th>
                <th>Fecha y hora</th><th class="num">Peso</th><th class="num">Importe</th><th>Acción</th></tr></thead>
            <tbody>${activeEntries.map(entry => `<tr>
                <td>${escapeHtml(entry.worker.name || "—")}</td>
                <td class="mono">${escapeHtml(entry.worker.barcode || "—")}</td>
                <td>${escapeHtml(entry.worker.slot_label || "—")}</td>
                <td>${escapeHtml(entry.product_name || "—")}</td>
                <td>${escapeHtml(entry.registration_type_label)}${entry.sack_count ? ` (${entry.sack_count} arpillas, ${escapeHtml(entry.average_sack_weight_kg)} kg/arpilla)` : ""}</td>
                <td>${escapeHtml(activeDate.value)} ${escapeHtml(entry.created_at_local)}</td>
                <td class="num">${escapeHtml(entry.weight_kg)} kg</td>
                <td class="num">${entry.amount_mxn == null ? "—" : `$${escapeHtml(entry.amount_mxn)}`}</td>
                <td><button class="btn btn--danger btn--void" type="button"
                    data-entry-id="${entry.id}" data-worker="${escapeHtml(entry.worker.name || "—")}"
                    data-weight="${escapeHtml(entry.weight_kg)}">Anular</button></td>
            </tr>`).join("")}</tbody>
        </table></div>`;
}

async function loadActiveEntries() {
    activeEntriesContent.innerHTML = '<p class="empty-state">Cargando...</p>';
    try {
        const response = await fetch(`/api/admin/harvest-entries?date=${encodeURIComponent(activeDate.value)}`);
        renderActiveEntries((await readJson(response)).entries || []);
    } catch (error) {
        activeEntriesContent.innerHTML = `<p class="empty-state empty-state--error">${escapeHtml(error.message)}</p>`;
    }
}

async function loadVoids() {
    const query = voidSearch.value.trim();
    const url = query ? `/api/voids?q=${encodeURIComponent(query)}` : "/api/voids";
    voidsContent.innerHTML = '<p class="empty-state">Cargando...</p>';
    try {
        const data = await readJson(await fetch(url));
        if (!data.entries.length) {
            voidsContent.innerHTML = '<p class="empty-state">No hay movimientos anulados.</p>';
            return;
        }
        voidsContent.innerHTML = `
            <div class="table-scroll"><table class="detail-table">
                <thead><tr><th>Trabajador</th><th>Código</th><th>Cupo</th><th>Producto</th><th>Tipo</th>
                    <th>Fecha</th><th>Hora</th><th class="num">Peso</th><th class="num">Importe</th>
                    <th>Motivo</th><th>Fecha de anulación</th></tr></thead>
                <tbody>${data.entries.map(entry => `<tr>
                    <td>${escapeHtml(entry.worker_name || "—")}</td>
                    <td class="mono">${escapeHtml(entry.worker_barcode || "—")}</td>
                    <td>${escapeHtml(entry.slot_label || "—")}</td>
                    <td>${escapeHtml(entry.product_name || "—")}</td>
                    <td>${escapeHtml(entry.registration_type_label)}${entry.sack_count ? ` (${entry.sack_count} arpillas, ${escapeHtml(entry.average_sack_weight_kg)} kg/arpilla)` : ""}</td>
                    <td>${escapeHtml(entry.date)}</td><td>${escapeHtml(entry.time)}</td>
                    <td class="num">${escapeHtml(entry.weight_kg)} kg</td>
                    <td class="num">${entry.amount_mxn == null ? "—" : `$${escapeHtml(entry.amount_mxn)}`}</td>
                    <td>${escapeHtml(entry.void_reason)}</td><td>${escapeHtml(entry.voided_at)}</td>
                </tr>`).join("")}</tbody>
            </table></div>`;
    } catch (error) {
        voidsContent.innerHTML = `<p class="empty-state empty-state--error">${escapeHtml(error.message)}</p>`;
    }
}

function closeVoidModal() {
    voidModal.hidden = true;
    currentVoidEntryId = null;
    voidReasonInput.value = "";
    voidActionMessage.hidden = true;
}

activeEntriesContent.addEventListener("click", event => {
    const button = event.target.closest(".btn--void[data-entry-id]");
    if (!button) return;
    currentVoidEntryId = button.dataset.entryId;
    voidModalText.textContent = `¿Confirma anular el movimiento #${currentVoidEntryId} de ${button.dataset.worker} (${button.dataset.weight} kg)?`;
    voidReasonInput.value = "";
    voidActionMessage.hidden = true;
    voidModal.hidden = false;
    voidReasonInput.focus();
});

voidCancelBtn.addEventListener("click", closeVoidModal);
voidModal.addEventListener("click", event => {
    if (event.target === voidModal) closeVoidModal();
});

voidConfirmBtn.addEventListener("click", async () => {
    const reason = voidReasonInput.value.trim();
    if (!reason) {
        voidActionMessage.textContent = "El motivo de anulación es obligatorio.";
        voidActionMessage.className = "form__message form__message--error";
        voidActionMessage.hidden = false;
        return;
    }
    voidConfirmBtn.disabled = true;
    voidConfirmBtn.textContent = "Anulando...";
    try {
        await readJson(await fetch(`/api/admin/harvest-entries/${currentVoidEntryId}/void`, {
            method: "PATCH", headers: csrfHeaders(), body: JSON.stringify({reason}),
        }));
        closeVoidModal();
        await Promise.all([loadActiveEntries(), loadVoids()]);
    } catch (error) {
        voidActionMessage.textContent = error.message;
        voidActionMessage.className = "form__message form__message--error";
        voidActionMessage.hidden = false;
    } finally {
        voidConfirmBtn.disabled = false;
        voidConfirmBtn.textContent = "Confirmar anulación";
    }
});

activeDate.addEventListener("change", loadActiveEntries);
voidSearch.addEventListener("input", () => {
    window.clearTimeout(voidSearchTimer);
    voidSearchTimer = window.setTimeout(loadVoids, 250);
});

loadActiveEntries();
loadVoids();
