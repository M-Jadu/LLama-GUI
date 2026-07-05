(function () {
    "use strict";

    const THEME_STORAGE_KEY = "llama_gui_theme";
    const DEFAULT_THEME = "tokyo";
    const SUPPORTED_THEMES = new Set([DEFAULT_THEME, "cappuccino"]);

    function normalizeTheme(theme) {
        return SUPPORTED_THEMES.has(theme) ? theme : DEFAULT_THEME;
    }

    function getStoredTheme() {
        try {
            return normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY));
        } catch (e) {
            console.debug("Failed to read theme preference", e);
            return DEFAULT_THEME;
        }
    }

    function updateColorScheme(theme) {
        const meta = document.querySelector('meta[name="color-scheme"]');
        if (meta) meta.setAttribute("content", theme === "cappuccino" ? "light dark" : "dark light");
    }

    function applyTheme(theme, options = {}) {
        const nextTheme = normalizeTheme(theme);
        if (nextTheme === DEFAULT_THEME) {
            document.documentElement.removeAttribute("data-theme");
        } else {
            document.documentElement.dataset.theme = nextTheme;
        }
        updateColorScheme(nextTheme);

        if (options.persist) {
            try {
                localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
            } catch (e) {
                console.warn("Failed to save theme preference", e);
            }
        }

        refreshSwitcher(nextTheme);
        return nextTheme;
    }

    function refreshSwitcher(activeTheme = getCurrentTheme()) {
        document.querySelectorAll("[data-theme-option]").forEach(button => {
            const isActive = normalizeTheme(button.dataset.themeOption) === activeTheme;
            button.classList.toggle("active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
    }

    function getCurrentTheme() {
        return normalizeTheme(document.documentElement.dataset.theme || DEFAULT_THEME);
    }

    function init() {
        applyTheme(getStoredTheme());
        document.querySelectorAll("[data-theme-option]").forEach(button => {
            button.addEventListener("click", () => {
                applyTheme(button.dataset.themeOption, { persist: true });
            });
        });
        refreshSwitcher();
    }

    window.LlamaGui = window.LlamaGui || {};
    window.LlamaGui.themeUi = {
        applyTheme,
        getCurrentTheme,
        init,
        storageKey: THEME_STORAGE_KEY,
    };
})();
