// The card-shaping controller: the TS mirror of jarvis/ui/controller.py (AppController) + design
// spec §8. Each front-end owns its own presentation; this one calls the API and shapes the exact
// same cards the Flet GUI does (titles, the cached suffix, agenda/finance/goal line formats, the
// suggestion WhyStrip, redacted error cards). NO capability logic lives here.
import { api, ApiError } from "./api";
import type { CalendarEvent, CardData, Suggestion } from "./types";

export const MARKETS_QUERY = "What's happening in markets and tech news today?";
const MONTHLY_SPEND_QUERY = "How much have I spent this month?";

export type Post = (card: CardData) => void;

/** "HH:MM" in the event's own clock (slice the ISO time, no tz reinterpretation). */
function wallTime(iso: string): string {
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] : iso;
}

function eventLine(e: CalendarEvent): string {
  const when = e.all_day ? "all day" : `${wallTime(e.start)}-${wallTime(e.end)}`;
  const location = e.location ? ` @ ${e.location}` : "";
  return `- ${when} ${e.summary}${location}`;
}

export function makeController(post: Post) {
  const postError = (exc: unknown) => {
    // Backend failures arrive already redacted; transport errors carry a generic message.
    const body = exc instanceof ApiError ? exc.message : "Something went wrong.";
    post({ title: "Error", body, kind: "error" });
  };

  async function ask(text: string): Promise<void> {
    const t = text.trim();
    if (!t) return; // empty input posts nothing (mirrors the early return)
    post({ title: "You", body: t, kind: "chat" }); // echo the question
    try {
      const r = await api.ask(t);
      const title = r.cached ? "Jarvis (cached)" : "Jarvis";
      post({ title, body: r.text, kind: r.grounded ? "answer" : "chat" });
    } catch (exc) {
      postError(exc);
    }
  }

  async function showBriefing(): Promise<void> {
    try {
      const r = await api.briefing();
      post({ title: "Daily briefing", body: r.text, kind: "briefing" });
    } catch (exc) {
      postError(exc);
    }
  }

  async function showAgenda(): Promise<void> {
    try {
      const r = await api.agenda();
      let body: string;
      if (!r.connected) body = "Not connected. Run: python -m jarvis calendar-auth";
      else if (r.events.length === 0) body = "No events today.";
      else body = r.events.map(eventLine).join("\n");
      post({ title: "Today's calendar", body, kind: "agenda" });
    } catch (exc) {
      postError(exc);
    }
  }

  const askMarketsNews = () => ask(MARKETS_QUERY);

  async function showFinance(): Promise<void> {
    try {
      const r = await api.financeAsk(MONTHLY_SPEND_QUERY);
      post({ title: "Finance", body: r.text, kind: "finance" });
    } catch (exc) {
      postError(exc);
    }
  }

  async function addGoal(text: string): Promise<void> {
    const t = text.trim();
    if (!t) return;
    try {
      const goal = await api.addGoal(t);
      post({ title: "Goal added", body: `#${goal.id}  ${goal.description}`, kind: "goal" });
    } catch (exc) {
      postError(exc);
    }
  }

  async function showSuggestions(): Promise<Suggestion[]> {
    try {
      const { suggestions } = await api.suggestions();
      if (suggestions.length === 0) {
        post({ title: "Jarvis", body: "Nothing worth surfacing right now.", kind: "suggestion" });
        return [];
      }
      for (const s of suggestions) {
        post({ title: "Suggestion", body: s.content, kind: "suggestion", why: s.why });
      }
      return suggestions;
    } catch (exc) {
      postError(exc);
      return [];
    }
  }

  // The goal-driven PULL feed, surfaced INTO the readable feed on demand: one card per active goal
  // with relevant info, reusing the 'suggestion' kind so its WhyStrip explains the relevance.
  async function showGoalFeed(): Promise<void> {
    try {
      const { feed } = await api.goalFeed();
      const withItems = feed.filter((f) => f.items.length > 0);
      if (withItems.length === 0) {
        post({
          title: "Goal feed",
          body: "No goal-relevant info surfaced right now.",
          kind: "suggestion",
        });
        return;
      }
      for (const f of withItems) {
        const body = f.items
          .map((it) => {
            const link = it.url ? ` ([${it.source}](${it.url}))` : ` _(${it.source})_`;
            return `- **${it.title}** — ${it.detail}${link}`;
          })
          .join("\n");
        post({
          title: `Goal #${f.goal_id}: ${f.goal}`,
          body,
          kind: "suggestion",
          why: `Surfaced for goal #${f.goal_id}: ${f.goal}`,
        });
      }
    } catch (exc) {
      postError(exc);
    }
  }

  // The off-loopback write guard (jarvis/api/app.py) returns 503 with a "set JARVIS_API_TOKEN"
  // message. Surface it as a clear, actionable card - it is config, not a crash.
  const isWriteGuard = (exc: unknown) =>
    exc instanceof ApiError && exc.status === 503 && /JARVIS_API_TOKEN/.test(exc.message);

  const postFsError = (exc: unknown) => {
    if (isWriteGuard(exc)) {
      post({
        title: "File writes locked",
        body:
          (exc as ApiError).message +
          "\n\nThis cockpit is reachable off-localhost without a token. Set JARVIS_API_TOKEN on " +
          "the server and open it once via ?token=… to enable writes.",
        kind: "error",
      });
      return;
    }
    postError(exc); // bad path, permission denied, etc. - already redacted by the backend
  };

  async function createFile(path: string, content: string): Promise<void> {
    const p = path.trim();
    if (!p) return;
    try {
      const r = await api.createFile(p, content);
      const size = r.bytes != null ? `  (${r.bytes} B)` : "";
      post({ title: "File created", body: `\`${r.path}\`${size}`, kind: "answer" });
    } catch (exc) {
      postFsError(exc);
    }
  }

  async function createFolder(path: string): Promise<void> {
    const p = path.trim();
    if (!p) return;
    try {
      const r = await api.createFolder(p);
      const verb = r.created ? "Folder created" : "Folder already exists";
      post({ title: verb, body: `\`${r.path}\``, kind: "answer" });
    } catch (exc) {
      postFsError(exc);
    }
  }

  return {
    ask,
    showBriefing,
    showAgenda,
    askMarketsNews,
    showFinance,
    addGoal,
    showSuggestions,
    showGoalFeed,
    createFile,
    createFolder,
  };
}

export type Controller = ReturnType<typeof makeController>;
