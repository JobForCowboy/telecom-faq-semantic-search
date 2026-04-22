import json
from pathlib import Path

from app.eval import (
    DEFAULT_SMOKE_MATCHED_CANONICAL,
    CaseResult,
    DatasetReport,
    combine_reports,
    compute_metrics,
    evaluate_dataset,
    load_eval_cases,
    render_markdown_summary,
    run_smoke,
    write_reports,
)


class StubApiClient:
    def __init__(
        self,
        *,
        health_payload: dict | None = None,
        query_responses: dict[str, dict] | None = None,
        debug_responses: dict[str, dict] | None = None,
        faqs: list[dict] | None = None,
    ) -> None:
        self.health_payload = health_payload or {
            "status": "ok",
            "model_ready": True,
            "embedding_backend": "hash",
        }
        self.query_responses = query_responses or {}
        self.debug_responses = debug_responses or {}
        self.faqs = faqs or []
        self.debug_calls: list[str] = []

    def health(self) -> dict:
        return self.health_payload

    def query_chat(self, question: str) -> dict:
        return self.query_responses[question]

    def retrieval_debug(self, question: str) -> dict:
        self.debug_calls.append(question)
        return self.debug_responses[question]

    def list_faqs(self) -> list[dict]:
        return self.faqs


def test_load_eval_cases_supports_new_and_legacy_rows(tmp_path: Path) -> None:
    dataset_path = tmp_path / "eval.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "question": "У меня пропал домашний интернет",
                    "expected_status": "matched",
                    "expected_faq_id": 1,
                    "case_type": "main",
                    "normalization_sensitive": True,
                },
                {
                    "query": "Не могу зайти в лк",
                    "expected_status": "matched",
                    "expected_canonical_question": "Как войти в личный кабинет и восстановить доступ?",
                    "category": "abbreviation",
                },
                {
                    "query": "Какая сегодня погода?",
                    "expected_status": "escalated",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_eval_cases(
        dataset_path,
        faq_lookup={"Как войти в личный кабинет и восстановить доступ?": 3},
    )

    assert [case.question for case in cases] == [
        "У меня пропал домашний интернет",
        "Не могу зайти в лк",
        "Какая сегодня погода?",
    ]
    assert cases[0].expected_faq_id == 1
    assert cases[0].normalization_sensitive is True
    assert cases[1].expected_faq_id == 3
    assert cases[1].case_type == "abbreviation"
    assert cases[1].normalization_sensitive is True
    assert cases[2].expected_faq_id is None
    assert cases[2].case_type == "eval"


def test_evaluate_dataset_computes_metrics_and_debug_only_for_failures(tmp_path: Path) -> None:
    dataset_path = tmp_path / "main.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "question": "У меня пропал домашний интернет",
                    "expected_status": "matched",
                    "expected_faq_id": 1,
                    "case_type": "core",
                },
                {
                    "question": "Не могу зайти в лк",
                    "expected_status": "matched",
                    "expected_faq_id": 3,
                    "case_type": "abbreviation",
                    "normalization_sensitive": True,
                },
                {
                    "question": "Какая сегодня погода?",
                    "expected_status": "escalated",
                    "case_type": "negative",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    client = StubApiClient(
        query_responses={
            "У меня пропал домашний интернет": {
                "status": "matched",
                "matched_faq_id": 1,
                "matched_question": "У меня пропал домашний интернет",
                "score": 0.91,
                "top_matches": [
                    {"faq_id": 1, "canonical_question": "Почему не работает домашний интернет?", "score": 0.91}
                ],
            },
            "Не могу зайти в лк": {
                "status": "matched",
                "matched_faq_id": 5,
                "matched_question": "Не могу зайти в лк",
                "score": 0.74,
                "top_matches": [
                    {"faq_id": 5, "canonical_question": "Как оплатить услуги связи?", "score": 0.74},
                    {
                        "faq_id": 3,
                        "canonical_question": "Как войти в личный кабинет и восстановить доступ?",
                        "score": 0.70,
                    },
                ],
            },
            "Какая сегодня погода?": {
                "status": "matched",
                "matched_faq_id": 6,
                "matched_question": "баланс",
                "score": 0.72,
                "top_matches": [
                    {"faq_id": 6, "canonical_question": "Как узнать баланс по номеру?", "score": 0.72}
                ],
            },
        },
        debug_responses={
            "Не могу зайти в лк": {
                "normalized_question": "не могу зайти в личный кабинет",
                "threshold": 0.72,
                "top_matches": [
                    {
                        "faq_id": 5,
                        "canonical_question": "Как оплатить услуги связи?",
                        "score": 0.74,
                    }
                ],
            },
            "Какая сегодня погода?": {
                "normalized_question": "какая сегодня погода",
                "threshold": 0.72,
                "top_matches": [
                    {
                        "faq_id": 6,
                        "canonical_question": "Как узнать баланс по номеру?",
                        "score": 0.72,
                    }
                ],
            },
        },
    )

    report = evaluate_dataset(client, dataset_path, with_debug=True, save_responses=True)

    assert report.metrics.total_cases == 3
    assert report.metrics.passed_cases == 1
    assert report.metrics.accuracy == 1 / 3
    assert report.metrics.matched_accuracy == 1 / 2
    assert report.metrics.escalation_accuracy == 0.0
    assert report.metrics.false_escalations == 0
    assert report.metrics.false_matches == 1
    assert report.metrics.wrong_faq_matches == 1
    assert report.metrics.top_3_hit_rate == 1.0
    assert report.metrics.normalization_sensitive_total == 1
    assert report.metrics.normalization_sensitive_passed == 0
    assert client.debug_calls == ["Не могу зайти в лк", "Какая сегодня погода?"]
    assert report.results[0].debug is None
    assert report.results[1].debug is not None
    assert report.results[1].response is not None


def test_run_smoke_checks_health_positive_and_negative() -> None:
    client = StubApiClient(
        faqs=[{"id": 1, "canonical_question": DEFAULT_SMOKE_MATCHED_CANONICAL}],
        query_responses={
            "У меня пропал домашний интернет": {
                "status": "matched",
                "matched_faq_id": 1,
                "matched_question": "У меня пропал домашний интернет",
                "score": 0.93,
                "top_matches": [],
            },
            "Какая сегодня погода?": {
                "status": "escalated",
                "matched_faq_id": None,
                "matched_question": None,
                "score": 0.21,
                "top_matches": [],
            },
        },
    )

    report = run_smoke(client)

    assert report.ok is True
    assert [check.name for check in report.checks] == ["health", "matched_case", "negative_case"]
    assert all(check.passed for check in report.checks)


def test_write_reports_persists_json_and_markdown_summary(tmp_path: Path) -> None:
    results = [
        CaseResult(
            question="У меня пропал домашний интернет",
            expected_status="matched",
            expected_faq_id=1,
            expected_canonical_question="Почему не работает домашний интернет?",
            case_type="core",
            notes=None,
            normalization_sensitive=False,
            actual_status="matched",
            actual_faq_id=1,
            actual_canonical_question="Почему не работает домашний интернет?",
            score=0.91,
            matched_question="У меня пропал домашний интернет",
            top_matches=[{"faq_id": 1, "canonical_question": "Почему не работает домашний интернет?", "score": 0.91}],
            passed=True,
            failure_reason=None,
        )
    ]
    metrics = compute_metrics("main", results)
    report = DatasetReport(
        dataset_name="main",
        dataset_path=tmp_path / "main.json",
        metrics=metrics,
        results=results,
    )

    written_paths = write_reports(
        tmp_path / "reports",
        base_url="http://localhost:8000",
        reports=[report],
        combined_metrics=combine_reports([report]),
    )

    assert written_paths["main"].exists()
    assert written_paths["summary_json"].exists()
    assert written_paths["summary_md"].exists()
    assert "Eval Summary" in written_paths["summary_md"].read_text(encoding="utf-8")


def test_render_markdown_summary_includes_combined_row() -> None:
    payload = {
        "generated_at": "2026-04-22T00:00:00+00:00",
        "base_url": "http://localhost:8000",
        "datasets": [
            {
                "dataset_name": "main",
                "total_cases": 1,
                "passed_cases": 1,
                "accuracy": 1.0,
                "matched_accuracy": 1.0,
                "escalation_accuracy": None,
                "false_escalations": 0,
                "false_matches": 0,
                "top_3_hit_rate": 1.0,
                "normalization_sensitive_accuracy": None,
            }
        ],
        "combined": {
            "dataset_name": "all",
            "total_cases": 1,
            "passed_cases": 1,
            "accuracy": 1.0,
            "matched_accuracy": 1.0,
            "escalation_accuracy": None,
            "false_escalations": 0,
            "false_matches": 0,
            "top_3_hit_rate": 1.0,
            "normalization_sensitive_accuracy": None,
        },
    }

    markdown = render_markdown_summary(payload)

    assert "| main | 1 | 1 | 1.000 | 1.000 | n/a | 0 | 0 | 1.000 | n/a |" in markdown
    assert "| all | 1 | 1 | 1.000 | 1.000 | n/a | 0 | 0 | 1.000 | n/a |" in markdown
