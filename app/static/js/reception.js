const barcodeInput = document.getElementById("barcode");
const productInfo = document.getElementById("product-info");

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
            Buscando producto...
        </div>
    `;

    try {
        const response = await fetch(
            `/api/products/${encodeURIComponent(barcode)}`
        );

        if (response.status === 404) {
            productInfo.innerHTML = `
                <div class="status-message status-message--error">
                    <p><strong>Producto no encontrado.</strong></p>
                    <p>Código: ${barcode}</p>
                </div>
            `;

            barcodeInput.select();
            return;
        }

        if (!response.ok) {
            throw new Error("Error al consultar el producto");
        }

        const product = await response.json();

        await showProduct(product);

    } catch (error) {
        console.error(error);

        productInfo.innerHTML = `
            <div class="status-message status-message--error">
                No fue posible consultar el producto.
            </div>
        `;
    }
});


async function showProduct(product) {
    try {
        const response = await fetch(
            `/api/inventory/stock/${encodeURIComponent(product.barcode)}`
        );

        if (!response.ok) {
            throw new Error("Error al consultar el inventario");
        }

        const inventory = await response.json();

        productInfo.innerHTML = `
            <div class="product-card">
                <h2 class="product-card__name">${product.name}</h2>

                <div class="product-card__details">
                    <div class="product-card__detail">
                        <span class="product-card__label">Código</span>
                        <span class="product-card__value">${product.barcode}</span>
                    </div>

                    <div class="product-card__detail">
                        <span class="product-card__label">Unidad</span>
                        <span class="product-card__value">${product.unit}</span>
                    </div>

                    <div class="product-card__detail product-card__detail--full">
                        <span class="product-card__label">Stock actual</span>
                        <div class="stock-display">
                            <span class="stock-display__number">${inventory.stock}</span>
                            <span class="stock-display__unit">${product.unit}</span>
                        </div>
                    </div>
                </div>

                <div class="receipt-form">
                    <label class="receipt-form__label" for="quantity">
                        Cantidad recibida
                    </label>

                    <input
                        class="receipt-form__input"
                        type="number"
                        id="quantity"
                        min="1"
                        step="1"
                        autocomplete="off"
                    >

                    <button
                        class="receipt-form__button"
                        type="button"
                        id="register-receipt"
                    >
                        Registrar entrada
                    </button>
                </div>
            </div>
        `;


        const quantityInput = document.getElementById("quantity");
        const registerButton = document.getElementById("register-receipt");

        requestAnimationFrame(() => {
            setTimeout(() => {
                quantityInput.focus({ preventScroll: true });
                quantityInput.select();
            }, 150);
        });

        quantityInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                registerButton.click();
            }
        });

        registerButton.addEventListener("click", async () => {
            const quantity = parseInt(quantityInput.value, 10);

            if (!quantity || quantity <= 0) {
                alert("Ingrese una cantidad válida.");
                quantityInput.focus();
                return;
            }

            registerButton.disabled = true;
            registerButton.textContent = "Registrando...";

            try {
                const response = await fetch("/api/inventory/receipts", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        barcode: product.barcode,
                        quantity: quantity
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || "No fue posible registrar la entrada");
                }

                productInfo.innerHTML = `
                    <div class="success-card">
                        <div class="success-card__icon">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                            </svg>
                        </div>
                        <h2 class="success-card__title">Entrada registrada correctamente</h2>
                        <div class="success-card__details">
                            <p><strong>Producto:</strong> ${product.name}</p>
                            <p><strong>Cantidad recibida:</strong> ${quantity}</p>
                        </div>
                        <p class="success-card__hint">Preparado para el siguiente producto.</p>
                    </div>
                `;

                barcodeInput.value = "";
                barcodeInput.focus();

            } catch (error) {
                console.error(error);

                alert(error.message);

                registerButton.disabled = false;
                registerButton.textContent = "Registrar entrada";
                requestAnimationFrame(() => {
                    setTimeout(() => {
                        quantityInput.focus({ preventScroll: true });
                        quantityInput.select();
                    }, 150);
                });
            }
        });
    } catch (error) {
        console.error(error);

        productInfo.innerHTML = `
            <div class="status-message status-message--error">
                Producto encontrado, pero no fue posible consultar el stock.
            </div>
        `;
    }
}
