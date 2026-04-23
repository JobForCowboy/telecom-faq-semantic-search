from app.config import Settings
from app.services.chat import MatchCandidate
from app.services.decision_policy import DecisionPolicy
from app.services.domain_filter import DomainFilter


def build_settings() -> Settings:
    return Settings(
        database_url="postgresql://postgres:postgres@localhost:5432/postgres",
        match_threshold=0.72,
        domain_threshold=0.52,
        soft_match_enabled=True,
        soft_match_min_score=0.68,
        soft_match_min_margin=0.05,
    )


def test_domain_filter_marks_obvious_weather_query_as_out_of_domain() -> None:
    filter_ = DomainFilter(build_settings())

    result = filter_.evaluate(
        raw_query="какая погода",
        normalized_query="какая погода",
        candidates=[],
    )

    assert result.is_in_domain is False
    assert result.offtopic_rule_hit == "weather"
    assert result.ood_reason == "off-topic pattern matched: weather"


def test_domain_filter_keeps_short_payment_query_in_domain() -> None:
    filter_ = DomainFilter(build_settings())

    result = filter_.evaluate(
        raw_query="не могу оплатить",
        normalized_query="не могу оплатить",
        candidates=[
            MatchCandidate(
                faq_id=5,
                canonical_question="Как оплатить услуги связи?",
                matched_question="как оплатить связь",
                answer="Оплатите через приложение.",
                score=0.49,
            )
        ],
    )

    assert result.is_in_domain is True
    assert "оплатить" in result.domain_keyword_hits
    assert result.ood_reason is None


def test_decision_policy_applies_soft_match_for_clear_telecom_near_miss() -> None:
    policy = DecisionPolicy(build_settings())
    candidates = [
        MatchCandidate(
            faq_id=1,
            canonical_question="Почему не работает домашний интернет?",
            matched_question="не работает интернет дома",
            answer="Проверьте роутер.",
            score=0.70,
            intent_tag="home_internet",
            intent_label="Домашний интернет",
        ),
        MatchCandidate(
            faq_id=13,
            canonical_question="Почему не работает мобильный интернет?",
            matched_question="не работает интернет на телефоне",
            answer="Проверьте мобильные данные.",
            score=0.61,
            intent_tag="mobile_internet",
            intent_label="Мобильный интернет",
        ),
    ]

    result = policy.decide(
        raw_query="не работает интернет дома",
        normalized_query="не работает интернет дома",
        candidates=candidates,
    )

    assert result.response.status == "matched"
    assert result.response.soft_match_used is True
    assert result.response.soft_match_reason is not None
