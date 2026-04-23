from app.config import Settings
from app.services.chat import MatchCandidate, build_chat_response
from app.services.conversations import InMemoryConversationStore
from app.services.dialogue import DialogueChatService


def test_build_chat_response_returns_match_when_score_is_high() -> None:
    candidate = MatchCandidate(
        faq_id=5,
        canonical_question="Почему не работает домашний интернет?",
        matched_question="Почему не работает интернет дома?",
        answer="Проверьте роутер и статус оплаты.",
        score=0.91,
    )

    response = build_chat_response([candidate], threshold=0.72, fallback_message="fallback")

    assert response.status == "matched"
    assert response.matched_faq_id == 5
    assert response.matched_question == "Почему не работает интернет дома?"
    assert response.score == 0.91
    assert response.top_matches[0].canonical_question == "Почему не работает домашний интернет?"


def test_build_chat_response_returns_escalation_when_score_is_low() -> None:
    candidate = MatchCandidate(
        faq_id=5,
        canonical_question="Почему не работает домашний интернет?",
        matched_question="Почему не работает интернет дома?",
        answer="Проверьте роутер и статус оплаты.",
        score=0.41,
    )

    response = build_chat_response(
        [candidate],
        threshold=0.72,
        fallback_message="Точный ответ не найден.",
    )

    assert response.status == "escalated"
    assert response.matched_faq_id == 5
    assert response.matched_question == "Почему не работает интернет дома?"
    assert response.answer == "Точный ответ не найден."
    assert response.top_matches[0].score == 0.41


class StubChatService:
    def __init__(self, candidates_by_query: dict[str, list[MatchCandidate]]) -> None:
        self.candidates_by_query = candidates_by_query
        self.last_find_query: str | None = None
        self.stored_queries: list[dict] = []

    def prepare_question(self, question: str) -> tuple[str, str]:
        trimmed = question.strip()
        return trimmed, trimmed.lower()

    def find_top_matches(self, normalized_question: str, top_k: int = 3) -> list[MatchCandidate]:
        self.last_find_query = normalized_question
        return self.candidates_by_query.get(normalized_question, [])[:top_k]

    def answer_normalized_question(
        self,
        normalized_question: str,
        *,
        original_question: str,
        top_k: int = 3,
        conversation_id: str = "",
        conversation_message_count: int = 0,
        is_follow_up: bool = False,
    ):
        return build_chat_response(
            self.find_top_matches(normalized_question, top_k=top_k),
            threshold=0.72,
            fallback_message="fallback",
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
        )

    def store_query(self, **payload) -> None:
        self.stored_queries.append(payload)


def build_settings() -> Settings:
    return Settings(
        database_url="postgresql://postgres:postgres@localhost:5432/postgres",
        clarification_score_gap=0.04,
        clarification_min_score=0.58,
        follow_up_short_message_max_chars=24,
        conversation_max_messages=6,
    )


def test_dialogue_service_returns_clarification_for_ambiguous_internet_query() -> None:
    stub_chat = StubChatService(
        {
            "не работает интернет": [
                MatchCandidate(
                    faq_id=1,
                    canonical_question="Почему не работает домашний интернет?",
                    matched_question="инет дома не работает",
                    answer="home",
                    score=0.79,
                    intent_tag="home_internet",
                    intent_label="Домашний интернет",
                ),
                MatchCandidate(
                    faq_id=13,
                    canonical_question="Почему не работает мобильный интернет?",
                    matched_question="не работает интернет на телефоне",
                    answer="mobile",
                    score=0.77,
                    intent_tag="mobile_internet",
                    intent_label="Мобильный интернет",
                ),
            ]
        }
    )
    store = InMemoryConversationStore(max_messages=6)
    service = DialogueChatService(stub_chat, store, build_settings())

    response = service.answer_question("не работает интернет")

    assert response.status == "clarification_required"
    assert response.clarification_type == "internet_scope"
    assert response.clarification_question == "Уточните, домашний или мобильный интернет?"
    assert [item.label for item in response.quick_replies] == ["Домашний", "Мобильный"]
    assert [item.value for item in response.quick_replies] == ["домашний", "мобильный"]
    assert response.conversation_id.startswith("conv_")
    assert response.conversation_message_count == 2


def test_dialogue_service_uses_previous_turn_for_short_follow_up() -> None:
    stub_chat = StubChatService(
        {
            "не работает интернет домашний": [
                MatchCandidate(
                    faq_id=1,
                    canonical_question="Почему не работает домашний интернет?",
                    matched_question="инет дома не работает",
                    answer="Проверьте роутер.",
                    score=0.88,
                    intent_tag="home_internet",
                    intent_label="Домашний интернет",
                ),
                MatchCandidate(
                    faq_id=13,
                    canonical_question="Почему не работает мобильный интернет?",
                    matched_question="не работает интернет на телефоне",
                    answer="Проверьте передачу данных.",
                    score=0.65,
                    intent_tag="mobile_internet",
                    intent_label="Мобильный интернет",
                ),
            ]
        }
    )
    store = InMemoryConversationStore(max_messages=6)
    conversation = store.create()
    store.append_message(conversation.conversation_id, "user", "не работает интернет")
    store.append_message(
        conversation.conversation_id,
        "assistant",
        "Уточните, домашний или мобильный интернет?",
        decision_type="clarification_required",
    )
    service = DialogueChatService(stub_chat, store, build_settings())

    response = service.answer_question("домашний", conversation.conversation_id)

    assert stub_chat.last_find_query == "не работает интернет домашний"
    assert response.status == "matched"
    assert response.is_follow_up is True
    assert [item.label for item in response.quick_replies] == [
        "Не помогло",
        "Это про домашний интернет",
    ]
    assert response.conversation_id == conversation.conversation_id
    assert response.conversation_message_count == 4


def test_dialogue_service_returns_intent_hypotheses_for_escalation() -> None:
    stub_chat = StubChatService(
        {
            "нужна помощь": [
                MatchCandidate(
                    faq_id=1,
                    canonical_question="Почему не работает домашний интернет?",
                    matched_question="инет дома не работает",
                    answer="home",
                    score=0.56,
                    intent_tag="home_internet",
                    intent_label="Домашний интернет",
                ),
                MatchCandidate(
                    faq_id=13,
                    canonical_question="Почему не работает мобильный интернет?",
                    matched_question="не работает интернет на телефоне",
                    answer="mobile",
                    score=0.54,
                    intent_tag="mobile_internet",
                    intent_label="Мобильный интернет",
                ),
                MatchCandidate(
                    faq_id=3,
                    canonical_question="Как войти в личный кабинет и восстановить доступ?",
                    matched_question="Не могу зайти в личный кабинет",
                    answer="lk",
                    score=0.51,
                    intent_tag="lk_login",
                    intent_label="Личный кабинет",
                ),
            ]
        }
    )
    service = DialogueChatService(stub_chat, InMemoryConversationStore(max_messages=6), build_settings())

    response = service.answer_question("нужна помощь")

    assert response.status == "escalated"
    assert [item.label for item in response.quick_replies] == [
        "Домашний интернет",
        "Мобильный интернет",
        "Личный кабинет",
    ]
    assert [item.type for item in response.quick_replies] == [
        "intent_hypothesis",
        "intent_hypothesis",
        "intent_hypothesis",
    ]


def test_dialogue_service_reset_returns_fresh_conversation() -> None:
    stub_chat = StubChatService({})
    store = InMemoryConversationStore(max_messages=6)
    conversation = store.create()
    store.append_message(conversation.conversation_id, "user", "старый диалог")
    service = DialogueChatService(stub_chat, store, build_settings())

    response = service.reset_conversation(conversation.conversation_id)

    assert response.cleared is True
    assert response.message_count == 0
    assert response.conversation_id != conversation.conversation_id
    assert store.get(conversation.conversation_id) is None
