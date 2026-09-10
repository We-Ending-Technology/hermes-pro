from .ai_gateway.base import AIGateway

class TopicPlanner:
    def __init__(self, gateway: AIGateway) -> None:
        self.gateway = gateway

    async def next_topic(self) -> str:
        response = await self.gateway.complete(
            "Suggest one commercially useful, ethical ebook topic with a clear audience. Return only the topic, no quotes.",
            system="You are Hermes market researcher. Avoid medical, legal, financial promises, plagiarism, and unverifiable claims.",
        )
        topic = " ".join(response.content.strip().split())
        if not 3 <= len(topic) <= 500:
            raise ValueError("AI returned an invalid topic")
        return topic
