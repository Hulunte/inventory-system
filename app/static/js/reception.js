const barcodeInput = document.getElementById("barcode");
const productInfo = document.getElementById("product-info");

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

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
                    <p>Código: ${escapeHtml(barcode)}</p>
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
                        <span class="worker-card__label">Código</span>
                        <span class="worker-card__value">${escapeHtml(worker.barcode)}</span>
                    </div>

                    <div class="worker-card__detail worker-card__detail--full">
                        <span class="worker-card__label">Total del día</span>
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
            const weightKg = parseFloat(weightInput.value);

            if (!weightKg || weightKg <= 0) {
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
                        barcode: worker.barcode,
                        weight_kg: weightKg
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || "No fue posible registrar la pesada");
                }

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
                            <p><strong>Peso registrado:</strong> ${escapeHtml(result.weight_kg)} kg</p>
                            <p><strong>Total del día:</strong> ${escapeHtml(result.daily_total)} kg</p>
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
