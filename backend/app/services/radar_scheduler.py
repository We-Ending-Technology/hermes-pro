from __future__ import annotations
import asyncio, hashlib, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import httpx
from .commerce_store import CommerceStore
from ..db.supabase import SupabaseREST

def hid(v): return hashlib.sha256(v.encode()).hexdigest()[:32]
async def run_google_news(commerce,db,query="AI automation freelance website app"):
    started=datetime.now(timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as c:
            r=await c.get("https://news.google.com/rss/search",params={"q":query,"hl":"en-US","gl":"US","ceid":"US:en"}); r.raise_for_status()
        root=ET.fromstring(r.text); n=0
        for item in root.findall(".//item")[:20]:
            title=item.findtext("title") or ""; link=item.findtext("link") or ""
            if not title or not link: continue
            await commerce.create_opportunity({"source":"google_news","external_id":hid(link),"title":title,"description":title,"url":link,"source_url":link,"published_at":item.findtext("pubDate"),"kind":"radar_signal"},f"radar:google_news:{hid(link)}"); n+=1
        await db.insert("hermes_radar_runs",{"source":"google_news","status":"completed","items_found":n,"started_at":started,"finished_at":datetime.now(timezone.utc).isoformat()})
        return n
    except Exception as e:
        await db.insert("hermes_radar_runs",{"source":"google_news","status":"failed","started_at":started,"finished_at":datetime.now(timezone.utc).isoformat(),"error_message":str(e)[:500]}); return 0
async def run_radar_cycle(commerce,db):
    n=await run_google_news(commerce,db); return {"ran_at":datetime.now(timezone.utc).isoformat(),"sources":{"google_news":n},"total":n}
async def radar_scheduler_loop(commerce,db,controls):
    while True:
        try:
            s=controls.get_status()
            if not s.get("kill_switches",{}).get("global") and not s.get("settings",{}).get("pause_radar"): await run_radar_cycle(commerce,db)
        except asyncio.CancelledError: raise
        except Exception: pass
        await asyncio.sleep(900)
