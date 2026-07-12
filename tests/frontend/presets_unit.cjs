const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..", "..");
const source = fs.readFileSync(path.join(ROOT, "ui", "js", "presets.js"), "utf8");
const storageWarnings = [];
const context = {
    window: {},
    console: {
        ...console,
        debug: () => {},
        warn: (...args) => storageWarnings.push(args),
    },
    localStorage: {
        getItem() {
            throw new Error("storage blocked");
        },
        setItem() {
            throw new Error("storage blocked");
        },
    },
    FLAGS: [
        { id: "temperature", default: 0.8 },
        { id: "ctx_size", default: 4096 },
        { id: "custom_args", default: "" },
    ],
};

context.window = context;
context.window.LlamaGui = {};

vm.createContext(context);
assert.doesNotThrow(() => vm.runInContext(source, context, { filename: "presets.js" }));
assert.doesNotThrow(() => vm.runInContext("markPresetUsed('Blocked Storage Preset')", context));
assert.ok(storageWarnings.length > 0, "storage write failures should be logged without breaking preset actions");

const overrideIds = vm.runInContext(
    "getNonDefaultPresetFlagIds({ flags: { temperature: 0.8, ctx_size: 8192, custom_args: '' } })",
    context
);
assert.equal(JSON.stringify(Array.from(overrideIds)), JSON.stringify(["ctx_size"]));

const normalizeImportedPresetData = context.window.LlamaGui.presets.normalizeImportedPresetData;

const normalized = normalizeImportedPresetData({
    tool: "llama-server",
    model: "model.gguf",
    flags: {
        temperature: 0.72,
        ctx_size: 8192,
        unknown_flag: "drop me",
    },
});

assert.equal(
    JSON.stringify(normalized),
    JSON.stringify({
        tool: "llama-server",
        model: "model.gguf",
        flags: {
            temperature: 0.72,
            ctx_size: 8192,
        },
    })
);

const legacyPlainFlags = normalizeImportedPresetData({
    temperature: 0.33,
    custom_args: "--parallel 4",
    stale_flag: "drop me",
});

assert.equal(
    JSON.stringify(legacyPlainFlags),
    JSON.stringify({
        tool: null,
        model: "",
        flags: {
            temperature: 0.33,
            custom_args: "--parallel 4",
        },
    })
);

const invalidTool = normalizeImportedPresetData({
    tool: "llama-bench",
    model: 123,
    flags: { temperature: 0.9 },
});

assert.equal(
    JSON.stringify(invalidTool),
    JSON.stringify({
        tool: null,
        model: "",
        flags: { temperature: 0.9 },
    })
);

console.log("presets unit tests passed");
