import pytest

from backend.app.core.config import Settings
from backend.app.services import storage as storage_module
from backend.app.services.storage import StorageError, SupabaseStorage


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(self._payload)
        self.is_error = status_code >= 400

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(
            400,
            {
                "statusCode": "409",
                "error": "Duplicate",
                "message": "The resource already exists",
                "code": "BucketAlreadyExists",
            },
        )

    async def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return FakeResponse(200, {"id": "ebooks", "public": False})


@pytest.mark.asyncio
async def test_existing_bucket_duplicate_payload_is_updated_as_private(monkeypatch):
    clients = []

    def client_factory(*args, **kwargs):
        client = FakeAsyncClient(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(storage_module.httpx, "AsyncClient", client_factory)
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    await SupabaseStorage(settings, bucket="ebooks").ensure_bucket()

    assert len(clients) == 1
    assert [call[0] for call in clients[0].calls] == ["POST", "PUT"]
    assert clients[0].calls[1][1].endswith("/bucket/ebooks")
    assert clients[0].calls[1][2]["json"] == {"public": False}


@pytest.mark.asyncio
async def test_bucket_creation_failure_is_not_silently_ignored(monkeypatch):
    class FailingClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            return FakeResponse(403, {"message": "forbidden"}, "forbidden")

    monkeypatch.setattr(
        storage_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: FailingClient(*args, **kwargs),
    )
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    with pytest.raises(StorageError, match="403"):
        await SupabaseStorage(settings, bucket="ebooks").ensure_bucket()


@pytest.mark.asyncio
async def test_private_artifact_signed_url_can_be_refreshed(monkeypatch):
    clients = []

    class SigningClient:
        def __init__(self, *args, **kwargs):
            self.calls = []
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return FakeResponse(200, {"signedURL": "/storage/v1/object/sign/ebooks/product/book.pdf?token=fresh"})

    monkeypatch.setattr(storage_module.httpx, "AsyncClient", SigningClient)
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    url = await SupabaseStorage(settings, bucket="ebooks").create_signed_url("product/book.pdf")

    assert url == "https://project.supabase.co/storage/v1/object/sign/ebooks/product/book.pdf?token=fresh"
    assert clients[0].calls[0][1]["json"] == {"expiresIn": 604800}
