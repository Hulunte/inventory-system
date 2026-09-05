const logoutBtn = document.getElementById("logout-btn");
const productForm = document.getElementById("product-form");
const productName = document.getElementById("product-name");
const productRate = document.getElementById("product-rate");
const productMessage = document.getElementById("product-message");
const productSubmit = document.getElementById("product-submit");
const productSearchInput = document.getElementById("product-search-input");
const productList = document.getElementById("product-list");
const editProductModal = document.getElementById("edit-product-modal");
const editProductForm = document.getElementById("edit-product-form");
const editProductId = document.getElementById("edit-product-id");
const editProductName = document.getElementById("edit-product-name");
const editProductRate = document.getElementById("edit-product-rate");
const editProductMessage = document.getElementById("edit-product-message");
const editProductCancelBtn = document.getElementById("edit-product-cancel-btn");
const editProductSaveBtn = document.getElementById("edit-product-save-btn");

let csrfToken = "";
let productSearchTimeout = null;
let productsById = new Map();

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : csrfToken;
}

async function initCsrfToken() {
    try {
        const response = await fetch("/api/admin/session");
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = "/admin/login";
            return false;
        }
        csrfToken = data.csrf_token || "";
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) meta.setAttribute("content", csrfToken);
        return true;
    } catch (e) {
        window.location.href = "/admin/login";
        return false;
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `form__message form__message--${type}`;
    element.hidden = false;
}

function apiHeaders() {
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": getCsrfToken(),
    };
}

logoutBtn.addEventListener("click", async () => {
    try {
        await fetch("/api/admin/logout", {
            method: "POST",
            headers: apiHeaders(),
        });
    } catch (e) {
        // ignore
    }
    window.location.href = "/admin/login";
});


productForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = productName.value.trim();
    const rate = productRate.value;

    if (!name || !rate) {
        showMessage(productMessage, "Nombre y precio son requeridos.", "error");
        return;
    }

    productSubmit.disabled = true;
    productSubmit.textContent = "Registrando...";

    try {
        const response = await fetch("/api/admin/products", {
            method: "POST",
            headers: apiHeaders(),
            body: JSON.stringify({ name, rate_per_kg: rate }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible registrar el producto");
        }

        showMessage(productMessage, `Producto "${result.name}" registrado correctamente.`, "success");
        productName.value = "";
        productRate.value = "";
        productName.focus();
        loadProducts();

    } catch (error) {
        showMessage(productMessage, error.message, "error");
    } finally {
        productSubmit.disabled = false;
        productSubmit.textContent = "Registrar";
    }
});


productSearchInput.addEventListener("input", () => {
    clearTimeout(productSearchTimeout);
    productSearchTimeout = setTimeout(() => {
        loadProducts(productSearchInput.value.trim());
    }, 250);
});


async function loadProducts(query) {
    productList.innerHTML = `<p class="worker-list__empty">Cargando...</p>`;

    try {
        let url = "/api/admin/products";
        if (query) {
            url += `?q=${encodeURIComponent(query)}`;
        }

        const response = await fetch(url);

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Error al cargar productos");
        }

        const products = await response.json();
        productsById.clear();
        for (const p of products) {
            productsById.set(p.id, p);
        }

        if (products.length === 0) {
            productList.innerHTML = `<p class="worker-list__empty">No se encontraron productos.</p>`;
            return;
        }

        productList.innerHTML = products.map(renderProduct).join("");

    } catch (error) {
        productList.innerHTML = `<p class="worker-list__empty worker-list__empty--error">${escapeHtml(error.message)}</p>`;
    }
}


function renderProduct(product) {
    const statusClass = product.active ? "badge--active" : "badge--inactive";
    const statusText = product.active ? "Activo" : "Inactivo";
    const actionLabel = product.active ? "Desactivar" : "Reactivar";
    const actionClass = product.active ? "btn--danger" : "btn--success";
    const actionEndpoint = product.active ? "deactivate" : "activate";

    return `
        <div class="worker-row">
            <div class="worker-row__info">
                <span class="worker-row__name">${escapeHtml(product.name)}</span>
                <span class="worker-row__rate">$${escapeHtml(product.rate_per_kg)}/kg</span>
                <span class="badge ${statusClass}">${statusText}</span>
            </div>
            <div class="worker-row__actions">
                <button
                    class="btn btn--primary"
                    type="button"
                    data-product-id="${product.id}"
                    data-action="edit"
                >
                    Editar
                </button>
                <button
                    class="btn ${actionClass}"
                    type="button"
                    data-product-id="${product.id}"
                    data-action="${actionEndpoint}"
                >
                    ${actionLabel}
                </button>
            </div>
        </div>
    `;
}


productList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const productId = Number.parseInt(button.dataset.productId, 10);
    if (!Number.isInteger(productId)) return;
    const action = button.dataset.action;

    if (action === "edit") {
        const product = productsById.get(productId);
        if (!product) return;
        editProductId.value = product.id;
        editProductName.value = product.name;
        editProductRate.value = product.rate_per_kg;
        editProductMessage.hidden = true;
        editProductModal.hidden = false;
        editProductName.focus();
        return;
    }

    const actionLabel = action === "deactivate" ? "desactivar" : "reactivar";

    if (!confirm(`¿Desea ${actionLabel} este producto?`)) {
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(`/api/admin/products/${productId}/${action}`, {
            method: "PATCH",
            headers: apiHeaders(),
        });

        if (response.status === 401) {
            window.location.href = "/admin/login";
            return;
        }

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || "No fue posible cambiar el estado");
        }

        loadProducts(productSearchInput.value.trim());

    } catch (error) {
        alert(error.message);
        button.disabled = false;
    }
});


editProductCancelBtn.addEventListener("click", () => {
    editProductModal.hidden = true;
});

editProductModal.addEventListener("click", (event) => {
    if (event.target === editProductModal) {
        editProductModal.hidden = true;
    }
});


editProductForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const id = editProductId.value;
    const name = editProductName.value.trim();
    const rate = editProductRate.value;

    if (!name || !rate) {
        showMessage(editProductMessage, "Nombre y precio son requeridos.", "error");
        return;
    }

    editProductSaveBtn.disabled = true;
    editProductSaveBtn.textContent = "Guardando...";

    try {
        const response = await fetch(`/api/admin/products/${id}`, {
            method: "PATCH",
            headers: apiHeaders(),
            body: JSON.stringify({ name, rate_per_kg: rate }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "No fue posible actualizar el producto");
        }

        editProductModal.hidden = true;
        loadProducts(productSearchInput.value.trim());

    } catch (error) {
        showMessage(editProductMessage, error.message, "error");
    } finally {
        editProductSaveBtn.disabled = false;
        editProductSaveBtn.textContent = "Guardar";
    }
});


initCsrfToken().then((authenticated) => {
    if (authenticated) {
        loadProducts();
    }
});
