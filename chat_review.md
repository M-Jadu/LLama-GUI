# Chat Components Code Review

## Files Reviewed

| File | Size | Role |
|------|------|------|
| `ui/js/chat-ui.js` | 681 lines | Main chat tab logic |
| `ui/js/chat-rendering.js` | 295 lines | Markdown rendering, DOM helpers |
| `ui/js/sampler-presets.js` | 361 lines | Sampler preset CRUD |
| `ui/js/app.js` (chat-related) | ~160 lines | Stats polling, tool lifecycle, chat init |
| `ui/js/flag-core.js` (chat-related) | ~10 lines | Chat template filtering in launch args |
| `ui/js/config-flags-ui.js` (chat-related) | ~20 lines | Chat template flag rendering |
| `ui/js/api-tab.js` (chat-related) | ~6 lines | API endpoint/snippet rendering |
| `ui/js/quick-launch-ui.js` (chat-related) | ~3 lines | Chat template sync |
| `ui/js/app-data.js` (chat-related) | ~8 lines | Chat sampler slider map |
| `backend/routes/chat.py` | 136 lines | Chat completions route |
| `backend/services/chat.py` | 99 lines | Chat proxy helpers |
| `backend/services/web_search.py` | 214 lines | Web search service |

---

## Issues Found

### 1. `chat-rendering.js` — `renderMarkdown` uses `innerHTML` for model output (Medium risk)

**File:** `ui/js/chat-rendering.js`, lines 173-175 and 277

```js
bubble.innerHTML = renderMarkdown(content);
```

The AGENTS.md explicitly says: *"Never use `innerHTML` with user/model content. Use `textContent` for user-facing text. The `renderMarkdown()` function is the one exception for model output."*

This is a documented exception, but it means **any model output can inject arbitrary HTML**. If a model is compromised or the template is mishandled, this is a stored XSS vector. The `rawText` is preserved in `dataset.rawText` for copy purposes, but the rendered HTML is what the user sees.

**Recommendation:** Consider a safer markdown parser (like `DOMPurify` + `showdown` or a custom sanitizer) to strip dangerous attributes/protocols while preserving formatting.

---

### 2. `chat-rendering.js` — `appendChatStreamToken` re-renders the entire bubble on every token (Performance)

**File:** `ui/js/chat-rendering.js`, lines 275-280

```js
function appendChatStreamToken(bubble, token) {
    bubble.dataset.rawText = (bubble.dataset.rawText || "") + token;
    bubble.innerHTML = renderMarkdown(bubble.dataset.rawText);
    // ...
}
```

Every streamed token triggers a full markdown re-parse and DOM re-render of the entire message. For long responses (1000+ tokens), this compounds: each render processes progressively more text.

**Recommendation:** Incremental rendering — append raw text, then only re-render the new portion. Or debounce slightly. This is a low-priority optimization unless users report lag on long responses.

---

### 3. `chat-ui.js` — Conversation history can silently overflow localStorage (Medium risk)

**File:** `ui/js/chat-ui.js`, lines 327-341

```js
function saveConversationsToStorage(list) {
    try {
        localStorage.setItem(CHAT_CONVERSATIONS_STORAGE_KEY, JSON.stringify(list));
    } catch (e) {
        console.warn("Failed to save conversations to localStorage:", e);
    }
}
```

There's no size check or rotation. If a user has many long conversations, localStorage (typically 5-10 MB) can fill up. The `console.warn` is logged but the user gets no feedback.

**Recommendation:** Add a max-conversation limit (e.g., 50) and delete oldest conversations when exceeded. Or add a size check with user notification.

---

### 4. `backend/services/chat.py` — `build_search_context` truncates at 3500 chars (Design note)

**File:** `backend/services/chat.py`, lines 41-42

```python
if len(text) > 3500:
    text = text[:3500].rstrip() + "\n... (source excerpt truncated)"
```

This is a reasonable limit, but 3500 chars per source may be tight for 10 sources (35,000 chars total context). Combined with the system prompt and conversation history, this could exceed the model's context window.

**Recommendation:** No code change needed, but document this limit in the UI or allow users to adjust it.

---

### 5. `backend/services/chat.py` — `get_local_proxy_host` duplicate logic (Code smell)

**File:** `backend/services/chat.py`, lines 72-85 and lines 59-69

The `get_local_interface_addresses` function is called by `get_local_proxy_host`, and the same logic is duplicated in `backend/app.py` (lines 446-455).

**Recommendation:** Extract this into a shared utility and import it from both places.

---

### 6. `backend/services/web_search.py` — `fetch_page_text` silent HTMLParser fallback (Low risk)

**File:** `backend/services/web_search.py`, lines 86-96

```python
def html_to_readable_text(raw_html: str) -> str:
    parser = ReadableHTMLParser()
    try:
        parser.feed(raw_html)
        parser.close()
        return parser.text()
    except Exception:
        text = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", raw_html)
        # ...
```

The `except Exception` silently falls back to regex-based extraction. If the parser fails for a specific page, the fallback may produce different quality output without warning.

**Recommendation:** Log parser failures to stderr so quality issues can be diagnosed.

---

### 7. `app.js` — Stats polling has no error recovery for permanent failures (Medium risk)

**File:** `ui/js/app.js`, lines 676-726

```js
async function pollStats() {
    if (pollStatsActive) return;
    pollStatsActive = true;
    try {
        // ... fetch metrics ...
    } catch (e) {
        // server not ready yet or metrics unavailable
    } finally {
        pollStatsActive = false;
    }
}
```

The catch block silently swallows errors (empty catch body). Unlike the output polling which has a retry counter (`pollOutputFailCount`), stats polling never reports failure to the user or attempts recovery.

**AGENTS.md says:** *"Never use empty `catch` without re-raising or logging. Use `console.debug()` for expected optional failures."*

**Recommendation:** Add `console.debug()` in the catch block per AGENTS.md guidelines.

---

### 8. `backend/routes/chat.py` — `web_sources` sent before content is fully streamed (Minor logic note)

**File:** `backend/routes/chat.py`, lines 68-69

```python
writer.write({"type": "web_sources", "sources": sources})
writer.write({"type": "web_status", "content": "Answering..."})
```

The sources are written to the SSE stream **before** the model actually starts generating. The frontend receives them and renders them, but the assistant's response text hasn't started flowing yet. This means sources appear below the empty bubble before any text.

**Recommendation:** This is arguably fine UX (sources appear while waiting for the model to start). Not a bug.

---

### 9. `backend/app.py` — Chat route is registered without CORS-specific handling (Security note)

**File:** `backend/app.py`, line 843

```python
.add("POST", "/api/chat/completions", chat_routes.completions)
```

The chat route inherits the general CORS handling. It sends the raw llama-server response to the frontend (including SSE), which means any llama-server response headers (including potentially sensitive ones) are forwarded.

**Recommendation:** This is acceptable for a local-first app. No change needed.

---

### 10. `chat-ui.js` — `undoMessage` doesn't handle system prompt separation (Minor logic note)

**File:** `ui/js/chat-ui.js`, lines 285-304

The system prompt is stored separately (in the DOM textarea) and prepended to the messages list at send time (line 157-158), but it's not part of the `chatMessages` array. Undo correctly pops from `chatMessages` only. This is correct behavior, but the system prompt is not part of the conversation history storage either — it's re-read from the DOM on each save.

**Recommendation:** This is correct as-is. The system prompt is a per-conversation setting stored alongside messages, so it's fine.

---

### 11. `app.js` — `restoreRunningState` only restores tool/API host, not full flag state (Minor)

**File:** `ui/js/app.js`, lines 511-548

When the page reloads and finds a running server, it only restores the tool and API host/port from the status. It doesn't restore other flag values from the server's actual configuration.

**Recommendation:** This is out of scope for a code review — it's a design decision for the app's "restore running state" feature.

---

### 12. `chat-ui.js` — `sendMessage` has no rate limiting (Minor note)

**File:** `ui/js/chat-ui.js`, lines 141-142

```js
async function sendMessage(userText) {
    if (chatStreaming || !userText.trim()) return;
```

The `chatStreaming` guard prevents concurrent requests, but there's no debounce on the input field. Users can rapidly press Enter multiple times before the first request completes (the guard works, but the input field autosize happens immediately).

**Recommendation:** The existing guard is actually sufficient. This is a minor note, not a bug.

---

### 13. `backend/routes/chat.py` — Generic `except Exception` with tunnel-aware sanitization (Low risk, acceptable)

**File:** `backend/routes/chat.py`, lines 131-134

```python
except Exception as exc:
    tunnel_active = bool(ctx.state.remote_tunnel.snapshot().get("url"))
    writer.write({"error": {"message": sanitize_sse_error(exc, tunnel_active)}})
    writer.write("[DONE]")
```

This catches all exceptions in the chat proxy. The `sanitize_sse_error` function is used for tunnel security, but this means any unexpected error in the chat flow (e.g., malformed response from llama-server, network issues) is silently sanitized for the client while the real error goes to stderr.

**Recommendation:** This is acceptable per AGENTS.md guidelines. The error is logged to stderr. No change needed.

---

## Summary

| Severity | Count | Details |
|-----------|-------|---------|
| Security | 1 | XSS via `innerHTML` with model output (documented exception, but worth noting) |
| Performance | 1 | Full re-render of markdown on every streamed token |
| Reliability | 3 | localStorage overflow, silent stats errors, parser fallback |
| Code quality | 1 | Duplicate host validation logic |
| Design | 2 | 3500-char truncation, partial state restoration |
| Minor/Notes | 3 | Rate limiting (guard sufficient), web_sources timing, undo/system prompt |
| Acceptable | 1 | Generic exception handling (per AGENTS.md) |

## Actionable Items

1. **Add `console.debug()` to the stats polling catch block** (line 721-722 in `app.js`)
2. **Consider localStorage rotation for conversation history** to prevent silent failures on large histories
3. **Consider incremental markdown rendering** for performance on long responses
4. **Extract duplicate host validation logic** into a shared utility
