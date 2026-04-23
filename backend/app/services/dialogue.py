from __future__ import annotations

from dataclasses import dataclass

from .chat import ChatService, MatchCandidate
from .conversations import Conversation, ConversationMessage, ConversationStore
from ..config import Settings
from ..schemas import (
    ChatQueryResponse,
    ChatResetResponse,
    ConversationMessageResponse,
    QuickReplyResponse,
    RetrievalDebugResponse,
    RetrievalMatchResponse,
)


FOLLOW_UP_EXACT_REPLIES = {
    "да",
    "нет",
    "домашний",
    "домашний интернет",
    "мобильный",
    "мобильный интернет",
    "в приложении",
    "в личном кабинете",
    "в приложении не работает",
    "не помогло",
    "помогло",
    "смс",
    "через приложение",
}

HYPOTHESIS_SCORE_WINDOW = 0.08
MAX_HYPOTHESIS_REPLIES = 3
DEFAULT_FALLBACK_QUICK_REPLIES = (
    ("Домашний интернет", "домашний интернет"),
    ("Мобильная связь", "мобильная связь"),
    ("Личный кабинет", "личный кабинет"),
    ("Оплата", "оплата"),
)
DEFAULT_OOD_QUICK_REPLIES = (
    ("Не работает интернет", "не работает интернет"),
    ("Как оплатить связь", "как оплатить связь"),
    ("Не могу войти в личный кабинет", "не могу войти в личный кабинет"),
)


@dataclass(frozen=True)
class ClarificationOption:
    label: str
    value: str


@dataclass(frozen=True)
class ClarificationGroup:
    group_type: str
    question: str
    members: dict[str, ClarificationOption]


@dataclass(frozen=True)
class ClarificationDecision:
    group_type: str
    question: str
    options: tuple[ClarificationOption, ...]


class DialogueChatService:
    def __init__(
        self,
        chat_service: ChatService,
        conversation_store: ConversationStore,
        settings: Settings,
    ) -> None:
        self.chat_service = chat_service
        self.conversation_store = conversation_store
        self.settings = settings
        self.clarification_groups = [
            ClarificationGroup(
                group_type="internet_scope",
                question="Уточните, домашний или мобильный интернет?",
                members={
                    "Почему не работает домашний интернет?": ClarificationOption(
                        label="Домашний",
                        value="домашний",
                    ),
                    "Почему не работает мобильный интернет?": ClarificationOption(
                        label="Мобильный",
                        value="мобильный",
                    ),
                },
            )
        ]

    def answer_question(self, question: str, conversation_id: str | None = None) -> ChatQueryResponse:
        conversation = self.conversation_store.get_or_create(conversation_id)
        evaluation = self._evaluate(question, conversation)
        response = evaluation.response

        self.conversation_store.append_message(conversation.conversation_id, "user", evaluation.raw_query)
        updated = self.conversation_store.append_message(
            conversation.conversation_id,
            "assistant",
            response.answer,
            decision_type=response.status,
        )

        response.conversation_id = updated.conversation_id
        response.conversation_message_count = len(updated.messages)

        self.chat_service.store_query(
            question=evaluation.raw_query,
            normalized_question=evaluation.normalized_contextualized_query,
            contextualized_question=evaluation.contextualized_query,
            response=response,
        )
        return response

    def preview_question(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int = 3,
    ) -> RetrievalDebugResponse:
        conversation = self.conversation_store.get(conversation_id)
        evaluation = self._evaluate(question, conversation, top_k=top_k)
        response = evaluation.response
        response.conversation_id = conversation.conversation_id if conversation else conversation_id or ""
        response.conversation_message_count = len(conversation.messages) if conversation else 0

        return RetrievalDebugResponse(
            original_question=evaluation.raw_query,
            normalized_question=evaluation.normalized_contextualized_query,
            raw_query=evaluation.raw_query,
            contextualized_query=evaluation.contextualized_query,
            normalized_contextualized_query=evaluation.normalized_contextualized_query,
            threshold=self.settings.effective_match_threshold,
            match_threshold=self.settings.effective_match_threshold,
            domain_threshold=self.settings.domain_threshold,
            recent_messages=self._serialize_messages(evaluation.recent_messages),
            follow_up_detected=evaluation.is_follow_up,
            clarification_triggered=response.status == "clarification_required",
            threshold_decision=response.status,
            **response.model_dump(),
        )

    def reset_conversation(self, conversation_id: str | None = None) -> ChatResetResponse:
        conversation = self.conversation_store.reset(conversation_id)
        return ChatResetResponse(
            conversation_id=conversation.conversation_id,
            cleared=True,
            message_count=0,
        )

    def _evaluate(
        self,
        question: str,
        conversation: Conversation | None,
        *,
        top_k: int = 3,
    ) -> "_Evaluation":
        raw_query, _ = self.chat_service.prepare_question(question)
        recent_messages = list(conversation.messages) if conversation else []
        is_follow_up = self._is_follow_up(raw_query, recent_messages)
        contextualized_query = self._build_contextualized_query(raw_query, recent_messages, is_follow_up)
        _, normalized_contextualized_query = self.chat_service.prepare_question(contextualized_query)
        candidates = self.chat_service.find_top_matches(normalized_contextualized_query, top_k=top_k)

        clarification = self._maybe_build_clarification(raw_query, recent_messages, candidates)
        if clarification is not None:
            response = ChatQueryResponse(
                status="clarification_required",
                decision_type=None,
                answer=clarification.question,
                score=candidates[0].score if candidates else None,
                matched_faq_id=None,
                matched_question=None,
                top_matches=self._serialize_matches(candidates),
                conversation_id=conversation.conversation_id if conversation else "",
                is_follow_up=is_follow_up,
                clarification_question=clarification.question,
                clarification_type=clarification.group_type,
            )
        else:
            response = self.chat_service.answer_normalized_question(
                normalized_contextualized_query,
                original_question=raw_query,
                top_k=top_k,
                conversation_id=conversation.conversation_id if conversation else "",
                is_follow_up=is_follow_up,
            )
        response.quick_replies = self._suggest_quick_replies(
            response=response,
            clarification=clarification,
            candidates=candidates,
        )

        return _Evaluation(
            raw_query=raw_query,
            recent_messages=recent_messages,
            contextualized_query=contextualized_query,
            normalized_contextualized_query=normalized_contextualized_query,
            is_follow_up=is_follow_up,
            response=response,
        )

    def _is_follow_up(self, raw_query: str, recent_messages: list[ConversationMessage]) -> bool:
        if not recent_messages:
            return False

        last_assistant = next((message for message in reversed(recent_messages) if message.role == "assistant"), None)
        if last_assistant is None:
            return False

        if last_assistant and last_assistant.decision_type == "clarification_required":
            return len(raw_query.split()) <= 6

        if last_assistant.text.rstrip().endswith("?"):
            return self._looks_like_short_follow_up(raw_query)

        normalized = raw_query.strip().lower()
        return normalized in FOLLOW_UP_EXACT_REPLIES

    def _looks_like_short_follow_up(self, raw_query: str) -> bool:
        normalized = raw_query.strip().lower()
        if normalized in FOLLOW_UP_EXACT_REPLIES:
            return True

        words = [part for part in normalized.split() if part]
        return (
            len(normalized) <= self.settings.follow_up_short_message_max_chars
            and len(words) <= 4
        )

    def _build_contextualized_query(
        self,
        raw_query: str,
        recent_messages: list[ConversationMessage],
        is_follow_up: bool,
    ) -> str:
        if not is_follow_up:
            return raw_query

        anchor = self._find_anchor_user_message(recent_messages)
        if anchor is None:
            return raw_query
        if raw_query.casefold() in anchor.text.casefold():
            return anchor.text
        return f"{anchor.text} {raw_query}".strip()

    def _find_anchor_user_message(self, recent_messages: list[ConversationMessage]) -> ConversationMessage | None:
        fallback = None
        for message in reversed(recent_messages):
            if message.role != "user":
                continue
            if fallback is None:
                fallback = message
            if not self._looks_like_short_follow_up(message.text):
                return message
        return fallback

    def _maybe_build_clarification(
        self,
        raw_query: str,
        recent_messages: list[ConversationMessage],
        candidates: list[MatchCandidate],
    ) -> ClarificationDecision | None:
        if not self.settings.clarification_enabled or len(candidates) < 2:
            return None

        top1, top2 = candidates[0], candidates[1]
        if (
            top1.score < self.settings.clarification_min_score
            or top2.score < self.settings.clarification_min_score
        ):
            return None

        if abs(top1.score - top2.score) > self.settings.clarification_score_gap:
            return None

        for group in self.clarification_groups:
            member1 = group.members.get(top1.canonical_question)
            member2 = group.members.get(top2.canonical_question)
            if member1 and member2 and member1.value != member2.value:
                if recent_messages and self._looks_like_short_follow_up(raw_query):
                    return None
                options = self._unique_clarification_options((member1, member2))
                return ClarificationDecision(
                    group_type=group.group_type,
                    question=group.question,
                    options=options,
                )
        return None

    def _suggest_quick_replies(
        self,
        *,
        response: ChatQueryResponse,
        clarification: ClarificationDecision | None,
        candidates: list[MatchCandidate],
    ) -> list[QuickReplyResponse]:
        if clarification is not None:
            return [
                QuickReplyResponse(
                    type="clarification",
                    label=option.label,
                    value=option.value,
                )
                for option in clarification.options
            ]

        if response.status == "out_of_domain":
            return [
                QuickReplyResponse(type="fallback", label=label, value=value)
                for label, value in DEFAULT_OOD_QUICK_REPLIES
            ]

        if response.status == "matched":
            replies = [
                QuickReplyResponse(
                    type="followup",
                    label="Не помогло",
                    value="не помогло",
                )
            ]
            contextual_reply = self._build_matched_follow_up(candidates, response.matched_faq_id)
            if contextual_reply is not None:
                replies.append(contextual_reply)
            else:
                replies.append(
                    QuickReplyResponse(
                        type="followup",
                        label="Хочу уточнить",
                        value="хочу уточнить",
                    )
                )
            return replies

        hypothesis_replies = self._build_intent_hypothesis_replies(candidates)
        if hypothesis_replies:
            return hypothesis_replies

        return [
            QuickReplyResponse(type="fallback", label=label, value=value)
            for label, value in DEFAULT_FALLBACK_QUICK_REPLIES
        ]

    def _build_matched_follow_up(
        self,
        candidates: list[MatchCandidate],
        matched_faq_id: int | None,
    ) -> QuickReplyResponse | None:
        if matched_faq_id is None:
            return None

        matched = next((item for item in candidates if item.faq_id == matched_faq_id), None)
        label = self._resolve_intent_label(matched) if matched else None
        if not label:
            return None

        return QuickReplyResponse(
            type="followup",
            label=f"Это про {self._to_user_phrase(label)}",
            value=f"это про {self._to_user_phrase(label)}",
        )

    def _build_intent_hypothesis_replies(
        self,
        candidates: list[MatchCandidate],
    ) -> list[QuickReplyResponse]:
        if len(candidates) < 2:
            return []

        top_score = candidates[0].score
        replies: list[QuickReplyResponse] = []
        seen_intents: set[str] = set()
        for candidate in candidates:
            if top_score - candidate.score > HYPOTHESIS_SCORE_WINDOW:
                continue
            label = self._resolve_intent_label(candidate)
            key = candidate.intent_tag or label
            if not label or key in seen_intents:
                continue
            seen_intents.add(key)
            replies.append(
                QuickReplyResponse(
                    type="intent_hypothesis",
                    label=label,
                    value=self._to_user_phrase(label),
                )
            )
            if len(replies) == MAX_HYPOTHESIS_REPLIES:
                break

        return replies if len(replies) >= 2 else []

    def _resolve_intent_label(self, candidate: MatchCandidate | None) -> str | None:
        if candidate is None:
            return None
        label = (candidate.intent_label or "").strip()
        return label or None

    def _to_user_phrase(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return normalized
        return normalized[:1].lower() + normalized[1:]

    def _unique_clarification_options(
        self,
        options: tuple[ClarificationOption, ...],
    ) -> tuple[ClarificationOption, ...]:
        seen_values: set[str] = set()
        unique: list[ClarificationOption] = []
        for option in options:
            if option.value in seen_values:
                continue
            seen_values.add(option.value)
            unique.append(option)
        return tuple(unique)

    def _serialize_matches(self, candidates: list[MatchCandidate]) -> list[RetrievalMatchResponse]:
        return [
            RetrievalMatchResponse(
                faq_id=item.faq_id,
                canonical_question=item.canonical_question,
                matched_question=item.matched_question,
                score=item.score,
            )
            for item in candidates
        ]

    def _serialize_messages(
        self,
        messages: list[ConversationMessage],
    ) -> list[ConversationMessageResponse]:
        return [
            ConversationMessageResponse(
                role=message.role,
                text=message.text,
                created_at=message.created_at,
                decision_type=message.decision_type,
            )
            for message in messages
        ]


@dataclass(frozen=True)
class _Evaluation:
    raw_query: str
    recent_messages: list[ConversationMessage]
    contextualized_query: str
    normalized_contextualized_query: str
    is_follow_up: bool
    response: ChatQueryResponse
