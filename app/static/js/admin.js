const logoutBtn = document.getElementById("logout-btn");
const slotSearchInput = document.getElementById("slot-search-input");
const showInactiveSlots = document.getElementById("show-inactive-slots");
const slotList = document.getElementById("slot-list");
const cleanSlotsBtn = document.getElementById("clean-slots-btn");
const slotsEmailInput = document.getElementById("slots-email-input");
const emailSlotsBtn = document.getElementById("email-slots-btn");
const slotsEmailMessage = document.getElementById("slots-email-message");
const assignModal = document.getElementById("assign-modal");
const assignModalText = document.getElementById("assign-modal-text");
const assignForm = document.getElementById("assign-form");
const assignWorkerId = document.getElementById("assign-worker-id");
const assignPersonName = document.getElementById("assign-person-name");
const assignMessage = document.getElementById("assign-message");
const assignCancelBtn = document.getElementById("assign-cancel-btn");
const assignSaveBtn = document.getElementById("assign-save-btn");

let csrfToken = "";
let slotSearchTimeout = null;
const EXPORT_EMAIL_STORAGE_KEY = "inventory.exportRecipientEmail";

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

showInactiveSlots.addEventListener("change", () => {
    loadWorkerSlots(slotSearchInput.value.trim());
});


async function loadWorkerSlots(query) {
    slotList.innerHTML = `<p class="worker-list__empty">Cargando...</p>`;

    try {
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        if (showInactiveSlots.checked) params.set("include_inactive", "true");
        const url = `/api/admin/worker-slots${params.size ? `?${params}` : ""}`;

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


if (slotsEmailInput && emailSlotsBtn) {
    slotsEmailInput.value = localStorage.getItem(EXPORT_EMAIL_STORAGE_KEY) || "";

    emailSlotsBtn.addEventListener("click", async () => {
        const email = slotsEmailInput.value.trim();
        if (!email || !slotsEmailInput.checkValidity()) {
            showMessage(slotsEmailMessage, "Correo inválido.", "error");
            slotsEmailInput.focus();
            return;
        }

        emailSlotsBtn.disabled = true;
        emailSlotsBtn.textContent = "Enviando...";
        slotsEmailMessage.hidden = true;
        try {
            const response = await fetch("/api/admin/worker-slots/export/email", {
                method: "POST",
                headers: apiHeaders(),
                body: JSON.stringify({ email }),
            });
            const result = await response.json();
            if (response.status === 401) {
                window.location.href = "/admin/login";
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Error de conexión SMTP.");
            }
            localStorage.setItem(EXPORT_EMAIL_STORAGE_KEY, email);
            showMessage(slotsEmailMessage, result.message || "Correo enviado exitosamente.", "success");
        } catch (error) {
            showMessage(slotsEmailMessage, error.message || "Error de conexión SMTP.", "error");
        } finally {
            emailSlotsBtn.disabled = false;
            emailSlotsBtn.textContent = "Enviar por correo";
        }
    });

    slotsEmailInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            emailSlotsBtn.click();
        }
    });
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


initCsrfToken().then(() => {
    loadWorkerSlots();
    loadBackups();
});
