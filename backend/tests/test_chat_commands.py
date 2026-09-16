from backend.app.services.chat_commands import handle_chat_command


class FakeStore:
    async def create_product_and_job(self, topic, metadata, idempotency_key):
        return ({"id": "product-1"}, {"id": "job-1"})


class FakeQueue:
    def __init__(self):
        self.ids = []

    async def enqueue(self, job_id):
        self.ids.append(job_id)


async def test_chat_current_date_does_not_require_ai():
    result = await handle_chat_command("QUE DIA É HOJE", FakeStore(), FakeQueue())
    assert result["provider"] == "system"
    assert "/" in result["response"]


async def test_chat_product_request_creates_job():
    queue = FakeQueue()
    result = await handle_chat_command("produza um ebook sobre produtividade", FakeStore(), queue)
    assert queue.ids == ["job-1"]
    assert result["provider"] == "system"
    assert "produtividade" in result["response"]


async def test_chat_unsupported_message_falls_through():
    result = await handle_chat_command("me explique o radar", FakeStore(), FakeQueue())
    assert result is None
