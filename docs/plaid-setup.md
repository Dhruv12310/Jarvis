# Plaid setup (opt-in finance automation)

Plaid is the **optional, automatic** transaction source. It is the one path where your transactions
flow through a third party (Plaid's aggregator) — the local CSV/OFX import remains the everyday,
fully-local default. Set this up only if you want auto-sync and accept that tradeoff.

The deterministic engine and every figure are identical whether data comes from Plaid or a local file.

## 1. Create a Plaid account + app

1. Sign up at <https://dashboard.plaid.com/signup>.
2. **Sandbox** is free for testing (fake banks); request **Production** access later for your real bank.
3. From **Team Settings → Keys**, copy your `client_id` and the `secret` for the environment you'll use.

## 2. Link an account and get an access token

Plaid Link (a short browser flow) exchanges a bank login for a `public_token`, which you exchange for a
long-lived `access_token` for that bank ("Item"). For a single-user setup:

- Sandbox: use Plaid's Quickstart or the `/sandbox/public_token/create` + `/item/public_token/exchange`
  endpoints to mint a sandbox `access_token` in minutes (no real bank needed).
- Production: run Plaid Link once (Quickstart) against your real bank, then exchange for the token.

(See <https://plaid.com/docs/quickstart/> — the exchange is a few API calls; Jarvis only needs the
resulting `access_token`.)

## 3. Configure Jarvis (secrets in .env — never committed)

Add to your git-ignored `.env`:

```
JARVIS_PLAID_CLIENT_ID=your_client_id
JARVIS_PLAID_SECRET=your_secret
JARVIS_PLAID_ACCESS_TOKEN=access-sandbox-... (or access-production-...)
JARVIS_PLAID_ENV=sandbox        # or: production
```

> These are secrets. Keep `.env` out of git (it already is) and off shared machines.

## 4. Sync

```
python -m jarvis import --plaid
```

This pulls your transactions through `/transactions/sync`, normalizes them (Plaid reports outflows as
positive; Jarvis flips them to the negative-is-outflow convention), categorizes deterministically, and
stores them locally — exactly like a CSV/OFX import. Re-running is idempotent. Everything after the
sync is local; Jarvis never moves money and never gives advice.
