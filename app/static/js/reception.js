const barcodeInput = document.getElementById("barcode");
const productInfo = document.getElementById("product-info");
const productButtonsContainer = document.getElementById("product-buttons");
const productWarning = document.getElementById("product-warning");

const STORAGE_KEY = "selectedProductId";
let selectedProductId = null;
let allProducts = [];

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

async function loadProducts() {
    try {
        const response = await fetch("/api/products/active");
        if (!response.ok) {
            throw new Error("Error loading products");
        }
        allProducts = await response.json();
    } catch (error) {
        console.error(error);
        allProducts = [];
    }

    if (allProducts.length === 0) {
        productButtonsContainer.style.display = "none";
        productWarning.style.display = "";
        return;
    }

    productButtonsContainer.style.display = "";
    productWarning.style.display = "none";

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
}

function restoreSelection() {
    let storedId = null;
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw !== null) {
            storedId = Number.parseInt(raw, 10);
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


barcodeInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
        return;
    }

    event.preventDefault();
    barcodeInput.blur();
    const barcode = barcodeInput.value.trim();

    if (!barcode) {
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
                    <p><strong>Trabajador no encontrado.</strong></p>
                    <p>C&oacute;digo: ${escapeHtml(barcode)}</p>
                </div>
            `;

            barcodeInput.select();
            return;
        }

        if (!response.ok) {
            throw new Error("Error al consultar el trabajador");
        }

        const worker = await response.json();

        await showWorker(worker);

    } catch (error) {
        console.error(error);

        productInfo.innerHTML = `
            <div class="status-message status-message--error">
                No fue posible consultar el trabajador.
            </div>
        `;
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
                <h2 class="worker-card__name">${escapeHtml(worker.name)}</h2>

                <div class="worker-card__details">
                    <div class="worker-card__detail">
                        <span class="worker-card__label">C&oacute;digo</span>
                        <span class="worker-card__value">${escapeHtml(worker.barcode)}</span>
                    </div>

                    <div class="worker-card__detail worker-card__detail--full">
                        <span class="worker-card__label">Total del d&iacute;a</span>
                        <div class="stock-display">
                            <span class="stock-display__number">${escapeHtml(daily.daily_total)}</span>
                            <span class="stock-display__unit">kg</span>
                        </div>
                    </div>
                </div>

                <div class="receipt-form">
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
                </div>
            </div>
        `;


        const weightInput = document.getElementById("weight_kg");
        const registerButton = document.getElementById("register-receipt");

        requestAnimationFrame(() => {
            setTimeout(() => {
                weightInput.focus({ preventScroll: true });
                weightInput.select();
            }, 150);
        });

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

            const weightKg = parseFloat(weightInput.value);

            if (!weightKg || weightKg <= 0) {
                alert("Ingrese un peso v&aacute;lido mayor a cero.");
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
                        barcode: worker.barcode,
                        weight_kg: weightKg,
                        product_id: selectedProductId
                    })
                });

                const result = await response.json();

                if (!response.ok) {
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
                            <p><strong>Trabajador:</strong> ${escapeHtml(worker.name)}</p>
                            <p><strong>Producto:</strong> ${escapeHtml(result.product_name)}</p>
                            <p><strong>Peso registrado:</strong> ${escapeHtml(result.weight_kg)} kg</p>
                            ${amountDisplay}
                            <p><strong>Total del d&iacute;a:</strong> ${escapeHtml(result.daily_total)} kg</p>
                        </div>
                        <p class="success-card__hint">Preparado para el siguiente trabajador.</p>
                    </div>
                `;

                barcodeInput.value = "";
                barcodeInput.focus();

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
