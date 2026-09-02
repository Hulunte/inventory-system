const dateInput = document.getElementById("date-input");
const searchInput = document.getElementById("search-input");
const summaryTitle = document.getElementById("summary-title");
const summaryContent = document.getElementById("summary-content");
const detailSection = document.getElementById("detail-section");
const detailTitle = document.getElementById("detail-title");
const detailContent = document.getElementById("detail-content");

let selectedWorkerId = null;
let searchTimeout = null;


function initDate() {
    const cfg = window.HISTORY_CONFIG;
    if (cfg && cfg.operationalToday) {
        dateInput.value = cfg.operationalToday;
    }
}

initDate();


dateInput.addEventListener("change", () => {
    selectedWorkerId = null;
    detailSection.hidden = true;
    loadSummary();
});

searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadSummary();
    }, 250);
});


async function loadSummary() {
    const date = dateInput.value;
    const q = searchInput.value.trim();

    if (!date) {
        summaryContent.innerHTML = `<p class="empty-state">Seleccione una fecha.</p>`;
        return;
    }

    summaryContent.innerHTML = `<p class="empty-state">Cargando...</p>`;

    try {
        let url = `/api/history/daily?date=${encodeURIComponent(date)}`;
        if (q) {
            url += `&q=${encodeURIComponent(q)}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "Error al cargar el resumen");
        }

        const data = await response.json();

        const dateObj = new Date(data.date + "T12:00:00");
        const dateFormatted = dateObj.toLocaleDateString("es-ES", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
        summaryTitle.textContent = `Resumen del día ${dateFormatted}`;

        if (data.workers.length === 0) {
            summaryContent.innerHTML = `
                <p class="empty-state">No hay registros de cosecha para esta fecha.</p>
            `;
            return;
        }

        summaryContent.innerHTML = `
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Trabajador</th>
                        <th>Código</th>
                        <th class="num">Tandas</th>
                        <th class="num">Total kg</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.workers.map(w => `
                        <tr class="summary-row ${w.worker_id === selectedWorkerId ? "summary-row--selected" : ""}"
                            data-worker-id="${w.worker_id}">
                            <td>${escapeHtml(w.name)}</td>
                            <td class="mono">${escapeHtml(w.barcode)}</td>
                            <td class="num">${w.entries_count}</td>
                            <td class="num bold">${w.total_weight_kg}</td>
                        </tr>
                    `).join("")}
                </tbody>
                <tfoot>
                    <tr class="summary-total">
                        <td colspan="2">TOTAL</td>
                        <td class="num">${data.summary.total_entries}</td>
                        <td class="num bold">${data.summary.total_weight_kg}</td>
                    </tr>
                </tfoot>
            </table>
        `;

        document.querySelectorAll(".summary-row").forEach(row => {
            row.addEventListener("click", () => {
                const workerId = parseInt(row.dataset.workerId, 10);
                selectWorker(workerId, data.date);
            });
        });

    } catch (error) {
        summaryContent.innerHTML = `<p class="empty-state empty-state--error">${error.message}</p>`;
    }
}


async function selectWorker(workerId, date) {
    selectedWorkerId = workerId;

    document.querySelectorAll(".summary-row").forEach(row => {
        row.classList.toggle("summary-row--selected",
            parseInt(row.dataset.workerId, 10) === workerId);
    });

    detailSection.hidden = false;
    detailContent.innerHTML = `<p class="empty-state">Cargando...</p>`;

    try {
        const response = await fetch(
            `/api/history/workers/${workerId}/entries?date=${encodeURIComponent(date)}`
        );

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "Error al cargar el detalle");
        }

        const data = await response.json();

        const dateObj = new Date(data.date + "T12:00:00");
        const dateFormatted = dateObj.toLocaleDateString("es-ES", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
        detailTitle.textContent = `Detalle: ${data.worker.name} - ${dateFormatted}`;

        if (data.entries.length === 0) {
            detailContent.innerHTML = `
                <p class="empty-state">Este trabajador no tiene registros para esta fecha.</p>
            `;
            return;
        }

        detailContent.innerHTML = `
            <table class="detail-table">
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th class="num">Peso (kg)</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.entries.map(e => `
                        <tr>
                            <td>${escapeHtml(e.created_at)}</td>
                            <td class="num">${e.weight_kg}</td>
                        </tr>
                    `).join("")}
                </tbody>
                <tfoot>
                    <tr class="detail-total">
                        <td>Total</td>
                        <td class="num bold">${data.summary.total_weight_kg}</td>
                    </tr>
                </tfoot>
            </table>
        `;

    } catch (error) {
        detailContent.innerHTML = `<p class="empty-state empty-state--error">${error.message}</p>`;
    }
}


function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


loadSummary();
