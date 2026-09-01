const createForm = document.getElementById("create-form");
const createName = document.getElementById("create-name");
const createBarcode = document.getElementById("create-barcode");
const createMessage = document.getElementById("create-message");
const createSubmit = document.getElementById("create-submit");
const searchInput = document.getElementById("search-input");
const workerList = document.getElementById("worker-list");
const logoutBtn = document.getElementById("logout-btn");
const entryDateInput = document.getElementById("entry-date-input");
const entrySearchInput = document.getElementById("entry-search-input");
const entriesList = document.getElementById("entries-list");
const voidModal = document.getElementById("void-modal");
const voidModalText = document.getElementById("void-modal-text");
const voidReasonInput = document.getElementById("void-reason-input");
const voidCancelBtn = document.getElementById("void-cancel-btn");
const voidConfirmBtn = document.getElementById("void-confirm-btn");

let csrfToken = "";
let searchTimeout = null;
let entrySearchTimeout = null;
let currentVoidEntryId = null;

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


createForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = createName.value.trim();
    const barcode = createBarcode.value.trim();

    if (!name || !barcode) {
        showMessage(createMessage, "Nombre y código son requeridos.", "error");
        return;
    }

    createSubmit.disabled = true;
    createSubmit.textContent = "Registrando...";

    try {
        const response = await fetch("/api/admin/workers", {
            method: "POST",
            headers: apiHeaders(),
            body: JSON.stringify({ name, barcode }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible registrar el trabajador");
        }

        showMessage(createMessage, `Trabajador "${result.name}" registrado correctamente.`, "success");
        createName.value = "";
        createBarcode.value = "";
        createName.focus();
        loadWorkers();

    } catch (error) {
        showMessage(createMessage, error.message, "error");
    } finally {
        createSubmit.disabled = false;
        createSubmit.textContent = "Registrar";
    }
});


searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadWorkers(searchInput.value.trim());
    }, 250);
});


async function loadWorkers(query) {
    workerList.innerHTML = `<p class="worker-list__empty">Cargando...</p>`;

    try {
        let url = "/api/admin/workers";
        if (query) {
            url += `?q=${encodeURIComponent(query)}`;
        }

        const response = await fetch(url);

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Error al cargar trabajadores");
        }

        const workers = await response.json();

        if (workers.length === 0) {
            workerList.innerHTML = `<p class="worker-list__empty">No se encontraron trabajadores.</p>`;
            return;
        }

        workerList.innerHTML = workers.map(renderWorker).join("");

    } catch (error) {
        workerList.innerHTML = `<p class="worker-list__empty worker-list__empty--error">${error.message}</p>`;
    }
}


function renderWorker(worker) {
    const statusClass = worker.active ? "badge--active" : "badge--inactive";
    const statusText = worker.active ? "Activo" : "Inactivo";
    const actionLabel = worker.active ? "Desactivar" : "Reactivar";
    const actionClass = worker.active ? "btn--danger" : "btn--success";
    const actionEndpoint = worker.active ? "deactivate" : "activate";

    return `
        <div class="worker-row">
            <div class="worker-row__info">
                <span class="worker-row__name">${escapeHtml(worker.name)}</span>
                <span class="worker-row__barcode">${escapeHtml(worker.barcode)}</span>
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
            <button
                class="btn ${actionClass}"
                type="button"
                data-worker-id="${worker.id}"
                data-action="${actionEndpoint}"
            >
                ${actionLabel}
            </button>
        </div>
    `;
}


workerList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const workerId = button.dataset.workerId;
    const action = button.dataset.action;
    const actionLabel = action === "deactivate" ? "desactivar" : "reactivar";

    if (!confirm(`¿Desea ${actionLabel} este trabajador?`)) {
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(`/api/admin/workers/${workerId}/${action}`, {
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

        loadWorkers(searchInput.value.trim());

    } catch (error) {
        alert(error.message);
        button.disabled = false;
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
    const voidInfo = entry.voided
        ? `<div class="entry-row__void-info">
               <span class="entry-row__void-reason">Motivo: ${escapeHtml(entry.void_reason)}</span>
               <span class="entry-row__void-date">Anulado: ${entry.voided_at ? new Date(entry.voided_at).toLocaleString("es-MX") : ""}</span>
           </div>`
        : "";
    const voidButton = entry.voided
        ? ""
        : `<button class="btn btn--danger btn--void" type="button" data-entry-id="${entry.id}"
               data-worker="${escapeHtml(entry.worker.name)} / ${escapeHtml(entry.worker.barcode)}"
               data-weight="${entry.weight_kg}">Anular</button>`;

    return `
        <div class="entry-row">
            <div class="entry-row__info">
                <span class="entry-row__id">#${entry.id}</span>
                <span class="entry-row__worker">${escapeHtml(entry.worker.name)} / ${escapeHtml(entry.worker.barcode)}</span>
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


const today = new Date();
const year = today.getFullYear();
const month = String(today.getMonth() + 1).padStart(2, "0");
const day = String(today.getDate()).padStart(2, "0");
entryDateInput.value = `${year}-${month}-${day}`;

initCsrfToken().then(() => {
    loadWorkers();
    loadEntries();
});
