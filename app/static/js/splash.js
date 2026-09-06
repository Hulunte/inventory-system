(function () {
    "use strict";

    var SPLASH_DURATION_MS = 1200;
    var STORAGE_KEY = "agricola_vita_splash_shown";

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function shouldShowSplash() {
        try {
            if (sessionStorage.getItem(STORAGE_KEY) === "1") {
                return false;
            }
        } catch (e) {
            return true;
        }
        return true;
    }

    function markSplashShown() {
        try {
            sessionStorage.setItem(STORAGE_KEY, "1");
        } catch (e) {
            /* storage unavailable */
        }
    }

    function hideSplash(splash) {
        if (!splash) return;
        splash.classList.add("app-splash--hidden");
        setTimeout(function () {
            if (splash.parentNode) {
                splash.parentNode.removeChild(splash);
            }
        }, 500);
    }

    function initSplash() {
        var splash = document.getElementById("app-splash");
        if (!splash) return;

        if (!shouldShowSplash()) {
            if (splash.parentNode) {
                splash.parentNode.removeChild(splash);
            }
            return;
        }

        markSplashShown();

        if (prefersReducedMotion()) {
            hideSplash(splash);
            return;
        }

        setTimeout(function () {
            hideSplash(splash);
        }, SPLASH_DURATION_MS);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initSplash);
    } else {
        initSplash();
    }
})();
