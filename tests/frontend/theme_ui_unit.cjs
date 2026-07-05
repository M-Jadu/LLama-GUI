const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..", "..");
const source = fs.readFileSync(path.join(ROOT, "ui", "js", "theme-ui.js"), "utf8");

function makeButton(theme) {
    return {
        dataset: { themeOption: theme },
        classes: new Set(),
        attributes: {},
        listeners: {},
        classList: {
            toggle(name, active) {
                if (active) {
                    this.owner.classes.add(name);
                } else {
                    this.owner.classes.delete(name);
                }
            },
        },
        setAttribute(name, value) {
            this.attributes[name] = value;
        },
        addEventListener(name, handler) {
            this.listeners[name] = handler;
        },
    };
}

function runWithStoredTheme(storedTheme) {
    const buttons = [makeButton("tokyo"), makeButton("cappuccino")];
    for (const button of buttons) {
        button.classList.owner = button;
    }

    const storage = new Map();
    if (storedTheme !== undefined) storage.set("llama_gui_theme", storedTheme);

    const meta = { attributes: {}, setAttribute(name, value) { this.attributes[name] = value; } };
    const documentElement = {
        dataset: {},
        removeAttribute(name) {
            if (name === "data-theme") delete this.dataset.theme;
        },
    };

    const context = {
        window: {},
        console,
        document: {
            documentElement,
            querySelector(selector) {
                return selector === 'meta[name="color-scheme"]' ? meta : null;
            },
            querySelectorAll(selector) {
                return selector === "[data-theme-option]" ? buttons : [];
            },
        },
        localStorage: {
            getItem(key) {
                return storage.has(key) ? storage.get(key) : null;
            },
            setItem(key, value) {
                storage.set(key, value);
            },
        },
    };
    context.window = context;
    vm.createContext(context);
    vm.runInContext(source, context, { filename: "ui/js/theme-ui.js" });
    return { buttons, context, documentElement, meta, storage };
}

{
    const { buttons, context, documentElement, meta } = runWithStoredTheme(undefined);
    context.window.LlamaGui.themeUi.init();

    assert.equal(documentElement.dataset.theme, undefined);
    assert.equal(meta.attributes.content, "dark light");
    assert.equal(buttons[0].attributes["aria-pressed"], "true");
    assert.equal(buttons[1].attributes["aria-pressed"], "false");
}

{
    const { buttons, context, documentElement, meta } = runWithStoredTheme("cappuccino");
    context.window.LlamaGui.themeUi.init();

    assert.equal(documentElement.dataset.theme, "cappuccino");
    assert.equal(meta.attributes.content, "light dark");
    assert.equal(buttons[0].attributes["aria-pressed"], "false");
    assert.equal(buttons[1].attributes["aria-pressed"], "true");
}

{
    const { buttons, context, documentElement, storage } = runWithStoredTheme(undefined);
    context.window.LlamaGui.themeUi.init();
    buttons[1].listeners.click();

    assert.equal(documentElement.dataset.theme, "cappuccino");
    assert.equal(storage.get("llama_gui_theme"), "cappuccino");
    assert.equal(buttons[1].attributes["aria-pressed"], "true");
}

console.log("theme-ui unit checks passed");
