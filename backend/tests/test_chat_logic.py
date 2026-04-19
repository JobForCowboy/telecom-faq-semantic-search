from app.services.chat import MatchCandidate, build_chat_response


def test_build_chat_response_returns_match_when_score_is_high() -> None:
    candidate = MatchCandidate(
        faq_id=5,
        question="Почему не работает интернет дома?",
        answer="Проверьте роутер и статус оплаты.",
        score=0.91,
    )

    response = build_chat_response(candidate, threshold=0.72, fallback_message="fallback")

    assert response.status == "matched"
    assert response.matched_faq_id == 5


def test_build_chat_response_returns_fallback_when_score_is_low() -> None:
    candidate = MatchCandidate(
        faq_id=5,
        question="Почему не работает интернет дома?",
        answer="Проверьте роутер и статус оплаты.",
        score=0.41,
    )

    response = build_chat_response(
        candidate,
        threshold=0.72,
        fallback_message="Точный ответ не найден.",
    )

    assert response.status == "fallback"
    assert response.matched_faq_id is None
    assert response.answer == "Точный ответ не найден."

