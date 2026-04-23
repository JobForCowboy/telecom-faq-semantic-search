from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Protocol
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConversationMessage:
    role: str
    text: str
    created_at: datetime
    decision_type: str | None = None


@dataclass
class Conversation:
    conversation_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessage] = field(default_factory=list)


class ConversationStore(Protocol):
    def create(self) -> Conversation:
        raise NotImplementedError

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        raise NotImplementedError

    def get(self, conversation_id: str | None) -> Conversation | None:
        raise NotImplementedError

    def append_message(self, conversation_id: str, role: str, text: str, decision_type: str | None = None) -> Conversation:
        raise NotImplementedError

    def reset(self, conversation_id: str | None) -> Conversation:
        raise NotImplementedError


class InMemoryConversationStore:
    def __init__(self, max_messages: int = 6) -> None:
        self.max_messages = max_messages
        self._conversations: dict[str, Conversation] = {}
        self._lock = Lock()

    def create(self) -> Conversation:
        with self._lock:
            conversation = self._build_conversation()
            self._conversations[conversation.conversation_id] = conversation
            return conversation

    def get_or_create(self, conversation_id: str | None) -> Conversation:
        if conversation_id:
            existing = self.get(conversation_id)
            if existing is not None:
                return existing
        return self.create()

    def get(self, conversation_id: str | None) -> Conversation | None:
        if not conversation_id:
            return None
        with self._lock:
            return self._conversations.get(conversation_id)

    def append_message(
        self,
        conversation_id: str,
        role: str,
        text: str,
        decision_type: str | None = None,
    ) -> Conversation:
        with self._lock:
            conversation = self._conversations[conversation_id]
            conversation.messages.append(
                ConversationMessage(
                    role=role,
                    text=text,
                    created_at=utcnow(),
                    decision_type=decision_type,
                )
            )
            if len(conversation.messages) > self.max_messages:
                conversation.messages = conversation.messages[-self.max_messages :]
            conversation.updated_at = utcnow()
            return conversation

    def reset(self, conversation_id: str | None) -> Conversation:
        with self._lock:
            if conversation_id:
                self._conversations.pop(conversation_id, None)
            conversation = self._build_conversation()
            self._conversations[conversation.conversation_id] = conversation
            return conversation

    def _build_conversation(self) -> Conversation:
        now = utcnow()
        return Conversation(
            conversation_id=f"conv_{uuid4().hex}",
            created_at=now,
            updated_at=now,
        )
