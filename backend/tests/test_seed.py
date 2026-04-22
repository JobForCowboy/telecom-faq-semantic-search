from app.seed import normalize_seed_entry


def test_normalize_seed_entry_promotes_canonical_question_into_variants() -> None:
    entry = normalize_seed_entry(
        {
            "canonical_question": "Почему не работает домашний интернет?",
            "answer": "Проверьте роутер.",
            "variants": [
                "У меня пропал домашний интернет",
                "Почему не работает домашний интернет?",
            ],
        }
    )

    assert entry["canonical_question"] == "Почему не работает домашний интернет?"
    assert entry["variants"] == [
        "Почему не работает домашний интернет?",
        "У меня пропал домашний интернет",
    ]


def test_normalize_seed_entry_accepts_legacy_question_shape() -> None:
    entry = normalize_seed_entry(
        {
            "question": "Как оплатить услуги связи?",
            "answer": "Оплатить можно в приложении.",
        }
    )

    assert entry["canonical_question"] == "Как оплатить услуги связи?"
    assert entry["variants"] == ["Как оплатить услуги связи?"]


def test_normalize_seed_entry_deduplicates_variants_by_normalized_form() -> None:
    entry = normalize_seed_entry(
        {
            "canonical_question": "Как войти в личный кабинет и восстановить доступ?",
            "answer": "Используйте восстановление по SMS.",
            "variants": [
                "не могу зайти в лк",
                "не могу зайти в личный кабинет",
                "как попасть в личную кабину",
            ],
        }
    )

    assert entry["variants"] == [
        "Как войти в личный кабинет и восстановить доступ?",
        "не могу зайти в лк",
        "как попасть в личную кабину",
    ]
