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

    var csrfToken = "";
    var pollInterval = null;
    var isConnected = false;
    var lastWeight = null;
    var lastStable = false;

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
    }

    getCsrfToken();

    function setText(el, text) {
        if (el) el.textContent = text;
    }

    function setHidden(el, hidden) {
        if (el) el.hidden = hidden;
    }

    async function apiCall(method, url, body) {
        var opts = {
            method: method,
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
            var result = await apiCall("POST", "/api/scale/connect", { port: port });
            if (!result.ok) {
                var msg = (result.data && result.data.error) || "Error al conectar";
                alert(msg);
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
            var result = await apiCall("POST", "/api/scale/disconnect");
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
                if (r.stable) {
                    setText(stabilityIndicator, "Estable");
                    stabilityIndicator.className = "scale-reading__stability scale-reading__stability--stable";
                    useWeightBtn.disabled = false;
                } else {
                    setText(stabilityIndicator, "Inestable");
                    stabilityIndicator.className = "scale-reading__stability";
                    useWeightBtn.disabled = true;
                }
                if (r.error) {
                    setText(readingError, r.error);
                    setHidden(readingError, false);
                } else {
                    setHidden(readingError, true);
                }
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
        if (!lastWeight || !lastStable) return;
        var weightInput = document.getElementById("weight_kg");
        if (!weightInput) return;
        weightInput.value = lastWeight;
        weightInput.dispatchEvent(new Event("input", { bubbles: true }));
        weightInput.focus();
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
    document.addEventListener("visibilitychange", handleVisibility);

    async function init() {
        await loadPorts();
    }

    init();
})();
