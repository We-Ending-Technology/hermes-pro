from __future__ import annotations

from datetime import date
from typing import Any

import httpx


class KiwifyAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class KiwifyAPIClient:
    """Small async client for Kiwify's documented OAuth, products, sales and webhook API."""

    base_url = "https://public-api.kiwify.com/v1"

    def __init__(self, settings: Any):
        self.client_id = str(getattr(settings, "kiwify_api_client_id", "") or "").strip()
        self.client_secret = str(getattr(settings, "kiwify_api_client_secret", "") or "").strip()
        self.account_id = str(getattr(settings, "kiwify_account_id", "") or "").strip()
        self.webhook_token = str(getattr(settings, "kiwify_webhook_token", "") or "").strip()
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.account_id)

    async def _token(self, force: bool = False) -> str:
        import time

        if not self.configured:
            raise KiwifyAPIError(503, "Credenciais da API Kiwify não configuradas.")
        if not force and self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
                response = await client.post(
                    f"{self.base_url}/oauth/token",
                    data={"client_id": self.client_id, "client_secret": self.client_secret},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            if response.status_code >= 400:
                raise KiwifyAPIError(502 if response.status_code >= 500 else 401,
                                     "A Kiwify recusou a autenticação da API. Confira Client ID, Client Secret e permissões.")
            payload = response.json()
            token = str(payload.get("access_token") or "").strip()
            if not token:
                raise KiwifyAPIError(502, "A Kiwify não retornou um token de acesso válido.")
            expires_in = int(payload.get("expires_in") or 3600)
            self._access_token = token
            self._token_expires_at = time.time() + max(60, expires_in - 300)
            return token
        except KiwifyAPIError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise KiwifyAPIError(502, "Não foi possível autenticar na API da Kiwify.") from exc

    async def _request(self, method: str, path: str, *, params: dict | None = None,
                       json_body: dict | None = None) -> dict[str, Any]:
        for attempt in range(2):
            token = await self._token(force=attempt == 1)
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
                    response = await client.request(
                        method,
                        f"{self.base_url}{path}",
                        params=params,
                        json=json_body,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "x-kiwify-account-id": self.account_id,
                            "Content-Type": "application/json",
                        },
                    )
                if response.status_code == 401 and attempt == 0:
                    self._access_token = None
                    continue
                if response.status_code >= 400:
                    status = 429 if response.status_code == 429 else (502 if response.status_code >= 500 else 400)
                    raise KiwifyAPIError(status, f"Falha na API Kiwify (HTTP {response.status_code}).")
                data = response.json()
                if not isinstance(data, dict):
                    raise KiwifyAPIError(502, "Resposta inesperada da API Kiwify.")
                return data
            except KiwifyAPIError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise KiwifyAPIError(502, "Falha de comunicação com a API Kiwify.") from exc
        raise KiwifyAPIError(401, "A autenticação da API Kiwify expirou.")

    async def list_products(self, page_size: int = 100, page_number: int = 1) -> dict[str, Any]:
        return await self._request(
            "GET", "/products",
            params={"page_size": page_size, "page_number": page_number},
        )

    async def list_sales(self, start_date: date, end_date: date,
                         page_size: int = 100, page_number: int = 1) -> dict[str, Any]:
        if (end_date - start_date).days > 90:
            raise KiwifyAPIError(422, "A Kiwify permite no máximo 90 dias por consulta de vendas.")
        if end_date < start_date:
            raise KiwifyAPIError(422, "A data final não pode ser anterior à data inicial.")
        return await self._request(
            "GET", "/sales",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "page_size": page_size,
                "page_number": page_number,
                "view_full_sale_details": "false",
            },
        )

    async def list_webhooks(self) -> dict[str, Any]:
        return await self._request("GET", "/webhooks")

    async def ensure_sales_webhook(self, callback_url: str) -> dict[str, Any]:
        if not self.webhook_token:
            raise KiwifyAPIError(409, "KIWIFY_WEBHOOK_TOKEN não está configurado no Hermes.")
        current = await self.list_webhooks()
        existing = current.get("data") or current.get("webhooks") or []
        if isinstance(existing, list):
            for item in existing:
                if isinstance(item, dict) and str(item.get("url") or "").rstrip("/") == callback_url.rstrip("/"):
                    return {"created": False, "webhook": {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "url": item.get("url"),
                        "products": item.get("products"),
                        "triggers": item.get("triggers") or [],
                    }}
        created = await self._request(
            "POST", "/webhooks",
            json_body={
                "name": "Hermes Pro - vendas",
                "url": callback_url,
                "products": "all",
                "triggers": [
                    "boleto_gerado", "pix_gerado", "compra_recusada",
                    "compra_aprovada", "compra_reembolsada", "chargeback",
                    "subscription_canceled", "subscription_late",
                    "subscription_renewed", "subscription_trial_started",
                    "subscription_trial_canceled",
                ],
                "token": self.webhook_token,
            },
        )
        webhook = {
            "id": created.get("id"),
            "name": created.get("name"),
            "url": created.get("url"),
            "products": created.get("products"),
            "triggers": created.get("triggers") or [],
        }
        return {"created": True, "webhook": webhook}


def safe_product(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in (
        "id", "name", "type", "created_at", "currency", "price",
        "affiliate_enabled", "status", "payment_type",
    ) if key in item}


def safe_sale(item: dict[str, Any]) -> dict[str, Any]:
    product = item.get("product") if isinstance(item.get("product"), dict) else {}
    return {
        "id": item.get("id"),
        "reference": item.get("reference"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "product": {"id": product.get("id"), "name": product.get("name")},
        "status": item.get("status"),
        "payment_method": item.get("payment_method"),
        "net_amount": item.get("net_amount"),
        "currency": item.get("currency"),
    }
