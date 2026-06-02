# Google Calendar setup (one-time)

Jarvis reads your Google Calendar **read-only**, locally, behind the trust boundary. You do this
setup once. It produces a `credentials.json` (the OAuth client) and, after first auth, a `token.json`
(your user token). Both live in `./data/`, which is git-ignored — they are secrets and never get
committed.

## 1. Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>.
2. Top bar → project dropdown → **New Project**. Name it (e.g. `jarvis`), create, and select it.

## 2. Enable the Calendar API

1. **APIs & Services → Library**.
2. Search **Google Calendar API** → **Enable**.

## 3. Configure the OAuth consent screen (Testing mode, just you)

1. **APIs & Services → OAuth consent screen**.
2. User type: **External** → Create.
3. Fill the required fields (app name `jarvis`, your email for support + developer contact). Save.
4. **Scopes**: you can skip adding scopes here; the app requests `calendar.readonly` at runtime.
5. **Test users**: add your own Google account email. Save.
6. Leave the publishing status as **Testing** — no Google verification is needed for your own account.

## 4. Create the OAuth client (Desktop app)

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**. Name it (e.g. `jarvis-desktop`). Create.
3. **Download JSON**. Save it as:

   ```
   D:\Projects\Jarvis\data\credentials.json
   ```

## 5. Authorize Jarvis

From the repo root:

```
python -m jarvis calendar-auth
```

A browser window opens. Sign in with the test-user account, accept the read-only consent. On success
the token is written to `data\token.json` and the command prints a confirmation.

> If you see "Access blocked / app not verified", confirm the account is listed under **Test users**
> (step 3.5) and that you're signing in with that same account.

## 6. Use it

In the chat REPL:

```
:cal        # today's agenda
```

The token refreshes itself automatically. To revoke, delete `data\token.json` (and re-run
`calendar-auth` to reconnect). Widening beyond read-only (event creation) is a separate, later step
and will require re-authorizing with a broader scope.
