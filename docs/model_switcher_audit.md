# Model Switcher Diff Audit

Review date: 2026-07-16  
Scope: working-tree Model Switcher implementation vs `docs/model_switcher_plan.md`  
Reviewer notes: read-only code audit of backend, frontend lifecycle/UI, tests, and docs. Manual two-model hardware QA was not re-run.

## Overall assessment

The implementation is solid and largely matches the plan.

- Backend active-runtime identity, generation-bound stop/health, pure preflight, and launch-context normalization are coherent.
- Frontend lifecycle guard, pure target preflight, Quick Launch card, and Chat/API/metrics integration follow the intended contracts.
- Secrets handling looks correct: slot storage stores only preset-name references; fingerprints reject API keys; remote model URLs are redacted in runtime metadata.
- Automated coverage is broad. Remaining plan gaps are mostly intentional manual QA (two distinct GGUFs, live external API cutover, tunnel cutover).

No high-severity security, process-lock, or double-process issues were identified.

## Medium — fix before ship

### 1. Cancelled switches are stored as failures

`ui/js/model-switch-ui.js` `handleSwitch()` treats any `ok === false` outcome as a slot failure, including lifecycle cancellations (`cancelled: true`) caused by user Stop during loading or a superseded transition.

```javascript
const outcome = await switchSlot(slotId);
if (outcome && outcome.ok === false) {
    slotFailures[slotId] = outcome.error || "The model switch failed.";
}
```

Process-lifecycle unit tests already assert cancelled launches return `{ ok: false, cancelled: true }` without an error message. The card then shows **Failed** / “The model switch failed.” after an intentional Stop.

**Fix:** ignore `outcome.cancelled`, or only set `slotFailures` when `outcome.error` is present and the result is not cancelled.

### 2. Stale `slotFailures` never clear for the other slot

`delete slotFailures[slotId]` only runs for the slot currently being switched. A failed Model B remains **Failed** after a later successful switch to Model A (or after unrelated recovery) because standby/active checks run after the failure branch:

```javascript
else if (failure) state = "failure";
else if (activeIdentity && drifted) state = "drift";
else if (activeIdentity) state = "active";
else state = "standby";
```

**Fix:** clear all `slotFailures` on a successful switch, and/or clear a slot’s failure when that slot becomes healthy standby/active again.

### 3. Clearing a slot assignment while that runtime is still Active drops the Active badge

In `buildSlotViews()`, empty preset name becomes `unassigned` before `activeIdentity` is considered. If the user clears Model A in Manage slots while the live runtime still belongs to switcher slot `a`, the badge becomes **Unassigned** instead of **Active**.

Missing-preset-after-delete is intentional per the plan. Empty assignment while an active-runtime identity still owns that slot is inconsistent.

**Fix:** if `activeIdentity` is true, prefer active / drift / loading over unassigned.

## Low / edge

### 4. `hasLaunchModelArg` omits `-mu` / `--model-url`

Backend preflight accepts remote model URL flags (`_REMOTE_MODEL_VALUE_FLAGS` includes `-mu` / `--model-url`). Frontend `hasLaunchModelArg()` in `ui/js/app.js` does not:

```javascript
return token === "-m" || token === "-hf" || token === "--model" || token === "--hf-repo"
    || token.startsWith("-m=") || token.startsWith("-hf=")
    || token.startsWith("--model=") || token.startsWith("--hf-repo=");
```

A switcher preset whose only model source is `--model-url` in custom args fails client-side before preflight. There is currently no dedicated model-url flag in the UI definitions, so this mainly hits advanced custom-arg presets.

### 5. Switch clears the terminal immediately

`switchModelSlot()` invalidates output by stopping polling **and** calling `clearOutput()`. The plan requires stopping old-generation output/stats polling, but not necessarily wiping the previous server log before stop/launch. A failed target switch then has less of Model A’s diagnostic context.

**Preferable:** stop polling only; clear (or retain last N lines) when the new generation’s output starts.

### 6. Health probe deliberately omits API key

Backend tests assert launch API keys are not forwarded to the local `/health` probe. That matches current llama.cpp health behavior. If a future monkey-patched or differently configured build gates `/health`, readiness would map to `error` and switches would never mark Active. Already captured in the plan’s risk table; no code change required unless defensive auth is desired.

## Not bugs (verified OK)

| Concern | Result |
|---|---|
| Direct `flagValues` mutation | Changes go through setters / `applyFlagValues` / pure `buildLaunchArgs` |
| Unsafe rendering of preset/model text | Card uses `textContent` / `createElement` |
| Slot storage secrets | Only `{ version, slots: { a\|b: { preset } } }`; reload strips unexpected keys |
| Manual launch never attributes a slot | Empty launch context → `source: "manual"`; UI requires `source === "model-switcher"` |
| Preflight before stop | Target resolve/preflight runs before stop and apply |
| Non-server tools block switching | UI `other-tool` state + lifecycle refusal |
| Chat / API prefer active host·port·alias | `chat-ui.js`, `api-tab.js`, metrics routes, and chat route updated |
| Command preview / memory estimate stay on pending config | Pending flag-core path retained |
| Generation races / stop-during-load | Covered by `process_lifecycle_unit.cjs` |
| Script load order | Matches `docs/directory.md` and `ui/index.html` |
| Fingerprint canonicalization | Server-side sorted JSON + SHA-256; frontend does not invent digests |

## Plan items still open (not code defects)

- Manual A → B → A with two distinct small GGUF models
- Live external API cutover predictability during hard cutover
- Remote tunnel URL remains stable and targets the replacement server after readiness

These are already tracked as incomplete acceptance scenarios in `docs/model_switcher_plan.md` Phase 6.

## Severity summary

| Severity | Issue |
|---|---|
| Medium | Cancelled switch recorded as Failed badge |
| Medium | Stale `slotFailures` stick on idle slots |
| Medium | Clear assignment while Active loses Active badge |
| Low | Missing `-mu` / `--model-url` in `hasLaunchModelArg` |
| Low | Terminal wipe at switch start |
| Info | Health probe unauthenticated by design |

No high-severity security, lock, or double-process issues spotted in this pass. Core switch sequence matches the plan.

## Recommended follow-up

1. Patch the three medium UI/lifecycle presentation issues.
2. Optionally align `hasLaunchModelArg` with backend model-source flags and soften terminal clearing on switch.
3. Leave two-model/hardware and live API/tunnel checks on the remaining Phase 6 manual QA list.

## Primary files reviewed

- `ui/js/process-lifecycle.js`
- `ui/js/model-switch-ui.js`
- `ui/js/app.js`
- `ui/js/flag-core.js`
- `ui/js/presets.js`
- `ui/js/chat-ui.js`
- `ui/js/api-tab.js`
- `ui/js/benchmark-ui.js`
- `ui/js/manager.js`
- `backend/services/process_manager.py`
- `backend/routes/process.py`, `status.py`, `metrics.py`, `chat.py`
- `backend/state.py`, `backend/app.py`
- Focused tests under `tests/frontend/` and `tests/backend/`
- Docs: `docs/model_switcher_plan.md`, `docs/directory.md`, `docs/tests.md`, `README.md`
