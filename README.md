# Outlook connector

A small Python CLI that connects to your Outlook mailbox via the Microsoft Graph API. It can:

- List and search messages
- List, create, and move messages between folders
- Auto-organize the inbox using simple rules (sender / subject / regex)
- List and create calendar events

Auth uses the **device-code flow** with MSAL — no client secret, no hosted redirect URI. Works for personal Outlook.com accounts and Microsoft 365 work/school accounts.

## 1. Create an Azure AD app registration

You only need to do this once.

1. Sign in to <https://portal.azure.com> and open **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Fill in:
   - **Name**: `territory-planner` (or anything you like).
   - **Supported account types**: choose *Accounts in any organizational directory and personal Microsoft accounts* if you want both work and personal Outlook.com to work. Pick *Personal Microsoft accounts only* for Outlook.com only.
   - **Redirect URI**: leave blank.
3. Click **Register**, then copy the **Application (client) ID** from the overview page.
4. Open **Authentication** in the left nav, scroll to **Advanced settings**, set **Allow public client flows** to **Yes**, and **Save**. (This enables device-code auth.)
5. Open **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**, then add:
   - `Mail.ReadWrite`
   - `MailboxSettings.Read`
   - `Calendars.ReadWrite`
   - `User.Read`
   - `offline_access`

   Click **Add permissions**. (No admin consent is needed for personal accounts; for work accounts you may need to click **Grant admin consent**.)

## 2. Configure the project

```bash
cp .env.example .env
# edit .env, paste the Application (client) ID into OUTLOOK_CLIENT_ID
```

`OUTLOOK_TENANT_ID` defaults to `common`, which works for both personal and work accounts. Use `consumers` for personal-only or your tenant GUID for work-only.

## 3. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Sign in

```bash
python -m outlook login
```

The first run prints a URL and a one-time code — open the URL, paste the code, and approve. The token is cached in `.token_cache.bin` (chmod 600, gitignored). Subsequent runs reuse the cache and silently refresh.

## 5. Use it

```bash
# Who am I?
python -m outlook whoami

# Mail
python -m outlook email list --folder inbox --top 20 --unread
python -m outlook email search "invoice from acme"
python -m outlook email folders
python -m outlook email create-folder Newsletters
python -m outlook email move <message-id> Newsletters

# Calendar (defaults to next 7 days)
python -m outlook calendar list --days 14
python -m outlook calendar create \
  --subject "Territory review" \
  --start 2026-05-12T15:00:00Z \
  --end   2026-05-12T16:00:00Z \
  --attendee teammate@example.com

# Organize inbox by rules. Start with --dry-run to preview.
python -m outlook email organize --rules rules.example.json --dry-run
python -m outlook email organize --rules rules.example.json
```

### Rules file format

Each rule has a destination folder (created if missing) and at least one match condition. The first matching rule wins.

```json
[
  {
    "name": "Newsletters",
    "folder": "Newsletters",
    "from_contains": ["newsletter@", "noreply@"]
  },
  {
    "name": "Receipts",
    "folder": "Receipts",
    "subject_regex": "(receipt|invoice|order #)"
  }
]
```

Supported fields: `from_contains` (list of substrings, case-insensitive), `subject_contains` (list of substrings), `subject_regex` (Python regex, case-insensitive).

## Programmatic use

```python
from outlook import GraphClient
from outlook.mail import list_messages

client = GraphClient()
for msg in list_messages(client, folder="inbox", top=10, unread_only=True):
    print(msg["subject"])
```

## Notes

- All output is JSON to stdout; status messages and the device-code prompt go to stderr, so you can pipe results into `jq`.
- `Mail.ReadWrite` is required to move messages. If you only want read access, swap it for `Mail.Read` in `outlook/config.py` and in the Azure portal.
- Tokens are cached locally — running `python -m outlook logout` clears them.
