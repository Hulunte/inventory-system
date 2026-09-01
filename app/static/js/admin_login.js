const loginForm = document.getElementById("login-form");
const loginPassword = document.getElementById("password");
const loginMessage = document.getElementById("login-message");
const loginSubmit = document.getElementById("login-submit");

let csrfToken = "";

async function initCsrfToken() {
    try {
        const response = await fetch("/api/admin/session");
        const data = await response.json();
        csrfToken = data.csrf_token || "";
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            metaTag.setAttribute("content", csrfToken);
        }
    } catch (e) {
        // CSRF token unavailable, login will fail
    }
}

initCsrfToken();

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const password = loginPassword.value;

    if (!password) {
        showMessage(loginMessage, "La contraseña es requerida.", "error");
        return;
    }

    loginSubmit.disabled = true;
    loginSubmit.textContent = "Ingresando...";

    try {
        const response = await fetch("/api/admin/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({ password }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Error al iniciar sesión");
        }

        window.location.href = "/admin";

    } catch (error) {
        showMessage(loginMessage, error.message, "error");
    } finally {
        loginSubmit.disabled = false;
        loginSubmit.textContent = "Ingresar";
    }
});

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `form__message form__message--${type}`;
    element.hidden = false;
}
