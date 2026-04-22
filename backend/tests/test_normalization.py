from app.normalization import get_text_normalizer, prepare_variants


def test_text_normalizer_expands_abbreviations_and_typos() -> None:
    normalizer = get_text_normalizer()

    assert normalizer.normalize("  Не могу зайти в ЛК  ") == "не могу зайти в личный кабинет"
    assert normalizer.normalize("личная кабина не открывается") == "личный кабинет не открывается"
    assert normalizer.normalize("Интернета нету дома") == "нет интернета дома"


def test_prepare_variants_reuses_same_normalization_pipeline() -> None:
    variants = prepare_variants(
        "Как войти в личный кабинет и восстановить доступ?",
        [
            "не могу зайти в лк",
            "не могу зайти в личный кабинет",
            "Не могу   зайти   в  ЛК",
        ],
    )

    assert [variant.question for variant in variants] == [
        "Как войти в личный кабинет и восстановить доступ?",
        "не могу зайти в лк",
    ]
    assert variants[1].normalized_question == "не могу зайти в личный кабинет"
