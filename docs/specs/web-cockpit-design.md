# WINNER: Proposal 2 ("Restrained Premium HUD") as the base — it is the only proposal that protects daily readability (Inter prose, 720px capped measure, glow-only-on-focus discipline, blue/gold mutual exclusion). Onto it I graft Proposal 1's richer arc-reactor logo + cinematic card-glow-flare arrival + per-kind spine vocabulary, and Proposal 3's data-dense right rail (SuggestionPeek, tabular-nums numerics, StatusBar with health dot) — without adopting its three-column density that would crush reading comfort.

## Rationale
The brief's hard constraint is "kickass/cinematic but NEVER at the cost of daily usability or readability." Proposal 1 is the most movie-faithful but over-ornaments (corner reticles, watermarks, Rajdhani as body font, glow everywhere) — fatiguing for an assistant you read all day. Proposal 3 is the densest but its three-column cockpit and Rajdhani body text sacrifice reading comfort. Proposal 2 already solved the core tension: push the HUD to the FRAME (logo, hairline borders, status bar, mono numbers, gold rationed to owned data) and keep the READING COLUMN a calm premium document (Inter at 1.65, capped 720px, no glow under text). I keep that spine and selectively borrow the cinematic peaks — a breathing arc-reactor that spins while thinking, a one-shot glow-flare as each card lands, blur-in entrance — because those happen at the edges or on arrival, never under prose. I also resolve every backend-contract divergence the API doc surfaced: the GUI cached-suffix rule, the "You" echo chat card, the suggestion WhyStrip (which the legacy Flet view dropped but the contract says SHOULD render), markdown body rendering, and append-only newest-at-bottom auto-scroll. The card kind set is locked to the dataclass: briefing|answer|chat|agenda|goal|finance|suggestion|error (memory is declared but never produced — handled as a quiet fallback, not a first-class variant).

## Colors
- bg-void = #05080f  (App background base — deepest near-black navy, behind everything.)
- bg-base = #0a1018  (Body gradient floor; darkest surface rests on this.)
- bg-raised = #0e1622  (Side panel / status bar / dock surface, one step up from void.)
- bg-panel = rgba(18,28,42,0.55)  (Frosted glass panel fill (semi-transparent over backdrop-blur). Opacity 0.55 so you can read over it.)
- bg-panel-solid = #111c2a  (Opaque fallback fill where backdrop-filter is unsupported.)
- bg-inset = rgba(7,12,20,0.6)  (Inset wells: chat input, code blocks, the WhyStrip.)
- arc = #4fd0ff  (PRIMARY arc-reactor blue. Logo core, focused borders, primary button, links, active states, key ring strokes.)
- arc-bright = #8ae6ff  (Hover/active highlight, glow hotspot, pulse peak.)
- arc-deep = #1c93c4  (Gradient dark stop, pressed states, ring outer track, the quieter 'memory' fallback rail.)
- arc-glow = rgba(79,208,255,0.35)  (Box-shadow / drop-shadow glow color for focus/active halos.)
- arc-faint = rgba(79,208,255,0.12)  (Hairline borders AT REST, subtle fills, ring tracks, faint background grid.)
- gold = #f5c451  (SECONDARY accent, rationed. Goal progress, proactive/suggestion markers, a key figure. Flags things the USER owns/should act on.)
- gold-bright = #ffd97a  (Gold hover/peak.)
- gold-faint = rgba(245,196,81,0.14)  (Gold-tinted fills: goal cards, suggestion WhyStrip, watchlist movers.)
- gold-glow = rgba(245,196,81,0.30)  (Gold focus/active halo for goal + suggestion glow.)
- text-hi = #eaf2fb  (Primary body text + card titles. Soft white, slight cool tint. ~13:1 on bg-void (WCAG AAA).)
- text-mid = #9fb2c8  (Secondary text, labels, metadata, timestamps.)
- text-low = #5c7088  (Tertiary: placeholders, disabled, the WHY caption, captions, axis labels.)
- text-on-arc = #04141d  (Dark text on a filled blue button (contrast on #4fd0ff).)
- ok = #5fd6a8  (Positive finance deltas, success, connected/online status, market up. Desaturated to fit the HUD.)
- warn = #f5c451  (Warnings/attention — reuses gold.)
- danger = #ff6b6b  (Error cards, negative deltas, disconnected/offline status, market down.)
- danger-glow = rgba(255,107,107,0.30)  (Error-card border glow.)

## Fonts
- Display / brand wordmark (rationed to the single 'JARVIS' mark only): Orbitron — 700, 0.18em tracking, uppercase, 20px
- Section / region headings + card titles + uppercase labels (techy but readable small): Rajdhani — 600, headings 13px/0.22em uppercase, card titles 16px/0.04em, labels 11px/0.14em uppercase
- Body / long-form reading text (the comfort font — all prose, answers, chat, briefing): Inter — 400 body 15px/1.65, 600 inline emphasis, chat input 15px/1.5
- Data / numbers / prices / % / agenda times / clock / tickers: JetBrains Mono — 400–500, 13–22px by context, font-variant-numeric: tabular-nums so number columns align

## Effects
- FROSTED GLASS (base of every panel/card): `.hud-glass { background: var(--bg-panel); backdrop-filter: blur(14px) saturate(120%); -webkit-backdrop-filter: blur(14px) saturate(120%); border: 1px solid var(--arc-faint); border-radius: 14px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 30px rgba(0,0,0,0.45); } @supports not (backdrop-filter: blur(1px)) { .hud-glass { background: var(--bg-panel-solid); } }` — blur is a restrained 14px, opacity 0.55, NO colored glow at rest (only the hairline). Card radius 12px, panel radius 14px.
- GLOWING THIN BORDER (focus/active only — glow always MEANS something): `.hud-glow-active { border-color: rgba(79,208,255,0.45); box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 0 0 1px var(--arc-faint), 0 0 18px -2px var(--arc-glow), 0 8px 30px rgba(0,0,0,0.45); }` — 18px radius with −2px spread = a thin luxury rim, not a neon bloom. Gold variant swaps color: `.hud-glow-gold { border-color: rgba(245,196,81,0.40); box-shadow: 0 0 18px -2px var(--gold-glow), 0 8px 30px rgba(0,0,0,0.45); }`. Danger: `.hud-glow-danger { border-color: rgba(255,107,107,0.45); box-shadow: 0 0 18px -2px var(--danger-glow), 0 8px 30px rgba(0,0,0,0.45); }`. RULE: blue and gold never glow in the same component at once.
- PER-KIND LEFT SPINE (the primary kind cue — a 2px glowing rail, not a loud border): `.card-rail { position: relative; } .card-rail::before { content:''; position:absolute; left:0; top:14px; bottom:14px; width:2px; border-radius:2px; background: var(--rail); box-shadow: 0 0 8px -1px var(--rail); }` — set `--rail` per kind from the accent map. The card-glow-flare (framer one-shot on arrival) animates this rail's boxShadow once.
- INSET WELL (chat input, WhyStrip, code): `.hud-inset { background: var(--bg-inset); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; box-shadow: inset 0 1px 6px rgba(0,0,0,0.4); }`
- BODY BACKDROP (navy void + two near-invisible reactor washes — felt, not seen): `body { background: radial-gradient(1200px 700px at 78% -8%, rgba(79,208,255,0.06), transparent 60%), radial-gradient(900px 600px at 0% 110%, rgba(245,196,81,0.035), transparent 60%), linear-gradient(180deg, var(--bg-base), var(--bg-void)); background-attachment: fixed; }` — ~6% blue glow top-right where the logo lives, a whisper of gold bottom-left, both fixed.
- ARC RING (SVG, the signature circular gauge): `.arc-ring-track { stroke: var(--arc-faint); stroke-width:2; fill:none; } .arc-ring-value { stroke: var(--arc); stroke-width:2.5; fill:none; stroke-linecap:round; filter: drop-shadow(0 0 4px var(--arc-glow)); } .arc-ring-gold .arc-ring-value { stroke: var(--gold); filter: drop-shadow(0 0 4px rgba(245,196,81,0.4)); }` — value drawn via stroke-dasharray/offset.
- SECTION HAIRLINE DIVIDER: `.hr { height:1px; background: linear-gradient(90deg, transparent, var(--arc-faint), transparent); }` — used under region labels (fades at both ends).
- ACCENT BUTTON (primary/send): `.hud-btn { font-family: Rajdhani; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color: var(--arc-bright); background: linear-gradient(180deg, rgba(79,208,255,0.14), rgba(28,147,196,0.08)); border:1px solid rgba(79,208,255,0.45); border-radius:10px; padding:10px 16px; box-shadow: inset 0 0 14px rgba(79,208,255,0.08); transition: all .18s ease; } .hud-btn:hover { color:#fff; box-shadow: inset 0 0 18px rgba(79,208,255,0.16), 0 0 18px -2px var(--arc-glow); }`

## Layout
Two-column CSS-grid cockpit (NOT three — readability wins over density). Grid areas: "status status" / "feed side" / "dock dock", columns `1fr 340px`, rows `56px 1fr auto`, 16px gap, 16px padding, height 100vh. REGION.STATUS (top, 56px, full-width frosted bar, the only Orbitron on screen): ArcReactorLogo + "JARVIS" wordmark left; SystemPill cluster center-right (markets ●, ai ● — pulsing dots colored by health); tabular-mono Clock (HH:MM:SS) far right. REGION.FEED (center, scrolls, append-only newest-at-BOTTOM with auto-scroll matching the Flet ListView, inner content capped 720px and centered so prose never exceeds a comfortable measure on a 27in monitor; a small "FEED" rail label sits above the first card; briefing is always the first card auto-posted on launch). REGION.SIDE (340px, own scroll, stacks three HudPanels: GoalsPanel top with gold progress rings, WatchlistPanel middle with mono ticker rows + colored deltas, SuggestionPeek bottom showing the next nudge — this is where the borrowed data-density lives, always-visible owned-data state). REGION.DOCK (bottom, full-width frosted, fixed so feed scrolls behind it for the console feel): row 1 = ShortcutBar (Briefing, Agenda, Markets/News, Finance, Add Goal, Suggestions — 1:1 with controller methods); row 2 = ChatInput with arc-ring send button. Responsive: <1024px the side panel becomes a right slide-over drawer (toggle in status bar), feed goes full-width still capped 720px; <640px ShortcutBar becomes a horizontally scrollable icon row.

## Animations
Centralized in motion.ts. EASE = [0.22, 0.61, 0.36, 1] (cinematic ease-out); DUR = {fast:0.22, base:0.34, slow:0.55}. (1) entrance: shell regions fade+slide-up staggered top→bottom — status (0ms) → side rail (delay 0.1s) → dock → feed (delay 0.2s); ~0.6s graceful power-on, NOT a fake boot log; region variant `{opacity:0,y:10}→{opacity:1,y:0}` over DUR.slow. (2) card-in (the signature feed motion): `{opacity:0, y:14, filter:'blur(4px)'} → {opacity:1, y:0, filter:'blur(0px)'}` over DUR.base with `delay: Math.min(index*0.05, 0.3)`; wrapped in AnimatePresence + `layout` so existing cards slide smoothly when a new one mounts at the bottom; exit `{opacity:0, y:-8}`. On first paint ONLY, the card's left rail runs a one-shot glow-flare (boxShadow keyframes `['0 0 0px var(--rail)','0 0 14px -1px var(--rail)','0 0 8px -1px var(--rail)']` over 0.7s) — the cinematic "it landed" beat, borrowed from Proposal 1 but confined to the 2px spine, never under text. (3) hover (cards/panels/buttons): subtle `y:-2` lift over DUR.fast, NO scale jump on cards; CSS handles border+glow brighten on :hover (cheaper than JS box-shadow). Buttons add `whileTap:{scale:0.97}`. (4) status: SystemPills + ArcReactor idle breathe — `opacity:[0.55,1,0.55]` + reactor core `filter` drop-shadow swell, 3.2s easeInOut infinite loop = the "alive" cue. (5) thinking (request in flight): ArcReactorLogo switches to state='thinking' → outer segmented ring `rotate:360` over 6s linear (slow, dignified, not a spinner race); ChatInput send arc-ring goes indeterminate. (6) ALL loops + blur/slide wrapped in useReducedMotion() → collapse to opacity-only DUR.fast fades, kill every repeat:Infinity. Timing budget: nothing user-blocking exceeds ~600ms; ambient loops are transform/opacity only (GPU-cheap); no ring animation ever sits under prose being read.

## Components
### AppShell
Top-level CSS-grid cockpit (status/feed/side/dock). Mounts the entrance stagger and the prefers-reduced-motion provider.
Props: { children } — composes StatusBar, Feed, SidePanel, CommandDock into the named grid areas.
### StatusBar
Top instrument cluster: ArcReactorLogo + 'JARVIS' wordmark (only Orbitron on screen), SystemPill cluster, live Clock. Drives the global thinking/alert state of the reactor.
Props: { systems: {id:string; label:string; state:'ok'|'warn'|'down'}[]; busy?:boolean; onToggleSide?:()=>void }
### ArcReactorLogo
The single hero reactor + global activity indicator. SVG bright core + two concentric rings (one segmented into 9 short arc dashes, the reactor housing) + faint outer track, drop-shadow glow. The only literal Iron Man object.
Props: { size?:number=28; state?:'idle'|'thinking'|'alert' } — idle breathes, thinking spins the segmented ring, alert flashes danger.
### Clock
Tabular-mono live clock, ticks once per second via setInterval(1000).
Props: { format?:'24h'|'12h'='24h'; showSeconds?:boolean=true }
### SystemPill
A glowing status dot + Rajdhani uppercase label; slow pulse on 'ok'. Used for markets/ai health in the status bar.
Props: { label:string; state:'ok'|'warn'|'down' }
### HudPanel
The universal frosted-glass container primitive every region/panel/card composes. Glass at rest (hairline only), glow on focus/active.
Props: { glow?:'none'|'arc'|'gold'|'danger'='none'; label?:string; corner?:boolean=false; className?:string; children:ReactNode }
### Feed
Maps the append-only card list → Card components; manages AnimatePresence stagger + auto-scroll to the newest card at the BOTTOM (matches Flet ListView auto_scroll). Renders the 'FEED' rail label above the first card.
Props: { cards: CardData[]; autoScroll?:boolean=true } where CardData = {title:string; body:string; kind:CardKind; why?:string|null}
### Card
Single polymorphic component; dispatches on `kind` to a sub-renderer. Built on HudPanel + a 2px per-kind glowing left spine (.card-rail). Header = KindIcon + title (Rajdhani 16/600) + right-aligned mono timestamp. Body rendered per kind. index drives staggered entrance delay.
Props: { card:CardData; index:number } — CardKind='briefing'|'answer'|'chat'|'agenda'|'goal'|'finance'|'suggestion'|'error' (memory falls back to the answer renderer with arc-deep rail).
### MarkdownBody
Renders Card.body as GitHub-flavored markdown in Inter 15/1.65 (mirrors Flet ft.Markdown). Used by briefing/answer/chat/finance/suggestion. Text is selectable.
Props: { source:string }
### AgendaBody
Parses the controller's `- HH:MM-HH:MM summary @ loc` / `- all day summary` lines into a mono time column + Inter summary with a small reticle dot per event. Handles the literal not-connected and 'No events today.' states verbatim.
Props: { body:string }
### FinanceFigure
Renders the finance answer body; any leading currency figure shown large in JetBrains Mono tabular-nums, colored --ok/--danger by sign with an up/down chevron; remaining prose in Inter.
Props: { body:string }
### WhyStrip
The explainability contract for suggestion cards (and the legacy Flet view dropped it — we restore it). Gold-tinted inset well: 'WHY' caption (Rajdhani 11 uppercase, --text-low) + the why string in Inter 13. Always rendered when card.why is present.
Props: { why:string }
### ChatInput
The ask() surface. Frosted inset field (Inter 15), arc-ring send button. Enter submits, Shift+Enter newline, trims empty (mirrors controller early-return). Focus lifts border to --arc + active glow. busy → send ring goes indeterminate and reactor goes thinking.
Props: { onSubmit:(text:string)=>void; busy?:boolean; placeholder?:string='Ask Jarvis…' }
### ShortcutBar
Action buttons mapping 1:1 to controller methods: Briefing(show_briefing), Agenda(show_agenda), Markets/News(ask_markets_news — sends the exact preset query), Finance(show_finance — exact monthly-spend question), Add Goal(add_goal — reuses chat field text), Suggestions(show_suggestions). Suggest button carries the gold accent.
Props: { actions: ShortcutAction[] } where ShortcutAction = {id:string; label:string; icon:ReactNode; onClick:()=>void; accent?:'arc'|'gold'}
### ShortcutButton
One ghost pill (transparent + arc-faint border); a thin 3/4 arc segment around the icon completes + glows on hover/active to signal 'live control'. Icon is a thin-line/arc glyph.
Props: { icon:ReactNode; label:string; onClick:()=>void; accent?:'arc'|'gold'='arc'; busy?:boolean }
### SidePanel
Right rail container; stacks GoalsPanel, WatchlistPanel, SuggestionPeek. Becomes a slide-over drawer below 1024px.
Props: { goals:Goal[]; watchlist:Watch[]; topSuggestion?:Suggestion; onAddGoal?:(t:string)=>void; onOpenSuggestion?:()=>void }
### GoalsPanel
HudPanel (label 'GOALS', gold glow). Each row: small gold ArcRing showing progress + mono #id + Inter description. Optional inline add field calling add_goal. Empty state: faint 'No goals yet.'
Props: { goals:{id:number; description:string; progress?:number}[]; onAdd?:(t:string)=>void }
### WatchlistPanel
HudPanel (label 'WATCHLIST', arc glow). Symbol rows: mono symbol + mono price (tabular-nums) + mono delta colored --ok/--danger with ▲/▼. News-kind rows show a count. Maps the Watch{kind,value} side-panel shape.
Props: { items:{kind:string; value:string; price?:number; delta?:number}[] }
### SuggestionPeek
Always-visible 'next nudge' preview at the bottom of the right rail (borrowed data-density). Shows the top suggestion's first line + a gold dot; click opens it into the feed via show_suggestions.
Props: { top?:{content:string; why:string}; onOpen?:()=>void }
### ArcRing
Reusable SVG arc gauge/decoration. track + value stroke via stroke-dasharray/offset; mono % center optional. Used in goals, finance ratios, the send button (indeterminate=spin). The circular motif only ever where it holds ONE value or is a control edge — never around a card or under text.
Props: { value?:number /*0..1*/; size?:number=44; accent?:'arc'|'gold'='arc'; indeterminate?:boolean; showLabel?:boolean }
### KindIcon
Per-kind thin-line icon tinted to the kind's accent (briefing/answer/agenda/goal/finance/suggestion/chat/error).
Props: { kind:CardKind }

## Full Design Spec
# JARVIS Web Cockpit — Build-Ready Design System
### "Restrained Premium HUD" — Iron Man identity at the frame, premium readable document at the core
Stack: Vite + React + TypeScript + Tailwind CSS + framer-motion

> **Governing principle:** The HUD is a *finish*, not a *theme*. It lives in the logo, hairline borders, the status bar, monospace numbers, and on-arrival motion — **never inside the reading column.** Long-form card bodies read like a premium document (Inter, capped measure); the chrome around them reads like a cockpit. Cinematic on arrival and at the edges; calm at rest.

---

## 1. Color Tokens
Define on `:root` in `src/theme.css`, mirror into `tailwind.config.ts` under `theme.extend.colors`. Two files own the identity (`theme.css` + `motion.ts`).

```css
:root {
  /* Background ramp (deep navy -> near-black) */
  --bg-void:        #05080f;
  --bg-base:        #0a1018;
  --bg-raised:      #0e1622;
  --bg-panel:       rgba(18,28,42,0.55);   /* frosted fill */
  --bg-panel-solid: #111c2a;               /* no-blur fallback */
  --bg-inset:       rgba(7,12,20,0.6);      /* wells */

  /* Arc-reactor blue (PRIMARY) */
  --arc:        #4fd0ff;
  --arc-bright: #8ae6ff;
  --arc-deep:   #1c93c4;
  --arc-glow:   rgba(79,208,255,0.35);
  --arc-faint:  rgba(79,208,255,0.12);

  /* Gold (SECONDARY, rationed) */
  --gold:        #f5c451;
  --gold-bright: #ffd97a;
  --gold-faint:  rgba(245,196,81,0.14);
  --gold-glow:   rgba(245,196,81,0.30);

  /* Text */
  --text-hi:     #eaf2fb;   /* AAA on void */
  --text-mid:    #9fb2c8;
  --text-low:    #5c7088;
  --text-on-arc: #04141d;

  /* Semantic (desaturated to fit the HUD) */
  --ok:          #5fd6a8;
  --warn:        #f5c451;   /* = gold */
  --danger:      #ff6b6b;
  --danger-glow: rgba(255,107,107,0.30);
}
```

**Discipline rules:** (1) **blue and gold never glow in the same component at the same time** — blue is the system voice; gold flags the few things the user owns/should act on. (2) Glow is reserved for focus / active / arrival — never constant. (3) Default panels show only the hairline `--arc-faint` border.

**Per-card-kind accent map** (sets `--rail` on the card's left spine + tints the KindIcon):

| kind | `--rail` | rationale |
|---|---|---|
| `briefing` | `--arc` | the system speaking (hero) |
| `answer` | `--arc` | grounded, cited answer |
| `chat` | `--text-mid` | conversational echo, **no glow** |
| `agenda` | `--arc` | schedule |
| `goal` | `--gold` | user-owned |
| `finance` | `--ok` / `--danger` by sign | green up / red down |
| `suggestion` | `--gold` | proactive, act-on-me |
| `error` | `--danger` | failure |
| `memory` *(declared, never produced)* | `--arc-deep` | quiet recall — falls back to the answer renderer |

---

## 2. Typography
Self-host via `@fontsource` (local-first, no CDN call — honors the trust boundary): `@fontsource/orbitron`, `@fontsource/rajdhani`, `@fontsource/jetbrains-mono`, `@fontsource/inter`.

```js
// tailwind.config.ts
fontFamily: {
  display: ['Orbitron', 'sans-serif'],
  head:    ['Rajdhani', 'sans-serif'],
  body:    ['Inter', 'system-ui', 'sans-serif'],
  mono:    ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
}
```

| Role | Font | Size / line | Weight / tracking |
|---|---|---|---|
| Brand wordmark "JARVIS" (the ONLY Orbitron) | Orbitron | 20 / 1 | 700, 0.18em, uppercase |
| Region heading ("FEED","GOALS","WATCHLIST") | Rajdhani | 13 / 1.2 | 600, 0.22em, uppercase |
| Card title | Rajdhani | 16 / 1.3 | 600, 0.04em |
| **Card body / answer / briefing / chat (reading text)** | **Inter** | 15 / 1.65 | 400 |
| Inline emphasis | Inter | 15 | 600 |
| Data / numbers / prices / % / agenda times / clock / tickers | JetBrains Mono | 13–22 ctx | 400–500, 0, `tabular-nums` |
| Label / caption / "WHY" / status pill | Rajdhani | 11 / 1.4 | 500, 0.14em, uppercase |
| Chat input | Inter | 15 / 1.5 | 400 |

**Rule:** Orbitron is the costume — rationed to the single wordmark. Rajdhani carries headings/labels (techy, readable small). **Inter carries everything you read.** Mono carries every *value*, with `tabular-nums` so number columns align.

---

## 3. Glass / Glow / Border / Arc — CSS recipes
*(All recipes are in the `tokens.effects` field — reproduced here for the builder.)*

```css
/* Frosted glass — base of every panel & card */
.hud-glass {
  background: var(--bg-panel);
  backdrop-filter: blur(14px) saturate(120%);
  -webkit-backdrop-filter: blur(14px) saturate(120%);
  border: 1px solid var(--arc-faint);
  border-radius: 14px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 30px rgba(0,0,0,0.45);
}
@supports not (backdrop-filter: blur(1px)) { .hud-glass { background: var(--bg-panel-solid); } }

/* Glowing thin border — focus/active ONLY. Thin rim (18px @ -2px spread), not a bloom */
.hud-glow-active { border-color: rgba(79,208,255,0.45);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 0 0 1px var(--arc-faint),
              0 0 18px -2px var(--arc-glow), 0 8px 30px rgba(0,0,0,0.45); }
.hud-glow-gold   { border-color: rgba(245,196,81,0.40);
  box-shadow: 0 0 18px -2px var(--gold-glow), 0 8px 30px rgba(0,0,0,0.45); }
.hud-glow-danger { border-color: rgba(255,107,107,0.45);
  box-shadow: 0 0 18px -2px var(--danger-glow), 0 8px 30px rgba(0,0,0,0.45); }

/* Per-kind left spine — primary kind cue */
.card-rail { position: relative; }
.card-rail::before { content:''; position:absolute; left:0; top:14px; bottom:14px;
  width:2px; border-radius:2px; background: var(--rail); box-shadow: 0 0 8px -1px var(--rail); }

/* Inset well — chat input, WhyStrip, code */
.hud-inset { background: var(--bg-inset); border:1px solid rgba(255,255,255,0.05);
  border-radius:12px; box-shadow: inset 0 1px 6px rgba(0,0,0,0.4); }

/* Body backdrop — navy void + two near-invisible reactor washes */
body { background:
  radial-gradient(1200px 700px at 78% -8%, rgba(79,208,255,0.06), transparent 60%),
  radial-gradient(900px 600px at 0% 110%, rgba(245,196,81,0.035), transparent 60%),
  linear-gradient(180deg, var(--bg-base), var(--bg-void)); background-attachment: fixed; }

/* Arc ring (SVG) */
.arc-ring-track { stroke: var(--arc-faint); stroke-width:2; fill:none; }
.arc-ring-value { stroke: var(--arc); stroke-width:2.5; fill:none; stroke-linecap:round;
  filter: drop-shadow(0 0 4px var(--arc-glow)); }
.arc-ring-gold .arc-ring-value { stroke: var(--gold); filter: drop-shadow(0 0 4px rgba(245,196,81,0.4)); }

/* Hairline divider, accent button */
.hr { height:1px; background: linear-gradient(90deg, transparent, var(--arc-faint), transparent); }
.hud-btn { font-family: Rajdhani; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;
  color: var(--arc-bright); background: linear-gradient(180deg, rgba(79,208,255,0.14), rgba(28,147,196,0.08));
  border:1px solid rgba(79,208,255,0.45); border-radius:10px; padding:10px 16px;
  box-shadow: inset 0 0 14px rgba(79,208,255,0.08); transition: all .18s ease; }
.hud-btn:hover { color:#fff; box-shadow: inset 0 0 18px rgba(79,208,255,0.16), 0 0 18px -2px var(--arc-glow); }
```
Standardize on: **blur 14px**, **panel radius 14px**, **card radius 12px**, idle border `--arc-faint`, focus glow `0 0 18px -2px var(--arc-glow)`, lift shadow `0 8px 30px rgba(0,0,0,.45)`.

---

## 4. Screen Layout (named regions)
Two-column CSS-grid cockpit — readability over density.

```
┌───────────────────────────────────────────────────────────────┐
│ STATUS  [◉ JARVIS]      markets ●  ai ●            14:32:07     │ 56px
├──────────────────────────────────────────┬────────────────────┤
│ FEED (scroll, inner cap 720px, centered)  │ SIDE (340px,scroll)│
│  FEED label                               │  ┌ GOALS ────────┐ │
│  [Card briefing]  ← auto-posted first     │  │ ◔ #1 …        │ │
│  [Card You(chat)] [Card answer/chat]      │  └───────────────┘ │
│  [Card agenda] [Card finance] …           │  ┌ WATCHLIST ────┐ │
│  [Card suggestion + WHY]                  │  │ NVDA +1.2% ▲   │ │
│            (newest at BOTTOM, autoscroll)  │  └───────────────┘ │
│                                           │  ┌ NEXT NUDGE ───┐ │
│                                           │  └───────────────┘ │
├──────────────────────────────────────────┴────────────────────┤
│ DOCK  [Briefing][Agenda][Markets][Finance][+Goal][Suggest]     │
│       [ Ask Jarvis……………………………………………………… ⟶ ]       │
└───────────────────────────────────────────────────────────────┘
```
```css
.cockpit { display:grid; grid-template-columns: 1fr 340px;
  grid-template-rows: 56px 1fr auto;
  grid-template-areas: "status status" "feed side" "dock dock";
  height:100vh; gap:16px; padding:16px; }
.feed-inner { max-width:720px; margin:0 auto; }  /* comfortable measure even on 27" */
```
- **STATUS** (only Orbitron): `ArcReactorLogo` + wordmark left; `SystemPill[]` (markets ●, ai ●, pulse on ok) center-right; mono `Clock` (HH:MM:SS) right. The reactor doubles as the global thinking/alert indicator.
- **FEED**: append-only `Card` list, **newest at BOTTOM with auto-scroll** (matches the Flet `ListView`). Inner content capped **720px**, centered. `briefing` is always the first card (auto-posted on launch).
- **SIDE**: `GoalsPanel` (gold-leaning) → `WatchlistPanel` (arc) → `SuggestionPeek`. Always-visible owned-data state.
- **DOCK** (fixed bottom, feed scrolls behind it): row 1 `ShortcutBar`, row 2 `ChatInput`.
- **Responsive:** <1024px → side becomes a right slide-over drawer (toggle in status bar), feed full-width (still 720px cap). <640px → ShortcutBar becomes a horizontally scrollable icon row.

---

## 5. Component Inventory
*(Full props in the `components` field. Key contracts:)*
- `Card({card,index})` dispatches on `kind`; built on `.hud-glass` + `.card-rail`. Header = `KindIcon` + title (Rajdhani 16/600) + right-aligned mono timestamp. Body sub-renderer per kind: prose kinds → `MarkdownBody` (Inter 15/1.65, selectable); `agenda` → `AgendaBody`; `finance` → `FinanceFigure`; `suggestion` → `MarkdownBody` + `WhyStrip`. `index` drives entrance delay. `memory` → answer renderer with `--arc-deep` rail.
- `WhyStrip({why})` — **restored explainability contract** (legacy Flet `_card_view` dropped it; the API contract says it SHOULD render). Gold-tinted `.hud-inset`, "WHY" caption + why in Inter 13. Always shown when `card.why` is present.
- `ShortcutBar` actions map 1:1 to controller methods and MUST call the exact literals:
  - Briefing → `show_briefing`
  - Agenda → `show_agenda`
  - Markets/News → `ask_markets_news` (sends exactly `"What's happening in markets and tech news today?"` through the same ask endpoint)
  - Finance → `show_finance` (asks exactly `"How much have I spent this month?"`)
  - +Goal → `add_goal` (reuses the chat field text)
  - Suggest → `show_suggestions` (gold accent)
- `ArcRing` / `ArcReactorLogo` — the circular motif, only where it holds ONE value or is a control edge.

---

## 6. Animation Language (`motion.ts`)
```ts
export const EASE = [0.22, 0.61, 0.36, 1] as const;
export const DUR  = { fast: 0.22, base: 0.34, slow: 0.55 };

export const region = { initial:{opacity:0,y:10}, animate:{opacity:1,y:0,
  transition:{duration:DUR.slow,ease:EASE}} };           // stagger 0.08, delay 0.05

export const cardIn = (index:number) => ({
  initial:{opacity:0,y:14,filter:'blur(4px)'},
  animate:{opacity:1,y:0,filter:'blur(0px)',
    transition:{duration:DUR.base,ease:EASE,delay:Math.min(index*0.05,0.3)}},
  exit:{opacity:0,y:-8,transition:{duration:DUR.fast,ease:EASE}} });

// one-shot rail glow-flare on first paint (cinematic "landed" beat — on the 2px spine only)
export const railFlare = { animate:{ boxShadow:[
  '0 0 0px var(--rail)','0 0 14px -1px var(--rail)','0 0 8px -1px var(--rail)'] },
  transition:{duration:0.7,ease:EASE} };

export const hoverLift = { whileHover:{y:-2,transition:{duration:DUR.fast,ease:EASE}},
  whileTap:{scale:0.97} };  // CSS handles border/glow brighten on :hover

export const statusPulse = { animate:{opacity:[0.55,1,0.55]},
  transition:{duration:3.2,repeat:Infinity,ease:'easeInOut'} };

export const arcThinking = { animate:{rotate:360},
  transition:{duration:6,repeat:Infinity,ease:'linear'} };  // dignified, not a spinner race
```
Rules: entrance powers on top→bottom (~0.6s, no fake boot log). New feed cards use `AnimatePresence` + `layout` so existing cards slide as one mounts at the bottom. Hover = 2px lift, no scale on cards. Idle reactor + pills breathe (the "alive" cue). `ChatInput.busy`/in-flight → reactor `thinking` + send ring indeterminate. **Wrap everything in `useReducedMotion()`** → opacity-only `DUR.fast`, kill all `repeat:Infinity`. Nothing user-blocking exceeds ~600ms; loops are transform/opacity only; **no ring ever animates under prose.**

---

## 7. Arc-Reactor / Ring Motif — without hurting usability
The ring is **a frame or a single-value gauge, never a surface for text.** Ranked by prominence:
1. **`ArcReactorLogo`** (status bar, ~28px) — the one hero reactor + global activity indicator (idle breathe → thinking spin → alert red pulse). Nothing else competes.
2. **Send button** — small `ArcRing` that completes on hover, runs indeterminate while answering.
3. **Goal progress** — gold `ArcRing` per goal: a ring genuinely communicates "% to target," tying the motif to real data.
4. **Background reactor wash** — the 6% radial glow top-right; felt, not seen.

**Hard DO-NOT:** no circular text / curved labels / radial menus; no ring *around* a card or the feed (cards stay rectangular, radius 12px); no full-screen rotating overlay, scanlines, boot sequence, or fake telemetry; rings never animate continuously in the reading path — only the out-of-the-way logo and active/loading states loop; numbers inside rings stay horizontal + mono.

---

## 8. Backend Render Contract — resolved decisions (build exactly this)
Card model: `{ title:string; body:string; kind:CardKind; why?:string|null }`. `body` is always pre-formatted by the backend; the UI does **zero** formatting except markdown rendering + the agenda/finance light parse. Bodies render as **GitHub-flavored Markdown, selectable** (mirrors `ft.Markdown`). Append-only, **newest at bottom, auto-scroll**.

- **Briefing** — title literal `"Daily briefing"`; body = `service.briefing()` verbatim → Markdown. Auto-posted as the first card on launch.
- **Ask / free-text** — first post a `chat` card titled `"You"` with the raw stripped question (the echo). Then the answer card: title = `"Jarvis (cached)"` if `result.cached` else `"Jarvis"` (cached suffix applies **regardless** of grounded vs chat — GUI keys only on `cached`); kind = `"answer"` if `result.grounded` else `"chat"`. Empty/whitespace input posts **nothing** (early return).
- **Markets/News** — sends the exact literal `"What's happening in markets and tech news today?"` through the *same* ask path (You-echo + answer shaping).
- **Finance** — title literal `"Finance"`; asks the exact literal `"How much have I spent this month?"`; body verbatim → `FinanceFigure` (leading currency figure shown large/mono/colored by sign).
- **Agenda** — title literal `"Today's calendar"`. Connected-check FIRST, then empty, then lines. Lines: `- HH:MM-HH:MM summary @ location` or `- all day summary` (single space before `@`, no `@` when no location). Not-connected body = literal `"Not connected. Run: python -m jarvis calendar-auth"`. Empty-but-connected = literal `"No events today."` `AgendaBody` parses these into a mono time column + Inter summary.
- **Add goal** — title literal `"Goal added"`; body = `` `#${id}  ${description}` `` (two spaces after id). Empty text posts nothing.
- **Suggestions** — empty → single card title `"Jarvis"`, body literal `"Nothing worth surfacing right now."`. Otherwise one card per suggestion: title `"Suggestion"`, body = `content`, **`why` carried separately and rendered via `WhyStrip`** ("WHY: {why}").
- **Error (cross-cutting)** — any backend failure → card title `"Error"`, kind `"error"`, body = redacted exception text (`redact(str(exc))`, applied backend-side). Danger rail + `.hud-glow-danger`. The feed keeps receiving — never crash.

---

## 9. Net effect
The reading column is calm — Inter at 1.65 over near-black navy, capped at 720px, comfortable for hours. The Iron Man identity is fully present but pushed to the frame: a breathing arc-reactor that spins while thinking, hairline blue borders that glow only on focus, gold reserved for the handful of things you own, monospace tabular numbers, and cinematic-but-short fade-slide-blur motion with a one-shot glow-flare as each card lands. Premium product first, Iron Man second — kickass without sacrificing daily usability.