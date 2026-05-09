import os
import sys
from pathlib import Path

import msal

from .config import SCOPES, Settings, load_settings


def _load_cache(path: str) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    p = Path(path)
    if p.exists():
        cache.deserialize(p.read_text())
    return cache


def _save_cache(cache: msal.SerializableTokenCache, path: str) -> None:
    if cache.has_state_changed:
        p = Path(path)
        p.write_text(cache.serialize())
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


def _build_app(settings: Settings, cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=settings.client_id,
        authority=settings.authority,
        token_cache=cache,
    )


def get_access_token(settings: Settings | None = None) -> str:
    """Return a valid access token, prompting for device-code login if needed."""
    settings = settings or load_settings()
    cache = _load_cache(settings.token_cache_path)
    app = _build_app(settings, cache)

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to start device-code flow: {flow}")
        # Print to stderr so stdout stays clean for piping JSON output.
        print(flow["message"], file=sys.stderr, flush=True)
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache, settings.token_cache_path)

    if "access_token" not in result:
        raise RuntimeError(
            f"Auth failed: {result.get('error')}: {result.get('error_description')}"
        )
    return result["access_token"]


def logout(settings: Settings | None = None) -> int:
    """Remove all cached accounts. Returns the number of accounts removed."""
    settings = settings or load_settings()
    cache = _load_cache(settings.token_cache_path)
    app = _build_app(settings, cache)
    accounts = app.get_accounts()
    for acct in accounts:
        app.remove_account(acct)
    _save_cache(cache, settings.token_cache_path)
    return len(accounts)
