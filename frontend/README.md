# Jarvis Web Cockpit (JARVIS HUD)

A thin React front-end over the Jarvis FastAPI seam — the same `JarvisService` facade the CLI, Flet
GUI, and voice loop call. No capability logic lives here; it renders the structured results into the
"JARVIS HUD" (Iron Man) design (arc-reactor blue + gold on deep navy, frosted glass, glowing
borders, cinematic fade/slide). Design record: [`docs/specs/web-cockpit-design.md`](../docs/specs/web-cockpit-design.md).

## Run it (production — one command)

From the repo root, build the frontend once, then serve everything from FastAPI:

```bash
# 1. build the static cockpit into frontend/dist (Node 18+)
cd frontend
npm install
npm run build

# 2. serve it (FastAPI wraps JarvisService and serves dist/ at /)
cd ..
python -m jarvis serve
# -> http://127.0.0.1:8765
```

`serve` reuses the exact same backend the other front-ends use (`source="web"`), so every action
still emits one signal and all logic stays in the engines.

## Develop (hot reload)

Run the API and the Vite dev server side by side — Vite proxies `/api` to the backend:

```bash
python -m jarvis serve          # terminal 1: API on :8765
cd frontend && npm run dev       # terminal 2: HUD on :5173 (proxies /api -> :8765)
```

## Reach it from another device (Tailscale)

The server binds to localhost by default. To reach the cockpit from your phone/laptop over your
private Tailscale mesh, bind the Tailscale interface **and set a token** — without a token every
route (including finance/calendar) is unauthenticated on the network:

```bash
# PowerShell
$env:JARVIS_API_HOST = "0.0.0.0"
$env:JARVIS_API_TOKEN = "pick-a-long-random-string"
python -m jarvis serve
# then open this ONCE on the other device (the SPA stores the token, then strips it from the URL):
#   http://<your-tailscale-ip>:8765/?token=pick-a-long-random-string
```

When `JARVIS_API_TOKEN` is set, every `/api` data route requires an `X-Jarvis-Token` header (the SPA
sends it automatically after the one-time `?token=` visit). This both authenticates the caller and
defeats browser CSRF / DNS-rebinding (the custom header forces a CORS preflight the server never
grants cross-origin). `serve` prints a loud warning if you bind off-localhost without a token.

| Env var | Default | Meaning |
| --- | --- | --- |
| `JARVIS_API_HOST` | `127.0.0.1` | bind address (set to a Tailscale IP / `0.0.0.0` for mesh access) |
| `JARVIS_API_PORT` | `8765` | port |
| `JARVIS_API_TOKEN` | _(unset)_ | shared secret required on `/api` routes; **set this for any off-localhost bind** |

## Layout

- `src/api.ts` — fetch client over `/api` (works in dev via proxy, prod same-origin).
- `src/controller.ts` — card-shaping (the TS mirror of `jarvis/ui/controller.py`).
- `src/components/` — the HUD: `AppShell`, `StatusBar`, `ArcReactorLogo`, `Feed`/`Card`, `ChatInput`,
  `ShortcutBar`, `SidePanel` (goals · watchlist · next-nudge), `ArcRing`.
- `src/theme.css` + `src/motion.ts` — the two files that own the visual identity.
