(function () {
    "use strict";

    var portSelect = document.getElementById("scale-port-select");
    var refreshPortsBtn = document.getElementById("scale-refresh-ports");
    var connectBtn = document.getElementById("scale-connect-btn");
    var disconnectBtn = document.getElementById("scale-disconnect-btn");
    var readingArea = document.getElementById("scale-reading-area");
    var weightValue = document.getElementById("scale-weight-value");
    var stabilityIndicator = document.getElementById("scale-stability-indicator");
    var readingError = document.getElementById("scale-reading-error");
    var useWeightBtn = document.getElementById("scale-use-weight-btn");
    var connectionStatus = document.getElementById("scale-connection-status");
    var autoReadSelect = document.getElementById("scale-auto-read");
    var readOnceBtn = document.getElementById("scale-read-once-btn");
    var lastReadingTime = document.getElementById("scale-last-reading-time");
    var autofillSelect = document.getElementById("scale-autofill-weight");

    var csrfToken = "";
    var pollInterval = null;
    var isConnected = false;
    var lastWeight = null;
    var lastStable = false;
    var lastReadingAt = null;
    var workerIsValid = false;
    var MAX_AUTOFILL_AGE_MS = 5000;
    var AUTOFILL_STORAGE_KEY = "inventory.scaleAutofillWeight";
    var automaticRead = sessionStorage.getItem("inventory.scaleAutomaticRead") === "on";
    var storedAutofillPreference = sessionStorage.getItem(AUTOFILL_STORAGE_KEY);
    var autofillEnabled = storedAutofillPreference === null
        ? true
        : storedAutofillPreference === "on";
    if (autoReadSelect) autoReadSelect.value = automaticRead ? "on" : "off";
    if (autofillSelect) autofillSelect.value = autofillEnabled ? "on" : "off";

    var MESSAGES = {
        pyserial_unavailable: "PySerial no disponible",
        no_serial_ports: "No hay puertos disponibles",
        scale_not_connected:
            "Hay puertos disponibles, pero no se ha conectado una bascula.",
        port_in_use:
            "El puerto seleccionado esta siendo utilizado por otra aplicacion.",
        connected: "Bascula conectada.",
        serial_read_error:
            "La bascula esta conectada, pero aun no se reconoce su formato.",
        invalid_configuration:
            "Configuracion serial invalida. Verifique los parametros.",
        unsupported_platform:
            "Plataforma no soportada para lectura serial.",
    };

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        csrfToken = meta ? meta.content : "";
        return csrfToken;
    }

    getCsrfToken();

    async function refreshAdminSession() {
        var response = await fetch("/api/admin/session", {
            method: "GET",
            cache: "no-store",
            credentials: "same-origin",
        });
        var data = await response.json();
        if (!response.ok || !data.authenticated) {
            csrfToken = "";
            return false;
        }
        csrfToken = data.csrf_token || "";
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) meta.content = csrfToken;
        return Boolean(csrfToken);
    }

    function setText(el, text) {
        if (el) el.textContent = text;
    }

    function setHidden(el, hidden) {
        if (el) el.hidden = hidden;
    }

    function resetAutofill() {
        workerIsValid = false;
        if (!autofillSelect) return;
        autofillSelect.disabled = true;
    }

    function readingIsFreshAndStable() {
        return lastWeight !== null
            && lastStable
            && lastReadingAt instanceof Date
            && !Number.isNaN(lastReadingAt.getTime())
            && Date.now() - lastReadingAt.getTime() <= MAX_AUTOFILL_AGE_MS;
    }

    function fillWeightIfEnabled() {
        if (!workerIsValid || !autofillSelect || !autofillEnabled) return;
        if (!readingIsFreshAndStable()) return;
        var weightInput = document.getElementById("weight_kg");
        if (!weightInput) return;
        weightInput.value = lastWeight;
        weightInput.dispatchEvent(new Event("input", { bubbles: true }));
    }

    async function apiCall(method, url, body, requiresFreshCsrf) {
        if (requiresFreshCsrf && !(await refreshAdminSession())) {
            return {
                ok: false,
                status: 401,
                data: { error: "Sesión expirada", code: "admin_session_required" },
            };
        }
        var opts = {
            method: method,
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
        };
        if (body !== undefined) {
            opts.body = JSON.stringify(body);
        }
        var resp = await fetch(url, opts);
        var data = await resp.json();
        return { ok: resp.ok, status: resp.status, data: data };
    }

    function messageForCode(code) {
        return MESSAGES[code] || "Estado desconocido de la bascula.";
    }

    async function loadPorts() {
        try {
            var result = await apiCall("GET", "/api/scale/ports");
            portSelect.textContent = "";

            if (result.status === 503) {
                var opt = document.createElement("option");
                opt.value = "";
                opt.textContent = MESSAGES.pyserial_unavailable;
                portSelect.appendChild(opt);
                connectBtn.disabled = true;
                return;
            }

            if (!result.ok) {
                var opt = document.createElement("option");
                opt.value = "";
                opt.textContent = (result.data && result.data.error) || "Error al cargar puertos";
                portSelect.appendChild(opt);
                connectBtn.disabled = true;
                return;
            }

            var data = result.data || {};
            var code = data.code || "";

            if (!data.available) {
                var opt = document.createElement("option");
                opt.value = "";
                opt.textContent = MESSAGES[code] || MESSAGES.pyserial_unavailable;
                portSelect.appendChild(opt);
                connectBtn.disabled = true;
                return;
            }

            if (!data.ports || data.ports.length === 0) {
                var opt = document.createElement("option");
                opt.value = "";
                opt.textContent = MESSAGES[code] || MESSAGES.no_serial_ports;
                portSelect.appendChild(opt);
                connectBtn.disabled = true;
                return;
            }

            data.ports.forEach(function (p) {
                var opt = document.createElement("option");
                opt.value = p.device;
                opt.textContent = p.device + " - " + p.description;
                portSelect.appendChild(opt);
            });
            connectBtn.disabled = false;
        } catch (e) {
            portSelect.textContent = "";
            var opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "Error al cargar puertos";
            portSelect.appendChild(opt);
            connectBtn.disabled = true;
        }
    }

    async function connect() {
        var port = portSelect.value;
        if (!port) {
            alert("Seleccione un puerto.");
            return;
        }
        connectBtn.disabled = true;
        setText(connectBtn, "Conectando...");
        try {
            var result = await apiCall("POST", "/api/scale/connect", {
                port: port,
                automatic_read: automaticRead,
            }, true);
            if (!result.ok) {
                if (result.status === 401) {
                    alert("Sesión expirada. Inicie sesión nuevamente para conectar la báscula.");
                    return;
                }
                var msg = (result.data && result.data.error) || "Error al conectar";
                alert(msg);
                return;
            }
            updateUiFromStatus(result.data);
        } catch (e) {
            alert("Error de conexion");
        } finally {
            setText(connectBtn, "Conectar");
            connectBtn.disabled = false;
        }
    }

    async function disconnect() {
        try {
            var result = await apiCall("POST", "/api/scale/disconnect", undefined, true);
            if (result.status === 401) {
                alert("Sesión expirada. Inicie sesión nuevamente para desconectar la báscula.");
                return;
            }
            if (!result.ok) {
                alert((result.data && result.data.error) || "Error al desconectar");
                return;
            }
            updateUiFromStatus(result.data);
        } catch (e) {
            alert("Error al desconectar");
        }
    }

    function updateUiFromStatus(status) {
        if (!status) return;

        var code = status.code || "";
        var msg = status.message || messageForCode(code);

        isConnected = status.connected;
        automaticRead = Boolean(status.automatic_read);
        if (autoReadSelect) autoReadSelect.value = automaticRead ? "on" : "off";
        if (readOnceBtn) readOnceBtn.disabled = !isConnected || automaticRead;

        if (isConnected) {
            setText(connectionStatus, msg);
            connectionStatus.className = "scale-section__status scale-section__status--connected";
            setHidden(connectBtn, true);
            setHidden(disconnectBtn, false);
            setHidden(readingArea, false);
            startPolling();
        } else {
            setText(connectionStatus, msg);
            connectionStatus.className = "scale-section__status";
            setHidden(connectBtn, false);
            setHidden(disconnectBtn, true);
            setHidden(readingArea, true);
            stopPolling();
            setText(weightValue, "---");
            setText(stabilityIndicator, "Inestable");
            lastWeight = null;
            lastStable = false;
            lastReadingAt = null;
            setText(lastReadingTime, "Sin lectura");
            useWeightBtn.disabled = true;
        }

        if (status.error && code !== "connected" && code !== "no_serial_ports" && code !== "scale_not_connected") {
            setText(readingError, status.error);
            setHidden(readingError, false);
        } else {
            setHidden(readingError, true);
        }
    }

    async function pollStatus() {
        if (!isConnected) {
            stopPolling();
            return;
        }
        try {
            var result = await apiCall("GET", "/api/scale/status");
            if (result.status === 401) {
                stopPolling();
                isConnected = false;
                setText(connectionStatus, "Sesión expirada. Inicie sesión nuevamente.");
                return;
            }
            if (!result.ok) return;
            var data = result.data;
            if (!data.connected) {
                updateUiFromStatus(data);
                return;
            }
            if (data.last_reading) {
                var r = data.last_reading;
                setText(weightValue, r.weight_kg);
                lastWeight = r.weight_kg;
                lastStable = r.stable;
                lastReadingAt = r.received_at ? new Date(r.received_at) : null;
                if (r.stable) {
                    setText(stabilityIndicator, "Estable");
                    stabilityIndicator.className = "scale-reading__stability scale-reading__stability--stable";
                    useWeightBtn.disabled = false;
                } else {
                    setText(stabilityIndicator, "Inestable");
                    stabilityIndicator.className = "scale-reading__stability";
                    useWeightBtn.disabled = false;
                }
                var readAt = lastReadingAt;
                setText(lastReadingTime, readAt && !Number.isNaN(readAt.getTime())
                    ? `Última lectura: ${readAt.toLocaleTimeString()}`
                    : "Lectura recibida");
                if (r.error) {
                    setText(readingError, r.error);
                    setHidden(readingError, false);
                } else {
                    setHidden(readingError, true);
                }
                fillWeightIfEnabled();
            } else {
                setText(weightValue, "---");
                setText(stabilityIndicator, "Sin lectura");
                useWeightBtn.disabled = true;
            }
        } catch (e) {
            /* ignore poll errors */
        }
    }

    function startPolling() {
        if (pollInterval) return;
        pollInterval = setInterval(pollStatus, 800);
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    function useWeight() {
        if (lastWeight === null) return;
        var weightInput = document.getElementById("weight_kg");
        if (!weightInput) return;
        weightInput.value = lastWeight;
        weightInput.dispatchEvent(new Event("input", { bubbles: true }));
        weightInput.focus();
    }

    function handleWorkerValidated() {
        workerIsValid = true;
        if (autofillSelect) autofillSelect.disabled = false;
        fillWeightIfEnabled();
    }

    function handleWorkerInvalid() {
        resetAutofill();
    }

    function handleMovementRegistered() {
        var weightInput = document.getElementById("weight_kg");
        if (weightInput) weightInput.value = "";
        resetAutofill();
    }

    function changeAutofillPreference() {
        if (!autofillSelect) return;
        autofillEnabled = autofillSelect.value === "on";
        sessionStorage.setItem(AUTOFILL_STORAGE_KEY, autofillEnabled ? "on" : "off");
        fillWeightIfEnabled();
    }

    async function requestSingleReading() {
        if (!isConnected || automaticRead) return;
        readOnceBtn.disabled = true;
        try {
            var result = await apiCall("POST", "/api/scale/read", undefined, true);
            if (!result.ok) alert((result.data && result.data.error) || "No fue posible solicitar la lectura");
        } finally {
            readOnceBtn.disabled = !isConnected || automaticRead;
        }
    }

    async function changeAutomaticRead() {
        automaticRead = autoReadSelect.value === "on";
        sessionStorage.setItem("inventory.scaleAutomaticRead", automaticRead ? "on" : "off");
        if (!isConnected) return;
        var result = await apiCall("POST", "/api/scale/automatic", { enabled: automaticRead }, true);
        if (!result.ok) {
            alert((result.data && result.data.error) || "No fue posible cambiar el modo de lectura");
            automaticRead = false;
            autoReadSelect.value = "off";
        }
        if (readOnceBtn) readOnceBtn.disabled = !isConnected || automaticRead;
    }

    function handleVisibility() {
        if (document.hidden) {
            stopPolling();
        } else if (isConnected) {
            startPolling();
        }
    }

    if (refreshPortsBtn) refreshPortsBtn.addEventListener("click", loadPorts);
    if (connectBtn) connectBtn.addEventListener("click", connect);
    if (disconnectBtn) disconnectBtn.addEventListener("click", disconnect);
    if (useWeightBtn) useWeightBtn.addEventListener("click", useWeight);
    if (readOnceBtn) readOnceBtn.addEventListener("click", requestSingleReading);
    if (autoReadSelect) autoReadSelect.addEventListener("change", changeAutomaticRead);
    if (autofillSelect) autofillSelect.addEventListener("change", changeAutofillPreference);
    if (useWeightBtn) useWeightBtn.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && lastWeight !== null) {
            event.preventDefault();
            useWeight();
        }
    });
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("inventory:worker-validated", handleWorkerValidated);
    window.addEventListener("inventory:worker-invalid", handleWorkerInvalid);
    window.addEventListener("inventory:movement-registered", handleMovementRegistered);

    async function init() {
        await loadPorts();
    }

    init();
})();
