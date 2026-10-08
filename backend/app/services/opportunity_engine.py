from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import httpx

KEYWORDS={"python":18,"api":16,"automation":16,"automação":16,"ai":14,"ia":14,"data":12,"scraping":10,"backend":10,"fastapi":10,"django":8,"integration":12,"integração":12,"pandas":8}
BLOCKED=("captcha bypass","credential theft","malware","spam bot","fraud","phishing","cracking")

@dataclass
class Opportunity:
    title:str; url:str; source:str; summary:str=""; score:int=0; difficulty:str="unknown"; suggested_price:float|None=None; proposal:str=""; rejection_reason:str|None=None

class _Parser(HTMLParser):
    def __init__(self,base): super().__init__(); self.base=base; self.links=[]; self.href=None; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            href=dict(attrs).get("href")
            if href: self.href=urljoin(self.base,href); self.text=[]
    def handle_data(self,data):
        if self.href: self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            text=re.sub(r"\s+"," "," ".join(self.text)).strip()
            if text: self.links.append((self.href,text[:300]))
            self.href=None; self.text=[]

class OpportunityEngine:
    def __init__(self,db,settings): self.db=db; self.settings=settings
    def source_urls(self):
        configured=[x.strip() for x in self.settings.radar_source_urls.split(",") if x.strip()]
        return configured or ["https://www.freelancer.com/jobs/python","https://www.99freelas.com.br/projects?q=python","https://www.workana.com/pt/jobs?skills=python","https://www.workana.com/pt/jobs?skills=api"]
    async def collect(self,limit=1000):
        results={}
        async with httpx.AsyncClient(timeout=25,follow_redirects=True,headers={"User-Agent":"Hermes-Pro-Radar/1.0"}) as client:
            for source in self.source_urls():
                for page in range(1,11):
                    url=source if page==1 else source+("&" if "?" in source else "?")+f"page={page}"
                    try: r=await client.get(url); r.raise_for_status()
                    except Exception: break
                    p=_Parser(str(r.url)); p.feed(r.text); found=0
                    for href,title in p.links:
                        if not any(k in title.lower() for k in KEYWORDS): continue
                        key=self.canonical(href)
                        if key not in results:
                            results[key]=Opportunity(title,key,urlparse(key).netloc); found+=1
                        if len(results)>=limit: return list(results.values())
                    if not found: break
        return list(results.values())
    def score(self,x):
        text=(x.title+" "+x.summary).lower()
        if any(b in text for b in BLOCKED): x.rejection_reason="conteúdo incompatível"; return x
        match=sum(w for k,w in KEYWORDS.items() if k in text)
        x.score=min(100,match+18+(15 if len(text)<700 else 8)+(15 if not any(z in text for z in ("certificado digital","hardware","android nativo","ios nativo")) else 3))
        x.difficulty="baixa" if x.score>=65 else ("média" if x.score>=45 else "alta")
        x.suggested_price=450 if x.score>=80 else (300 if x.score>=65 else (200 if x.score>=50 else 120))
        x.proposal=f"Olá! Vi o projeto “{x.title}” e consigo atacar o problema com Python, APIs e automação. Posso estruturar, implementar, testar e documentar a solução. Estimativa inicial: R$ {x.suggested_price:.0f}, ajustável após confirmar requisitos e acessos. Não incluo credenciais/serviços externos que o cliente não forneça."
        if x.score<40: x.rejection_reason="aderência insuficiente"
        return x
    @staticmethod
    def canonical(url):
        p=urlparse(url); return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
    async def run(self,limit=1000):
        items=[self.score(x) for x in await self.collect(limit)]
        minimum = max(0, min(100, self.settings.radar_min_score))
        top=sorted([x for x in items if not x.rejection_reason and x.score >= minimum],key=lambda x:x.score,reverse=True)[:10]
        now=datetime.now(timezone.utc).isoformat()
        for x in top:
            try:
                await self.db.insert("hermes_opportunities",{"type":"service","source":x.source,"source_url":x.url,"title":x.title,"description":x.summary,"url":x.url,"summary":x.summary,"signals":{"python":100},"score":x.score,"confidence":90,"difficulty":x.difficulty,"suggested_price":x.suggested_price,"currency":"BRL","proposal":x.proposal,"status":"approved","application_status":"not_attempted","idempotency_key":x.source+":"+x.url,"metadata":{"radar":"autonomous"},"created_at":now,"updated_at":now})
            except Exception:
                pass
        approved = [x for x in items if not x.rejection_reason and x.score >= minimum]
        return {"collected":len(items),"approved":len(approved),"top":[x.__dict__ for x in top],"ran_at":now}
