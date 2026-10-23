from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..core.config import Settings


class DatabaseError(RuntimeError):
    """Raised when the PostgreSQL persistence layer cannot complete an operation."""


class PostgresStore:
    """
    Compatibility adapter for the existing Hermes PostgREST-shaped persistence API.
    Each logical resource is stored as JSONB in PostgreSQL, allowing gradual migration
    without requiring the legacy Supabase table schemas to exist in the new database.
    """

    def __init__(self, settings: Settings) -> None:
        self.database_url = (settings.database_url or "").strip()
        if self.database_url.startswith("postgres://"):
            self.database_url = "postgresql://" + self.database_url[len("postgres://"):]
        self._initialized: set[str] = set()

    def _require_url(self) -> None:
        if not self.database_url:
            raise DatabaseError("DATABASE_URL não configurada para PostgreSQL.")

    @staticmethod
    def _table(table: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", table):
            raise DatabaseError("Nome de recurso inválido.")
        return '"hermes_' + table + '"'

    async def _ensure_table(self, table: str) -> str:
        self._require_url()
        physical = self._table(table)
        if table not in self._initialized:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS {physical} (
                        id TEXT PRIMARY KEY,
                        record JSONB NOT NULL,
                        idempotency_key TEXT GENERATED ALWAYS AS (record->>'idempotency_key') STORED
                    )"""
                )
                await conn.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {physical[1:-1]}_idem_uq "
                    f"ON {physical} (idempotency_key) WHERE idempotency_key IS NOT NULL AND idempotency_key <> ''"
                )
                await conn.execute(
                    f"CREATE INDEX IF NOT EXISTS {physical[1:-1]}_created_idx ON {physical} ((record->>'created_at'))"
                )
                await conn.commit()
            self._initialized.add(table)
        return physical

    @staticmethod
    def _field_expr(field: str) -> str:
        # Supports ordinary JSON fields and the PostgREST expression payload->>product_id.
        if "->>" in field:
            base, child = field.split("->>", 1)
            if not re.fullmatch(r"[a-z][a-z0-9_]*", base) or not re.fullmatch(r"[a-z][a-z0-9_]*", child):
                raise DatabaseError("Filtro JSON inválido.")
            return f"(record->'{base}'->>'{child}')"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", field):
            raise DatabaseError("Campo de consulta inválido.")
        return f"(record->>'{field}')"

    @staticmethod
    def _decode_value(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (dict, list)):
            return value
        return value

    async def select(self, table: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        physical = await self._ensure_table(table)
        params = params or {}
        clauses: list[str] = []
        values: list[Any] = []
        for key, raw in params.items():
            if key in {"select", "order", "limit", "offset"}:
                continue
            if "." not in raw:
                raise DatabaseError(f"Filtro inválido para {key}.")
            op, val = raw.split(".", 1)
            expr = self._field_expr(key)
            if op == "eq":
                clauses.append(f"{expr} = %s")
                values.append(val)
            elif op == "neq":
                clauses.append(f"{expr} <> %s")
                values.append(val)
            elif op == "gte":
                clauses.append(f"{expr} >= %s")
                values.append(val)
            elif op == "lte":
                clauses.append(f"{expr} <= %s")
                values.append(val)
            elif op == "is" and val == "null":
                clauses.append(f"{expr} IS NULL")
            else:
                raise DatabaseError(f"Operador de filtro não suportado: {op}.")
        sql = f"SELECT record FROM {physical}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        order = params.get("order")
        if order:
            bits = order.split(".")
            if len(bits) not in (1, 2):
                raise DatabaseError("Ordenação inválida.")
            field = self._field_expr(bits[0])
            direction = bits[1].lower() if len(bits) == 2 else "asc"
            if direction not in {"asc", "desc"}:
                raise DatabaseError("Direção de ordenação inválida.")
            sql += f" ORDER BY {field} {direction.upper()} NULLS LAST"
        limit = min(max(int(params.get("limit", "1000")), 1), 5000)
        sql += " LIMIT %s"
        values.append(limit)
        if "offset" in params:
            sql += " OFFSET %s"
            values.append(max(0, int(params["offset"])))
        async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
            cur = await conn.execute(sql, values)
            rows = await cur.fetchall()
        records = [dict(row["record"]) for row in rows]
        selected = params.get("select", "*")
        if selected != "*":
            fields = [f.strip() for f in selected.split(",")]
            records = [{field: record.get(field) for field in fields} for record in records]
        return records

    async def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        physical = await self._ensure_table(table)
        record = dict(values)
        record.setdefault("id", str(uuid4()))
        async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
            cur = await conn.execute(
                f"INSERT INTO {physical} (id, record) VALUES (%s, %s) RETURNING record",
                (str(record["id"]), Jsonb(record)),
            )
            row = await cur.fetchone()
            await conn.commit()
        return dict(row["record"])

    async def update(self, table: str, values: dict[str, Any], *, where: dict[str, str]) -> dict[str, Any]:
        physical = await self._ensure_table(table)
        clauses: list[str] = []
        params: list[Any] = []
        for key, raw in where.items():
            op, val = raw.split(".", 1)
            if op != "eq":
                raise DatabaseError("UPDATE aceita somente filtros eq.")
            clauses.append(f"{self._field_expr(key)} = %s")
            params.append(val)
        if not clauses:
            raise DatabaseError("UPDATE sem filtro foi bloqueado.")
        async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
            cur = await conn.execute(
                f"UPDATE {physical} SET record = record || %s WHERE {' AND '.join(clauses)} RETURNING record",
                [Jsonb(values), *params],
            )
            row = await cur.fetchone()
            await conn.commit()
        if not row:
            raise DatabaseError(f"Atualização não encontrou registro em {table}.")
        return dict(row["record"])

    async def upsert(self, table: str, values: dict[str, Any], *, conflict: str) -> dict[str, Any]:
        physical = await self._ensure_table(table)
        record = dict(values)
        record.setdefault("id", str(uuid4()))
        if conflict != "idempotency_key":
            raise DatabaseError("Chave de conflito não suportada.")
        async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
            cur = await conn.execute(
                f"""INSERT INTO {physical} (id, record) VALUES (%s, %s)
                    ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL AND idempotency_key <> ''
                    DO UPDATE SET record = {physical}.record || EXCLUDED.record
                    RETURNING record""",
                (str(record["id"]), Jsonb(record)),
            )
            row = await cur.fetchone()
            await conn.commit()
        return dict(row["record"])

    async def claim_persistence_test_execution(self, test_id: str) -> tuple[dict[str, Any], bool]:
        """Atomically mark a diagnostic no-op as executed exactly once."""
        physical = await self._ensure_table("hermes_persistence_tests")
        async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
            cur = await conn.execute(
                f"""UPDATE {physical}
                    SET record = record || %s
                    WHERE id = %s AND record->>'status' = 'pending'
                    RETURNING record""",
                (Jsonb({
                    "status": "executed",
                    "execution_count": 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }), test_id),
            )
            row = await cur.fetchone()
            if row:
                await conn.commit()
                return dict(row["record"]), True
            cur = await conn.execute(
                f"SELECT record FROM {physical} WHERE id = %s",
                (test_id,),
            )
            existing = await cur.fetchone()
            if not existing:
                raise DatabaseError("Teste de persistência não encontrado.")
            await conn.commit()
            return dict(existing["record"]), False

    async def rpc(self, function: str, payload: dict[str, Any] | None = None) -> Any:
        raise DatabaseError(f"RPC legado '{function}' não está implementado no PostgreSQL.")

    async def identity(self) -> dict[str, str]:
        """Return non-secret identity of the connected PostgreSQL database."""
        self._require_url()
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                cur = await conn.execute("SELECT current_database() AS database_name, current_schema() AS schema_name")
                row = await cur.fetchone()
                if not row:
                    raise DatabaseError("Não foi possível identificar o banco PostgreSQL.")
                return {"database_name": str(row["database_name"]), "schema_name": str(row["schema_name"] or "")}
        except psycopg.Error as exc:
            raise DatabaseError("Não foi possível consultar a identidade do PostgreSQL.") from exc

    async def health(self) -> bool:
        if not self.database_url:
            return False
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False
