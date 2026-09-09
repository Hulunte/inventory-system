const barcodeInput = document.getElementById("barcode");
const productInfo = document.getElementById("product-info");
const productButtonsContainer = document.getElementById("product-buttons");
const productWarning = document.getElementById("product-warning");
const movementsContent = document.getElementById("movements-content");
const refreshMovementsBtn = document.getElementById("refresh-movements");
const recentMovementsSection = document.getElementById("recent-movements");
const quickVoidDialog = document.getElementById("quick-void-dialog");
const quickVoidConfirmBtn = document.getElementById("quick-void-confirm");
const quickVoidFields = {
    worker: document.getElementById("quick-void-worker"),
    code: document.getElementById("quick-void-code"),
    product: document.getElementById("quick-void-product"),
    weight: document.getElementById("quick-void-weight"),
    amount: document.getElementById("quick-void-amount"),
};

const STORAGE_KEY = "inventory.selectedProductId";
const SCANNER_DEBUG = new URLSearchParams(window.location.search)
    .get("scannerDebug") === "1";
let selectedProductId = null;
let allProducts = [];

function scannerDebug(message) {
    if (SCANNER_DEBUG) {
        console.log(message);
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

async function responseError(response, operation) {
    let detail = "";
    try {
        const body = await response.json();
        detail = typeof body.error === "string" ? body.error : "";
    } catch (_) {
        detail = response.statusText || "Respuesta no válida";
    }
    return new Error(`${operation} (HTTP ${response.status})${detail ? `: ${detail}` : ""}`);
}

async function loadProducts() {
    try {
        const response = await fetch("/api/products/active");
        if (!response.ok) {
            throw await responseError(response, "No fue posible cargar los productos");
        }
        allProducts = await response.json();
    } catch (error) {
        console.error("Error al cargar /api/products/active:", error);
        allProducts = [];
        productButtonsContainer.hidden = true;
        productWarning.hidden = false;
        productWarning.textContent = error.message;
        return;
    }

    if (allProducts.length === 0) {
        productButtonsContainer.hidden = true;
        productWarning.hidden = false;
        productWarning.textContent = "No hay productos activos. Contacte al administrador.";
        return;
    }

    productButtonsContainer.hidden = false;
    productWarning.hidden = true;

    renderProductButtons();
    restoreSelection();
}

function renderProductButtons() {
    let html = "";
    for (const product of allProducts) {
        const isSelected = selectedProductId === product.id;
        html += `<button type="button"
            class="product-btn${isSelected ? " product-btn--selected" : ""}"
            data-product-id="${escapeHtml(String(product.id))}"
            aria-pressed="${isSelected}"
        >${escapeHtml(product.name)} — $${escapeHtml(product.rate_per_kg)}/kg</button>`;
    }
    productButtonsContainer.innerHTML = html;

    productButtonsContainer.querySelectorAll(".product-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = Number.parseInt(btn.dataset.productId, 10);
            selectProduct(id);
        });
    });
}

function selectProduct(productId) {
    selectedProductId = productId;
    try {
        localStorage.setItem(STORAGE_KEY, String(productId));
    } catch (_e) {
        /* storage unavailable */
    }
    renderProductButtons();

    const weightInput = document.getElementById("weight_kg");
    if (weightInput) {
        scrollToWeightControl(weightInput);
    }
}

function restoreSelection() {
    let storedId = null;
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw !== null) {
            if (/^\d+$/.test(raw)) {
                storedId = Number.parseInt(raw, 10);
            }
        }
    } catch (_e) {
        /* storage unavailable */
    }

    if (storedId === null || Number.isNaN(storedId)) {
        selectedProductId = null;
        renderProductButtons();
        return;
    }

    const exists = allProducts.some((p) => p.id === storedId);
    if (exists) {
        selectedProductId = storedId;
    } else {
        selectedProductId = null;
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (_e) {
            /* storage unavailable */
        }
    }
    renderProductButtons();
}

loadProducts();


function findScrollableAncestor(element) {
    let parent = element.parentElement;
    while (parent && parent !== document.body) {
        const style = window.getComputedStyle(parent);
        if (
            parent.scrollHeight > parent.clientHeight
            && ["auto", "scroll"].includes(style.overflowY)
        ) {
            return parent;
        }
        parent = parent.parentElement;
    }
    return null;
}

function debugScrollAncestors(element) {
    if (!SCANNER_DEBUG) {
        return;
    }
    let node = element;
    while (node && node !== document.body) {
        const style = window.getComputedStyle(node);
        console.log(node, {
            overflowY: style.overflowY,
            scrollHeight: node.scrollHeight,
            clientHeight: node.clientHeight
        });
        node = node.parentElement;
    }
}

async function scrollToWeightControl(element) {
    await new Promise((resolve) => requestAnimationFrame(resolve));

    if (!element || !element.isConnected) {
        return false;
    }

    const style = window.getComputedStyle(element);
    const isVisible = style.display !== "none"
        && style.visibility !== "hidden"
        && element.offsetWidth > 0
        && element.offsetHeight > 0;
    if (!isVisible) {
        return false;
    }

    debugScrollAncestors(element);
    element.focus({ preventScroll: true });

    return new Promise((resolve) => {
        window.setTimeout(() => {
            if (!element.isConnected) {
                resolve(false);
                return;
            }

            const scrollableParent = findScrollableAncestor(element);
            const elementRect = element.getBoundingClientRect();
            if (scrollableParent) {
                const parentRect = scrollableParent.getBoundingClientRect();
                scrollableParent.scrollTop += elementRect.top - parentRect.top
                    - (scrollableParent.clientHeight - elementRect.height) / 2;
            } else {
                window.scrollTo({
                    top: window.scrollY + elementRect.top
                        - (window.innerHeight - elementRect.height) / 2,
                    behavior: "smooth"
                });
            }
            element.focus({ preventScroll: true });
            scannerDebug("scroll ejecutado");
            resolve(true);
        }, 300);
    });
}

async function restoreBarcodePosition(scrollTop) {
    barcodeInput.focus({ preventScroll: true });
    barcodeInput.select();
    const restoreScroll = () => {
        const scrollingElement = document.scrollingElement;
        if (scrollingElement && typeof scrollingElement.scrollTo === "function") {
            scrollingElement.scrollTo({ top: scrollTop, behavior: "instant" });
            scrollingElement.scrollTop = scrollTop;
        }
    };
    await new Promise((resolve) => requestAnimationFrame(resolve));
    restoreScroll();
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    restoreScroll();
}


barcodeInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
        return;
    }

    event.preventDefault();
    scannerDebug("scanner enter recibido");
    const initialScrollTop = document.scrollingElement?.scrollTop ?? window.scrollY;
    const barcode = barcodeInput.value.trim();

    if (!barcode) {
        await restoreBarcodePosition(initialScrollTop);
        return;
    }

    productInfo.innerHTML = `
        <div class="status-message status-message--loading">
            <span class="spinner"></span>
            Buscando trabajador...
        </div>
    `;

    try {
        const response = await fetch(
            `/api/workers/${encodeURIComponent(barcode)}`
        );

        if (response.status === 404) {
            productInfo.innerHTML = `
                <div class="status-message status-message--error">
                    <p><strong>Cupo no encontrado.</strong></p>
                    <p>Código: ${escapeHtml(barcode)}</p>
                </div>
            `;

            await restoreBarcodePosition(initialScrollTop);
            return;
        }

        if (!response.ok) {
            throw new Error("Error al consultar el trabajador");
        }

        const worker = await response.json();

        scannerDebug("trabajador validado");
        barcodeInput.blur();
        await showWorker(worker);

    } catch (error) {
        console.error(error);

        productInfo.innerHTML = `
            <div class="status-message status-message--error">
                No fue posible consultar el trabajador.
            </div>
        `;
        await restoreBarcodePosition(initialScrollTop);
    }
});


async function showWorker(worker) {
    try {
        const response = await fetch(
            `/api/harvest/daily/${encodeURIComponent(worker.barcode)}`
        );

        if (!response.ok) {
            throw new Error("Error al consultar el total diario");
        }

        const daily = await response.json();

        productInfo.innerHTML = `
            <div class="worker-card">
                <h2 class="worker-card__slot">${escapeHtml(daily.worker.slot_label)}</h2>
                <h3 class="worker-card__name">${escapeHtml(daily.worker.name || "Sin nombre")}</h3>

                <div class="worker-card__details">
                    <div class="worker-card__detail">
                        <span class="worker-card__label">Código</span>
                        <span class="worker-card__value">${escapeHtml(daily.worker.barcode)}</span>
                    </div>

                    <div class="worker-card__detail worker-card__detail--full">
                        <span class="worker-card__label">Total del día</span>
                        <div class="stock-display">
                            <span class="stock-display__number">${escapeHtml(daily.daily_total)}</span>
                            <span class="stock-display__unit">kg</span>
                        </div>
                    </div>
                </div>

                <section class="receipt-form" id="weight-entry-section">
                    <label class="receipt-form__label" for="weight_kg">
                        Peso de la tanda (kg)
                    </label>

                    <input
                        class="receipt-form__input"
                        type="number"
                        id="weight_kg"
                        min="0.001"
                        step="0.001"
                        autocomplete="off"
                    >

                    <button
                        class="receipt-form__button"
                        type="button"
                        id="register-receipt"
                    >
                        Registrar pesada
                    </button>
                </section>
            </div>
        `;


        const weightInput = document.getElementById("weight_kg");
        const registerButton = document.getElementById("register-receipt");

        await scrollToWeightControl(weightInput);

        weightInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                registerButton.click();
            }
        });

        registerButton.addEventListener("click", async () => {
            if (selectedProductId === null) {
                alert("Seleccione un producto antes de registrar.");
                return;
            }

            const weightKg = weightInput.value.trim();

            if (!weightKg || !weightInput.checkValidity()) {
                alert("Ingrese un peso válido mayor a cero.");
                weightInput.focus();
                return;
            }

            registerButton.disabled = true;
            registerButton.textContent = "Registrando...";

            try {
                const response = await fetch("/api/harvest/entries", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        barcode: daily.worker.barcode,
                        weight_kg: weightKg,
                        product_id: selectedProductId
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    if (result.code === "product_unavailable") {
                        selectedProductId = null;
                        try {
                            localStorage.removeItem(STORAGE_KEY);
                        } catch (_e) {
                            /* storage unavailable */
                        }
                        await loadProducts();
                        alert("El producto seleccionado ya no está disponible. Seleccione otro producto.");
                        registerButton.disabled = false;
                        registerButton.textContent = "Registrar pesada";
                        requestAnimationFrame(() => {
                            setTimeout(() => {
                                weightInput.focus({ preventScroll: true });
                                weightInput.select();
                            }, 150);
                        });
                        return;
                    }
                    throw new Error(result.error || "No fue posible registrar la pesada");
                }

                const amountDisplay = result.amount_mxn
                    ? `<p><strong>Importe:</strong> $${escapeHtml(result.amount_mxn)} MXN</p>`
                    : "";

                productInfo.innerHTML = `
                    <div class="success-card">
                        <div class="success-card__icon">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                            </svg>
                        </div>
                        <h2 class="success-card__title">Pesada registrada correctamente</h2>
                        <div class="success-card__details">
                            <p><strong>Trabajador:</strong> ${escapeHtml(result.worker.slot_label)} — ${escapeHtml(result.worker.name)}</p>
                            <p><strong>Producto:</strong> ${escapeHtml(result.product_name)}</p>
                            <p><strong>Precio aplicado:</strong> $${escapeHtml(result.rate_per_kg)} MXN/kg</p>
                            <p><strong>Peso registrado:</strong> ${escapeHtml(result.weight_kg)} kg</p>
                            ${amountDisplay}
                            <p><strong>Total del día:</strong> ${escapeHtml(result.daily_total)} kg</p>
                        </div>
                        <p class="success-card__hint">Preparado para el siguiente trabajador.</p>
                    </div>
                `;

                barcodeInput.value = "";
                await showRecentMovementAfterRegistration();

            } catch (error) {
                console.error(error);

                alert(error.message);

                registerButton.disabled = false;
                registerButton.textContent = "Registrar pesada";
                requestAnimationFrame(() => {
                    setTimeout(() => {
                        weightInput.focus({ preventScroll: true });
                        weightInput.select();
                    }, 150);
                });
            }
        });
    } catch (error) {
        console.error(error);

        productInfo.innerHTML = `
            <div class="status-message status-message--error">
                Trabajador encontrado, pero no fue posible consultar el total diario.
            </div>
        `;
    }
}


// --- Recent Movements ---

let isLoadingMovements = false;
let movementsPollInterval = null;
let recentAdminAuthenticated = false;
let recentCsrfToken = "";
let recentMovementsById = new Map();
let quickVoidPromise = null;

async function loadRecentAdminSession() {
    try {
        const response = await fetch("/api/admin/session", {cache: "no-store"});
        if (!response.ok) return false;
        const data = await response.json();
        recentAdminAuthenticated = data.authenticated === true;
        recentCsrfToken = recentAdminAuthenticated ? (data.csrf_token || "") : "";
        return recentAdminAuthenticated;
    } catch (error) {
        console.error("No fue posible validar la sesión administrativa del preview.", error);
        recentAdminAuthenticated = false;
        recentCsrfToken = "";
        return false;
    }
}

async function loadRecentMovements() {
    if (isLoadingMovements) {
        return;
    }

    isLoadingMovements = true;
    refreshMovementsBtn.disabled = true;

    try {
        const [response] = await Promise.all([
            fetch("/api/harvest/recent?limit=10", {cache: "no-store"}),
            loadRecentAdminSession(),
        ]);

        if (!response.ok) {
            throw await responseError(response, "No fue posible cargar los movimientos");
        }

        const data = await response.json();
        const movements = data.movements;
        recentMovementsById = new Map(movements.map(movement => [String(movement.id), movement]));

        if (movements.length === 0) {
            movementsContent.innerHTML = `
                <div class="status-message status-message--idle">
                    No hay movimientos registrados hoy.
                </div>
            `;
            return;
        }

        let html = '<div class="movements-list">';
        for (const m of movements) {
            const statusClass = m.voided ? "movement--voided" : "movement--active";
            const statusLabel = m.voided ? "Anulado" : "Vigente";
            const productName = m.product_name ? escapeHtml(m.product_name) : "Sin producto";
            const rateDisplay = m.rate_per_kg ? `$${escapeHtml(m.rate_per_kg)}` : "\u2014";
            const amountDisplay = m.amount_mxn ? `$${escapeHtml(m.amount_mxn)} MXN` : "\u2014";

            const slotLabel = m.worker.slot_label
                ? `${escapeHtml(m.worker.slot_label)} — `
                : "";

            html += `
                <div class="movement ${statusClass}">
                    <div class="movement__row">
                        <span class="movement__time">${escapeHtml(m.time)}</span>
                        <span class="movement__worker">${slotLabel}${escapeHtml(m.worker.name || "Sin nombre")} (${escapeHtml(m.worker.barcode || "")})</span>
                        <span class="movement__badge movement__badge--${m.voided ? "voided" : "active"}">${escapeHtml(statusLabel)}</span>
                        ${recentAdminAuthenticated && m.can_void && !m.voided ? `<button type="button" class="movement__void-btn" data-void-entry-id="${m.id}">Anular</button>` : ""}
                    </div>
                    <div class="movement__row movement__details">
                        <span class="movement__product">${productName}</span>
                        <span class="movement__weight">${escapeHtml(m.weight_kg)} kg</span>
                        <span class="movement__rate">${rateDisplay}/kg</span>
                        <span class="movement__amount">${amountDisplay}</span>
                    </div>
                </div>
            `;
        }
        html += '</div>';
        movementsContent.innerHTML = html;
    } catch (error) {
        console.error("Error al cargar /api/harvest/recent?limit=10:", error);

        if (!movementsContent.querySelector('.movements-list')) {
            movementsContent.innerHTML = `
                <div class="status-message status-message--error">
                    ${escapeHtml(error.message)}
                </div>
            `;
        }
    } finally {
        isLoadingMovements = false;
        refreshMovementsBtn.disabled = false;
    }
}

async function showRecentMovementAfterRegistration() {
    await loadRecentMovements();
    recentMovementsSection.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "nearest",
    });
    barcodeInput.focus({preventScroll: true});
}

function confirmQuickVoid(movement, opener) {
    if (!quickVoidDialog || typeof quickVoidDialog.showModal !== "function" || !movement) {
        return Promise.resolve(false);
    }
    if (quickVoidPromise) return quickVoidPromise;

    quickVoidFields.worker.textContent = movement.worker.name || "Sin nombre";
    quickVoidFields.code.textContent = movement.worker.barcode || "—";
    quickVoidFields.product.textContent = movement.product_name || "Sin producto";
    quickVoidFields.weight.textContent = `${movement.weight_kg} kg`;
    quickVoidFields.amount.textContent = movement.amount_mxn ? `$${movement.amount_mxn} MXN` : "—";

    quickVoidPromise = new Promise(resolve => {
        const handleClose = () => {
            const confirmed = quickVoidDialog.returnValue === "confirm";
            quickVoidPromise = null;
            if (opener && opener.isConnected) opener.focus({preventScroll: true});
            resolve(confirmed);
        };
        quickVoidDialog.addEventListener("close", handleClose, {once: true});
        quickVoidDialog.showModal();
        quickVoidConfirmBtn.focus({preventScroll: true});
    });
    return quickVoidPromise;
}

if (quickVoidDialog && quickVoidConfirmBtn) {
    quickVoidDialog.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            event.stopPropagation();
            if (!quickVoidConfirmBtn.disabled) quickVoidDialog.close("confirm");
        } else if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            quickVoidDialog.close("cancel");
        }
    });
}

movementsContent.addEventListener("click", async event => {
    const button = event.target.closest("[data-void-entry-id]");
    if (!button) return;
    if (button.dataset.voidPending === "true") return;
    button.dataset.voidPending = "true";
    const movement = recentMovementsById.get(button.dataset.voidEntryId);
    if (!(await confirmQuickVoid(movement, button))) {
        delete button.dataset.voidPending;
        return;
    }

    button.disabled = true;
    try {
        if (!(await loadRecentAdminSession())) {
            throw new Error("Se requiere una sesión administrativa activa.");
        }
        const response = await fetch(`/api/admin/harvest-entries/${button.dataset.voidEntryId}/void`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": recentCsrfToken,
            },
            body: JSON.stringify({reason: "Anulación rápida"}),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "No fue posible anular el movimiento.");
        }
        await loadRecentMovements();
    } catch (error) {
        alert(error.message);
        button.disabled = false;
        delete button.dataset.voidPending;
    }
});

function startMovementsPolling() {
    stopMovementsPolling();
    movementsPollInterval = setInterval(loadRecentMovements, 15000);
}

function stopMovementsPolling() {
    if (movementsPollInterval !== null) {
        clearInterval(movementsPollInterval);
        movementsPollInterval = null;
    }
}

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        stopMovementsPolling();
    } else {
        loadRecentMovements();
        startMovementsPolling();
    }
});

refreshMovementsBtn.addEventListener("click", () => {
    loadRecentMovements();
});

loadRecentMovements();
startMovementsPolling();
