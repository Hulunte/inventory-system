const startDateInput = document.getElementById("start-date");
const endDateInput = document.getElementById("end-date");
const queryBtn = document.getElementById("query-btn");
const searchInput = document.getElementById("search-input");
const rangeWarning = document.getElementById("range-warning");
const summarySection = document.getElementById("summary-section");
const summaryTitle = document.getElementById("summary-title");
const statsBar = document.getElementById("stats-bar");
const summaryContent = document.getElementById("summary-content");

let searchTimeout = null;


function initDates() {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const dd = String(today.getDate()).padStart(2, "0");
    endDateInput.value = `${yyyy}-${mm}-${dd}`;

    const firstOfMonth = new Date(yyyy, today.getMonth(), 1);
    const mmFirst = String(firstOfMonth.getMonth() + 1).padStart(2, "0");
    const ddFirst = String(firstOfMonth.getDate()).padStart(2, "0");
    startDateInput.value = `${yyyy}-${mmFirst}-${ddFirst}`;
}

initDates();


function checkRangeWarning() {
    const start = startDateInput.value;
    const end = endDateInput.value;

    if (!start || !end) {
        rangeWarning.hidden = true;
        return;
    }

    const startMs = new Date(start + "T00:00:00").getTime();
    const endMs = new Date(end + "T00:00:00").getTime();
    const diffDays = (endMs - startMs) / (1000 * 60 * 60 * 24);

    rangeWarning.hidden = diffDays <= 365;
}

startDateInput.addEventListener("change", checkRangeWarning);
endDateInput.addEventListener("change", checkRangeWarning);


queryBtn.addEventListener("click", () => {
    loadReport();
});

startDateInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        loadReport();
    }
});

endDateInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        loadReport();
    }
});

searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadReport();
    }, 250);
});


async function loadReport() {
    const start = startDateInput.value;
    const end = endDateInput.value;
    const q = searchInput.value.trim();

    if (!start || !end) {
        summarySection.hidden = true;
        return;
    }

    summarySection.hidden = false;
    summaryContent.innerHTML = `<p class="empty-state">Cargando...</p>`;
    statsBar.innerHTML = "";

    try {
        let url = `/api/reports/harvest?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        if (q) {
            url += `&q=${encodeURIComponent(q)}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "Error al cargar el reporte");
        }

        const data = await response.json();

        const startObj = new Date(data.start_date + "T12:00:00");
        const endObj = new Date(data.end_date + "T12:00:00");
        const opts = { day: "numeric", month: "long", year: "numeric" };
        const startFormatted = startObj.toLocaleDateString("es-ES", opts);
        const endFormatted = endObj.toLocaleDateString("es-ES", opts);
        summaryTitle.textContent = `Resumen del período ${startFormatted} — ${endFormatted}`;

        statsBar.innerHTML = `
            <span class="stats-bar__item">
                <strong>${data.summary.total_workers}</strong> trabajadores
            </span>
            <span class="stats-bar__item">
                <strong>${data.summary.total_entries}</strong> tandas
            </span>
            <span class="stats-bar__item">
                <strong>${data.summary.total_weight_kg}</strong> kg
            </span>
        `;

        if (data.workers.length === 0) {
            summaryContent.innerHTML = `
                <p class="empty-state">No hay registros de cosecha para este período.</p>
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
                        <tr>
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

    } catch (error) {
        summaryContent.innerHTML = `<p class="empty-state empty-state--error">${escapeHtml(error.message)}</p>`;
        statsBar.innerHTML = "";
    }
}


function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


// --- Week buttons ---

const weekCurrentBtn = document.getElementById("week-current-btn");
const weekPreviousBtn = document.getElementById("week-previous-btn");

if (weekCurrentBtn) {
    weekCurrentBtn.addEventListener("click", () => {
        const cfg = window.REPORTS_CONFIG;
        if (cfg) {
            startDateInput.value = cfg.currentWeekStart;
            endDateInput.value = cfg.currentWeekEnd;
            checkRangeWarning();
            loadReport();
        }
    });
}

if (weekPreviousBtn) {
    weekPreviousBtn.addEventListener("click", () => {
        const cfg = window.REPORTS_CONFIG;
        if (cfg) {
            startDateInput.value = cfg.previousWeekStart;
            endDateInput.value = cfg.previousWeekEnd;
            checkRangeWarning();
            loadReport();
        }
    });
}


// --- Export button ---

const exportBtn = document.getElementById("export-btn");

if (exportBtn) {
    exportBtn.addEventListener("click", () => {
        const start = startDateInput.value;
        const end = endDateInput.value;

        if (!start || !end) {
            alert("Selecciona un rango de fechas antes de exportar.");
            return;
        }

        const q = searchInput.value.trim();
        let url = `/api/reports/harvest/export?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
        if (q) {
            url += `&q=${encodeURIComponent(q)}`;
        }

        window.location.href = url;
    });
}
