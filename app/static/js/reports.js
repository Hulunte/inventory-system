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
    const cfg = window.REPORTS_CONFIG;
    if (!cfg || !cfg.operationalToday) return;

    const todayStr = cfg.operationalToday;
    endDateInput.value = todayStr;

    const yyyy = todayStr.slice(0, 4);
    const mm = todayStr.slice(5, 7);
    startDateInput.value = `${yyyy}-${mm}-01`;
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

        const modeTable = (title, mode) => {
            const isSacks = mode === "sacks";
            const rows = data.workers.filter(w => (isSacks ? w.sack_entries_count : w.scale_entries_count) > 0);
            const totals = data.summary[mode];
            return `<section class="report-mode-section" data-measurement-mode="${mode}">
                <h3>${title}</h3>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Cupo</th>
                        <th>Trabajador</th>
                        <th>Código</th>
                        <th class="num">Movimientos</th>
                        ${isSacks ? '<th class="num">Arpillas</th>' : ''}
                        <th class="num">${isSacks ? 'Peso estimado' : 'Peso medido'} (kg)</th>
                        <th class="num">Importe</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.map(w => `
                        <tr>
                            <td>${w.slot_label ? escapeHtml(w.slot_label) : "—"}</td>
                            <td>${w.name ? escapeHtml(w.name) : "Sin asignar"}</td>
                            <td class="mono">${w.barcode ? escapeHtml(w.barcode) : "—"}</td>
                            <td class="num">${isSacks ? w.sack_entries_count : w.scale_entries_count}</td>
                            ${isSacks ? `<td class="num">${w.total_sacks}</td>` : ''}
                            <td class="num bold">${isSacks ? w.sack_weight_kg : w.scale_weight_kg}</td>
                            <td class="num bold">$${isSacks ? w.sack_amount_mxn : w.scale_amount_mxn}</td>
                        </tr>
                    `).join("")}
                </tbody>
                <tfoot>
                    <tr class="summary-total">
                        <td colspan="3">TOTAL</td>
                        <td class="num">${totals.movements}</td>
                        ${isSacks ? `<td class="num">${totals.sack_count}</td>` : ''}
                        <td class="num bold">${totals.weight_kg}</td>
                        <td class="num bold">$${totals.amount_mxn}</td>
                    </tr>
                </tfoot>
            </table></section>`;
        };
        summaryContent.innerHTML = modeTable("Movimientos de báscula", "scale")
            + modeTable("Movimientos de arpillas", "sacks")
            + `<p class="summary-grand-total"><strong>Totales generales:</strong> ${data.summary.total_entries} movimientos · ${data.summary.total_weight_kg} kg · $${data.summary.total_amount_mxn}</p>`;

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


// --- Email export ---

const emailSection = document.getElementById("email-section");
const emailInput = document.getElementById("email-input");
const sendEmailBtn = document.getElementById("send-email-btn");
const emailMessage = document.getElementById("email-message");
const EXPORT_EMAIL_STORAGE_KEY = "inventory.exportRecipientEmail";

if (emailInput) {
    emailInput.value = localStorage.getItem(EXPORT_EMAIL_STORAGE_KEY) || "";
}

if (emailSection) {
    emailSection.hidden = false;
}

function showEmailMessage(text, isError) {
    if (!emailMessage) return;
    emailMessage.hidden = false;
    emailMessage.textContent = text;
    emailMessage.className = isError
        ? "filters__email-message filters__email-message--error"
        : "filters__email-message filters__email-message--success";
}

function hideEmailMessage() {
    if (!emailMessage) return;
    emailMessage.hidden = true;
    emailMessage.textContent = "";
}

if (sendEmailBtn) {
    sendEmailBtn.addEventListener("click", async () => {
        const start = startDateInput.value;
        const end = endDateInput.value;

        if (!start || !end) {
            showEmailMessage("Selecciona un rango de fechas antes de enviar.", true);
            return;
        }

        const email = (emailInput.value || "").trim();
        if (!email) {
            showEmailMessage("Ingresa un correo electrónico válido.", true);
            emailInput.focus();
            return;
        }

        const q = searchInput.value.trim();

        sendEmailBtn.disabled = true;
        sendEmailBtn.textContent = "Enviando...";
        hideEmailMessage();

        try {
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.content : "";

            const response = await fetch("/api/reports/harvest/export/email", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({
                    email: email,
                    start_date: start,
                    end_date: end,
                    q: q || undefined,
                }),
            });

            const result = await response.json();

            if (!response.ok) {
                showEmailMessage(result.error || "No fue posible enviar el correo.", true);
                return;
            }

            showEmailMessage(result.message || "Correo enviado exitosamente.", false);
            localStorage.setItem(EXPORT_EMAIL_STORAGE_KEY, email);

        } catch (error) {
            showEmailMessage("No fue posible enviar el correo. Intente nuevamente.", true);
        } finally {
            sendEmailBtn.disabled = false;
            sendEmailBtn.textContent = "Enviar por correo";
        }
    });

    emailInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            sendEmailBtn.click();
        }
    });
}
