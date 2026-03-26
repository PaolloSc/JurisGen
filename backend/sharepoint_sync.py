"""
SharePoint Auto-Sync
====================
Downloads all files from a SharePoint document library, saves them to disk,
and indexes them in ChromaDB via Docling for RAG.

Configuration (env vars):
  MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET  — Azure AD credentials
  SHAREPOINT_DRIVE_ID                           — OneDrive/SharePoint drive ID
  SHAREPOINT_SYNC_INTERVAL_HOURS               — re-sync interval (default 1)
  SHAREPOINT_FILES_DIR                          — local cache dir (default ./sharepoint_files)
  SHAREPOINT_AUTO_SYNC                          — "true" to sync on startup (default true)
  SHAREPOINT_EXTENSIONS                         — comma-separated exts (default pdf,docx,doc,txt)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ─── Settings ────────────────────────────────────────────────────────────────

FILES_DIR = Path(os.getenv("SHAREPOINT_FILES_DIR", Path(__file__).parent / "sharepoint_files"))
MANIFEST_PATH = FILES_DIR / ".manifest.json"
SYNC_INTERVAL_HOURS = float(os.getenv("SHAREPOINT_SYNC_INTERVAL_HOURS", "1"))
AUTO_SYNC = os.getenv("SHAREPOINT_AUTO_SYNC", "true").lower() == "true"
ALLOWED_EXTENSIONS = set(
    e.strip().lower()
    for e in os.getenv("SHAREPOINT_EXTENSIONS", "pdf,docx,doc,txt").split(",")
    if e.strip()
)

# ─── Sync state (in-memory, updated during/after sync) ───────────────────────

sync_state: dict[str, Any] = {
    "running": False,
    "last_sync": None,
    "next_sync": None,
    "total_files": 0,
    "new_files": 0,
    "updated_files": 0,
    "skipped_files": 0,
    "error_files": 0,
    "progress": "Aguardando",
    "error": None,
    "files": [],  # list of {"name", "folder", "size", "modified", "local_path", "status"}
}

_scheduler_task: asyncio.Task | None = None


# ─── Manifest helpers ─────────────────────────────────────────────────────────

def _load_manifest() -> dict[str, dict]:
    """Load {item_id: {hash, modified, local_path, name}} from disk."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_manifest(manifest: dict[str, dict]):
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Token helper ─────────────────────────────────────────────────────────────

def _get_graph_token() -> str | None:
    """Get Microsoft Graph token using MSAL client credentials. Returns None if not configured."""
    tenant_id = os.getenv("MS_TENANT_ID")
    client_id = os.getenv("MS_CLIENT_ID")
    client_secret = os.getenv("MS_CLIENT_SECRET")
    if not all([tenant_id, client_id, client_secret]):
        return None
    import msal  # type: ignore
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result.get("access_token")


# ─── Core sync logic ──────────────────────────────────────────────────────────

async def _collect_items(client: httpx.AsyncClient, headers: dict, drive_id: str,
                          folder_path: str = "root", folder_name: str = "") -> list[dict]:
    """Recursively collect all file items from SharePoint drive."""
    url = f"{GRAPH_BASE}/drives/{drive_id}/{folder_path}/children"
    params = {"$top": "200", "$select": "id,name,size,file,folder,lastModifiedDateTime,webUrl"}
    items = []

    while url:
        resp = await client.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"[Sync] Graph error {resp.status_code} listing {folder_path}")
            break
        data = resp.json()
        params = None  # only on first request; next pages use @odata.nextLink

        for item in data.get("value", []):
            if "folder" in item:
                sub_name = f"{folder_name}/{item['name']}" if folder_name else item["name"]
                sub_items = await _collect_items(
                    client, headers, drive_id,
                    f"items/{item['id']}", sub_name
                )
                items.extend(sub_items)
            else:
                name = item.get("name", "")
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext in ALLOWED_EXTENSIONS:
                    items.append({
                        "id": item["id"],
                        "name": name,
                        "folder": folder_name,
                        "size": item.get("size", 0),
                        "modified": item.get("lastModifiedDateTime", ""),
                        "web_url": item.get("webUrl", ""),
                        "ext": ext,
                    })

        url = data.get("@odata.nextLink")  # pagination

    return items


async def run_sync(force: bool = False) -> dict[str, Any]:
    """
    Full SharePoint → local disk → ChromaDB sync.

    Args:
        force: Re-index even if file hasn't changed.

    Returns the updated sync_state.
    """
    global sync_state

    if sync_state["running"]:
        return sync_state

    drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
    if not drive_id:
        sync_state["error"] = "SHAREPOINT_DRIVE_ID não configurado."
        sync_state["progress"] = "Erro: SHAREPOINT_DRIVE_ID não configurado."
        return sync_state

    token = _get_graph_token()
    if not token:
        sync_state["error"] = "Credenciais Azure AD não configuradas (MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET)."
        sync_state["progress"] = "Erro: credenciais não configuradas."
        return sync_state

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()

    sync_state.update({
        "running": True,
        "progress": "Listando arquivos no SharePoint...",
        "new_files": 0,
        "updated_files": 0,
        "skipped_files": 0,
        "error_files": 0,
        "error": None,
        "files": [],
    })

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # 1. Collect all items
            all_items = await _collect_items(client, headers, drive_id)
            sync_state["total_files"] = len(all_items)
            sync_state["progress"] = f"Encontrados {len(all_items)} arquivos. Baixando..."
            logger.info(f"[Sync] {len(all_items)} arquivos encontrados no SharePoint.")

            # 2. Process each file
            loop = asyncio.get_event_loop()
            from vector_store import index_document  # type: ignore

            for item in all_items:
                item_id = item["id"]
                name = item["name"]
                folder = item["folder"]
                modified = item["modified"]

                sync_state["progress"] = f"Processando: {name}"

                # Check if unchanged (skip download if modified date matches)
                cached = manifest.get(item_id, {})
                if not force and cached.get("modified") == modified and cached.get("local_path"):
                    local_path = Path(cached["local_path"])
                    if local_path.exists():
                        sync_state["skipped_files"] += 1
                        sync_state["files"].append({
                            "name": name,
                            "folder": folder,
                            "size": item["size"],
                            "modified": modified,
                            "local_path": str(local_path),
                            "web_url": item["web_url"],
                            "status": "sem alteração",
                        })
                        continue

                # Download file
                try:
                    dl_resp = await client.get(
                        f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content",
                        headers=headers,
                        timeout=120,
                    )
                    if not dl_resp.is_success:
                        raise RuntimeError(f"HTTP {dl_resp.status_code}")
                    content_bytes = dl_resp.content
                except Exception as e:
                    logger.warning(f"[Sync] Erro ao baixar '{name}': {e}")
                    sync_state["error_files"] += 1
                    sync_state["files"].append({"name": name, "folder": folder, "status": f"erro download: {e}"})
                    continue

                # Save to local disk
                local_folder = FILES_DIR / folder if folder else FILES_DIR
                local_folder.mkdir(parents=True, exist_ok=True)
                local_path = local_folder / name
                local_path.write_bytes(content_bytes)

                # Index with Docling → ChromaDB
                try:
                    result = await loop.run_in_executor(
                        None,
                        lambda b=content_bytes, n=name, f=folder, u=item["web_url"]: index_document(
                            file_bytes=b,
                            filename=n,
                            folder=f,
                            web_url=u,
                            source="sharepoint",
                            force=force,
                        )
                    )
                    status = result.get("status", "indexado")
                    chunks = result.get("chunks", 0)
                except Exception as e:
                    logger.warning(f"[Sync] Erro ao indexar '{name}': {e}")
                    status = f"erro indexação: {str(e)[:80]}"
                    chunks = 0

                # Update manifest
                manifest[item_id] = {
                    "name": name,
                    "folder": folder,
                    "modified": modified,
                    "local_path": str(local_path),
                    "web_url": item["web_url"],
                    "size": item["size"],
                    "chunks": chunks,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }

                is_new = item_id not in cached or not cached
                if is_new or force:
                    sync_state["new_files"] += 1
                else:
                    sync_state["updated_files"] += 1

                sync_state["files"].append({
                    "name": name,
                    "folder": folder,
                    "size": item["size"],
                    "modified": modified,
                    "local_path": str(local_path),
                    "web_url": item["web_url"],
                    "chunks": chunks,
                    "status": status,
                })

            _save_manifest(manifest)
            now = datetime.now(timezone.utc).isoformat()
            sync_state["last_sync"] = now
            sync_state["progress"] = (
                f"Sincronização concluída: {sync_state['new_files']} novos, "
                f"{sync_state['updated_files']} atualizados, "
                f"{sync_state['skipped_files']} sem alteração, "
                f"{sync_state['error_files']} erros."
            )
            logger.info(f"[Sync] {sync_state['progress']}")

    except Exception as e:
        sync_state["error"] = str(e)
        sync_state["progress"] = f"Erro na sincronização: {e}"
        logger.error(f"[Sync] Erro: {e}", exc_info=True)
    finally:
        sync_state["running"] = False

    return sync_state


# ─── Scheduler ────────────────────────────────────────────────────────────────

async def _scheduler_loop():
    """Background loop that re-syncs every SYNC_INTERVAL_HOURS."""
    interval_secs = SYNC_INTERVAL_HOURS * 3600
    logger.info(f"[Sync] Scheduler iniciado. Intervalo: {SYNC_INTERVAL_HOURS}h")

    # Initial sync on startup
    await asyncio.sleep(5)  # short delay to let server finish starting
    await run_sync()

    while True:
        next_time = time.time() + interval_secs
        sync_state["next_sync"] = datetime.fromtimestamp(next_time, tz=timezone.utc).isoformat()
        await asyncio.sleep(interval_secs)
        await run_sync()


def start_scheduler() -> asyncio.Task | None:
    """Start the background sync scheduler if credentials are configured."""
    global _scheduler_task

    drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
    has_creds = all([
        os.getenv("MS_TENANT_ID"),
        os.getenv("MS_CLIENT_ID"),
        os.getenv("MS_CLIENT_SECRET"),
        drive_id,
    ])

    if not AUTO_SYNC or not has_creds:
        if not has_creds:
            logger.info("[Sync] Credenciais SharePoint não configuradas — auto-sync desativado.")
        else:
            logger.info("[Sync] AUTO_SYNC=false — scheduler não iniciado.")
        return None

    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task

    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("[Sync] Scheduler de sincronização SharePoint iniciado.")
    return _scheduler_task


def stop_scheduler():
    """Cancel the background scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("[Sync] Scheduler cancelado.")


# ─── Local file listing ───────────────────────────────────────────────────────

def list_local_files() -> list[dict]:
    """Return all locally cached SharePoint files from manifest."""
    manifest = _load_manifest()
    files = []
    for item_id, info in manifest.items():
        local_path = Path(info.get("local_path", ""))
        files.append({
            "item_id": item_id,
            "name": info.get("name", ""),
            "folder": info.get("folder", ""),
            "size": info.get("size", 0),
            "modified": info.get("modified", ""),
            "synced_at": info.get("synced_at", ""),
            "chunks": info.get("chunks", 0),
            "web_url": info.get("web_url", ""),
            "available_locally": local_path.exists(),
            "local_path": str(local_path),
        })
    # Sort by folder then name
    files.sort(key=lambda f: (f["folder"], f["name"]))
    return files
