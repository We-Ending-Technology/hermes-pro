from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.app.services.artifacts import build_artifacts
from worker import main as worker_main


class FakeStore:
    def __init__(self):
        self.job = {
            "id": "job-test",
            "job_type": "product_generation",
            "status": "pending",
            "attempts": 0,
            "max_attempts": 3,
            "payload": {"product_id": "product-test", "topic": "Organização financeira pessoal"},
        }
        self.product = {
            "id": "product-test",
            "topic": "Organização financeira pessoal",
            "status": "queued",
            "current_stage": "topic",
            "metadata": {},
            "paused": False,
        }

    async def get_job(self, job_id):
        return self.job if job_id == self.job["id"] else None

    async def get_product(self, product_id):
        return self.product if product_id == self.product["id"] else None

    async def update_job(self, job_id, status, *, attempts=None, error_message=None, payload=None):
        self.job["status"] = status
        self.job["error_message"] = error_message
        if attempts is not None:
            self.job["attempts"] = attempts
        if payload is not None:
            self.job["payload"] = payload
        return self.job

    async def update_product(self, product_id, *, status=None, current_stage=None, title=None, metadata=None):
        if status is not None:
            self.product["status"] = status
        if current_stage is not None:
            self.product["current_stage"] = current_stage
        if title is not None:
            self.product["title"] = title
        if metadata is not None:
            self.product["metadata"] = metadata
        return self.product


class FakeGateway:
    def __init__(self):
        self.responses = [
            {
                "positioning": "Guia prático",
                "audience": "Adultos que querem organizar o orçamento",
                "title": "Organize seu dinheiro",
                "subtitle": "Um guia prático para começar",
                "outline": ["Mapeie gastos", "Monte um orçamento"],
            },
            {
                "introduction": "Comece registrando suas receitas e despesas.",
                "chapters": [
                    {"title": "Mapeie gastos", "content": "Registre todas as despesas por categoria."},
                    {"title": "Monte um orçamento", "content": "Defina limites realistas para cada categoria."},
                ],
                "conclusion": "Revise seu orçamento toda semana.",
            },
            {"score": 92, "findings": [], "approved": True},
        ]

    async def complete(self, prompt, *, system=None):
        return SimpleNamespace(
            content=json.dumps(self.responses.pop(0), ensure_ascii=False),
            provider="fake-test",
            model="no-network",
        )


class FakeStorage:
    def __init__(self, settings):
        self.uploads = []

    async def upload(self, path, content, content_type):
        self.uploads.append((path, content, content_type))
        return f"https://storage.invalid/{path}"


@pytest.mark.asyncio
async def test_product_pipeline_creates_and_uploads_all_artifact_types(monkeypatch):
    store = FakeStore()
    gateway = FakeGateway()
    storage_instances = []

    monkeypatch.setattr(worker_main, "build_ai_gateway", lambda settings: gateway)
    monkeypatch.setattr(worker_main, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(worker_main, "SupabaseStorage", lambda settings: storage_instances.append(FakeStorage(settings)) or storage_instances[-1])

    await worker_main.process_product("job-test", store, queue=SimpleNamespace(enqueue=lambda job_id: None))

    assert store.job["status"] == "completed"
    assert store.product["status"] == "ready_to_publish"
    assert store.product["current_stage"] == "studio"
    assert store.product["metadata"]["quality_score"] == 92

    uploaded = storage_instances[0].uploads
    assert {item[2] for item in uploaded} == {
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
    }
    assert all(content for _, content, _ in uploaded)
    assert store.product["metadata"]["artifacts"].keys() == {"cover", "docx", "pdf"}
    assert all(url.startswith("https://storage.invalid/") for url in store.product["metadata"]["artifacts"].values())


def test_artifact_builders_return_real_file_signatures():
    artifacts = build_artifacts(
        "Teste de Produto",
        "Subtítulo",
        json.dumps({
            "introduction": "Introdução do conteúdo.",
            "chapters": [{"title": "Capítulo 1", "content": "Texto de exemplo."}],
            "conclusion": "Conclusão do conteúdo.",
        }, ensure_ascii=False),
    )

    assert set(artifacts) == {"cover", "docx", "pdf"}
    assert artifacts["cover"][1].startswith(b"\\x89PNG\\r\\n\\x1a\\n")
    assert artifacts["docx"][1].startswith(b"PK")
    assert artifacts["pdf"][1].startswith(b"%PDF")
