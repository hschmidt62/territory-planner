from __future__ import annotations

from typing import Any, Iterator

from .client import GraphClient

DEFAULT_MAIL_FIELDS = (
    "id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview,parentFolderId"
)


def list_messages(
    client: GraphClient,
    folder: str = "inbox",
    *,
    top: int = 25,
    unread_only: bool = False,
    select: str = DEFAULT_MAIL_FIELDS,
    order_by: str = "receivedDateTime desc",
) -> Iterator[dict[str, Any]]:
    params: dict[str, Any] = {"$top": min(top, 100), "$select": select, "$orderby": order_by}
    if unread_only:
        params["$filter"] = "isRead eq false"
    yield from client.paged(f"/me/mailFolders/{folder}/messages", params=params, max_items=top)


def search_messages(
    client: GraphClient,
    query: str,
    *,
    top: int = 25,
    select: str = DEFAULT_MAIL_FIELDS,
) -> Iterator[dict[str, Any]]:
    """Full-text search across the mailbox using Graph $search."""
    params = {"$search": f'"{query}"', "$top": min(top, 25), "$select": select}
    yield from client.paged("/me/messages", params=params, max_items=top)


def list_folders(client: GraphClient) -> Iterator[dict[str, Any]]:
    yield from client.paged(
        "/me/mailFolders",
        params={"$top": 100, "$select": "id,displayName,parentFolderId,totalItemCount,unreadItemCount"},
    )


def find_folder_by_name(client: GraphClient, name: str) -> dict[str, Any] | None:
    """Case-insensitive lookup of a folder by display name (top-level only)."""
    target = name.casefold()
    for folder in list_folders(client):
        if folder.get("displayName", "").casefold() == target:
            return folder
    return None


def create_folder(client: GraphClient, name: str, parent_id: str | None = None) -> dict[str, Any]:
    path = "/me/mailFolders" if parent_id is None else f"/me/mailFolders/{parent_id}/childFolders"
    return client.post(path, json={"displayName": name})


def ensure_folder(client: GraphClient, name: str) -> dict[str, Any]:
    folder = find_folder_by_name(client, name)
    return folder if folder else create_folder(client, name)


def move_message(client: GraphClient, message_id: str, destination_folder_id: str) -> dict[str, Any]:
    return client.post(
        f"/me/messages/{message_id}/move",
        json={"destinationId": destination_folder_id},
    )


def mark_read(client: GraphClient, message_id: str, read: bool = True) -> dict[str, Any]:
    return client.patch(f"/me/messages/{message_id}", json={"isRead": read})
