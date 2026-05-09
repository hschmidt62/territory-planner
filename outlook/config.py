import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = [
    "Mail.ReadWrite",
    "MailboxSettings.Read",
    "Calendars.Read",
    "Calendars.ReadWrite",
    "User.Read",
]


@dataclass(frozen=True)
class Settings:
    client_id: str
    tenant_id: str
    token_cache_path: str

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"


def load_settings() -> Settings:
    client_id = os.environ.get("OUTLOOK_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError(
            "OUTLOOK_CLIENT_ID is not set. Copy .env.example to .env and fill it in. "
            "See README.md for how to create an Azure AD app registration."
        )
    return Settings(
        client_id=client_id,
        tenant_id=os.environ.get("OUTLOOK_TENANT_ID", "common").strip() or "common",
        token_cache_path=os.environ.get("OUTLOOK_TOKEN_CACHE", ".token_cache.bin").strip(),
    )
