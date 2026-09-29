from __future__ import annotations
import base64, hashlib, json, secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException
from ..core.config import get_settings
from ..db.supabase import SupabaseREST

GOOGLE_SCOPES=["https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/gmail.readonly","https://www.googleapis.com/auth/calendar.readonly"]
THREADS_SCOPES=["threads_basic","threads_content_publish","threads_read_replies","threads_manage_insights"]
CANVA_SCOPES=["asset:read","asset:write","design:content:read","design:content:write"]

def now(): return datetime.now(timezone.utc)
def cipher():
    key=get_settings().oauth_encryption_key
    if not key: raise RuntimeError("OAUTH_ENCRYPTION_KEY is required")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
def enc(v): return cipher().encrypt(json.dumps(v).encode()).decode()
def dec(v): return json.loads(cipher().decrypt(v.encode()).decode())
def redirect(provider):
    base=(get_settings().public_api_url or "").rstrip("/")
    if not base: raise RuntimeError("PUBLIC_API_URL is required")
    return f"{base}/api/v1/connections/{provider}/callback"

async def save_state(db,provider,uri,metadata=None):
    state=secrets.token_urlsafe(32)
    await db.insert("hermes_oauth_states",{"state":state,"provider":provider,"redirect_uri":uri,"metadata":metadata or {},"expires_at":(now()+timedelta(minutes=10)).isoformat()})
    return state
async def consume_state(db,state,provider):
    rows=await db.select("hermes_oauth_states",params={"select":"*","state":f"eq.{state}","provider":f"eq.{provider}","limit":"1"})
    if not rows: raise HTTPException(400,"OAuth state inválido ou expirado")
    row=rows[0]
    if datetime.fromisoformat(row["expires_at"].replace("Z","+00:00"))<now(): raise HTTPException(400,"OAuth state expirado")
    await db.request("DELETE","hermes_oauth_states",params={"state":f"eq.{state}"})
    return row
async def save_connection(db,provider,token,metadata=None):
    account=str(token.get("user_id") or token.get("id") or "default")
    values={"provider":provider,"account_id":account,"status":"connected","scopes":token.get("scopes",[]),"encrypted_token":enc(token),"token_expires_at":token.get("expires_at"),"metadata":metadata or {},"updated_at":now().isoformat()}
    rows=await db.select("hermes_connections",params={"select":"id","provider":f"eq.{provider}","account_id":f"eq.{account}","limit":"1"})
    if rows: return await db.update("hermes_connections",values,where={"id":f"eq.{rows[0]['id']}"})
    values["created_at"]=now().isoformat()
    return await db.insert("hermes_connections",values)
async def token_for(db,provider):
    rows=await db.select("hermes_connections",params={"select":"*","provider":f"eq.{provider}","status":"eq.connected","order":"updated_at.desc","limit":"1"})
    if not rows: raise HTTPException(409,f"{provider} não conectado")
    return dec(rows[0]["encrypted_token"])

def build_connections_router(db:SupabaseREST)->APIRouter:
    r=APIRouter(prefix="/api/v1/connections",tags=["connections"])
    @r.get("")
    async def statuses():
        rows=await db.select("hermes_connections",params={"select":"provider,account_id,status,scopes,token_expires_at,updated_at","order":"provider.asc"})
        known={x["provider"]:x for x in rows}
        return [{"provider":p,"status":known.get(p,{}).get("status","not_configured"),"scopes":known.get(p,{}).get("scopes",[]),"account_id":known.get(p,{}).get("account_id"),"token_expires_at":known.get(p,{}).get("token_expires_at")} for p in ("google","threads","canva")]
    @r.get("/google/start")
    async def google_start():
        s=get_settings()
        if not s.google_client_id: raise HTTPException(503,"GOOGLE_CLIENT_ID não configurado")
        uri=redirect("google"); state=await save_state(db,"google",uri)
        q={"client_id":s.google_client_id,"redirect_uri":uri,"response_type":"code","access_type":"offline","prompt":"consent","scope":" ".join(GOOGLE_SCOPES),"state":state}
        return {"authorization_url":"https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(q),"scopes":GOOGLE_SCOPES}
    @r.get("/google/callback")
    async def google_callback(code:str,state:str):
        s=get_settings(); saved=await consume_state(db,state,"google")
        async with httpx.AsyncClient(timeout=20) as c:
            x=await c.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":s.google_client_id,"client_secret":s.google_client_secret,"redirect_uri":saved["redirect_uri"],"grant_type":"authorization_code"})
        if x.is_error: raise HTTPException(400,x.text[:500])
        t=x.json(); t["scopes"]=GOOGLE_SCOPES; t["expires_at"]=(now()+timedelta(seconds=int(t.get("expires_in",3600)))).isoformat()
        await save_connection(db,"google",t,{"services":["drive","gmail","calendar"]})
        return {"connected":True,"provider":"google"}
    @r.get("/threads/start")
    async def threads_start():
        s=get_settings()
        if not s.threads_app_id: raise HTTPException(503,"THREADS_APP_ID não configurado")
        uri=redirect("threads"); state=await save_state(db,"threads",uri)
        q={"client_id":s.threads_app_id,"redirect_uri":uri,"response_type":"code","scope":",".join(THREADS_SCOPES),"state":state}
        return {"authorization_url":"https://threads.net/oauth/authorize?"+urlencode(q),"scopes":THREADS_SCOPES}
    @r.get("/threads/callback")
    async def threads_callback(code:str,state:str):
        s=get_settings(); saved=await consume_state(db,state,"threads")
        async with httpx.AsyncClient(timeout=20) as c:
            x=await c.post("https://graph.threads.net/oauth/access_token",data={"client_id":s.threads_app_id,"client_secret":s.threads_app_secret,"code":code,"grant_type":"authorization_code","redirect_uri":saved["redirect_uri"]})
        if x.is_error: raise HTTPException(400,x.text[:500])
        t=x.json(); short=t.get("access_token")
        if not short: raise HTTPException(400,"Threads não retornou access_token")
        async with httpx.AsyncClient(timeout=20) as c:
            y=await c.get("https://graph.threads.net/access_token",params={"grant_type":"th_exchange_token","client_secret":s.threads_app_secret,"access_token":short})
        longt=y.json() if y.is_success else {}
        t["access_token"]=longt.get("access_token",short); t["scopes"]=THREADS_SCOPES; t["user_id"]=t.get("user_id") or longt.get("user_id"); t["expires_at"]=(now()+timedelta(seconds=int(longt.get("expires_in",5184000)))).isoformat()
        await save_connection(db,"threads",t)
        return {"connected":True,"provider":"threads"}
    @r.get("/canva/start")
    async def canva_start():
        s=get_settings()
        if not s.canva_client_id: raise HTTPException(503,"CANVA_CLIENT_ID não configurado")
        uri=redirect("canva"); verifier=secrets.token_urlsafe(48); digest=hashlib.sha256(verifier.encode()).digest(); challenge=base64.urlsafe_b64encode(digest).decode().rstrip("=")
        state=await save_state(db,"canva",uri,{"code_verifier":verifier})
        q={"code_challenge":challenge,"code_challenge_method":"s256","scope":" ".join(CANVA_SCOPES),"response_type":"code","client_id":s.canva_client_id,"state":state,"redirect_uri":uri}
        return {"authorization_url":"https://www.canva.com/api/oauth/authorize?"+urlencode(q),"scopes":CANVA_SCOPES}
    @r.get("/canva/callback")
    async def canva_callback(code:str,state:str):
        s=get_settings(); saved=await consume_state(db,state,"canva"); verifier=(saved.get("metadata") or {}).get("code_verifier")
        async with httpx.AsyncClient(timeout=20) as c:
            x=await c.post("https://api.canva.com/rest/v1/oauth/token",data={"grant_type":"authorization_code","code":code,"redirect_uri":saved["redirect_uri"],"client_id":s.canva_client_id,"client_secret":s.canva_client_secret,"code_verifier":verifier})
        if x.is_error: raise HTTPException(400,x.text[:500])
        t=x.json(); t["scopes"]=CANVA_SCOPES; t["expires_at"]=(now()+timedelta(seconds=int(t.get("expires_in",3600)))).isoformat()
        await save_connection(db,"canva",t)
        return {"connected":True,"provider":"canva"}
    @r.post("/threads/publish")
    async def threads_publish(body:dict):
        text=str(body.get("text","")).strip()
        if not text or len(text)>500: raise HTTPException(422,"text obrigatório e até 500 caracteres")
        if body.get("dry_run",True): return {"executed":False,"dry_run":True,"provider":"threads","text":text}
        t=await token_for(db,"threads"); a=t["access_token"]
        async with httpx.AsyncClient(timeout=30) as c:
            x=await c.post("https://graph.threads.net/me/threads",params={"media_type":"TEXT","text":text,"access_token":a})
            if x.is_error: raise HTTPException(502,x.text[:500])
            y=await c.post("https://graph.threads.net/me/threads_publish",params={"creation_id":x.json()["id"],"access_token":a})
        if y.is_error: raise HTTPException(502,y.text[:500])
        return {"executed":True,"provider":"threads","post":y.json()}
    @r.post("/canva/design")
    async def canva_design(body:dict):
        if body.get("dry_run",True): return {"executed":False,"dry_run":True,"provider":"canva"}
        t=await token_for(db,"canva"); payload={"type":"type_and_asset","design_type":body.get("design_type",{"type":"preset","name":"doc"}),"title":body.get("title","Hermes Design")}
        if body.get("asset_id"): payload["asset_id"]=body["asset_id"]
        async with httpx.AsyncClient(timeout=30) as c:
            x=await c.post("https://api.canva.com/rest/v1/designs",headers={"Authorization":f"Bearer {t['access_token']}"},json=payload)
        if x.is_error: raise HTTPException(502,x.text[:500])
        return {"executed":True,"provider":"canva",**x.json()}
    @r.post("/canva/export")
    async def canva_export(body:dict):
        did=str(body.get("design_id","")).strip()
        if not did: raise HTTPException(422,"design_id obrigatório")
        if body.get("dry_run",True): return {"executed":False,"dry_run":True,"provider":"canva","design_id":did}
        t=await token_for(db,"canva")
        async with httpx.AsyncClient(timeout=30) as c:
            x=await c.post("https://api.canva.com/rest/v1/exports",headers={"Authorization":f"Bearer {t['access_token']}"},json={"design_id":did,"format":{"type":body.get("format","png")}})
        if x.is_error: raise HTTPException(502,x.text[:500])
        return {"executed":True,"provider":"canva",**x.json()}
    return r
