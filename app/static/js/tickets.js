const dateInput = document.getElementById("date-input");
const searchInput = document.getElementById("search-input");
const queryBtn = document.getElementById("query-btn");
const ticketListSection = document.getElementById("ticket-list-section");
const ticketList = document.getElementById("ticket-list");
const ticketListTitle = document.getElementById("ticket-list-title");
const statsSection = document.getElementById("stats-section");
const statsBar = document.getElementById("stats-bar");
const previewSection = document.getElementById("preview-section");
const previewContent = document.getElementById("preview-content");
const printSelectedBtn = document.getElementById("print-selected-btn");
const printerSelect = document.getElementById("printer-select");
const printerStatus = document.getElementById("printer-status");
const refreshPrintersBtn = document.getElementById("refresh-printers-btn");
const testPrintBtn = document.getElementById("test-print-btn");
const printerMessage = document.getElementById("printer-message");
const printerUnavailable = document.getElementById("printer-unavailable");
const printAllAutoBtn = document.getElementById("print-all-auto-btn");
const printAllConfirmBtn = document.getElementById("print-all-confirm-btn");
const printProgress = document.getElementById("print-progress");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const confirmDialog = document.getElementById("confirm-dialog");
const confirmWorkerInfo = document.getElementById("confirm-worker-info");
const confirmActions = document.getElementById("confirm-actions");
const errorActions = document.getElementById("error-actions");
const confirmPrintBtn = document.getElementById("confirm-print-btn");
const confirmSkipBtn = document.getElementById("confirm-skip-btn");
const confirmStopBtn = document.getElementById("confirm-stop-btn");
const errorRetryBtn = document.getElementById("error-retry-btn");
const errorSkipBtn = document.getElementById("error-skip-btn");
const errorStopBtn = document.getElementById("error-stop-btn");
const confirmMessage = document.getElementById("confirm-message");
const quickScanEnabled = document.getElementById("quick-scan-enabled");
const quickScanInput = document.getElementById("quick-scan-input");
const quickScanMessage = document.getElementById("quick-scan-message");
const quickScanPreview = document.getElementById("quick-scan-preview");
const quickScanDate = document.getElementById("quick-scan-date");

let tickets = [];
let selectedAssignmentId = null;
let searchTimeout = null;
let isPrinting = false;
let csrfToken = "";
let printAbortController = null;
let quickScanBusy = false;
const quickPrintedTickets = new Set();

function setInputsDisabled(disabled) {
    dateInput.disabled = disabled;
    searchInput.disabled = disabled;
    queryBtn.disabled = disabled;
    printerSelect.disabled = disabled;
    refreshPrintersBtn.disabled = disabled;
    testPrintBtn.disabled = disabled;
    printSelectedBtn.disabled = disabled;
    printAllAutoBtn.disabled = disabled;
    printAllConfirmBtn.disabled = disabled;
    quickScanEnabled.disabled = disabled;
    quickScanInput.disabled = disabled || !quickScanEnabled.checked;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    csrfToken = meta ? meta.content : "";
}

getCsrfToken();

function initDate() {
    const cfg = window.TICKETS_CONFIG;
    if (cfg && cfg.operationalToday) {
        dateInput.value = cfg.operationalToday;
    }
}

function getOperationalDate() {
    const configuredToday = window.TICKETS_CONFIG && window.TICKETS_CONFIG.operationalToday;
    const date = dateInput.value || configuredToday;
    if (date && !dateInput.value) dateInput.value = date;
    quickScanDate.textContent = date || "No disponible";
    return date;
}

initDate();
getOperationalDate();

function showMessage(el, text, isError) {
    el.hidden = false;
    el.textContent = text;
    el.className = isError ? "printer-message printer-message--error" : "printer-message printer-message--success";
}

function hideMessage(el) {
    el.hidden = true;
    el.textContent = "";
}

async function loadTickets() {
    const date = dateInput.value;
    const q = searchInput.value.trim();

    if (!date) {
        ticketList.innerHTML = '<p class="empty-state">Seleccione una fecha.</p>';
        statsSection.hidden = true;
        previewSection.hidden = true;
        return;
    }

    ticketList.innerHTML = '<p class="empty-state">Cargando...</p>';

    try {
        let url = `/api/tickets/daily?date=${encodeURIComponent(date)}`;
        if (q) url += `&q=${encodeURIComponent(q)}`;

        const resp = await fetch(url);
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || "Error al cargar tickets");
        }

        const data = await resp.json();
        tickets = data.tickets;

        if (window.__TICKETS_DEBUG__) {
            console.log("[Tickets] status:", resp.status, "tickets:", tickets.length, "raw:", data);
        }

        statsBar.textContent = "";
        if (tickets.length > 0) {
            statsSection.hidden = false;
            const statsHtml = `<span class="stats-bar__item"><strong>${data.total_workers}</strong> trabajadores</span><span class="stats-bar__item"><strong>${data.total_day_weight_kg}</strong> kg</span><span class="stats-bar__item"><strong>$${data.total_day_amount_mxn}</strong> MXN</span>`;
            statsBar.innerHTML = statsHtml;
        } else {
            statsSection.hidden = true;
        }

        renderTicketList();

    } catch (err) {
        ticketList.innerHTML = `<p class="empty-state empty-state--error">${escapeHtml(err.message)}</p>`;
        statsSection.hidden = true;
        previewSection.hidden = true;
    }
}

function renderTicketList() {
    if (tickets.length === 0) {
        ticketList.innerHTML = '<p class="empty-state">No hay movimientos para esta fecha.</p>';
        ticketListTitle.textContent = "Trabajadores";
        previewSection.hidden = true;
        selectedAssignmentId = null;
        return;
    }

    ticketListTitle.textContent = `Trabajadores (${tickets.length})`;

    let html = '<table class="summary-table"><thead><tr><th></th><th>Cupo</th><th>Nombre</th><th>Codigo</th><th class="num">Kg</th><th class="num">Pago</th></tr></thead><tbody>';

    for (const t of tickets) {
        const checked = t.worker_assignment_id === selectedAssignmentId ? "checked" : "";
        const incompleteClass = t.has_incomplete_amounts ? " ticket-row--incomplete" : "";
        const incompleteTag = t.has_incomplete_amounts ? ' <span class="incomplete-tag">PAGO INCOMPLETO</span>' : "";
        html += `<tr class="ticket-row${incompleteClass}" data-id="${t.worker_assignment_id}">
            <td><input type="radio" name="ticket-select" value="${t.worker_assignment_id}" ${checked}></td>
            <td>${escapeHtml(t.slot_label)}${incompleteTag}</td>
            <td>${escapeHtml(t.worker_name)}</td>
            <td class="mono">${escapeHtml(t.worker_barcode)}</td>
            <td class="num">${t.total_weight_kg}</td>
            <td class="num bold">$${t.total_amount_mxn}</td>
        </tr>`;
    }

    html += "</tbody></table>";
    ticketList.innerHTML = html;

    ticketList.querySelectorAll(".ticket-row").forEach(row => {
        row.addEventListener("click", () => {
            const assignmentId = parseInt(row.dataset.id, 10);
            if (selectedAssignmentId === assignmentId) {
                selectedAssignmentId = null;
                previewSection.hidden = true;
            } else {
                selectedAssignmentId = assignmentId;
                showPreview(assignmentId);
            }
            renderTicketList();
        });
    });

    if (selectedAssignmentId) {
        const stillExists = tickets.some(t => t.worker_assignment_id === selectedAssignmentId);
        if (stillExists) {
            showPreview(selectedAssignmentId);
        } else {
            selectedAssignmentId = null;
            previewSection.hidden = true;
        }
    }
}

function showPreview(assignmentId) {
    const ticket = tickets.find(t => t.worker_assignment_id === assignmentId);
    if (!ticket) {
        previewSection.hidden = true;
        return;
    }

    previewSection.hidden = false;

    let html = '<div class="preview-box">';
    html += `<div class="preview-header"><strong>${escapeHtml(ticket.slot_label)}</strong> &mdash; ${escapeHtml(ticket.worker_name)}</div>`;
    html += `<div class="preview-meta">Codigo: ${escapeHtml(ticket.worker_barcode)} | Asignacion: ${ticket.worker_assignment_id}</div>`;
    html += '<table class="preview-table"><thead><tr><th>Producto</th><th class="num">Kg</th><th class="num">Precio/kg</th><th class="num">Subtotal</th></tr></thead><tbody>';

    for (const line of ticket.product_lines) {
        const amountDisplay = line.amount_mxn !== null ? `$${line.amount_mxn}` : "N/D";
        const type = line.registration_type === "sacks"
            ? `Arpillas: ${line.sack_count}; estimado con ${line.average_sack_weight_kg} kg/arpilla`
            : "Báscula: peso medido";
        html += `<tr><td>${escapeHtml(line.product_name)}<br><small>${escapeHtml(type)}</small></td><td class="num">${line.weight_kg}</td><td class="num">$${line.rate_per_kg}</td><td class="num">${amountDisplay}</td></tr>`;
    }

    html += "</tbody></table>";
    html += `<div class="preview-totals"><span>Total: ${ticket.total_weight_kg} kg</span><span class="bold">$${ticket.total_amount_mxn} MXN</span></div>`;

    if (ticket.has_incomplete_amounts) {
        html += '<div class="preview-warning">Este ticket contiene movimientos historicos sin precio y su pago puede estar incompleto.</div>';
    }

    html += "</div>";
    previewContent.innerHTML = html;
}

async function loadPrinters() {
    try {
        const resp = await fetch("/api/tickets/printers");
        const data = await resp.json();

        printerSelect.textContent = "";

        if (!data.direct_printing_available) {
            printerUnavailable.hidden = false;
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "Impresion no disponible";
            printerSelect.appendChild(opt);
            testPrintBtn.disabled = true;
            printAllAutoBtn.disabled = true;
            printAllConfirmBtn.disabled = true;
            return;
        }

        printerUnavailable.hidden = true;
        testPrintBtn.disabled = false;
        printAllAutoBtn.disabled = false;
        printAllConfirmBtn.disabled = false;

        if (data.printers.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "No hay impresoras instaladas";
            printerSelect.appendChild(opt);
            return;
        }

        for (const p of data.printers) {
            const opt = document.createElement("option");
            opt.value = p.name;
            opt.textContent = p.name + (p.is_default ? " (predeterminada)" : "");
            printerSelect.appendChild(opt);
        }

        const saved = localStorage.getItem("inventory.ticketPrinterName");
        if (saved && data.printers.some(p => p.name === saved)) {
            printerSelect.value = saved;
        } else if (data.default_printer) {
            printerSelect.value = data.default_printer;
            localStorage.setItem("inventory.ticketPrinterName", data.default_printer);
        }

        updatePrinterStatus();

    } catch (err) {
        printerSelect.textContent = "";
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Error al cargar";
        printerSelect.appendChild(opt);
    }
}

function updatePrinterStatus() {
    const name = printerSelect.value;
    if (!name) {
        printerStatus.textContent = "";
        return;
    }

    const opt = printerSelect.options[printerSelect.selectedIndex];
    const text = opt ? opt.textContent : "";
    if (text.includes("predeterminada")) {
        printerStatus.textContent = "Impresora predeterminada";
    } else {
        printerStatus.textContent = "";
    }
}

printerSelect.addEventListener("change", () => {
    const name = printerSelect.value;
    if (name) {
        localStorage.setItem("inventory.ticketPrinterName", name);
    }
    updatePrinterStatus();
});

refreshPrintersBtn.addEventListener("click", loadPrinters);

testPrintBtn.addEventListener("click", async () => {
    const printerName = printerSelect.value;
    if (!printerName) {
        showMessage(printerMessage, "Seleccione una impresora.", true);
        return;
    }

    testPrintBtn.disabled = true;
    testPrintBtn.textContent = "Enviando...";
    hideMessage(printerMessage);

    try {
        const resp = await fetch("/api/tickets/printers/test", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({ printer_name: printerName }),
        });

        const result = await resp.json();
        if (!resp.ok) {
            showMessage(printerMessage, result.error || "Error al imprimir prueba", true);
        } else {
            showMessage(printerMessage, result.message || "Prueba enviada", false);
        }
    } catch (err) {
        showMessage(printerMessage, "Error de conexion", true);
    } finally {
        testPrintBtn.disabled = false;
        testPrintBtn.textContent = "Imprimir prueba";
    }
});

printSelectedBtn.addEventListener("click", async () => {
    if (isPrinting) return;
    if (!selectedAssignmentId) {
        alert("Seleccione un trabajador.");
        return;
    }

    const printerName = printerSelect.value;
    if (!printerName) {
        alert("Seleccione una impresora.");
        return;
    }

    const date = dateInput.value;
    if (!date) return;

    const ticket = tickets.find(t => t.worker_assignment_id === selectedAssignmentId);
    if (ticket && ticket.has_incomplete_amounts) {
        if (!confirm("Este ticket contiene importes incompletos. Desea imprimirlo?")) return;
    }

    const result = await sendPrintRequest(
        date,
        selectedAssignmentId,
        printerName,
        ticket,
        Boolean(ticket && ticket.has_incomplete_amounts),
    );
    showMessage(printerMessage, result.error || result.message, Boolean(result.error));
});

function renderQuickScanPreview(ticket) {
    const incomplete = ticket.has_incomplete_amounts
        ? '<div class="preview-warning">Este ticket contiene importes incompletos.</div>'
        : "";
    quickScanPreview.innerHTML = `<div class="preview-box">
        <div class="preview-header"><strong>${escapeHtml(ticket.worker_name)}</strong></div>
        <div class="preview-meta">${escapeHtml(ticket.worker_barcode)} | ${escapeHtml(ticket.slot_label)}</div>
        <div class="preview-totals"><span>${ticket.total_weight_kg} kg</span><span class="bold">$${ticket.total_amount_mxn} MXN</span></div>
        ${incomplete}
    </div>`;
    quickScanPreview.hidden = false;
}

async function processQuickScan() {
    if (!quickScanEnabled.checked || quickScanBusy) return;
    const barcode = quickScanInput.value.trim().toUpperCase();
    if (!barcode) return;

    quickScanBusy = true;
    quickScanInput.disabled = true;
    hideMessage(quickScanMessage);
    quickScanPreview.hidden = true;

    try {
        const date = getOperationalDate();
        if (!date) throw new Error("No fue posible determinar la fecha de operación.");
        const response = await fetch(`/api/tickets/daily?date=${encodeURIComponent(date)}&q=${encodeURIComponent(barcode)}`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "No fue posible consultar el ticket.");

        const ticket = payload.tickets.find(item => item.worker_barcode.toUpperCase() === barcode);
        if (!ticket) {
            showMessage(quickScanMessage, "El trabajador no tiene movimientos en la fecha seleccionada.", true);
            return;
        }

        renderQuickScanPreview(ticket);
        const printerName = printerSelect.value;
        if (!printerName) {
            showMessage(quickScanMessage, "Configure primero una impresora", true);
            return;
        }
        const duplicateKey = `${date}:${ticket.worker_assignment_id}`;
        if (quickPrintedTickets.has(duplicateKey)) {
            showMessage(quickScanMessage, "Este ticket ya fue impreso en esta sesión rápida.", true);
            return;
        }

        let confirmIncomplete = false;
        if (ticket.has_incomplete_amounts) {
            confirmIncomplete = confirm("Este ticket contiene importes incompletos. ¿Desea imprimirlo?");
            if (!confirmIncomplete) {
                showMessage(quickScanMessage, "Impresión cancelada.", true);
                return;
            }
        }

        const result = await sendPrintRequest(
            date,
            ticket.worker_assignment_id,
            printerName,
            ticket,
            confirmIncomplete,
        );
        if (result.error || result.needsConfirm) {
            throw new Error(result.error || "Debe confirmar los importes incompletos.");
        }
        quickPrintedTickets.add(duplicateKey);
        showMessage(quickScanMessage, "Ticket impreso exitosamente.", false);
    } catch (error) {
        showMessage(quickScanMessage, error.message || "Error inesperado al imprimir.", true);
    } finally {
        quickScanBusy = false;
        quickScanInput.value = "";
        quickScanInput.disabled = !quickScanEnabled.checked;
        if (quickScanEnabled.checked) quickScanInput.focus();
    }
}

quickScanEnabled.addEventListener("change", () => {
    quickScanInput.disabled = !quickScanEnabled.checked;
    hideMessage(quickScanMessage);
    if (!quickScanEnabled.checked) {
        quickScanPreview.hidden = true;
        quickScanInput.value = "";
        return;
    }
    quickScanInput.focus();
});

dateInput.addEventListener("change", getOperationalDate);

if (window.location.hash === "#quick-scan-section") {
    quickScanEnabled.checked = true;
    quickScanInput.disabled = false;
    requestAnimationFrame(() => {
        document.getElementById("quick-scan-section").scrollIntoView({ behavior: "smooth", block: "center" });
        quickScanInput.focus({ preventScroll: true });
    });
}

quickScanInput.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    processQuickScan();
});

async function sendPrintRequest(date, assignmentId, printerName, ticket, confirmIncomplete = false) {
    const body = {
        date: date,
        worker_assignment_id: assignmentId,
        printer_name: printerName,
    };

    if (confirmIncomplete) {
        body.confirm_incomplete_amounts = true;
    }

    const resp = await fetch("/api/tickets/print", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify(body),
    });

    const result = await resp.json();

    if (resp.status === 409 && result.has_incomplete_amounts) {
        if (confirmIncomplete) {
            return { needsConfirm: false, error: result.error };
        }
        return { needsConfirm: true, error: result.error };
    }

    if (!resp.ok) {
        return { error: result.error || "Error al imprimir" };
    }

    return { success: true, message: result.message };
}

async function printAllAutomatic() {
    if (isPrinting) return;
    if (tickets.length === 0) {
        alert("No hay tickets para imprimir.");
        return;
    }

    const printerName = printerSelect.value;
    if (!printerName) {
        alert("Seleccione una impresora.");
        return;
    }

    const date = dateInput.value;
    if (!date) return;

    if (!confirm(`Se imprimiran ${tickets.length} tickets. Desea continuar?`)) return;

    isPrinting = true;
    setInputsDisabled(true);
    printProgress.hidden = false;
    const stableTickets = [...tickets];
    const total = stableTickets.length;

    for (let i = 0; i < total; i++) {
        if (!isPrinting) break;

        const t = stableTickets[i];
        progressText.textContent = `Imprimiendo ${i + 1} de ${total} - ${t.slot_label} - ${t.worker_name}`;
        progressFill.style.width = `${((i + 1) / total) * 100}%`;

        const result = await sendPrintRequest(date, t.worker_assignment_id, printerName, t);

        if (result.needsConfirm) {
            const confirmed = confirm("Este ticket tiene importes incompletos. Imprimir de todos modos?");
            if (!confirmed) continue;
            const retry = await sendPrintRequest(date, t.worker_assignment_id, printerName, t, true);
            if (retry.error) {
                progressText.textContent = `Error en ticket ${i + 1}: ${retry.error}`;
                isPrinting = false;
                setInputsDisabled(false);
                alert(`Error al imprimir ${t.slot_label}. Cadena detenida.`);
                return;
            }
        } else if (result.error) {
            progressText.textContent = `Error en ticket ${i + 1}: ${result.error}`;
            isPrinting = false;
            setInputsDisabled(false);
            alert(`Error al imprimir ${t.slot_label}. Cadena detenida.`);
            return;
        }
    }

    progressText.textContent = `Completado: ${total} tickets impresos`;
    isPrinting = false;
    setInputsDisabled(false);
}

async function printAllWithConfirmation() {
    if (isPrinting) return;
    if (tickets.length === 0) {
        alert("No hay tickets para imprimir.");
        return;
    }

    const printerName = printerSelect.value;
    if (!printerName) {
        alert("Seleccione una impresora.");
        return;
    }

    const date = dateInput.value;
    if (!date) return;

    isPrinting = true;
    setInputsDisabled(true);
    printProgress.hidden = false;
    confirmDialog.hidden = false;
    confirmActions.hidden = false;
    errorActions.hidden = true;
    hideMessage(confirmMessage);

    const stableTickets = [...tickets];
    let i = 0;

    async function processNext() {
        if (i >= stableTickets.length || !isPrinting) {
            progressText.textContent = isPrinting ? "Completado" : "Impresion detenida";
            confirmDialog.hidden = true;
            isPrinting = false;
            setInputsDisabled(false);
            return;
        }

        const t = stableTickets[i];
        progressText.textContent = `Ticket ${i + 1} de ${stableTickets.length}`;
        progressFill.style.width = `${((i + 1) / stableTickets.length) * 100}%`;

        let infoHtml = `<strong>${escapeHtml(t.slot_label)}</strong> - ${escapeHtml(t.worker_name)}<br>`;
        infoHtml += `Kg: ${t.total_weight_kg} | Pago: $${t.total_amount_mxn}`;
        if (t.has_incomplete_amounts) {
            infoHtml += '<br><span class="preview-warning-inline">Importes incompletos</span>';
        }
        confirmWorkerInfo.innerHTML = infoHtml;

        confirmActions.hidden = false;
        errorActions.hidden = true;
        hideMessage(confirmMessage);

        confirmPrintBtn.onclick = async () => {
            confirmPrintBtn.disabled = true;
            confirmSkipBtn.disabled = true;

            const result = await sendPrintRequest(date, t.worker_assignment_id, printerName, t);

            confirmPrintBtn.disabled = false;
            confirmSkipBtn.disabled = false;

            if (result.needsConfirm) {
                const confirmed = confirm("Importes incompletos. Imprimir de todos modos?");
                if (confirmed) {
                    const retry = await sendPrintRequest(date, t.worker_assignment_id, printerName, t, true);
                    if (retry.error) {
                        showErrorState(retry.error, t, i);
                        return;
                    }
                }
            } else if (result.error) {
                showErrorState(result.error, t, i);
                return;
            }

            i++;
            processNext();
        };

        confirmSkipBtn.onclick = () => {
            i++;
            processNext();
        };

        confirmStopBtn.onclick = () => {
            confirmDialog.hidden = true;
            progressText.textContent = "Impresion detenida";
            isPrinting = false;
            setInputsDisabled(false);
        };
    }

    function showErrorState(errorMsg, t, index) {
        confirmActions.hidden = true;
        errorActions.hidden = false;
        showMessage(confirmMessage, `Error al imprimir ${t.slot_label}. Estado de impresion incierto. Revise fisicamente la impresora antes de reintentar.`, true);

        errorRetryBtn.onclick = async () => {
            errorRetryBtn.disabled = true;
            errorSkipBtn.disabled = true;

            const result = await sendPrintRequest(date, t.worker_assignment_id, printerName, t);

            errorRetryBtn.disabled = false;
            errorSkipBtn.disabled = false;

            if (result.error) {
                showMessage(confirmMessage, `Error al reintentar: ${result.error}. Revise la impresora.`, true);
                return;
            }

            i++;
            processNext();
        };

        errorSkipBtn.onclick = () => {
            i++;
            processNext();
        };

        errorStopBtn.onclick = () => {
            confirmDialog.hidden = true;
            progressText.textContent = "Impresion detenida";
            isPrinting = false;
            setInputsDisabled(false);
        };
    }

    processNext();
}

printAllAutoBtn.addEventListener("click", printAllAutomatic);
printAllConfirmBtn.addEventListener("click", printAllWithConfirmation);

queryBtn.addEventListener("click", loadTickets);
dateInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadTickets();
});
dateInput.addEventListener("change", loadTickets);
searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadTickets, 250);
});

loadTickets();
loadPrinters();
