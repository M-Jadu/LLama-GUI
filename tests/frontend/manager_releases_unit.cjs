const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..", "..");
const source = fs.readFileSync(path.join(ROOT, "ui", "js", "manager.js"), "utf8");

function makeElement() {
    let html = "";
    const classNames = new Set();
    const el = {
        children: [],
        value: "",
        textContent: "",
        className: "",
        style: {},
        disabled: false,
        classList: {
            add(...names) {
                names.forEach((name) => classNames.add(name));
                el.className = Array.from(classNames).join(" ");
            },
            remove(...names) {
                names.forEach((name) => classNames.delete(name));
                el.className = Array.from(classNames).join(" ");
            },
            toggle(name, force) {
                const shouldAdd = force === undefined ? !classNames.has(name) : Boolean(force);
                if (shouldAdd) {
                    classNames.add(name);
                } else {
                    classNames.delete(name);
                }
                el.className = Array.from(classNames).join(" ");
                return shouldAdd;
            },
            contains(name) {
                return classNames.has(name);
            },
        },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        addEventListener() {},
        removeEventListener() {},
        querySelectorAll() {
            return [];
        },
    };
    Object.defineProperty(el, "options", {
        get() {
            return this.children;
        },
        configurable: true,
    });
    Object.defineProperty(el, "innerHTML", {
        get() {
            return html;
        },
        set(value) {
            html = String(value || "");
            this.children = [];
            this.value = "";
        },
        configurable: true,
    });
    return el;
}

const elements = new Map();
[
    "release-select",
    "backend-select",
    "installed-backend-summary",
    "version-badge",
    "sidebar-status",
    "sidebar-status-text",
    "installed-info",
    "btn-repair",
    "btn-install",
    "btn-update",
    "release-group",
    "custom-backend-info",
].forEach((id) => elements.set(id, makeElement()));

const fetchCalls = [];
const fetchPayload = [{ tag: "b1294", published: "2024-01-01T00:00:00Z", assets: [] }];

const context = {
    window: { addEventListener() {}, LlamaGui: {} },
    document: {
        createElement: () => makeElement(),
        createTextNode: (text) => ({ textContent: String(text || "") }),
        getElementById: (id) => elements.get(id) || null,
    },
    console,
    fetch: async (url, options) => {
        fetchCalls.push({ url, options });
        return { ok: true, json: async () => fetchPayload };
    },
};
context.window.window = context.window;
vm.createContext(context);
vm.runInContext(source, context, { filename: "ui/js/manager.js" });

(async () => {
    const backendSelect = elements.get("backend-select");
    backendSelect.value = "lemonade-rocm-gfx110X";

    assert.equal(
        context.selectedBackendId(),
        "lemonade-rocm-gfx110X",
        "selectedBackendId should read backend-select value"
    );

    await context.fetchReleases("lemonade-rocm-gfx110X");
    assert.equal(
        fetchCalls[fetchCalls.length - 1].url,
        "/api/releases?backend=lemonade-rocm-gfx110X",
        "fetchReleases(backend) should hit backend-aware releases URL"
    );
    assert.equal(
        fetchCalls[fetchCalls.length - 1].options.cache,
        "no-store",
        "fetchJson should bypass browser cache for API requests"
    );

    await context.fetchReleases();
    assert.equal(
        fetchCalls[fetchCalls.length - 1].url,
        "/api/releases",
        "fetchReleases() without backend should hit default releases URL"
    );

    backendSelect.value = "cpu";
    await context.onBackendChange();
    assert.equal(
        fetchCalls[fetchCalls.length - 1].url,
        "/api/releases?backend=cpu",
        "onBackendChange should refetch releases for the selected backend"
    );

    const availableBackends = [
        { id: "cpu", label: "CPU" },
        { id: "vulkan", label: "Vulkan" },
        { id: "custom", label: "Custom (User-Provided)" },
    ];
    const cpuStatus = {
        installed: true,
        config_stale: false,
        version: "smoke",
        backend: "cpu",
        tag: "smoke",
        running: false,
        available_backends: availableBackends,
        executables: {
            "llama-cli": true,
            "llama-server": true,
        },
    };
    context.updateStatusUI(cpuStatus);
    assert.equal(elements.get("btn-update").disabled, false);

    backendSelect.value = "custom";
    context.onBackendChange();
    context.updateStatusUI(cpuStatus);
    assert.equal(backendSelect.value, "custom");
    assert.equal(elements.get("btn-update").disabled, true);
    assert.equal(elements.get("btn-repair").disabled, true);
    assert.equal(
        elements.get("btn-repair").classList.contains("hidden"),
        false,
        "repair button should be visible but disabled when custom is selected as install target"
    );

    backendSelect.value = "cpu";
    context.onBackendChange();
    context.updateStatusUI(cpuStatus);
    assert.equal(elements.get("btn-update").disabled, false);
    assert.equal(elements.get("btn-repair").classList.contains("hidden"), true);

    const customStatus = {
        installed: true,
        config_stale: false,
        version: "custom",
        backend: "custom",
        tag: "custom",
        running: false,
        available_backends: availableBackends,
        executables: {
            "llama-cli": true,
            "llama-server": true,
        },
    };
    context.updateStatusUI(customStatus);
    assert.equal(backendSelect.value, "custom");
    assert.match(
        elements.get("installed-backend-summary").textContent,
        /Installed backend: Custom/,
        "installed backend summary should render as read-only status"
    );

    backendSelect.value = "vulkan";
    context.onBackendChange();
    context.updateStatusUI(customStatus);
    assert.equal(
        backendSelect.value,
        "vulkan",
        "pending install backend should survive status refresh while installed backend is still custom"
    );
    assert.equal(elements.get("btn-install").textContent, "Install");
    assert.equal(
        elements.get("btn-update").disabled,
        true,
        "custom installed backend should not become auto-updatable because a default backend is selected as install target"
    );

    context.updateStatusUI({ ...customStatus, version: "smoke", backend: "vulkan", tag: "smoke" });
    assert.equal(
        backendSelect.value,
        "vulkan",
        "install target should remain on the newly installed backend once status catches up"
    );
    assert.equal(elements.get("btn-update").disabled, false);

    const pending = new Map();
    context.fetch = async (url, options) => {
        fetchCalls.push({ url, options });
        return new Promise((resolve) => {
            pending.set(url, (payload) => resolve({ ok: true, json: async () => payload }));
        });
    };

    const first = context.fetchReleases("cpu");
    const second = context.fetchReleases("lemonade-rocm-gfx110X");
    pending.get("/api/releases?backend=lemonade-rocm-gfx110X")([
        { tag: "b1294", published: "2024-01-01T00:00:00Z", assets: [] },
    ]);
    await second;
    const releaseSelect = elements.get("release-select");
    assert.equal(releaseSelect.options.length, 1);
    assert.equal(releaseSelect.options[0].value, "b1294");

    pending.get("/api/releases?backend=cpu")([
        { tag: "b9999", published: "2024-01-02T00:00:00Z", assets: [] },
    ]);
    await first;
    assert.equal(
        releaseSelect.options[0].value,
        "b1294",
        "stale release responses should not overwrite the latest backend releases"
    );

    console.log("manager releases unit tests passed");
})().catch((err) => {
    console.error(err);
    process.exit(1);
});
