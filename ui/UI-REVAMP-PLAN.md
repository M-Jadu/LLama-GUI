# UI Revamp Plan — Sidebar Navigation

**Reference Mockup:** `ui/mockup-sidebar-nav.html`
**Status:** Implemented

---

## Overview

Replace the current top-tab layout with a fixed left sidebar navigation and apply a comprehensive visual overhaul. The mockup at `ui/mockup-sidebar-nav.html` is the single source of truth for the target design.

All changes are CSS-first and HTML-structural. No JS framework is introduced. The existing `app.js` state management, flag system, and API wiring remain untouched — only DOM structure, class names, and styles change.

---

## Phase 1: Design Token Foundation

Create a shared token layer that both the new CSS and any future components can reference.

### 1.1 Create `ui/css/tokens.css`

Extract from the mockup's `:root` block:

| Token Category | Tokens |
|---|---|
| **Colors** | `--bg-base`, `--bg-surface`, `--bg-raised`, `--bg-elevated`, `--bg-hover`, `--fg`, `--fg-muted`, `--fg-bright`, `--fg-faint`, `--accent`, `--accent-hover`, `--accent-subtle`, `--accent-border`, plus green/red/yellow/cyan/magenta semantic colors with `-subtle` and `-border` variants |
| **Radii** | `--radius-xs` (4px), `--radius-sm` (6px), `--radius-md` (10px), `--radius-lg` (14px) |
| **Shadows** | `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-accent` |
| **Spacing** | `--space-1` through `--space-6` (4px scale) |
| **Typography** | `--font`, `--mono` (switch from Manrope to Inter, keep JetBrains Mono) |
| **Transitions** | `--ease-fast`, `--ease-med` |

### 1.2 Add `prefers-reduced-motion` override

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition-duration: 0s !important; animation-duration: 0s !important; }
}
```

### 1.3 Add `<meta name="color-scheme" content="dark">` to `index.html`

Prevents white flash on load.

---

## Phase 2: SVG Icon System

Replace every emoji / HTML entity icon with inline Lucide-style SVGs.

### 2.1 Create `ui/css/icons.css` (optional helper)

Define `.icon`, `.icon-sm`, `.icon-lg` sizing classes and the shared SVG stroke/fill rules. These are currently embedded in the mockup's `<style>` block.

### 2.2 Icon mapping — every location that needs updating

| Current | Replacement SVG (Lucide name) | Locations |
|---|---|---|
| Tab labels (text only) | `download`, `zap`, `sliders`, `message-square`, `code`, `save` | Tab nav items |
| `&#x21bb;` refresh buttons | `refresh-cw` | Model refresh, release refresh |
| `&#x2715;` clear/close | `x` | Search clear, sidebar close |
| `&#x229E;` / `&#x229F;` expand/collapse | `chevrons-down` / `chevrons-up` | Config controls |
| `&#x2398;` copy | `copy` | Server URL copy buttons |
| `&#128172;` chat | `message-square` | Chat tab, history panel toggle |
| `&#9881;` gear | `settings` | Settings sidebar toggle |
| `&#128465;` trash | `trash-2` | Delete buttons |
| `&#10010;` plus | `plus` | New chat |
| `&#10148;` send | `send` | Chat send |
| `&#9632;` stop | `square` | Stop buttons |
| `&#8630;` undo | `undo` | Undo button |
| `&#8635;` redo | `refresh-cw` | Regenerate button |
| `&#9679;` dot | CSS dot (6px circle) | Status badges |

### 2.3 Card header icons

Add colored icon badges to Quick Launch cards:

| Card | Icon | Color class |
|---|---|---|
| Model | `box` | `icon-blue` |
| Launch Mode | `zap` | `icon-green` |
| Memory & Fit | `cpu` / `memory-stick` | `icon-cyan` |
| Sampler | `sliders` | `icon-magenta` |

---

## Phase 3: HTML Structural Changes — `index.html`

This is the largest phase. The outer page structure changes from:

```
header > h1 + badges
nav.tabs > button.tab * 6
div.tab-content * 6
```

To:

```
div.app-shell
  aside.sidebar
    div.sidebar-brand > logo + title
    nav.sidebar-nav
      div.nav-section-label + button.nav-item * 6
    div.sidebar-footer > status badge
  div.main-content
    div.page-header > h1 + subtitle + actions
    div.section-panel * 6
```

### 3.1 Remove old header

- Delete the `<header>` element and its gradient/glow styling
- Brand info moves into `.sidebar-brand`

### 3.2 Remove old tab nav

- Delete `<nav class="tabs">` and all `<button class="tab">` elements
- Replace with `<aside class="sidebar">` containing `<nav class="sidebar-nav">`

### 3.3 Rename tab-content panels

- Change `.tab-content` → `.section-panel`
- Change `.tab-content.active` logic to `.section-panel` with `display:none` toggled by JS
- The active panel starts visible; all others start `display:none`

### 3.4 Wrap in app-shell

```html
<div class="app-shell">
  <aside class="sidebar">...</aside>
  <div class="main-content">...</div>
</div>
```

### 3.5 Add page headers inside each section

Each section panel gets its own `.page-header` with title + subtitle + contextual actions. These replace the old `<h2>` that was inside each `.panel`.

### 3.6 Quick Launch card structure

Each card gains a `.card-header` with a `.card-icon` badge and `.card-kicker` step label. The existing content stays but uses the new form classes.

### 3.7 Add mobile hamburger toggle

```html
<button class="mobile-toggle" onclick="...">
    <svg>hamburger icon</svg>
</button>
```

Hidden above 900px, visible below. Toggles `.sidebar.open`.

---

## Phase 4: CSS Rewrite — `ui/css/style.css`

### 4.1 Import tokens

```css
@import url('tokens.css');
```

Remove the old `:root` variable block and the Google Fonts `@import` for Manrope. Add the Inter import instead.

### 4.2 Delete old rules to replace

| Old selector | Action |
|---|---|
| `header`, `header h1`, `header::after`, `.header-status` | Delete |
| `.tabs`, `.tab`, `.tab.active` | Delete |
| `.tab-content`, `.tab-content.active` | Delete |
| `.panel` | Rewrite to `.card` semantics |
| Badge `.badge` | Rewrite with pill + border style from mockup |
| `.btn`, `.btn-primary`, `.btn-danger` | Update colors/shadows to token values |
| Form inputs | Update to use `--bg-raised` base, `--accent` focus ring |
| `.quick-card` | Rename to `.card`, update bg/shadow/hover |
| `.accordion-*` | Update colors to token values |
| Chat section | Update colors to token values, use new avatar/bubble styles |

### 4.3 Add new rules

| Selector | Purpose |
|---|---|
| `.app-shell` | Flex layout for sidebar + main |
| `.sidebar` | Fixed left sidebar, 220px width |
| `.sidebar-brand` | Logo + title row |
| `.sidebar-nav` | Flex column nav items |
| `.nav-item` | Button-style nav with hover/active states |
| `.nav-item.active::before` | Left accent bar indicator |
| `.nav-section-label` | Uppercase section dividers in nav |
| `.sidebar-footer` | Status badge at bottom |
| `.main-content` | `margin-left: var(--sidebar-w)` content area |
| `.page-header` | Title + subtitle + actions row |
| `.card`, `.card-header`, `.card-icon` | Elevated card with icon badge |
| `.card-kicker` | Step label (Step 1, Step 2...) |
| `.toggle`, `.toggle-track`, `.toggle-thumb` | CSS-only toggle switch |
| `.seg-control`, `.seg-btn` | Segmented control component |
| `.code-block::before` | Dollar sign prefix |
| `.progress-fill::after` | Shimmer animation |
| `.toast-container`, `.toast` | Fixed toast notification |
| `.launch-preview` | Accent-bordered launch card |
| `.mobile-toggle` | Hamburger button for mobile |
| `.modal-overlay` | Backdrop blur + scale-in modal |

### 4.4 Stats bar update

```css
.stats-bar {
    left: var(--sidebar-w);  /* offset from sidebar */
    /* ... rest stays similar */
}
```

### 4.5 Responsive breakpoint

At 900px and below:
- `.sidebar` slides off-screen (`transform: translateX(-100%)`)
- `.main-content` gets `margin-left: 0`
- `.stats-bar` gets `left: 0`
- `.mobile-toggle` becomes visible
- Quick Launch grid collapses to single column
- Chat panels stack vertically

---

## Phase 5: JavaScript Updates — `ui/js/app.js`

### 5.1 Tab switching logic

Replace the current tab switching (which toggles `.tab-content.active`) with sidebar nav switching:

```js
// Old: button.tab[data-tab] -> div.tab-content#tab-{name}
// New: button.nav-item[data-section] -> div.section-panel#section-{name}
```

The `switchTab()` function needs to:
1. Hide all `.section-panel` elements
2. Show the target panel
3. Remove `.active` from all `.nav-item`
4. Add `.active` to the clicked nav item
5. Close the sidebar on mobile (`sidebar.classList.remove('open')`)

### 5.2 Update element ID references

The JS currently references IDs like:
- `#tab-install` → `#section-install`
- `#tab-quick-launch` → `#section-quick-launch`
- `#tab-configure` → `#section-configure`
- `#tab-chat` → `#section-chat`
- `#tab-api` → `#section-api`
- `#tab-presets` → `#section-presets`

Grep for all `#tab-` references in `app.js` and update them.

### 5.3 Remove header badge update code

The old header had `#version-badge` and `#process-badge`. These move to the sidebar footer. Update the JS selectors that set their text/visibility.

### 5.4 Toast notifications (optional enhancement)

Add a `showToast(message, type)` helper that creates a `.toast` element inside `.toast-container`, auto-removes after 4 seconds. This can replace some of the inline status box updates.

---

## Phase 6: Chat Tab Polish

### 6.1 Avatar icons

Replace emoji avatars with SVG icons:
- User: monogram "U" or `user` icon in accent circle
- Assistant: `zap` icon in magenta circle

### 6.2 Code blocks in chat

Add a copy button to `<pre>` blocks inside chat bubbles.

### 6.3 Empty state

Style the `.chat-empty` state with the mockup's `.empty-state` pattern (large icon badge, title, description, suggestion chips).

---

## Phase 7: Modal & Toast Polish

### 7.1 Modal upgrade

- Add `backdrop-filter: blur(4px)` to `.modal-backdrop`
- Add scale+fade entry animation
- Update border-radius and padding to match token values

### 7.2 Toast system

- Add a `.toast-container` fixed element
- Implement `showToast(message, type)` for transient success/error/info messages
- Use alongside existing status boxes (not a full replacement)

---

## File Change Summary

| File | Action |
|---|---|
| `ui/css/tokens.css` | **NEW** — Design token definitions |
| `ui/css/icons.css` | **NEW** — Icon helper classes (optional, can stay in style.css) |
| `ui/css/style.css` | **REWRITE** — New token imports, sidebar layout, component styles, delete old rules |
| `ui/index.html` | **RESTRUCTURE** — Sidebar shell, new section panels, SVG icons, toggle switches, page headers |
| `ui/js/app.js` | **UPDATE** — Tab switching logic, ID references, optional toast helper |
| `ui/js/manager.js` | **MINOR** — Any element ID references that changed |
| `ui/js/presets.js` | **MINOR** — Any element ID references that changed |
| `ui/js/flags.js` | **NO CHANGE** — Pure data, no DOM |
| `ui/mockup-sidebar-nav.html` | **KEEP** — Reference mockup |

---

## Implementation Order

1. **Phase 1** — tokens.css (no visual change yet)
2. **Phase 3** — HTML restructure (breaks layout temporarily)
3. **Phase 4** — CSS rewrite (restores layout with new design)
4. **Phase 2** — SVG icons (swap all emoji/entities)
5. **Phase 5** — JS updates (tab switching, ID refs)
6. **Phase 6** — Chat polish
7. **Phase 7** — Modal & toast polish

Phases 2-4 can overlap since they're in different files. Phase 5 must come after 3 since IDs change.

---

## Verification Checklist

After each phase, verify:

- [ ] All 6 sections (Install, Quick Launch, Configure, Chat, API, Presets) render correctly
- [ ] Sidebar navigation switches between sections
- [ ] Sidebar active state matches current section
- [ ] Mobile: hamburger toggle shows/hides sidebar
- [ ] Quick Launch cards show correct step labels and icons
- [ ] Configure accordion expand/collapse still works
- [ ] Chat messages send/receive/stream correctly
- [ ] Stats bar appears at bottom, offset from sidebar
- [ ] Modal confirmations still appear and function
- [ ] All existing JS features work (preset save/load, sampler presets, HF download, etc.)
- [ ] No console errors
- [ ] Responsive at 900px and 700px breakpoints
