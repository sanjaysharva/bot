"""
cogs/_pterodactyl.py — Nexora Cloud
Async Pterodactyl client API helper for per-user server panel integration.
Each user connects their own Pterodactyl Client API key.
"""

import json
import os
from typing import Optional

import aiohttp

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "pterodactyl_config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Per-user config (preferred) ───────────────────────────────────────────────


def get_user_config(user_id: int) -> dict:
    all_cfg = load_config()
    return all_cfg.setdefault("users", {}).setdefault(str(user_id), {})


def set_user_config(user_id: int, cfg: dict):
    all_cfg = load_config()
    all_cfg.setdefault("users", {})[str(user_id)] = cfg
    save_config(all_cfg)


# ── Legacy per-guild config (kept for admin pool features) ─────────────────────


def get_guild_config(guild_id: int) -> dict:
    return load_config().setdefault("guilds", {}).setdefault(str(guild_id), {})


def set_guild_config(guild_id: int, cfg: dict):
    all_cfg = load_config()
    all_cfg.setdefault("guilds", {})[str(guild_id)] = cfg
    save_config(all_cfg)


# ── Request helpers ───────────────────────────────────────────────────────────


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _base_url(panel_url: str) -> str:
    panel_url = panel_url.rstrip("/")
    if not panel_url.endswith("/api/client"):
        panel_url = f"{panel_url}/api/client"
    return panel_url


def _cfg_for_context(user_id: Optional[int] = None, guild_id: Optional[int] = None) -> dict:
    if user_id is not None:
        cfg = get_user_config(user_id)
        if cfg.get("panel_url") and cfg.get("api_key"):
            return cfg
    if guild_id is not None:
        return get_guild_config(guild_id)
    return {}


async def _request(
    method: str,
    endpoint: str,
    user_id: Optional[int] = None,
    guild_id: Optional[int] = None,
    payload: dict = None,
) -> dict:
    cfg = _cfg_for_context(user_id, guild_id)
    panel_url = cfg.get("panel_url")
    api_key = cfg.get("api_key")
    if not panel_url or not api_key:
        raise RuntimeError(
            "Pterodactyl is not configured. Use `!pterodactyl_setup <panel_url> <api_key>` first."
        )

    base = _base_url(panel_url)
    url = f"{base}/{endpoint.lstrip('/')}"

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, headers=_headers(api_key), json=payload, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Pterodactyl API error {resp.status}: {text[:500]}")
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}


# ── Client API wrappers ─────────────────────────────────────────────────────────


async def list_servers(user_id: Optional[int] = None, guild_id: Optional[int] = None) -> list:
    data = await _request("GET", "/", user_id=user_id, guild_id=guild_id)
    return data.get("data", [])


async def server_details(identifier: str, user_id: Optional[int] = None, guild_id: Optional[int] = None) -> dict:
    return await _request("GET", f"/servers/{identifier}", user_id=user_id, guild_id=guild_id)


async def server_resources(identifier: str, user_id: Optional[int] = None, guild_id: Optional[int] = None) -> dict:
    data = await _request("GET", f"/servers/{identifier}/resources", user_id=user_id, guild_id=guild_id)
    return data.get("attributes", {})


async def power_action(identifier: str, signal: str, user_id: Optional[int] = None, guild_id: Optional[int] = None) -> bool:
    valid = {"start", "stop", "restart", "kill"}
    if signal not in valid:
        raise ValueError(f"Invalid signal. Must be one of: {', '.join(valid)}")
    await _request("POST", f"/servers/{identifier}/power", user_id=user_id, guild_id=guild_id, payload={"signal": signal})
    return True


async def send_command(identifier: str, command: str, user_id: Optional[int] = None, guild_id: Optional[int] = None) -> bool:
    await _request(
        "POST",
        f"/servers/{identifier}/command",
        user_id=user_id,
        guild_id=guild_id,
        payload={"command": command},
    )
    return True



async def request_upload_url(identifier: str, directory: str, user_id: Optional[int] = None, guild_id: Optional[int] = None) -> str:
    """Return a signed Pterodactyl upload URL for a server file."""
    endpoint = f"/servers/{identifier}/files/upload"
    if directory:
        endpoint += f"?directory={directory.lstrip('/')}"
    data = await _request("GET", endpoint, user_id=user_id, guild_id=guild_id)
    url = data.get("attributes", {}).get("url") or data.get("url")
    if not url:
        raise RuntimeError("Pterodactyl did not return an upload URL.")
    return url


async def upload_to_signed_url(upload_url: str, filename: str, file_bytes: bytes):
    """Upload file bytes to the signed Pterodactyl upload URL."""
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("files", file_bytes, filename=filename, content_type="application/octet-stream")
        async with session.post(upload_url, data=data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Upload failed {resp.status}: {text[:500]}")
            return True


async def test_connection(user_id: Optional[int] = None, guild_id: Optional[int] = None) -> dict:
    """Return the account info if the API key is valid."""
    return await _request("GET", "/account", user_id=user_id, guild_id=guild_id)
