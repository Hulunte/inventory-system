const logoutBtn = document.getElementById("logout-btn");
const slotSearchInput = document.getElementById("slot-search-input");
const slotList = document.getElementById("slot-list");
const cleanSlotsBtn = document.getElementById("clean-slots-btn");
const assignModal = document.getElementById("assign-modal");
const assignModalText = document.getElementById("assign-modal-text");
const assignForm = document.getElementById("assign-form");
const assignWorkerId = document.getElementById("assign-worker-id");
const assignPersonName = document.getElementById("assign-person-name");
const assignMessage = document.getElementById("assign-message");
const assignCancelBtn = document.getElementById("assign-cancel-btn");
const assignSaveBtn = document.getElementById("assign-save-btn");

const entryDateInput = document.getElementById("entry-date-input");
const entrySearchInput = document.getElementById("entry-search-input");
const entriesList = document.getElementById("entries-list");
const voidModal = document.getElementById("void-modal");
const voidModalText = document.getElementById("void-modal-text");
const voidReasonInput = document.getElementById("void-reason-input");
const voidCancelBtn = document.getElementById("void-cancel-btn");
const voidConfirmBtn = document.getElementById("void-confirm-btn");

const productForm = document.getElementById("product-form");
const productName = document.getElementById("product-name");
const productRate = document.getElementById("product-rate");
const productMessage = document.getElementById("product-message");
const productSubmit = document.getElementById("product-submit");
const productSearchInput = document.getElementById("product-search-input");
const productList = document.getElementById("product-list");
const editProductModal = document.getElementById("edit-product-modal");
const editProductForm = document.getElementById("edit-product-form");
const editProductId = document.getElementById("edit-product-id");
const editProductName = document.getElementById("edit-product-name");
const editProductRate = document.getElementById("edit-product-rate");
const editProductMessage = document.getElementById("edit-product-message");
const editProductCancelBtn = document.getElementById("edit-product-cancel-btn");
const editProductSaveBtn = document.getElementById("edit-product-save-btn");

let csrfToken = "";
let slotSearchTimeout = null;
let entrySearchTimeout = null;
let productSearchTimeout = null;
let currentVoidEntryId = null;
let productsById = new Map();

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : csrfToken;
}

async function initCsrfToken() {
    try {
        const response = await fetch("/api/admin/session");
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = "/admin/login";
            return;
        }
        csrfToken = data.csrf_token || "";
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) meta.setAttribute("content", csrfToken);
    } catch (e) {
        window.location.href = "/admin/login";
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `form__message form__message--${type}`;
    element.hidden = false;
}

function apiHeaders() {
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": getCsrfToken(),
    };
}

logoutBtn.addEventListener("click", async () => {
    try {
        await fetch("/api/admin/logout", {
            method: "POST",
            headers: apiHeaders(),
        });
    } catch (e) {
        // ignore
    }
    window.location.href = "/admin/login";
});


slotSearchInput.addEventListener("input", () => {
    clearTimeout(slotSearchTimeout);
    slotSearchTimeout = setTimeout(() => {
        loadWorkerSlots(slotSearchInput.value.trim());
    }, 250);
});


async function loadWorkerSlots(query) {
    slotList.innerHTML = `<p class="worker-list__empty">Cargando...</p>`;

    try {
        let url = "/api/admin/worker-slots";
        if (query) {
            url += `?q=${encodeURIComponent(query)}`;
        }

        const response = await fetch(url);

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Error al cargar cupos");
        }

        const slots = await response.json();

        if (slots.length === 0) {
            slotList.innerHTML = `<p class="worker-list__empty">No se encontraron cupos.</p>`;
            return;
        }

        slotList.innerHTML = slots.map(renderWorkerSlot).join("");

    } catch (error) {
        slotList.innerHTML = `<p class="worker-list__empty worker-list__empty--error">${error.message}</p>`;
    }
}


function renderWorkerSlot(slot) {
    const statusClass = slot.active ? "badge--active" : "badge--inactive";
    const statusText = slot.active ? "Activo" : "Inactivo";
    const actionLabel = slot.active ? "Desactivar" : "Reactivar";
    const actionClass = slot.active ? "btn--danger" : "btn--success";
    const actionEndpoint = slot.active ? "deactivate" : "activate";

    const displayName = slot.person_name ? escapeHtml(slot.person_name) : '<span class="text-muted">Sin asignar</span>';
    const assignLabel = slot.person_name ? "Cambiar" : "Asignar";

    return `
        <div class="worker-row">
            <div class="worker-row__info">
                <span class="worker-row__slot">${slot.slot_label}</span>
                <span class="worker-row__barcode">${escapeHtml(slot.barcode)}</span>
                <span class="worker-row__name">${displayName}</span>
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
            <div class="worker-row__actions">
                <button
                    class="btn btn--primary"
                    type="button"
                    data-slot-id="${slot.id}"
                    data-action="assign"
                    data-name="${slot.person_name ? escapeHtml(slot.person_name) : ""}"
                >
                    ${assignLabel}
                </button>
                <button
                    class="btn ${actionClass}"
                    type="button"
                    data-slot-id="${slot.id}"
                    data-action="${actionEndpoint}"
                >
                    ${actionLabel}
                </button>
            </div>
        </div>
    `;
}


slotList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const slotId = button.dataset.slotId;
    const action = button.dataset.action;

    if (action === "assign") {
        const currentName = button.dataset.name || "";
        assignWorkerId.value = slotId;
        assignPersonName.value = currentName;
        assignMessage.hidden = true;
        assignModal.hidden = false;
        assignPersonName.focus();
        return;
    }

    const actionLabel = action === "deactivate" ? "desactivar" : "reactivar";

    if (!confirm(`¿Desea ${actionLabel} este cupo?`)) {
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(`/api/admin/worker-slots/${slotId}/${action}`, {
            method: "PATCH",
            headers: apiHeaders(),
        });

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "No fue posible cambiar el estado");
        }

        loadWorkerSlots(slotSearchInput.value.trim());

    } catch (error) {
        alert(error.message);
        button.disabled = false;
    }
});


assignCancelBtn.addEventListener("click", () => {
    assignModal.hidden = true;
});

assignModal.addEventListener("click", (event) => {
    if (event.target === assignModal) {
        assignModal.hidden = true;
    }
});


assignForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const workerId = assignWorkerId.value;
    const personName = assignPersonName.value.trim();

    if (!personName) {
        showMessage(assignMessage, "El nombre es requerido.", "error");
        return;
    }

    assignSaveBtn.disabled = true;
    assignSaveBtn.textContent = "Guardando...";

    try {
        const response = await fetch(`/api/admin/worker-slots/${workerId}/assign`, {
            method: "PATCH",
            headers: apiHeaders(),
            body: JSON.stringify({ person_name: personName }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible asignar la persona");
        }

        assignModal.hidden = true;
        loadWorkerSlots(slotSearchInput.value.trim());

    } catch (error) {
        showMessage(assignMessage, error.message, "error");
    } finally {
        assignSaveBtn.disabled = false;
        assignSaveBtn.textContent = "Guardar";
    }
});


cleanSlotsBtn.addEventListener("click", async () => {
    const msg = "Esta acción dejará sin nombre los 150 cupos. Los movimientos e historiales anteriores se conservarán. ¿Desea continuar?";

    if (!confirm(msg)) {
        return;
    }

    cleanSlotsBtn.disabled = true;
    cleanSlotsBtn.textContent = "Limpiando...";

    try {
        const response = await fetch("/api/admin/worker-slots/clean", {
            method: "POST",
            headers: apiHeaders(),
        });

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible limpiar las asignaciones");
        }

        alert(result.message);
        loadWorkerSlots(slotSearchInput.value.trim());

    } catch (error) {
        alert(error.message);
    } finally {
        cleanSlotsBtn.disabled = false;
        cleanSlotsBtn.textContent = "Limpiar todas las asignaciones";
    }
});


async function loadEntries() {
    entriesList.innerHTML = `<p class="entries-list__empty">Cargando movimientos...</p>`;

    try {
        let url = "/api/admin/harvest-entries";
        const params = [];
        if (entryDateInput.value) {
            params.push(`date=${encodeURIComponent(entryDateInput.value)}`);
        }
        if (entrySearchInput.value.trim()) {
            params.push(`q=${encodeURIComponent(entrySearchInput.value.trim())}`);
        }
        if (params.length > 0) {
            url += "?" + params.join("&");
        }

        const response = await fetch(url);

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Error al cargar movimientos");
        }

        const data = await response.json();
        const entries = data.entries || [];

        if (entries.length === 0) {
            entriesList.innerHTML = `<p class="entries-list__empty">No se encontraron movimientos.</p>`;
            return;
        }

        entriesList.innerHTML = entries.map(renderEntry).join("");

    } catch (error) {
        entriesList.innerHTML = `<p class="entries-list__empty entries-list__empty--error">${error.message}</p>`;
    }
}

function renderEntry(entry) {
    const statusClass = entry.voided ? "badge--inactive" : "badge--active";
    const statusText = entry.voided ? "Anulado" : "Activo";
    const worker = entry.worker;
    const workerDisplay = `${escapeHtml(worker.slot_label)} — ${escapeHtml(worker.name)} / ${escapeHtml(worker.barcode)}`;
    const voidInfo = entry.voided
        ? `<div class="entry-row__void-info">
               <span class="entry-row__void-reason">Motivo: ${escapeHtml(entry.void_reason)}</span>
               <span class="entry-row__void-date">Anulado: ${entry.voided_at_local ? escapeHtml(entry.voided_at_local) : ""}</span>
           </div>`
        : "";
    const voidButton = entry.voided
        ? ""
        : `<button class="btn btn--danger btn--void" type="button" data-entry-id="${entry.id}"
               data-worker="${escapeHtml(worker.slot_label)} — ${escapeHtml(worker.name)} / ${escapeHtml(worker.barcode)}"
               data-weight="${entry.weight_kg}">Anular</button>`;

    return `
        <div class="entry-row">
            <div class="entry-row__info">
                <span class="entry-row__id">#${entry.id}</span>
                <span class="entry-row__worker">${workerDisplay}</span>
                <span class="entry-row__weight">${entry.weight_kg} kg</span>
                <span class="entry-row__time">${entry.created_at_local}</span>
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
            ${voidInfo}
            ${voidButton}
        </div>
    `;
}

entryDateInput.addEventListener("change", loadEntries);

entrySearchInput.addEventListener("input", () => {
    clearTimeout(entrySearchTimeout);
    entrySearchTimeout = setTimeout(loadEntries, 250);
});

entriesList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-entry-id]");
    if (!button) return;

    currentVoidEntryId = button.dataset.entryId;
    const worker = button.dataset.worker;
    const weight = button.dataset.weight;

    voidModalText.textContent = `¿Desea anular el movimiento #${currentVoidEntryId} de ${worker} (${weight} kg)?`;
    voidReasonInput.value = "";
    voidModal.hidden = false;
    voidReasonInput.focus();
});

voidCancelBtn.addEventListener("click", () => {
    voidModal.hidden = true;
    currentVoidEntryId = null;
});

voidModal.addEventListener("click", (event) => {
    if (event.target === voidModal) {
        voidModal.hidden = true;
        currentVoidEntryId = null;
    }
});

voidConfirmBtn.addEventListener("click", async () => {
    const reason = voidReasonInput.value.trim();

    if (!reason) {
        alert("El motivo de anulación es obligatorio.");
        return;
    }

    voidConfirmBtn.disabled = true;
    voidConfirmBtn.textContent = "Anulando...";

    try {
        const response = await fetch(`/api/admin/harvest-entries/${currentVoidEntryId}/void`, {
            method: "PATCH",
            headers: apiHeaders(),
            body: JSON.stringify({ reason }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible anular el movimiento");
        }

        voidModal.hidden = true;
        currentVoidEntryId = null;
        loadEntries();

    } catch (error) {
        alert(error.message);
    } finally {
        voidConfirmBtn.disabled = false;
        voidConfirmBtn.textContent = "Confirmar anulación";
    }
});


const todayStr = window.ADMIN_CONFIG ? window.ADMIN_CONFIG.operationalToday : null;
if (todayStr) {
    entryDateInput.value = todayStr;
}

const backupCreateBtn = document.getElementById("backup-create-btn");
const backupMessage = document.getElementById("backup-message");
const backupLatest = document.getElementById("backup-latest");
const backupLatestInfo = document.getElementById("backup-latest-info");
const backupList = document.getElementById("backup-list");

function renderBackup(backup) {
    return `
        <div class="backup-row">
            <span class="backup-row__filename">${escapeHtml(backup.filename)}</span>
            <span class="backup-row__size">${escapeHtml(backup.size_human)}</span>
            <span class="backup-row__date">${escapeHtml(backup.created_at)}</span>
        </div>
    `;
}

async function loadBackups() {
    backupList.innerHTML = `<p class="backup-list__empty">Cargando respaldos...</p>`;

    try {
        const response = await fetch("/api/admin/backups");

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "Error al cargar respaldos");
        }

        const data = await response.json();
        const backups = data.backups || [];

        if (data.latest) {
            backupLatest.hidden = false;
            backupLatestInfo.innerHTML = `
                <span class="backup-latest__filename">${escapeHtml(data.latest.filename)}</span>
                <span class="backup-latest__size">${escapeHtml(data.latest.size_human)}</span>
                <span class="backup-latest__date">${escapeHtml(data.latest.created_at)}</span>
            `;
        } else {
            backupLatest.hidden = true;
            backupLatestInfo.innerHTML = "";
        }

        if (backups.length === 0) {
            backupList.innerHTML = `<p class="backup-list__empty">No hay respaldos disponibles.</p>`;
            return;
        }

        backupList.innerHTML = backups.map(renderBackup).join("");

    } catch (error) {
        backupList.innerHTML = `<p class="backup-list__empty backup-list__empty--error">${error.message}</p>`;
    }
}

backupCreateBtn.addEventListener("click", async () => {
    backupCreateBtn.disabled = true;
    backupCreateBtn.textContent = "Creando respaldo...";
    showMessage(backupMessage, "Creando respaldo...", "success");

    try {
        const response = await fetch("/api/admin/backups", {
            method: "POST",
            headers: apiHeaders(),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible crear el respaldo");
        }

        showMessage(backupMessage, "Respaldo creado exitosamente.", "success");
        loadBackups();

    } catch (error) {
        showMessage(backupMessage, error.message, "error");
    } finally {
        backupCreateBtn.disabled = false;
        backupCreateBtn.textContent = "Crear respaldo";
    }
});


productForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = productName.value.trim();
    const rate = productRate.value;

    if (!name || !rate) {
        showMessage(productMessage, "Nombre y tarifa son requeridos.", "error");
        return;
    }

    productSubmit.disabled = true;
    productSubmit.textContent = "Registrando...";

    try {
        const response = await fetch("/api/admin/products", {
            method: "POST",
            headers: apiHeaders(),
            body: JSON.stringify({ name, rate_per_kg: rate }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible registrar el producto");
        }

        showMessage(productMessage, `Producto "${result.name}" registrado correctamente.`, "success");
        productName.value = "";
        productRate.value = "";
        productName.focus();
        loadProducts();

    } catch (error) {
        showMessage(productMessage, error.message, "error");
    } finally {
        productSubmit.disabled = false;
        productSubmit.textContent = "Registrar";
    }
});


productSearchInput.addEventListener("input", () => {
    clearTimeout(productSearchTimeout);
    productSearchTimeout = setTimeout(() => {
        loadProducts(productSearchInput.value.trim());
    }, 250);
});


async function loadProducts(query) {
    productList.innerHTML = `<p class="worker-list__empty">Cargando...</p>`;

    try {
        let url = "/api/admin/products";
        if (query) {
            url += `?q=${encodeURIComponent(query)}`;
        }

        const response = await fetch(url);

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Error al cargar productos");
        }

        const products = await response.json();
        productsById.clear();
        for (const p of products) {
            productsById.set(p.id, p);
        }

        if (products.length === 0) {
            productList.innerHTML = `<p class="worker-list__empty">No se encontraron productos.</p>`;
            return;
        }

        productList.innerHTML = products.map(renderProduct).join("");

    } catch (error) {
        productList.innerHTML = `<p class="worker-list__empty worker-list__empty--error">${escapeHtml(error.message)}</p>`;
    }
}


function renderProduct(product) {
    const statusClass = product.active ? "badge--active" : "badge--inactive";
    const statusText = product.active ? "Activo" : "Inactivo";
    const actionLabel = product.active ? "Desactivar" : "Reactivar";
    const actionClass = product.active ? "btn--danger" : "btn--success";
    const actionEndpoint = product.active ? "deactivate" : "activate";

    return `
        <div class="worker-row">
            <div class="worker-row__info">
                <span class="worker-row__name">${escapeHtml(product.name)}</span>
                <span class="worker-row__rate">$${escapeHtml(product.rate_per_kg)}/kg</span>
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
            <div class="worker-row__actions">
                <button
                    class="btn btn--primary"
                    type="button"
                    data-product-id="${product.id}"
                    data-action="edit"
                >
                    Editar
                </button>
                <button
                    class="btn ${actionClass}"
                    type="button"
                    data-product-id="${product.id}"
                    data-action="${actionEndpoint}"
                >
                    ${actionLabel}
                </button>
            </div>
        </div>
    `;
}


productList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const productId = Number.parseInt(button.dataset.productId, 10);
    if (!Number.isInteger(productId)) return;
    const action = button.dataset.action;

    if (action === "edit") {
        const product = productsById.get(productId);
        if (!product) return;
        editProductId.value = product.id;
        editProductName.value = product.name;
        editProductRate.value = product.rate_per_kg;
        editProductMessage.hidden = true;
        editProductModal.hidden = false;
        editProductName.focus();
        return;
    }

    const actionLabel = action === "deactivate" ? "desactivar" : "reactivar";

    if (!confirm(`¿Desea ${actionLabel} este producto?`)) {
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(`/api/admin/products/${productId}/${action}`, {
            method: "PATCH",
            headers: apiHeaders(),
        });

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "No fue posible cambiar el estado");
        }

        loadProducts(productSearchInput.value.trim());

    } catch (error) {
        alert(error.message);
        button.disabled = false;
    }
});


editProductCancelBtn.addEventListener("click", () => {
    editProductModal.hidden = true;
});

editProductModal.addEventListener("click", (event) => {
    if (event.target === editProductModal) {
        editProductModal.hidden = true;
    }
});


editProductForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const id = editProductId.value;
    const name = editProductName.value.trim();
    const rate = editProductRate.value;

    if (!name || !rate) {
        showMessage(editProductMessage, "Nombre y tarifa son requeridos.", "error");
        return;
    }

    editProductSaveBtn.disabled = true;
    editProductSaveBtn.textContent = "Guardando...";

    try {
        const response = await fetch(`/api/admin/products/${id}`, {
            method: "PATCH",
            headers: apiHeaders(),
            body: JSON.stringify({ name, rate_per_kg: rate }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible actualizar el producto");
        }

        editProductModal.hidden = true;
        loadProducts(productSearchInput.value.trim());

    } catch (error) {
        showMessage(editProductMessage, error.message, "error");
    } finally {
        editProductSaveBtn.disabled = false;
        editProductSaveBtn.textContent = "Guardar";
    }
});


initCsrfToken().then(() => {
    loadWorkerSlots();
    loadEntries();
    loadBackups();
    loadProducts();
});
