"""Google OAuth for the calendar (read-only).

The InstalledApp flow runs once (``python -m jarvis calendar-auth``) and persists a token to
./data/token.json (git-ignored). Afterwards ``load_credentials`` reads and silently refreshes that
token. The OAuth client (credentials.json) is downloaded by the user from Google Cloud; see
docs/google-calendar-setup.md.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jarvis.config import config

# Read-only: Phase 2 never writes to the calendar. Widening this scope (3b) requires re-auth.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def load_credentials(
    credentials_path: Path | None = None, token_path: Path | None = None
) -> Credentials | None:
    """Return valid stored credentials (refreshing if needed), or None if not yet authorized."""
    token_path = token_path or config.google_token_path
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _persist(creds, token_path)
        return creds
    return None


def authorize(credentials_path: Path | None = None, token_path: Path | None = None) -> Credentials:
    """Run the interactive consent flow once and persist the token. Used by ``calendar-auth``."""
    credentials_path = credentials_path or config.google_credentials_path
    token_path = token_path or config.google_token_path
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"missing OAuth client at {credentials_path}. Download it from Google Cloud "
            "(see docs/google-calendar-setup.md) and place it there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _persist(creds, token_path)
    return creds


def build_service(creds: Credentials):
    """Build the Calendar v3 service. cache_discovery=False avoids a noisy local-cache warning."""
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _persist(creds: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    # The token holds a long-lived refresh_token; restrict it to the owner. Effective on POSIX
    # (e.g. the Heartbeat box); a near no-op on Windows ACLs, hence best-effort.
    try:
        token_path.chmod(0o600)
    except OSError:
        pass
