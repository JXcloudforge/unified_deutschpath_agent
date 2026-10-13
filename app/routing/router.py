from typing import Protocol

from .models import RouteDecision, RoutingContext


class IntentRouter(Protocol):
    def route(self, message: str, context: RoutingContext) -> RouteDecision:
        """Classify one message without querying RAG, databases, or external services."""
        ...
