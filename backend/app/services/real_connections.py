from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException

from ..core.config import get_settings
from ..db.supabase import SupabaseREST

CANVA_SCOPES = ["asset:read", "asset:write", "design:content:read", "design:content:write"]


def now():
    return datetime.now(timezone.utc)


def cipher():
    key = get_settings().oauth_encryption_key
    if not key:
        raise RuntimeError("OAUTH_ENCRYPTION_KEY is required")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def enc(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()


def dec(value):
    return json.loads(cipher().decrypt(value.encode()).decode())


def redirect(provider: str) -> str:
    base = (get_settings().public_api_url or "").rstrip("/")
    if not base:
        raise RuntimeError("PUBLIC_API_URL is required")
    return f"{base}/api/v1/connections/{provider}/callback"


async def save_state(db, provider: str, uri: str, metadata=None):
    state = secrets.token_urlsafe(32)
    await db.insert(
        "hermes_oauth_states",
        {
            "state": state,
            "provider": provider,
            "redirect_uri": uri,
            "metadata": metadata or {},
            "expires_at": (now() + timedelta(minutes=10)).isoformat(),
        },
    )
    return state


async def consume_state(db, state: str, provider: str):
    rows = await db.select(
        "hermes_oauth_states",
        params={"select": "*", "state": f"eq.{state}", "provider": f"eq.{provider}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(400, "OAuth state inválido ou expirado")
    row = rows[0]
    if datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) < now():
        raise HTTPException(400, "OAuth state expirado")
    await db.request("DELETE", "hermes_oauth_states", params={"state": f"eq.{state}"})
    return row


async def save_connection(db, provider: str, token: dict, metadata=None):
    account = str(token.get("user_id") or token.get("id") or "default")
    values = {
        "provider": provider,
        "account_id": account,
        "status": "connected",
        "scopes": token.get("scopes", []),
        "encrypted_token": enc(token),
        "token_expires_at": token.get("expires_at"),
        "metadata": metadata or {},
        "updated_at": now().isoformat(),
    }
    rows = await db.select(
        "hermes_connections",
        params={"select": "id", "provider": f"eq.{provider}", "account_id": f"eq.{account}", "limit": "1"},
    )
    if rows:
        return await db.update("hermes_connections", values, where={"id": f"eq.{rows[0]['id']}"})
    values["created_at"] = now().isoformat()
    return await db.insert("hermes_connections", values)


async def token_for(db, provider: str):
    rows = await db.select(
        "hermes_connections",
        params={"select": "*", "provider": f"eq.{provider}", "status": "eq.connected", "order": "updated_at.desc", "limit": "1"},
    )
    if not rows:
        raise HTTPException(409, f"{provider} não conectado")
    return dec(rows[0]["encrypted_token"])


def build_connections_router(db: SupabaseREST) -> APIRouter:
    router = APIRouter(prefix="/api/v1/connections", tags=["connections"])

    @router.get("")
    async def statuses():
        rows = await db.select(
            "hermes_connections",
            params={"select": "provider,account_id,status,scopes,token_expires_at,updated_at", "order": "provider.asc"},
        )
        known = {row["provider"]: row for row in rows}
        row = known.get("canva", {})
        return [{
            "provider": "canva",
            "status": row.get("status", "not_configured"),
            "scopes": row.get("scopes", []),
            "account_id": row.get("account_id"),
            "token_expires_at": row.get("token_expires_at"),
        }]

    @router.get("/canva/start")
    async def canva_start():
        settings = get_settings()
        if not settings.canva_client_id:
            raise HTTPException(503, "CANVA_CLIENT_ID não configurado")
        uri = redirect("canva")
        verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        state = await save_state(db, "canva", uri, {"code_verifier": verifier})
        query = {
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": " ".join(CANVA_SCOPES),
            "response_type": "code",
            "client_id": settings.canva_client_id,
            "state": state,
            "redirect_uri": uri,
        }
        return {"authorization_url": "https://www.canva.com/api/oauth/authorize?" + urlencode(query), "scopes": CANVA_SCOPES, "redirect_uri": uri}

    @router.get("/canva/callback")
    async def canva_callback(code: str, state: str):
        settings = get_settings()
        saved = await consume_state(db, state, "canva")
        verifier = (saved.get("metadata") or {}).get("code_verifier")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.canva.com/rest/v1/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": saved["redirect_uri"],
                    "client_id": settings.canva_client_id,
                    "client_secret": settings.canva_client_secret,
                    "code_verifier": verifier,
                },
            )
        if response.is_error:
            raise HTTPException(400, response.text[:500])
        token = response.json()
        token["scopes"] = CANVA_SCOPES
        token["expires_at"] = (now() + timedelta(seconds=int(token.get("expires_in", 3600)))).isoformat()
        await save_connection(db, "canva", token)
        return {"connected": True, "provider": "canva"}

    @router.post("/canva/design")
    async def canva_design(body: dict):
        if body.get("dry_run", True):
            return {"executed": False, "dry_run": True, "provider": "canva"}
        token = await token_for(db, "canva")
        payload = {
            "type": "type_and_asset",
            "design_type": body.get("design_type", {"type": "preset", "name": "doc"}),
            "title": body.get("title", "Hermes Design"),
        }
        if body.get("asset_id"):
            payload["asset_id"] = body["asset_id"]
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.canva.com/rest/v1/designs",
                headers={"Authorization": f"Bearer {token['access_token']}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.is_error:
            raise HTTPException(502, response.text[:500])
        return {"executed": True, "provider": "canva", **response.json()}

    @router.post("/canva/export")
    async def canva_export(body: dict):
        design_id = str(body.get("design_id", "")).strip()
        if not design_id:
            raise HTTPException(422, "design_id obrigatório")
        if body.get("dry_run", True):
            return {"executed": False, "dry_run": True, "provider": "canva", "design_id": design_id}
        token = await token_for(db, "canva")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.canva.com/rest/v1/exports",
                headers={"Authorization": f"Bearer {token['access_token']}", "Content-Type": "application/json"},
                json={"design_id": design_id, "format": {"type": body.get("format", "png")}},
            )
        if response.is_error:
            raise HTTPException(502, response.text[:500])
        return {"executed": True, "provider": "canva", **response.json()}

    return router
