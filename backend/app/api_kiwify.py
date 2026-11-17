from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .core.config import get_settings
from .services.kiwify_api import KiwifyAPIClient, KiwifyAPIError, safe_product, safe_sale

settings = get_settings()
client = KiwifyAPIClient(settings)
router = APIRouter(prefix="/api/v1/kiwify", tags=["kiwify"])


def _raise_api_error(exc: KiwifyAPIError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/status")
async def kiwify_api_status() -> dict[str, Any]:
    if not client.configured:
        return {
            "configured": False,
            "connected": False,
            "account_verified": False,
            "webhook_token_configured": bool(client.webhook_token),
            "message": "Credenciais incompletas no backend. O Hermes precisa de Client ID, Client Secret e Account ID.",
        }
    try:
        account = await client.account_details()
        returned_account_id = str(account.get("id") or "").strip()
        expected_account_id = str(client.account_id or "").strip()
        if not returned_account_id or returned_account_id != expected_account_id:
            return {
                "configured": True,
                "connected": False,
                "account_verified": False,
                "webhook_token_configured": bool(client.webhook_token),
                "message": "OAuth funcionou, mas a identidade retornada pela Kiwify não corresponde ao Account ID configurado. Nenhuma publicação foi realizada.",
            }

        products = await client.list_products(page_size=1, page_number=1)
        pagination = products.get("pagination") or {}
        return {
            "configured": True,
            "connected": True,
            "account_verified": True,
            "account_id": returned_account_id,
            "product_count": pagination.get("count"),
            "webhook_token_configured": bool(client.webhook_token),
            "message": "OAuth validado, Account ID confirmado e consulta de produtos autorizada.",
        }
    except KiwifyAPIError as exc:
        return {
            "configured": True,
            "connected": False,
            "account_verified": False,
            "webhook_token_configured": bool(client.webhook_token),
            "message": str(exc),
        }


@router.get("/products")
async def kiwify_products(
    page_size: int = Query(default=100, ge=1, le=100),
    page_number: int = Query(default=1, ge=1),
) -> dict[str, Any]:
    try:
        result = await client.list_products(page_size=page_size, page_number=page_number)
    except KiwifyAPIError as exc:
        _raise_api_error(exc)
    items = result.get("data") or []
    return {
        "items": [safe_product(item) for item in items if isinstance(item, dict)],
        "pagination": result.get("pagination") or {},
        "source": "kiwify_api",
    }


@router.get("/sales")
async def kiwify_sales(
    start_date: date | None = None,
    end_date: date | None = None,
    page_size: int = Query(default=100, ge=1, le=100),
    page_number: int = Query(default=1, ge=1),
) -> dict[str, Any]:
    today = date.today()
    end = end_date or today
    start = start_date or (end - timedelta(days=7))
    try:
        result = await client.list_sales(start, end, page_size=page_size, page_number=page_number)
    except KiwifyAPIError as exc:
        _raise_api_error(exc)
    items = result.get("data") or []
    return {
        "items": [safe_sale(item) for item in items if isinstance(item, dict)],
        "pagination": result.get("pagination") or {},
        "range": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "source": "kiwify_api",
        "note": "Dados de compradores foram omitidos. Esta consulta não altera nem publica produtos.",
    }


@router.post("/webhook/setup")
async def setup_kiwify_webhook(request: Request) -> dict[str, Any]:
    if not client.configured:
        raise HTTPException(status_code=409, detail="Configure as credenciais da API Kiwify antes de cadastrar o webhook.")
    if not client.webhook_token:
        raise HTTPException(status_code=409, detail="Configure KIWIFY_WEBHOOK_TOKEN no backend antes de cadastrar o webhook.")
    base_url = str(settings.hermes_public_api_url or "").strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise HTTPException(status_code=503, detail="HERMES_PUBLIC_API_URL precisa ser uma URL HTTPS pública.")
    callback_url = f"{base_url}/api/v1/webhooks/kiwify"
    try:
        result = await client.ensure_sales_webhook(callback_url)
    except KiwifyAPIError as exc:
        _raise_api_error(exc)
    return {
        "ok": True,
        "callback_url": callback_url,
        **result,
        "message": "Webhook Kiwify configurado e apontando para o Hermes." if result.get("created") else "Webhook Hermes já estava cadastrado; nenhuma duplicata foi criada.",
    }
