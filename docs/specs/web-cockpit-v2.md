# Web Cockpit v2 — "Hybrid HUD" redesign (Wave 1)

> Builds on `web-cockpit-design.md`. That doc defined a deliberately *restrained* surface; this one
> re-cinematics it (eDEX + JARVIS energy) and adds the live capabilities the first version couldn't
> show. Backend changes are strictly additive; the carefully-built core + its test suite are intact.

## Why
The v1 cockpit was a passive chat feed over a calm "engineering instrument" theme. It hid the
backend's strengths: the watchlist showed bare ticker names (no prices), the proactivity engine was
invisible ("Nothing worth surfacing"), and there was no weather/news/file capability. This redesign
makes the cockpit a live command center while keeping the central reading column readable.

## Direction (decided with the user)
- **Hybrid HUD** — readable center feed wrapped in cinematic live widgets; glow/motion/density up.
- **File ops: anywhere on disk** (no sandbox) — gated by a mandatory token off-loopback.
- **Wave 1**: live stocks + charts, goal-driven feed. **Wave 2**: news globe, weather.

## Theme (`frontend/src/theme.css`, `motion.ts`)
Full rewrite to the "solid instrument bolted to a blueprint board" system. Identity rule:
**glow is a STATE (focus / owned / live / alert), never a finish.** Solid 4px-radius panel faces,
corner reticles, IBM Plex Mono as the instrument typeface, arc-reactor cyan + rationed gold, a
no-glow reading column (`--reading-*`). New recipes: `.hud-reticle(-x)`, `.hud-ticker`, `.hud-spark`,
`.telemetry`, `.readout`, `.hud-bar`, `.hud-hex`, `.status-pill`, `.reactor`. New motion helpers:
`reactorBreathe`, `reactorThinking`, `pillPulse`, `barFill`, `sparkDraw`, `tickerScroll`, `frameScan`
— all collapse under `useReducedMotion()`. Variable/class names stayed stable, so nothing broke.

## Backend (additive — `+58` tests, suite green at 414)
| Capability | Endpoint | Notes |
|---|---|---|
| `quotes(symbols?)` → `Quote[]` | `GET /api/quotes` | Reuses `MarketsConnector`. **Read-only inspector: emits NO signal** (a poll would flood reflection fuel). One quote per requested symbol, in order; unknown ticker simply absent; never invents a price. |
| `symbol_search(q)` → `SymbolMatch[]` | `GET /api/symbol-search?q=` | Finnhub `/search` via a new `MarketsConnector.search()`. Query-relevance ranking (exact ticker → ticker-prefix → description-starts-with → plain US listing) so "apple"→AAPL, not a pineapple co. `CachingConnector.__getattr__` transparently exposes it. No signal. |
| `goal_feed()` → `GoalFeed[]` | `GET /api/goal-feed` | **The PULL view** — per active goal, deterministic terms (`proactivity/goal_terms.py`, no LLM) → markets/news/HN fetch + optional knowledge snippet + standing suggestions, each with a deterministic WHY. Capped per goal (`goal_feed_per_goal_cap=4`). Emits ONE metadata-only signal. Separate from and does not weaken the strict PUSH ranker. |
| `create_file` / `create_folder` / `list_dir` | `POST /api/fs/file`, `POST /api/fs/folder`, `GET /api/fs/list` | `jarvis/fs_ops.py` (pure pathlib). Full-disk reach; `~` expanded, `..` resolved. One content-free signal each (basename + byte length, never content/dir-chain). |

## File-ops security posture (audited)
Honors "anywhere on disk" with minimum hardening:
1. **`serve()` refuses to start off-loopback without `JARVIS_API_TOKEN`** (was: warn). Makes the
   custom-header/CORS-preflight CSRF defense load-bearing.
2. **All `/api/fs/*` routes (incl. `list`) refuse with 503 off-loopback without a token.** Localhost
   stays fully open. Killable via `JARVIS_FS_WRITES_ENABLED=0`.
3. **1 MB content cap** + 4096-char path cap (Pydantic) — disk-fill / event-loop-stall guard.
4. Reject existing non-regular targets (device/FIFO). Refuse clobber without `overwrite`.
5. Echoed path + error strings run through `redact()` (now scrubs home-dir usernames, both slash
   styles). File **content never enters the signal log**.

**Residual risk the user accepted:** anyone holding the token can read listings / create/overwrite
files anywhere the OS user can write (incl. `~/.ssh`, shell profiles, Startup). The token is the only
boundary (no path allowlist by design). Treat it like a password.

## Frontend (Hybrid HUD)
New: `AppShell` grid gains a full-width ticker row + 360px rail (drawer < 1180px). `StatusBar` gets a
breathing/thinking/alert reactor + telemetry-lite (uptime/link) + markets/ai/link pills. Right rail
stacks: `LiveStocksPanel` (StockTile + client-built `Sparkline` from rolling polls + add-by-name input)
→ `WatchlistPanel` → `GoalsPanel` → `GoalFeedWidget` → `NextNudgeWidget` → Weather/News placeholders
(honest "offline, Wave 2"). Dock adds **+ File / + Folder** (themed `FsModal`) and **Goal Feed**.
Polling lives in its own visibility-aware effects **outside `run()`** (no busy/online strobe; errors
degrade to last-good). Controller additions (`showGoalFeed`, `createFile`, `createFolder`) reuse the
locked `CardKind` union (`suggestion`/`answer`/`error`) — no widening. 503 write-guard surfaces a
clear "File writes locked — set JARVIS_API_TOKEN" card, not a crash.

## Run it
```
python -m jarvis serve          # localhost:8765, full reach
# off-localhost (Tailscale): set a token first, then open once with ?token=
$env:JARVIS_API_TOKEN = "<secret>"; $env:JARVIS_API_HOST = "<tailscale-ip>"; python -m jarvis serve
```
Rebuild the SPA after frontend edits: `cd frontend; npm run build` (FastAPI serves `frontend/dist`).

## Known limitations
- **GNews free tier rate-limits hard (HTTP 429).** News items in the goal-feed may be sparse; the
  connector degrades to empty and HN/markets/knowledge fill in. A paid key removes the ceiling.
- Sparklines build a short history client-side from polls ("warming up… N/3" until 3 samples). A real
  `GET /api/quotes/history` (Finnhub `/stock/candle`) is the one-line upgrade.

## Phase C/D — built (surfacing backend Phases A + B in the cockpit)
The backend Phases A (company fundamentals + cloud Deep Dive via the Anthropic Tier-2 router) and B
(GDELT/GNews news depth) were built backend-only; C/D surface them in the web cockpit as one cohesive
upgrade (decided with the user: full 3D globe, weather skipped):
- **Company depth** — clicking a stock tile opens `CompanyPanel` (profile + metric grid + analyst +
  recent news from `GET /api/company/{symbol}`) with a gold **Deep Dive** button: confirm-before-spend
  → `POST /api/company/{symbol}/deepdive` → the cloud report under a "☁ CLOUD-ESCALATED" label;
  gracefully disabled without `ANTHROPIC_API_KEY`. Frontend-only (routes already existed).
- **Navbar + view switch** — a `Cockpit | News` segmented control in the StatusBar; News view hides the
  rail (`AppShell hideSide`) so the globe gets full width.
- **World-news globe** — new read-only `GET /api/news` (`service.news()`, NO signal; reuses GDELT+GNews)
  → `NewsItem[]`. `NewsGlobe` (react-globe.gl/three.js, **lazy-loaded** so the main bundle stays ~145KB
  gz; globe chunk ~524KB gz) pins news by source country via a local `countryCentroids` table; auto-rotate
  off under reduced-motion. **Texture is a LOCAL asset** (`public/earth-dark.jpg`, NASA night-earth from
  the bundled three-globe package) — no CDN, honoring the trust boundary. Honest empty state on GDELT 429.
- Reviewed: five-axis APPROVE (GO); 468 tests pass, ruff/tsc/vite-build clean.

## Deferred
Weather (Open-Meteo, user-set location to keep PII off the trust boundary) — skipped by user choice;
the rail's weather placeholder was removed. A real `/api/quotes/history` (Finnhub `/stock/candle`) would
upgrade the sparklines from client-built to a true series.
