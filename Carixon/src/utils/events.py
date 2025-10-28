from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, List


EventHandler = Callable[[Any], None]


@dataclass(slots=True)
class Subscription:
    event: str
    handler: EventHandler
    bus: "EventBus"

    def unsubscribe(self) -> None:
        self.bus.unsubscribe(self.event, self.handler)


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> Subscription:
        self._handlers[event].append(handler)
        return Subscription(event, handler, self)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        if event in self._handlers:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]
            if not self._handlers[event]:
                self._handlers.pop(event)

    def emit(self, event: str, payload: Any | None = None) -> None:
        for handler in list(self._handlers.get(event, [])):
            handler(payload)


events = EventBus()
