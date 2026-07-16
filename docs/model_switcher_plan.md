# Two-Slot Model Switcher Implementation Plan

## Purpose

Add a compact Model Switcher card to Quick Launch that lets the user assign two
saved `llama-server` presets and explicitly switch the single managed
`llama-server` process between them.

The two slots are configuration standby slots. They do not keep two models
loaded, run two servers, route requests automatically, or provide llama-swap
semantics.

This document is the source of truth for implementation scope, sequencing,
acceptance criteria, decisions, and progress. Update the checklists and append a
progress-log entry whenever a phase changes state.

## Status Summary

| Phase | Status | Evidence |
|---|---|---|
| 0. Contracts and test scaffolding | Done | Contracts and focused fixtures landed with Phases 1-2 |
| 1. Authoritative active-runtime state | Done | Backend suite: 369 passed |
| 2. Pure preset preflight and slot storage | Done | Focused frontend tests and 369 backend tests passed |
| 3. Shared switch lifecycle and readiness | Done | 376 backend tests, lifecycle unit tests, and Playwright smoke passed |
| 4. Quick Launch Model Switcher UI | Done | Focused card tests and Playwright smoke passed |
| 5. Cross-feature integration hardening | Done | Full frontend suite and 377 backend tests passed |
| 6. Full verification and documentation | In progress | Automated verification complete; two-model/API/tunnel manual QA pending |
| 7. Audit remediation | Done | Full frontend suite passed; final re-review found no remaining P0-P2 issues |

Allowed phase statuses: `Not started`, `In progress`, `Blocked`, `Done`.

## Scope

### In scope

- Exactly two named slots: Model A and Model B.
- Each slot references one existing saved full launcher preset.
- Only presets whose tool is `llama-server` can be assigned.
- One managed llama.cpp subprocess at a time.
- Explicit user-initiated switching.
- Target validation before stopping the active server.
- Launch-time runtime identity exposed through `/api/status`.
- Health-based loading and ready states.
- Safe interruption of the built-in Chat stream.
- Correct coordination with Configure, Quick Launch, Chat, API, metrics,
  output polling, remote tunnel proxying, and Benchmarking.
- Persistent slot assignments without duplicating preset flag state.

### Out of scope

- Keeping two models resident in RAM or VRAM.
- Multiple simultaneous llama-server processes.
- Automatic routing based on an API request's `model` field.
- Queuing, draining, TTL eviction, load balancing, or rollback.
- Per-slot API keys.
- More than two slots.
- llama-swap or native llama.cpp router integration.
- Automatically saving unsaved Configure changes into a slot.

## Product and Architecture Decisions

1. The switcher remains in Quick Launch; it does not get a new navigation tab.
2. The card is collapsible. Slot assignment is handled by its `Manage slots`
   control rather than duplicating the Presets tab.
3. A slot stores a preset reference and small display metadata only. It never
   stores its own `flagValues`, custom arguments, or API key.
4. `flagCore` remains the only pending launch-state object. All visible
   Configure, Quick Launch, and Chat controls continue to use its setters.
5. The backend is authoritative for the active runtime. Editable frontend state
   must never determine which slot is marked Active.
6. Switches are hard cutovers. Built-in Chat is aborted first; external clients
   may see a temporary connection failure while the new model loads.
7. A failed target launch leaves the server stopped with the target preset
   visible and its output available. There is no automatic rollback.
8. The current session API key is preserved across switches. Slot data and
   presets do not persist secrets.
9. Existing chat history is preserved. A non-request message divider records
   the model transition without injecting a new message into the model prompt.
10. A running `llama-cli`, `llama-bench`, or `llama-perplexity` process disables
    the switcher. Switching must never stop a non-server process.

## State Contracts

### Pending configuration

Pending configuration is the current `flagCore` tool, selected model, and flag
values. It drives Configure, Quick Launch controls, command preview, memory
estimate, and the next manual launch.

### Active runtime

Active runtime is a launch-time snapshot owned by the backend and cleared when
the tracked process stops or is reaped. `/api/status` should expose a safe
shape similar to:

```json
{
  "active_runtime": {
    "generation": 12,
    "tool": "llama-server",
    "model": "models/qwen.gguf",
    "alias": "qwen-local",
    "host": "127.0.0.1",
    "port": 8080,
    "source": "model-switcher",
    "slot": "a",
    "preset": "Qwen Balanced",
    "preset_fingerprint": "safe-nonsecret-fingerprint"
  }
}
```

Do not retain or expose raw launch arguments. Model, alias, host, and port
should be derived or validated by the backend. Slot and preset context is
display metadata and must be strictly normalized.

### Slot assignments

Use a versioned frontend storage record:

```json
{
  "version": 1,
  "slots": {
    "a": { "preset": "Qwen Balanced" },
    "b": { "preset": "Gemma Creative" }
  }
}
```

Recommended storage key: `llama_gui_model_switcher_slots_v1`.

Preset names are references, not embedded snapshots. Missing or invalid
references must remain visible as recoverable UI states. Storage failures
should fall back to session-only assignments with a visible warning and a
`console.warn()` diagnostic.

### Normalization limits

- `slot`: exactly `a` or `b` when `source` is `model-switcher`; otherwise no
  slot is stored.
- `source`: exactly `manual` or `model-switcher`; omitted launch context
  defaults to `manual`.
- `preset`: trimmed printable text, 1-128 characters for switcher launches;
  empty for manual launches.
- `preset_fingerprint`: lowercase SHA-256 hex (`[0-9a-f]{64}`) computed from
  normalized non-sensitive preset data; empty for manual launches.
- `alias`: derived from launch arguments by the backend and limited to 128
  characters in status output.
- `model`: derived from the recognized model/Hugging Face launch argument by
  the backend and limited to 1024 characters in status output.
- Control characters are rejected from client-supplied launch context. Raw
  arguments and API keys are never copied into active-runtime metadata.

### Readiness response

`GET /api/llama/health?expected_generation=N` returns HTTP 200 for every successfully evaluated local
runtime state so the frontend can poll one stable JSON contract:

```json
{
  "ready": false,
  "state": "starting",
  "generation": 12,
  "expected_generation": 12,
  "message": "Waiting for llama-server"
}
```

Allowed `state` values are `stopped`, `starting`, `loading`, `ready`, `error`,
`failed`, and `superseded`.

- No tracked `llama-server`: `stopped`.
- Tracked process but the local socket is not accepting connections:
  `starting`.
- Upstream `/health` returns 503 with its documented Loading model error:
  `loading`.
- Upstream `/health` returns 200: `ready` and `ready: true`.
- An unexpected non-loading upstream response is `error` with a sanitized
  message.
- A nonzero process exit before readiness is `failed`; an expected generation
  that no longer owns the process is `superseded`.

The response includes the active runtime generation so stale health responses
can be ignored. Metrics are never used as a readiness signal. The current
[llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
confirms `/health` returns 503 while loading and 200 when ready.

## Required Switch Sequence

1. Acquire a frontend transition guard and disable all competing launch, stop,
   benchmark, and switch controls.
2. Resolve the target slot's saved preset.
3. Preflight the target without mutating `flagCore` or stopping the active
   process:
   - preset exists;
   - tool is `llama-server`;
   - model source is present and structurally valid;
   - custom launch arguments parse successfully;
   - generated arguments contain a model source;
   - executable/runtime dependencies remain available;
   - local model paths exist when they can be validated locally.
4. Abort and settle any built-in Chat stream.
5. Stop main output and stats polling for the previous runtime generation.
6. Request process stop and inspect the returned `stopped` result.
7. Confirm `/api/status` reports no active process. If the old process survived,
   abort the transition and do not launch the target.
8. Apply the already-validated target preset through the shared preset and
   `flagCore` setter paths.
9. Launch with normalized switch context containing slot, preset name, and safe
   preset fingerprint.
10. Begin fresh output polling using the returned output cursor.
11. Poll a dedicated local llama-server health proxy until the target is ready,
    exits, or the user stops it. A slow-load notice may appear, but an arbitrary
    UI timeout must not kill a process that is still loading.
12. Refresh backend status and mark the slot Active only when health succeeds
    and active-runtime identity matches the transition.
13. Reset stats counters/baselines, update Chat/API/runtime endpoint consumers,
    add the visual chat transition divider, and release the transition guard.

Any exception releases the guard, refreshes authoritative status, preserves
diagnostic output, and renders a recoverable error state.

## Implementation Phases

### Phase 0 — Contracts and test scaffolding

Goal: establish state shapes and reusable test fixtures before lifecycle code.

- [x] Add shared test fixtures for Model A and Model B full presets.
- [x] Add expected active-runtime and slot-storage shapes to tests.
- [x] Decide and document the exact readiness response contract.
- [x] Decide normalization limits for slot id, preset name, alias, and model
      display strings.
- [x] Add empty unit-test files or focused test sections for the new modules.
- [x] Confirm no source files outside the planned ownership list need changes.

Exit criteria:

- State contracts are represented by failing or pending focused tests.
- No production behavior has changed.

### Phase 1 — Authoritative active-runtime state

Goal: distinguish the running process from editable pending configuration.

Expected primary files:

- `backend/state.py`
- `backend/services/process_manager.py`
- `backend/routes/process.py`
- `backend/routes/status.py`
- `tests/backend/test_backend_foundation.py`
- `tests/backend/test_services.py`
- `tests/backend/test_extracted_routes.py`

Tasks:

- [x] Add safe active-runtime state protected by the existing process lock.
- [x] Add a monotonically changing runtime generation or equivalent identity.
- [x] Parse/normalize launch-time model, alias, host, and port.
- [x] Accept optional normalized launch context for source slot and preset.
- [x] Set active-runtime state only after `Popen` and state wiring succeed.
- [x] Clear it in normal stop, failed launch cleanup, natural-process reap, and
      lifecycle cleanup paths.
- [x] Expose it through `/api/status` without raw arguments or secrets.
- [x] Preserve backward compatibility for ordinary `/api/launch` callers.
- [x] Test manual launches, switch-context launches, stop, crash/reap, and
      partial-launch failure cleanup.

Exit criteria:

- `/api/status` always reports either a coherent tracked runtime or `null`.
- Editing frontend flag state cannot change active-runtime identity.
- Backend tests pass.

### Phase 2 — Pure preset preflight and slot storage

Goal: validate a target before stopping the current server and store only two
preset references.

Expected primary files:

- `ui/js/flag-core.js`
- `ui/js/presets.js`
- new `ui/js/model-switch-ui.js` or a focused storage/helper module
- `backend/services/process_manager.py`
- `backend/routes/process.py`
- `tests/frontend/launch_args_unit.cjs`
- `tests/frontend/presets_unit.cjs`
- new focused frontend unit test
- backend process route/service tests

Tasks:

- [x] Extract a pure launch-argument builder that accepts explicit tool, model,
      and flags; keep `getLaunchArgs()` as the current-state wrapper.
- [x] Reuse the existing custom-argument parser, omission rules, template
      mapping, warnings, redaction, and sensitive-value rules.
- [x] Expose focused preset lookup/normalization/apply helpers through the
      existing `window.LlamaGui.presets` namespace.
- [x] Add a non-mutating backend launch-preflight helper and route for
      executable/runtime/model-path checks that can be performed safely.
- [x] Ensure preflight permits the currently occupied target port because the
      old server is expected to release it during switching.
- [x] Implement versioned two-slot persistence with storage-failure fallback.
- [x] Detect missing presets, unsupported tools, invalid args, absent model
      sources, and duplicate assignments.
- [x] Compute a stable preset fingerprint from normalized non-sensitive preset
      data.
- [x] Verify slot storage never contains API keys or full flags.

Exit criteria:

- Model B can be completely preflighted while Model A and the visible pending
  state remain untouched.
- Invalid B never initiates a stop.
- Focused frontend and backend tests pass.

### Phase 3 — Shared switch lifecycle and readiness

Goal: provide one race-resistant process-control path used by the existing UI
and the switcher.

Expected primary files:

- new `ui/js/process-lifecycle.js`
- `ui/js/app.js`
- `ui/js/chat-ui.js`
- `ui/js/output-cursor.js` only if its public contract needs extension
- backend metrics/health route or a focused new health route
- corresponding frontend/backend unit tests

Tasks:

- [x] Move or wrap launch/stop orchestration behind a focused lifecycle
      namespace; do not add new global functions to `app.js`.
- [x] Route existing main Launch and Stop controls through the same controller.
- [x] Add a single transition guard that prevents double launch/switch/stop.
- [x] Make stop return and honor authoritative success/failure.
- [x] Export an awaitable `chatUi.abortActiveStream()` method.
- [x] Stop or invalidate old output and stats polling generations before stop.
- [x] Track and cancel the delayed initial stats poll as well as its interval.
- [x] Add a local, authenticated readiness proxy for llama-server `/health`.
- [x] Distinguish `starting`, `loading`, `ready`, `stopping`, and `failed`.
- [x] Do not mark a slot Active merely because its process was spawned.
- [x] Handle user Stop during loading without launching another process.
- [x] Preserve output cursor epoch behavior across rapid stop/start.
- [x] Reset model-specific stats baselines after a successful switch.

Exit criteria:

- A → B → A works without overlapping subprocesses or stale UI updates.
- Stop failure, early process exit, double click, and slow load are recoverable.
- Existing manual Launch and Stop behavior remains intact.

### Phase 4 — Quick Launch Model Switcher UI

Goal: implement the approved compact card without duplicating Presets or
Configure state.

Expected primary files:

- `ui/index.html`
- `ui/js/model-switch-ui.js`
- `ui/js/quick-launch-ui.js`
- `ui/js/app.js` for dependency injection only
- `ui/css/style.css`
- `docs/directory.md` for script loading order
- frontend namespace, syntax, unit, and Playwright tests

Tasks:

- [x] Add the full-width collapsible card below the Quick Launch heading.
- [x] Render two slots with model label, preset, GGUF name, and authoritative
      state badge.
- [x] Implement `Manage slots` with existing-preset selection only.
- [x] Reuse safe `textContent` rendering for all preset/model strings.
- [x] Provide states for unassigned, standby, active, loading, missing preset,
      invalid preset, modified since launch, failure, and other tool running.
- [x] Disable the active slot's action and provide one clear target Switch
      action.
- [x] Explain that Standby means configuration-ready, not memory-resident.
- [x] Keep the card usable when collapsed and on narrow/mobile layouts.
- [x] Add keyboard focus, ARIA state, and disabled-state coverage.
- [x] Wire only through injected preset, lifecycle, status, and `flagCore`
      dependencies.
- [x] Register new scripts in canonical order and update documentation.

Exit criteria:

- The card matches existing Quick Launch styling and remains compact.
- Configure, Quick Launch, Chat samplers, and command preview still share one
  state object.
- Module-load, syntax, unit, and browser smoke tests pass.

### Phase 5 — Cross-feature integration hardening

Goal: make every existing runtime consumer use active-runtime data correctly.

Expected primary files:

- `ui/js/api-tab.js`
- `ui/js/chat-ui.js`
- `ui/js/app.js`
- `ui/js/remote-tunnel-ui.js` only if rendering needs adjustment
- `ui/js/benchmark-ui.js`
- relevant focused tests and `tests/frontend/flag_sync_smoke.cjs`

Tasks:

- [x] Make Chat's request model prefer active launch alias/model while running.
- [x] Make Chat, metrics, slots, server links, and API snippets prefer the
      active runtime host/port while running.
- [x] Keep command preview and memory estimate tied to pending configuration.
- [x] Preserve session API authentication across preset application and launch.
- [x] Confirm the remote tunnel remains running and adopts the new backend
      target after launch.
- [x] Show a temporary unavailable/loading state to API and Chat UI consumers.
- [x] Add a visual-only chat divider after a successful model change.
- [x] Disable switching for `llama-cli`, `llama-bench`, and
      `llama-perplexity`.
- [x] Refresh the card after manual Launch, manual Stop, natural exit, page
      reload, preset update, preset deletion, and preset import.
- [x] Ensure a manual/custom launch is never falsely attributed to a slot.
- [x] Surface preset drift without changing the running snapshot.

Exit criteria:

- Runtime consumers cannot drift to pending host, port, alias, or model values.
- Tunnel and API behavior is understood during the cutover window.
- Existing features remain functional in the integration smoke test.

### Phase 6 — Full verification and documentation

Goal: complete regression testing, manual QA, and user-facing documentation.

Tasks:

- [x] Run `node --check` on every touched JavaScript file immediately after its
      edits.
- [x] Run focused frontend unit tests after each phase.
- [x] Run `npm run test:frontend:modules` after script/namespace changes.
- [x] Run `npm run test:frontend` after shared-state and DOM wiring changes.
- [x] Run `npm test` for the complete frontend suite.
- [x] Run `python -m unittest discover tests -v` after backend changes.
- [ ] Manually test with two small GGUF models on the installed backend.
- [x] Verify command previews before and after each switch through focused launch-argument tests.
- [x] Verify a loading model can be stopped safely through lifecycle tests.
- [x] Verify secrets do not appear in storage, status, output, or commands.
- [x] Verify browser reload and normal Stop/Launch recovery through lifecycle and browser smoke tests.
- [x] Update `docs/directory.md`, `docs/tests.md`, README screenshots/text if
      warranted, and this plan's final status.
- [x] Perform a final diff review for lifecycle races, direct `flagValues`
      mutation, unsafe rendering, sensitive data, and missing failure tests.

Exit criteria:

- All automated suites pass.
- Manual A → B → A verification passes.
- Documentation and screenshots match shipped behavior.
- The final review has no unresolved high-severity findings.

### Phase 7 — Audit remediation

Goal: fix the confirmed post-implementation UI state and model-source gaps
without changing the backend process, generation, readiness, or security
contracts.

Expected primary files:

- `ui/js/model-switch-ui.js`
- `ui/js/flag-core.js`
- `ui/js/app.js`
- `tests/frontend/model_switch_ui_unit.cjs`
- `tests/frontend/launch_args_unit.cjs`
- `tests/frontend/flag_sync_smoke.cjs` only if needed for terminal DOM behavior

Tasks:

- [x] Treat lifecycle cancellation as a neutral interruption. A user Stop or
      superseded transition must not create a `Failed` slot state.
- [x] Clear historical failures for both slots after any successful switch,
      and clear the affected slot's failure when its assignment changes.
- [x] Keep genuine switch failures visible and retryable until a successful
      switch or relevant assignment change makes them stale.
- [x] Give authoritative active-runtime identity precedence over an empty slot
      assignment so clearing an assignment cannot hide the live Active,
      Loading, or runtime-failure state.
- [x] When an active assignment has been cleared, display the launched
      runtime's safe preset/model snapshot while keeping Manage slots genuinely
      unassigned. Return to the normal Unassigned view after the runtime stops.
- [x] Preserve the intentional `Missing` state when a non-empty assigned preset
      is deleted; do not reinterpret that case as Active merely because the
      runtime was launched from the same slot.
- [x] Centralize frontend model-source detection with launch-argument helpers
      and align it with the backend-recognized flags: `-m`, `--model`, `-hf`,
      `--hf-repo`, `-mu`, and `--model-url`, including `--flag=value` forms.
- [x] Update launch/readiness copy that currently mentions only local models or
      Hugging Face repos so advanced model URLs are not described as invalid.
- [x] During a switch, stop old-generation output polling without clearing the
      visible terminal. Clear it only when the replacement generation has
      successfully started and fresh output polling is attached.
- [x] Preserve the old terminal plus the appended error when preflight, stop,
      or launch fails before a replacement generation is accepted.
- [x] Add focused regressions for cancelled switches, cross-slot failure
      cleanup, assignment-change cleanup, active-but-cleared display, the
      deleted-preset Missing state, separate and equals-form model URL flags,
      and terminal preservation/clear timing.
- [x] Run `node --check` for every touched JavaScript file, the focused Model
      Switcher and launch-argument tests, `npm test`, and `git diff --check`.

Exit criteria:

- Intentional cancellation never renders as failure.
- No failure badge survives a later successful switch or a changed assignment.
- The card continues to represent the authoritative live runtime after its
  assignment is cleared, without silently recreating that assignment.
- Every model-source form accepted by backend preflight passes the same
  frontend launch guard.
- Failed cutovers retain the prior diagnostic log; accepted replacement
  generations begin with a clean terminal and their own output.
- No backend changes are required, and the complete frontend suite passes.

## Required Acceptance Scenarios

- [x] A → B → A happy path (automated lifecycle simulation).
- [x] Invalid B does not stop A.
- [x] Missing B model does not stop A.
- [x] Stop refusal prevents B launch.
- [x] B spawns but exits before ready and is never marked Active.
- [x] Slow B remains Loading and can be stopped.
- [x] Double Switch click launches once.
- [x] Switching during built-in Chat aborts cleanly.
- [ ] External API callers fail predictably during cutover and recover after
      readiness succeeds.
- [x] Page reload restores the correct active-runtime and slot state.
- [x] Manual Stop clears the Active badge.
- [x] Manual/custom Launch is not falsely attributed to a slot.
- [x] Benchmark and CLI processes disable switching.
- [x] Preset update shows drift without altering the running snapshot.
- [x] Preset deletion produces a recoverable Missing state.
- [x] Different preset host/port values update all runtime consumers.
- [ ] Remote tunnel URL remains stable and targets the replacement server.
- [x] API key remains session-wide and is never persisted in slot data.
- [x] Old output/metrics responses cannot overwrite the new runtime UI.
- [x] Mobile layout and keyboard navigation remain usable.

## Known Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Windows process termination takes time or fails | Honor backend stop result and tracked-process state; never use an arbitrary sleep as proof of exit. |
| GPU resources are briefly unavailable after exit | Wait for confirmed process exit and report target launch failure; do not hide it with automatic retries. |
| Preset names are not immutable ids | Treat deleted/changed references as explicit UI states and compare a safe fingerprint to the launched snapshot. |
| Another browser acts during a frontend switch | Backend process lock remains authoritative; refresh status after every mutation and fail safely if another process appeared. |
| Health endpoint behavior differs by llama.cpp version | Verify against the installed supported build and keep readiness logic isolated behind one backend helper. |
| Metrics are disabled in a preset | Never use the metrics endpoint as the readiness signal. |
| External requests are active during cutover | Document hard-cutover semantics; do not claim draining or queueing support. |
| localStorage is unavailable | Use session-only slot assignments and warn; presets remain backend-managed. |

## Progress Log

Append entries; do not rewrite prior history.

| Date | Phase | Change | Validation | Result / Next step |
|---|---|---|---|---|
| 2026-07-16 | Planning | Created the scoped implementation plan, contracts, phased checklist, acceptance scenarios, and risk register. | Reviewed against current preset, process, Chat, API, metrics, output, tunnel, and benchmark architecture. | Ready to begin Phase 0 after plan approval. |
| 2026-07-16 | Phase 1 | Added authoritative active-runtime state, monotonic generations, strict switch launch context, safe launch metadata, status exposure, and complete cleanup behavior. | `python -m unittest discover tests -v` — 365 passed; `git diff --check` passed. | Phase 1 complete; begin pure preset preflight and slot storage. |
| 2026-07-16 | Phases 0 and 2 | Added contract fixtures, pure launch construction, reusable preset normalization/application, non-mutating launch preflight with safe fingerprints, and versioned two-slot preset-reference storage. | Focused model-switcher, preset, launch-args, and namespace tests passed; backend suite: 369 passed; `git diff --check` passed. | Contracts, preflight, and storage are complete; begin shared lifecycle and readiness. |
| 2026-07-16 | Phase 3 | Added generation-bound health and stop contracts, a guarded frontend lifecycle controller, awaitable Chat abort, stale-status protection, cancellable output/stats epochs, and routed existing Launch/Stop through readiness-aware orchestration. | Lifecycle unit tests passed; backend suite: 376 passed; Playwright flag-sync smoke passed. | Shared lifecycle complete; build and connect the Quick Launch card. |
| 2026-07-16 | Phases 4 and 5 | Added the compact accessible two-slot card, preset management and drift states, end-to-end preflight/switch wiring, active-runtime API/Chat/metrics consumers, benchmark lifecycle coordination, loading states, and visual Chat transitions. | `npm test` passed, including 41-file syntax, focused units, 151 installed flag checks, and Playwright; backend suite: 377 passed. | UI and integrations complete; finish documentation, review, and manual hardware caveat. |
| 2026-07-16 | Phase 6 | Completed documentation, full diff review, and race/security hardening for canonical fingerprints, signed model URLs, refused stops, stale status/output generations, observer failures, and out-of-band benchmark adoption. | `npm test` passed; Playwright smoke passed; 151 installed flag checks passed; backend suite: 379 passed; `git diff --check` passed. | Automated verification is complete. Manual two-distinct-model A → B → A plus live external-API/tunnel cutover QA remain pending because the workspace has only one GGUF model (14.4 GB), not two small test models. |
| 2026-07-16 | Phase 7 planning | Validated `docs/model_switcher_audit.md` against the current slot view precedence, lifecycle cancellation results, switch output hooks, frontend launch guard, and backend model-source flags. | Confirmed all three medium findings, the model-URL gap, and the terminal-preservation improvement; confirmed the unauthenticated health probe remains intentional. | Await approval, then implement the focused frontend remediation and regression tests before committing. |
| 2026-07-16 | Phase 7 | Began the approved audit remediation for slot failure state, active-but-cleared display, model URL recognition, and terminal preservation. | Implementation and focused regressions in progress. | Complete the frontend fixes, run focused tests, then run the full suite and review the diff. |
| 2026-07-16 | Phase 7 | Completed the audit remediation, including neutral cancellation with retained prior failures, authoritative healthy-runtime cleanup, active-but-cleared runtime display, model URL recognition, delayed terminal clearing, and single failure notification across direct and exception stop paths. | `npm.cmd test` passed: syntax for 41 frontend files, all focused units, 23-module loading, 151 flag definitions and installed compatibility checks, and Playwright smoke; `git diff --check` passed; final independent re-review found no P0-P2 issues. | Phase 7 complete. Phase 6 remains open only for the previously documented two-model, external API, and tunnel manual QA. |
