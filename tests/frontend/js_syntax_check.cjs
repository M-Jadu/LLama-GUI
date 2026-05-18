const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..", "..");
const TARGET_DIRS = [
    path.join(ROOT, "ui", "js"),
    path.join(ROOT, "tests", "frontend"),
];

function collectJsFiles(dir) {
    const files = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...collectJsFiles(fullPath));
        } else if (entry.isFile() && /\.(?:js|cjs)$/.test(entry.name)) {
            files.push(fullPath);
        }
    }
    return files;
}

const files = TARGET_DIRS.flatMap(collectJsFiles).sort();
const failures = [];

for (const file of files) {
    const result = spawnSync(process.execPath, ["--check", file], {
        cwd: ROOT,
        encoding: "utf8",
    });
    if (result.status !== 0) {
        failures.push({
            file: path.relative(ROOT, file),
            output: (result.stderr || result.stdout || "").trim(),
        });
    }
}

if (failures.length) {
    for (const failure of failures) {
        console.error(`Syntax check failed: ${failure.file}`);
        console.error(failure.output);
    }
    process.exit(1);
}

console.log(`syntax check passed for ${files.length} frontend JavaScript files`);
