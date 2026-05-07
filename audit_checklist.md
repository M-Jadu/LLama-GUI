# LLama-GUI Code Audit Checklist

## Critical / High Severity

- [x] **#1** Inverted `--no-*` flag logic (`flags.js:133,478` + `app.js:2231`) — **FIXED:** Changed `val === false` to `val === true` for `--no-*` flags in `getLaunchArgs()` so checked = emit `--no-*` flag = feature disabled.

- [x] **#2** TOCTOU race in `launch_process` (`server.py:719-777`) — **FIXED:** Moved entire Popen creation and process assignment inside `process_lock`.

- [x] **#3** `alert()` fires during command preview (`app.js:2251`) — **FIXED:** `getLaunchArgs()` now returns `{ args, error }`. Only `launchLlama()` shows the alert. `updateCommandPreview()` silently uses the args.

- [x] **#4** `mmap` default contradicts llama.cpp (`flags.js:155-156`) — **FIXED:** Changed `default: false` to `default: true`.

- [x] **#5** `context_shift` default contradicts llama.cpp (`flags.js:367-368`) — **FIXED:** Changed `default: false` to `default: true`.

- [x] **#6** `refreshQuickLaunchUI()` overwrites manual unlinking (`app.js:946`) — **FIXED:** Only recalculates `quickLaunchFitCtxLinked` when it's not explicitly `false`.

- [x] **#7** `crypto.randomUUID()` breaks on non-localhost HTTP (`app.js:2966`) — **FIXED:** Added fallback UUID v4 generator using `Math.random()` when `crypto.randomUUID` is unavailable.

- [x] **#8** Null dereference in `updateStatusUI` (`manager.js:110-111`) — **FIXED:** Added early return guard `if (!status) return;` and null check after `fetchJson` in `checkStatus`.

## Medium Severity

- [ ] **#9** Concurrent installs corrupt files (`server.py:1837-1864`)
  - No guard against two simultaneous `/api/install` requests. Both will `shutil.rmtree` and extract concurrently.

- [ ] **#10** No origin check on GET endpoints (`server.py:1671-1793`)
  - All GET API endpoints (`/api/status`, `/api/models`, `/api/output`, etc.) are accessible from any origin. `/api/app-update-status?fetch=true` even triggers `git fetch` as a side effect.

- [ ] **#11** `load_config` doesn't handle malformed JSON (`server.py:219-223`)
  - Corrupted `config.json` causes unhandled `json.JSONDecodeError` → 500 errors everywhere.

- [ ] **#12** `save_config` is not atomic (`server.py:226-228`)
  - Crash during write = corrupted `config.json`.

- [ ] **#13** `restart_gui_server` crashes on non-Windows (`server.py:831`)
  - Uses `subprocess.DETACHED_PROCESS` unconditionally — Windows-only constant.

- [ ] **#14** `multi_enum` changes bypass `setFlagValue` (`app.js:1950-1953`)
  - Directly mutates `flagValues[f.id]` and calls `updateCommandPreview()`, skipping `syncUiAfterSharedStateChange()`. Violates AGENTS.md sync rules.

- [ ] **#15** No debouncing on config search or sampler inputs (`app.js:1417-1424, 1200-1213`)
  - Every keystroke triggers full UI rebuild chains. Typing "0.85" for temperature = 4 full refreshes.

- [ ] **#16** Overlapping `pollOutput` / `pollStats` calls (`app.js:2341, 2355`)
  - No guard against overlapping intervals. Slow responses stack up, causing out-of-order DOM updates.

- [ ] **#17** `localStorage.setItem` has no error handling (`app.js:2948`)
  - `QuotaExceededError` crashes the current operation and leaves UI in inconsistent state.

- [ ] **#18** Null dereference in `fetchReleases` (`manager.js:62-63`)
  - `document.getElementById("release-select")` used without null check.

- [ ] **#19** `loadPreset` silently returns on not-found (`presets.js:404-428`)
  - No user feedback when preset name doesn't exist.

- [ ] **#20** `handlePresetImport` saves empty presets (`presets.js:467-488`)
  - No validation after normalization — garbage files create useless empty presets.

- [ ] **#21** `loadPreset` resets chat template dropdown (`presets.js:417` + `app.js:2091`)
  - `applyFlagValues` clears `selectedChatTemplatePresetValue`, so the dropdown shows wrong selection after loading a preset.

- [ ] **#22** Port validation inconsistency (`app.js:2786`)
  - Uses `Number(flagValues.port) || 8080` which converts port `0` to `8080`, while other locations correctly check `> 0`.

- [ ] **#23** `restartPythonServer` shows success on failure (`manager.js:316-322`)
  - Ignores `waitForServerReady()` return value — always shows "restarted successfully".

- [ ] **#24** `resp.body.getReader()` without null check (`app.js:2815`)
  - `resp.body` can be null, causing unhandled `TypeError`.

## Low Severity

- [ ] **#25** Unused `is_stderr` parameter in `stream_output` (`server.py:706`)

- [ ] **#26** Stale `global process` declaration in `do_POST` (`server.py:1796`)

- [ ] **#27** `.env` prefix match too broad (`server.py:951`) — matches `.envrc`, `.environment`, etc.

- [ ] **#28** `BUILTIN_CHAT_TEMPLATES` has many unexposed templates without documentation (`flags.js:18-70`)

- [ ] **#29** Enum flags labeled "(default)" lack explicit `default` property (`flags.js:188,351,359`)

- [ ] **#30** No debounce on preset search (`presets.js:315-317`)

- [ ] **#31** `savePreset` silently overwrites existing presets (`presets.js:353-377`)

- [ ] **#32** 6 inline `onclick` handlers instead of `addEventListener` (`index.html`)

- [ ] **#33** 5 links missing `rel="noopener noreferrer"` on `target="_blank"` (`index.html`)

- [ ] **#34** 10 missing/unassociated `<label>` elements (`index.html`)

- [ ] **#35** Inconsistent null handling patterns throughout `app.js` (`||` vs `??` vs explicit check)

- [ ] **#36` `stdin` write blocks under lock (`server.py:1921-1931`)

- [ ] **#37** `stop_process` holds lock during `wait()` (`server.py:788-791`)

- [ ] **#38** `preserve_thinking` flag architectural mismatch (`flags.js:331-332`)

- [ ] **#39** Preset name sanitization inconsistency between POST and DELETE (`server.py:1943-1944 vs 2015`)

- [ ] **#40** `gui_server` global has no lock (`server.py:203,797,808`)

- [ ] **#41** Side effects in GET requests (`server.py:1776`)

- [ ] **#42** Requests without Origin/Referer bypass origin check (`server.py:1542`)

- [ ] **#43** `/api/status` leaks full filesystem paths (`server.py:1699`)

- [ ] **#44** Terminated subprocess pipes never explicitly closed (`server.py:757-768`)

- [ ] **#45** `applyFlagValues` doesn't validate incoming data keys (`app.js:2089-2090`)

- [ ] **#46** Duplicate sampler preset logic between Configure and Quick Launch (`app.js:368-600 vs 1146-1190`)

- [ ] **#47** Magic numbers throughout `app.js` (poll intervals, delays, thresholds)

- [ ] **#48** `renderMarkdown` regex can produce broken HTML on nested patterns (`app.js:2524-2553`)

- [ ] **#49** Concurrent `confirmAction` calls corrupt event listeners (`manager.js:582-625`)

- [ ] **#50** `handlePresetImport` no file size validation (`presets.js:467-488`)

- [ ] **#51** `getPresetWarnings` doesn't validate `chat_template_custom` paths (`presets.js:44-54`)

- [ ] **#52** N+1 localStorage reads during preset group render (`presets.js:91-93,232`)

- [ ] **#53** 2 Quick Launch inputs use `type="text"` instead of `type="number"` (`index.html:186,202`)

- [ ] **#54** `<label>Command Preview</label>` used for non-form `<code>` element (`index.html:343`)

- [ ] **#55** Script cache-busting query strings applied inconsistently (`index.html:589-592`)
