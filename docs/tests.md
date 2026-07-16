# Tests

This repo has two main test groups:

- Frontend tests under `tests/frontend/`
- Backend tests under `tests/backend/`

The goal is not exhaustive coverage. Tests should make common regressions easier to diagnose, especially around shared launch state, command generation, route/service behavior, and UI helper logic.

## Common Commands

```powershell
npm test
```

Runs the full frontend suite: JavaScript syntax checks, fast Node unit tests, structural flag-definition validation, flag compatibility checks, module loading checks, and the Playwright smoke test.

```powershell
npm run test:syntax
```

Checks every frontend JavaScript file with `node --check`.

```powershell
npm run test:frontend:modules
```

Loads scripts in the same order as `ui/index.html` inside a Node VM and verifies expected `window.LlamaGui.*` namespaces exist.

```powershell
npm run test:flag-definitions
```

Validates structural invariants in `FLAGS` and `FLAG_CATEGORIES`, including ids, categories, types, defaults, and enum options.

```powershell
npm run test:flags
```

Compares exposed GUI flags against installed `llama-server` and `llama-cli` help output when those binaries are available.

```powershell
npm run test:frontend
```

Runs the Playwright smoke test for browser-level shared-state sync.

```powershell
python -m unittest discover tests -v
```

Runs the backend unittest suite.

## Frontend Tests

Fast Node tests:

- `custom_launch_args_unit.cjs`: custom launch arg tokenization, quote handling, duplicate flag warnings, and preset preservation.
- `launch_args_unit.cjs`: launch argument generation for inert defaults, sampler-related flag behavior, model-source recognition, and sensitive-value redaction.
- `output_cursor_unit.cjs`: generation-aware process output cursor consumption and stale-response rejection.
- `process_lifecycle_unit.cjs`: guarded launch/stop/switch ordering, readiness progression, generation conflicts, out-of-band replacement reconciliation, refused-stop recovery, stop-during-load, and stale transition handling.
- `model_switch_ui_unit.cjs`: two-slot persistence, assignment validation, recoverable slot states, cancellation/failure cleanup, active-runtime display precedence, sidebar slider availability/drag thresholds/markup, safe rendering helpers, and storage fallback.
- `benchmark_args_unit.cjs`: benchmark/perplexity argument adaptation without mutating source presets.
- `chat_rendering_unit.cjs`: markdown escaping, fenced code safety, and safe source-link rendering.
- `sampler_presets_unit.cjs`: sampler preset storage fallback, normalization, applying defaults, and built-in/custom preset shape.
- `hf_download_ui_unit.cjs`: Hugging Face downloader UI helper behavior, request payloads, duplicate overwrite retry, and completion handling.
- `api_tab_unit.cjs`: API endpoint host/port fallback, active-runtime endpoint/model preference, API-key snippet rendering, llama.cpp-compatible CSV parsing, active-auth status, and bearer-header selection.
- `presets_unit.cjs`: preset storage failure fallback, non-default override calculation, imported preset normalization, stale flag filtering, and sensitive Custom Launch Args rejection.
- `module_namespace_unit.cjs`: frontend script load order and exported namespaces.
- `flag_definitions_unit.cjs`: structural validation of flag/category definitions and representative invalid cases.
- `js_syntax_check.cjs`: syntax-only check for frontend JavaScript.

Browser smoke test:

- `flag_sync_smoke.cjs`: serves `ui/`, stubs backend APIs, and verifies shared state across Quick Launch, Configure, Chat, command preview, API authentication, API snippets, remote tunnel UI, sampler presets, custom launch args, and the sidebar Model Switcher's rendered drag/keyboard guards.

Use fast Node tests for focused debugging. Use the Playwright smoke test when a change affects real DOM wiring, mirrored controls, tab sync, command preview rendering, or launch blocking behavior.

## Backend Tests

Backend tests use Python `unittest` and mostly exercise route/service logic without starting the real app server.

- `test_backend_foundation.py`: config parsing, path setup, shared state containers, and context shape.
- `test_routing.py`: router matching for exact and prefix routes.
- `test_http_adapters.py`: request/response helpers and CORS origin handling.
- `test_server_baseline.py`: compatibility wrapper behavior, API dispatch, CORS, static asset versioning, and baseline server helpers.
- `test_services.py`: service-level helpers for install specs, runtime validation, process/auth and active-runtime lifecycle, generation-bound health/stop behavior, downloads, file picker behavior, chat/search helpers, and HF validation.
- `test_extracted_routes.py`: extracted route handlers and larger service flows, including preset secret scrubbing, launch preflight, active-runtime status, health/readiness, process launch/auth parsing, authoritative metrics/slots/chat targets, HF download, tunnel, app update, and lifecycle routes.

Run backend tests after changes under `backend/`, route behavior changes, service helper changes, process management changes, install/update changes, or security-sensitive validation changes.

## When Adding Tests

- Prefer a small unit test when a helper has clear inputs and outputs.
- Prefer Playwright only when browser DOM wiring or cross-tab shared state is the thing being protected.
- Prefer backend unit tests with mocked services over starting real external processes.
- Keep tests specific enough that a failure points to the broken behavior, not just "the app changed."
