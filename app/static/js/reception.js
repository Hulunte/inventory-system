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

    productInfo.innerHTML = "<p>Buscando producto...</p>";

    try {
        const response = await fetch(
            `/api/products/${encodeURIComponent(barcode)}`
        );

        if (response.status === 404) {
            productInfo.innerHTML = `
                <p>Producto no encontrado.</p>
                <p>Código: ${barcode}</p>
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
            <p>No fue posible consultar el producto.</p>
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
            <h2>${product.name}</h2>

            <p>
                <strong>Código:</strong>
                ${product.barcode}
            </p>

            <p>
                <strong>Unidad:</strong>
                ${product.unit}
            </p>

            <p>
                <strong>Stock actual:</strong>
                ${inventory.stock}
            </p>

            <label for="quantity">
                Cantidad recibida
            </label>

            <input
                type="number"
                id="quantity"
                min="1"
                step="1"
                autocomplete="off"
            >

            <button
                type="button"
                id="register-receipt"
            >
                Registrar entrada
            </button>
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
            <h2>Entrada registrada correctamente</h2>

            <p>
                <strong>Producto:</strong>
                ${product.name}
            </p>

            <p>
                <strong>Cantidad recibida:</strong>
                ${quantity}
            </p>

            <p>
                Preparado para el siguiente producto.
            </p>
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
            <p>
                Producto encontrado, pero no fue posible consultar el stock.
            </p>
        `;
    }
}