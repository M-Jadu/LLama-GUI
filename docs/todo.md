# TODO

## Code Review Checklist

### Architecture

- [ ] **Decompose `app.js` (3,190 lines)** into focused feature modules (chat, quick-launch, hf-download, tunnel, stats, output-polling, toast, conversation-history).
- [ ] **Split `backend/app.py` (819 lines)** into separate handler, service wiring, and proxy modules. Extract metrics host validation, port parsing, and arch normalization out of the Handler class.
- [ ] **Wrap `flags.js` in an IIFE** with a namespaced export (e.g. `window.LlamaGui.flags`) to match the encapsulation pattern used by `flag-core.js` and `config-flags-ui.js`.
- [ ] **Remove direct `FLAGS` global reference** in `config-flags-ui.js:580` and route it through the dependency injection pattern used everywhere else in that module.

### Security

- [ ] **Escape `message` in `showToast()`** (`app.js:2282`) — `toast.innerHTML` interpolates `message` without escaping. Switch to `textContent` or run through `escapeHtml()`.
- [ ] **Validate URL scheme on search source chips** (`app.js:2583`) — `chip.href = source.url` should reject `javascript:` and other dangerous schemes before assignment.
- [ ] **Add direct unit tests for `get_local_proxy_host()`** (`backend/services/chat.py`) — the SSRF gate for metrics/chat proxy has only indirect coverage.
- [ ] **Escape single quotes in `escapeHtml()`** (`app.js:2299`) — currently only escapes `&`, `<`, `>`, `"`. Add `'` → `&#39;` for defense in depth.
- [ ] **Replace `innerHTML` interpolation in `config-flags-ui.js:168-172`** with `textContent`/`createElement` for category headers to eliminate a latent XSS vector.

### Code Quality — Duplication

- [ ] **Extract shared sampler preset dropdown helper** — `createSamplerPresetControls()` and `refreshQuickSamplerPresetSelect()` duplicate ~40 lines each populating sampler preset `<select>` elements.
- [ ] **Extract shared sampler save/delete logic** — Configure tab and Quick Launch tab have near-identical save and delete handler code.
- [ ] **Consolidate host/port extraction** — The same 3–4 line pattern appears at 5 locations in `app.js`. Route all through the existing `getServerBaseUrl()` helper.
- [ ] **Extract `resetServerUI()` function** — The 8-line server-not-running UI cleanup block is copy-pasted at 4 locations.
- [ ] **Share KV cache type enum options** in `flags.js` — The same 9-option list is duplicated 4 times for `cache_type_k`, `cache_type_v`, `draft_cache_type_k`, `draft_cache_type_v`.

### Code Quality — Error Handling

- [ ] **Reduce silent error swallowing in `app.js`** — 19 try/catch blocks all swallow errors. At minimum, log unexpected errors to the console instead of silently discarding them.
- [ ] **Add `isNaN` guard after `parseInt`/`parseFloat`** in `config-flags-ui.js` numeric input handlers — `parseInt("abc")` stores `NaN` as the flag value.
- [ ] **Narrow `except Exception` in `llama_manager.py:install_release()`** — Distinguish network errors from disk errors to give users actionable messages.
- [ ] **Add warning for invalid tool values** in `getFlagsForTool()` (`flags.js`) — silently returns `[]` for invalid tools including `undefined`.

### Code Quality — Other

- [ ] **Validate `gpu_layers` numeric input** — Defined as `type: "text"` in `flags.js` to support `"auto"`/`"all"`, but custom numeric values pass with no validation.
- [ ] **Rename colliding category/flag IDs** in `flags.js` — `"conversation"`, `"lora"`, and `"grammar"` exist in both `FLAG_CATEGORIES` and `FLAGS`, creating a maintenance hazard.
- [ ] **Extract magic numbers into named constants** — debounce `200`ms, poll intervals `300`/`3000`ms, toast duration `4300`ms, etc.

### Testing — Frontend

- [ ] **Add `flag-core.js` unit tests** — cover `setFlagValue`/`setMultipleFlagValues` for all data types, `getLaunchArgs()` for bool/int/float/text/enum/multi_enum, `false_flag` handling, inert-default filtering, and tool switching.
- [ ] **Add `flags.js` validation tests** — verify flag IDs, types, categories, defaults, enum options, CLI flag names, and chat template preset structure.
- [ ] **Add `presets.js` tests** — cover save, load, delete, export, import, group-by-model rendering, and search.
- [ ] **Add `config-flags-ui.js` tests** — cover search/filtering, expand/collapse state, type-specific input builders, and input restoration.
- [ ] **Add `manager.js` tests** — cover `fetchJson()`, release fetching, installation progress UI, and app update flow.
- [ ] **Add `flag-validation.js` tests** — cover duplicate ID detection, invalid category/type/enum checks, and CLI flag collision detection.
- [ ] **Add `app.js` feature tests** — cover tab switching, conversation history CRUD, markdown rendering, Quick Launch profiles, and toast lifecycle.
- [ ] **Split `flag_sync_smoke.cjs` into named test cases** — current single `main()` function makes diagnosing failures harder.

### Testing — Backend

- [ ] **Test `download_file()` and archive extraction** — `download_file()`, `extract_zip_file_flat()`, `extract_tar_member_flat()`, `extract_archive_flat()` have no test coverage.
- [ ] **Test `install_release()` end-to-end** — the full install workflow (download, hash verify, extract, config save) is untested.
- [ ] **Test `stream_output()` and `_build_process_env()`** — output buffering/trimming and PATH/LD_LIBRARY_PATH/DYLD setup are untested.
- [ ] **Test `stop_process()` and `launch_process()` happy path** — only the missing-runtime error path is currently tested.
- [ ] **Test `_start_remote_tunnel_worker()`** — tunnel URL regex, stderr parsing, and error state transitions are untested.
- [ ] **Test `download_hf_file()` chunked download** — cancellation via `model_download_cancel` event and partial file cleanup are untested.
- [ ] **Test concurrent state mutation** — verify `install_in_progress` and `model_download_in_progress` locks prevent race conditions under concurrent requests.
- [ ] **Split `test_extracted_routes.py`** (~1,826 lines, 101 tests) into per-route or per-service test files.

---

## Custom Launch Args Input

Goal: add an advanced Configure-tab input where users can enter raw llama.cpp flags that are not yet represented in `ui/js/flags.js`. These args should be appended to the generated launch arguments so Llama GUI can temporarily support new or renamed upstream flags without waiting for a full UI flag-definition update.

### Intended Behavior

- Add a `Custom Launch Args` textarea to the Configure tab near the command preview.
- Treat the value as shared launch state, not as a per-tab scratch field.
- Save and load the value with presets by storing it in the preset `flags` object under a reserved key such as `custom_args`.
- Include the value in preset import/export without requiring a new preset schema version.
- Update command preview immediately when the textarea changes.
- Include parsed custom args in `flagCore.getLaunchArgs()`.
- Show a clear warning that custom args may conflict with configured UI flags and should only be used when the user understands the llama.cpp option they are adding.

### Implementation Plan

1. Add shared state support in `ui/js/flag-core.js`.
   - Keep the raw textarea value in `flagValues.custom_args`.
   - Let existing `setFlagValue()`, `collectFlagValues()`, and `applyFlagValues()` handle it naturally.
   - Do not add `custom_args` to `FLAGS`, because it is not a real llama.cpp flag definition.

2. Add a parser for custom args.
   - Parse shell-like tokens instead of splitting on spaces.
   - Support quoted values so JSON-style args can work, for example:
     `--chat-template-kwargs '{"preserve_thinking":true}'`
   - Return a structured error for unmatched quotes or malformed escapes.
   - Keep the parser frontend-only unless backend launch handling later needs the same logic.

3. Append custom args during launch argument generation.
   - In `getLaunchArgs()`, generate normal known flags first.
   - Parse `flagValues.custom_args`.
   - If parsing fails, return the existing launch args plus an error message so command preview and launch can block safely.
   - Append parsed custom args after known UI-generated flags.
   - Keep model arg handling unchanged unless testing proves llama.cpp requires custom args after `-m`.

4. Render the Configure-tab control in `ui/js/config-flags-ui.js` or directly in `ui/index.html`.
   - Prefer a simple static textarea in `ui/index.html` near the command preview.
   - Wire its `input` event to `window.LlamaGui.flagCore.setFlagValue("custom_args", value || undefined)`.
   - Add a refresh path so loading presets updates the textarea.
   - Display parser errors close to the textarea and in command-preview status when possible.

5. Preserve existing preset behavior in `ui/js/presets.js`.
   - No schema change should be required because preset flags already preserve unknown keys.
   - Confirm save, update, load, import, and export keep `custom_args`.
   - If preset warnings are expanded later, consider warning when a preset includes custom args.

6. Add verification coverage.
   - Extend `tests/frontend/flag_sync_smoke.cjs` to enter custom args and confirm:
     - command preview includes the parsed args
     - `flagCore.getLaunchArgs().args` includes the parsed tokens
     - `flagCore.collectFlagValues().custom_args` preserves the raw text
     - loading/applying preset-shaped state restores the textarea
   - Add a parser-error smoke case for unmatched quotes.
   - Run `node --check` on touched frontend scripts.
   - Run the Playwright smoke test from the repo root with the existing `NODE_PATH` setup.

### Open Design Notes

- Default persistence: save custom args with presets.
- Recommended placement: Configure tab only, near command preview.
- Recommended append order: after known UI flags and before the model arg, unless runtime testing shows llama.cpp expects otherwise.
- Security posture: this should not execute shell commands by itself, but it can enable dangerous llama.cpp flags such as tool execution, so the UI should label it as advanced.
- Future cleanup: once a custom arg becomes common or stable upstream, move it into `ui/js/flags.js` as a normal typed control.
