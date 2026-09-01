const createForm = document.getElementById("create-form");
const createName = document.getElementById("create-name");
const createBarcode = document.getElementById("create-barcode");
const createMessage = document.getElementById("create-message");
const createSubmit = document.getElementById("create-submit");
const searchInput = document.getElementById("search-input");
const workerList = document.getElementById("worker-list");

let searchTimeout = null;


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
            headers: { "Content-Type": "application/json" },
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
        });

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


function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `form__message form__message--${type}`;
    element.hidden = false;
}


function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


loadWorkers();
