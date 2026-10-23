#!/usr/bin/env python3
"""Authenticated, interactive Hermes PostgreSQL persistence/restart diagnostic.

The API key is read with getpass, never saved to disk or printed. Keep this process
open while restarting the API from the Render dashboard.
"""
from __future__ import annotations

import getpass
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "https://hermes-pro-api-virginia.onrender.com"


def request(method: str, path: str, token: str, payload: dict | None = None, idempotency_key: str | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "X-Hermes-API-Key": token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # Do not print request headers or the API key.
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} retornou HTTP {exc.code}: {body[:500]}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha de conexão em {method} {path}: {exc.reason}") from None


def wait_until_ready() -> dict:
    print("Aguardando a API responder /ready após o reinício (limite de 5 minutos)...")
    deadline = time.time() + 300
    last_error = "sem resposta"
    while time.time() < deadline:
        try:
            req = urllib.request.Request(BASE_URL + "/ready", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and body.get("status") in {"ok", "ready", "healthy"}:
                    return body
                last_error = f"HTTP {response.status}: status={body.get('status')}"
        except Exception as exc:
            last_error = str(exc)[:200]
        time.sleep(5)
    raise RuntimeError("API não ficou pronta em 5 minutos. Último estado: " + last_error)


def assert_count(record: dict, expected: int, stage: str) -> None:
    actual = record.get("execution_count")
    if actual != expected:
        raise RuntimeError(f"{stage}: execution_count esperado={expected}, recebido={actual}.")
    print(f"[OK] {stage}: execution_count={actual}, status={record.get('status')}")


def main() -> int:
    print("Hermes Pro — teste autenticado de persistência e recuperação")
    print("A chave é solicitada sem eco e não será gravada em arquivo.")
    token = getpass.getpass("X-Hermes-API-Key (entrada oculta): ").strip()
    if not token:
        print("Chave vazia; cancelado.")
        return 2

    try:
        ready = wait_until_ready()
        print("[OK] /ready respondeu. Verifique o estado PostgreSQL abaixo.")
        print("Readiness:", json.dumps(ready, ensure_ascii=False))

        identity_status, identity = request("GET", "/api/v1/diagnostics/database-identity", token)
        if identity_status != 200 or not identity.get("database_name"):
            raise RuntimeError("A identidade do banco não foi confirmada.")
        print("[OK] Banco real:", json.dumps(identity, ensure_ascii=False))

        key = "persistence-recovery-" + secrets.token_hex(16)
        status, created = request("POST", "/api/v1/diagnostics/persistence-test", token,
                                  {"purpose": "restart_recovery"}, key)
        record = created.get("test", {})
        test_id = record.get("id")
        if status not in (200, 201) or not test_id:
            raise RuntimeError("A API não retornou um ID válido para o registro de teste.")
        print(f"[OK] Registro criado/reutilizado: id={test_id}; HTTP {status}")
        assert_count(record, 0, "Antes da execução")

        _, read_before = request("GET", f"/api/v1/diagnostics/persistence-test/{test_id}", token)
        assert_count(read_before.get("test", {}), 0, "Leitura antes da execução")

        _, first = request("POST", f"/api/v1/diagnostics/persistence-test/{test_id}/execute", token, {})
        assert_count(first.get("test", {}), 1, "Primeira execução no-op")
        if not first.get("executed_now") or first.get("effect") != "no-op":
            raise RuntimeError("A primeira execução não confirmou o comportamento no-op esperado.")

        print()
        print("Agora reinicie manualmente SOMENTE o serviço da API no Render:")
        print("https://dashboard.render.com/web/srv-db8cphivcj2c73914aj0")
        print("No serviço, use o menu Manual Deploy/Service Actions para reiniciar.")
        input("Quando o reinício terminar, volte aqui e pressione Enter para validar a recuperação... ")

        ready_after = wait_until_ready()
        print("[OK] API respondeu após o reinício.")
        print("Readiness pós-reinício:", json.dumps(ready_after, ensure_ascii=False))

        identity_status, identity_after = request("GET", "/api/v1/diagnostics/database-identity", token)
        if identity_status != 200 or identity_after != identity:
            raise RuntimeError(f"A identidade do banco mudou ou não pôde ser confirmada: {identity_after}")
        print("[OK] Mesma identidade PostgreSQL após o reinício:", json.dumps(identity_after, ensure_ascii=False))

        _, read_after = request("GET", f"/api/v1/diagnostics/persistence-test/{test_id}", token)
        recovered = read_after.get("test", {})
        assert_count(recovered, 1, "Registro recuperado após reinício")

        _, second = request("POST", f"/api/v1/diagnostics/persistence-test/{test_id}/execute", token, {})
        assert_count(second.get("test", {}), 1, "Repetição após reinício")
        if not second.get("already_executed") or second.get("executed_now"):
            raise RuntimeError("A repetição não foi reconhecida como idempotente.")

        print()
        print("RESULTADO: APROVADO — banco identificado, registro sobreviveu ao reinício e execução permaneceu idempotente.")
        print("ID do teste:", test_id)
        return 0
    except (RuntimeError, KeyError, ValueError) as exc:
        print("RESULTADO: NÃO APROVADO —", exc, file=sys.stderr)
        return 1
    finally:
        token = ""


if __name__ == "__main__":
    raise SystemExit(main())
