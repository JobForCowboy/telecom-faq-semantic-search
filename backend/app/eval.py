from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request

from .normalization import eval_dir


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_API_PREFIX = "/api"
DEFAULT_SMOKE_MATCHED_QUESTION = "У меня пропал домашний интернет"
DEFAULT_SMOKE_MATCHED_CANONICAL = "Почему не работает домашний интернет?"
DEFAULT_SMOKE_NEGATIVE_QUESTION = "Какая сегодня погода?"
NORMALIZATION_SENSITIVE_CASE_TYPES = {
    "abbreviation",
    "typo",
    "colloquial",
    "hard_abbreviation",
    "hard_typo",
    "hard_colloquial",
    "normalization_sensitive",
}


class EvalError(RuntimeError):
    pass


class ApiClientProtocol(Protocol):
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def query_chat(self, question: str) -> dict[str, Any]:
        raise NotImplementedError

    def retrieval_debug(self, question: str) -> dict[str, Any]:
        raise NotImplementedError

    def list_faqs(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class HttpApiClient:
    def __init__(
        self,
        base_url: str,
        api_prefix: str = DEFAULT_API_PREFIX,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")

    def query_chat(self, question: str) -> dict[str, Any]:
        return self._request_json("POST", f"{self.api_prefix}/chat/query", {"question": question})

    def retrieval_debug(self, question: str) -> dict[str, Any]:
        return self._request_json("POST", f"{self.api_prefix}/admin/retrieval-debug", {"question": question})

    def list_faqs(self) -> list[dict[str, Any]]:
        payload = self._request_json("GET", f"{self.api_prefix}/admin/faqs")
        if not isinstance(payload, list):
            raise EvalError("Expected /api/admin/faqs to return a list.")
        return payload

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        url = f"{self.base_url}{path}"
        req = request.Request(url=url, method=method, data=body, headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise EvalError(f"{method} {url} failed with HTTP {exc.code}: {body_text}") from exc
        except error.URLError as exc:
            raise EvalError(f"{method} {url} failed: {exc.reason}") from exc

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise EvalError(f"{method} {url} returned invalid JSON: {raw_body}") from exc


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected_status: str
    expected_faq_id: int | None
    expected_canonical_question: str | None
    case_type: str
    notes: str | None = None
    normalization_sensitive: bool = False


@dataclass(frozen=True)
class CaseResult:
    question: str
    expected_status: str
    expected_faq_id: int | None
    expected_canonical_question: str | None
    case_type: str
    notes: str | None
    normalization_sensitive: bool
    actual_status: str | None
    actual_faq_id: int | None
    actual_canonical_question: str | None
    score: float | None
    matched_question: str | None
    top_matches: list[dict[str, Any]]
    passed: bool
    failure_reason: str | None
    response: dict[str, Any] | None = None
    debug: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "expected_status": self.expected_status,
            "expected_faq_id": self.expected_faq_id,
            "expected_canonical_question": self.expected_canonical_question,
            "case_type": self.case_type,
            "notes": self.notes,
            "normalization_sensitive": self.normalization_sensitive,
            "actual_status": self.actual_status,
            "actual_faq_id": self.actual_faq_id,
            "actual_canonical_question": self.actual_canonical_question,
            "score": self.score,
            "matched_question": self.matched_question,
            "top_matches": self.top_matches,
            "pass": self.passed,
            "failure_reason": self.failure_reason,
            "response": self.response,
            "debug": self.debug,
        }


@dataclass(frozen=True)
class DatasetMetrics:
    dataset_name: str
    total_cases: int
    passed_cases: int
    accuracy: float | None
    matched_cases: int
    matched_passed: int
    matched_accuracy: float | None
    escalated_cases: int
    escalated_passed: int
    escalation_accuracy: float | None
    false_escalations: int
    false_matches: int
    wrong_faq_matches: int
    top_3_hit_rate: float | None
    normalization_sensitive_total: int
    normalization_sensitive_passed: int
    normalization_sensitive_accuracy: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "accuracy": self.accuracy,
            "matched_cases": self.matched_cases,
            "matched_passed": self.matched_passed,
            "matched_accuracy": self.matched_accuracy,
            "escalated_cases": self.escalated_cases,
            "escalated_passed": self.escalated_passed,
            "escalation_accuracy": self.escalation_accuracy,
            "false_escalations": self.false_escalations,
            "false_matches": self.false_matches,
            "wrong_faq_matches": self.wrong_faq_matches,
            "top_3_hit_rate": self.top_3_hit_rate,
            "normalization_sensitive_total": self.normalization_sensitive_total,
            "normalization_sensitive_passed": self.normalization_sensitive_passed,
            "normalization_sensitive_accuracy": self.normalization_sensitive_accuracy,
        }


@dataclass(frozen=True)
class DatasetReport:
    dataset_name: str
    dataset_path: Path
    metrics: DatasetMetrics
    results: list[CaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "dataset_path": str(self.dataset_path),
            "summary": self.metrics.to_dict(),
            "results": [result.to_dict() for result in self.results],
        }


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class SmokeReport:
    checks: list[SmokeCheck]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": [check.to_dict() for check in self.checks]}


def resolve_eval_paths(dataset_args: list[str] | None = None) -> list[Path]:
    if dataset_args:
        return [Path(item).expanduser().resolve() for item in dataset_args]
    return sorted(eval_dir().glob("*.json"))


def load_eval_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise EvalError(f"Expected eval dataset {path} to contain a JSON array.")
    return payload


def build_seed_faq_lookup() -> dict[str, int]:
    from .seed import load_seed_dataset

    dataset = load_seed_dataset()
    lookup: dict[str, int] = {}
    for index, entry in enumerate(dataset, start=1):
        canonical = str(entry.get("canonical_question") or "").strip()
        if canonical:
            lookup[canonical] = index
    return lookup


def build_live_faq_lookup(api_client: ApiClientProtocol) -> dict[str, int]:
    return {
        str(faq["canonical_question"]).strip(): int(faq["id"])
        for faq in api_client.list_faqs()
        if faq.get("canonical_question") is not None and faq.get("id") is not None
    }


def build_faq_lookup(api_client: ApiClientProtocol | None = None) -> dict[str, int]:
    if api_client is not None:
        try:
            live_lookup = build_live_faq_lookup(api_client)
        except EvalError:
            live_lookup = {}
        if live_lookup:
            return live_lookup
    return build_seed_faq_lookup()


def load_eval_cases(
    path: Path,
    faq_lookup: dict[str, int] | None = None,
    default_case_type: str | None = None,
) -> list[EvalCase]:
    raw_rows = load_eval_dataset(path)
    resolved_lookup = faq_lookup or {}
    fallback_case_type = default_case_type or path.stem
    cases: list[EvalCase] = []
    for row in raw_rows:
        cases.append(normalize_eval_case(row, resolved_lookup, fallback_case_type))
    return cases


def normalize_eval_case(
    row: dict[str, Any],
    faq_lookup: dict[str, int],
    default_case_type: str,
) -> EvalCase:
    question = str(row.get("question") or row.get("query") or "").strip()
    if not question:
        raise EvalError(f"Eval row is missing question/query: {row}")

    expected_status = str(row.get("expected_status") or "").strip()
    if expected_status not in {"matched", "escalated"}:
        raise EvalError(f"Unsupported expected_status for question '{question}': {expected_status}")

    expected_canonical_question = _optional_text(
        row.get("expected_canonical_question") or row.get("expected_canonical")
    )
    expected_faq_id = _parse_expected_faq_id(
        row.get("expected_faq_id"),
        expected_status=expected_status,
        expected_canonical_question=expected_canonical_question,
        faq_lookup=faq_lookup,
        question=question,
    )

    case_type = _optional_text(row.get("case_type") or row.get("category")) or default_case_type
    notes = _optional_text(row.get("notes"))
    normalization_sensitive = bool(
        row.get("normalization_sensitive", case_type in NORMALIZATION_SENSITIVE_CASE_TYPES)
    )

    return EvalCase(
        question=question,
        expected_status=expected_status,
        expected_faq_id=expected_faq_id,
        expected_canonical_question=expected_canonical_question,
        case_type=case_type,
        notes=notes,
        normalization_sensitive=normalization_sensitive,
    )


def evaluate_case(
    api_client: ApiClientProtocol,
    case: EvalCase,
    *,
    with_debug: bool = False,
    save_response: bool = False,
) -> CaseResult:
    response = api_client.query_chat(case.question)
    top_matches = response.get("top_matches")
    top_matches_list = top_matches if isinstance(top_matches, list) else []
    actual_status = _optional_text(response.get("status"))
    actual_faq_id = _optional_int(response.get("matched_faq_id"))
    actual_canonical_question = None
    if top_matches_list:
        actual_canonical_question = _optional_text(top_matches_list[0].get("canonical_question"))

    passed, failure_reason = determine_case_outcome(case, actual_status, actual_faq_id)
    debug_payload = None
    if with_debug and not passed:
        try:
            debug_payload = api_client.retrieval_debug(case.question)
        except EvalError as exc:
            debug_payload = {"error": str(exc)}

    return CaseResult(
        question=case.question,
        expected_status=case.expected_status,
        expected_faq_id=case.expected_faq_id,
        expected_canonical_question=case.expected_canonical_question,
        case_type=case.case_type,
        notes=case.notes,
        normalization_sensitive=case.normalization_sensitive,
        actual_status=actual_status,
        actual_faq_id=actual_faq_id,
        actual_canonical_question=actual_canonical_question,
        score=_optional_float(response.get("score")),
        matched_question=_optional_text(response.get("matched_question")),
        top_matches=top_matches_list,
        passed=passed,
        failure_reason=failure_reason,
        response=response if save_response else None,
        debug=debug_payload,
    )


def determine_case_outcome(
    case: EvalCase,
    actual_status: str | None,
    actual_faq_id: int | None,
) -> tuple[bool, str | None]:
    if case.expected_status == "matched":
        if actual_status == "escalated":
            return False, "false_escalation"
        if actual_status != "matched":
            return False, "unexpected_status"
        if actual_faq_id != case.expected_faq_id:
            return False, "wrong_faq_match"
        return True, None

    if actual_status == "escalated":
        return True, None
    if actual_status == "matched":
        return False, "false_match"
    return False, "unexpected_status"


def evaluate_dataset(
    api_client: ApiClientProtocol,
    dataset_path: Path,
    *,
    faq_lookup: dict[str, int] | None = None,
    with_debug: bool = False,
    save_responses: bool = False,
) -> DatasetReport:
    cases = load_eval_cases(dataset_path, faq_lookup=faq_lookup)
    results = [
        evaluate_case(
            api_client,
            case,
            with_debug=with_debug,
            save_response=save_responses,
        )
        for case in cases
    ]
    return DatasetReport(
        dataset_name=dataset_path.stem,
        dataset_path=dataset_path,
        metrics=compute_metrics(dataset_path.stem, results),
        results=results,
    )


def compute_metrics(dataset_name: str, results: list[CaseResult]) -> DatasetMetrics:
    total_cases = len(results)
    passed_cases = sum(result.passed for result in results)

    matched_results = [result for result in results if result.expected_status == "matched"]
    matched_passed = sum(result.passed for result in matched_results)
    false_escalations = sum(result.failure_reason == "false_escalation" for result in matched_results)
    wrong_faq_matches = sum(result.failure_reason == "wrong_faq_match" for result in matched_results)

    escalated_results = [result for result in results if result.expected_status == "escalated"]
    escalated_passed = sum(result.passed for result in escalated_results)
    false_matches = sum(result.failure_reason == "false_match" for result in escalated_results)

    top_3_hits = sum(_is_top_3_hit(result) for result in matched_results)
    normalization_results = [result for result in results if result.normalization_sensitive]
    normalization_passed = sum(result.passed for result in normalization_results)

    return DatasetMetrics(
        dataset_name=dataset_name,
        total_cases=total_cases,
        passed_cases=passed_cases,
        accuracy=_safe_ratio(passed_cases, total_cases),
        matched_cases=len(matched_results),
        matched_passed=matched_passed,
        matched_accuracy=_safe_ratio(matched_passed, len(matched_results)),
        escalated_cases=len(escalated_results),
        escalated_passed=escalated_passed,
        escalation_accuracy=_safe_ratio(escalated_passed, len(escalated_results)),
        false_escalations=false_escalations,
        false_matches=false_matches,
        wrong_faq_matches=wrong_faq_matches,
        top_3_hit_rate=_safe_ratio(top_3_hits, len(matched_results)),
        normalization_sensitive_total=len(normalization_results),
        normalization_sensitive_passed=normalization_passed,
        normalization_sensitive_accuracy=_safe_ratio(normalization_passed, len(normalization_results)),
    )


def combine_reports(reports: list[DatasetReport]) -> DatasetMetrics:
    combined_results = [result for report in reports for result in report.results]
    return compute_metrics("all", combined_results)


def run_smoke(
    api_client: ApiClientProtocol,
    *,
    matched_question: str = DEFAULT_SMOKE_MATCHED_QUESTION,
    matched_faq_id: int | None = None,
    matched_canonical_question: str = DEFAULT_SMOKE_MATCHED_CANONICAL,
    negative_question: str = DEFAULT_SMOKE_NEGATIVE_QUESTION,
) -> SmokeReport:
    checks: list[SmokeCheck] = []

    health_payload = api_client.health()
    health_ok = health_payload.get("status") == "ok" and bool(health_payload.get("model_ready"))
    checks.append(
        SmokeCheck(
            name="health",
            passed=health_ok,
            detail=(
                f"status={health_payload.get('status')} "
                f"model_ready={health_payload.get('model_ready')} "
                f"backend={health_payload.get('embedding_backend')}"
            ),
        )
    )

    resolved_faq_id = matched_faq_id
    if resolved_faq_id is None and matched_canonical_question:
        faq_lookup = build_faq_lookup(api_client)
        resolved_faq_id = faq_lookup.get(matched_canonical_question)

    positive_response = api_client.query_chat(matched_question)
    positive_status = _optional_text(positive_response.get("status"))
    positive_faq_id = _optional_int(positive_response.get("matched_faq_id"))
    positive_ok = positive_status == "matched" and (
        resolved_faq_id is None or positive_faq_id == resolved_faq_id
    )
    checks.append(
        SmokeCheck(
            name="matched_case",
            passed=positive_ok,
            detail=(
                f"status={positive_status} "
                f"faq_id={positive_faq_id} "
                f"expected_faq_id={resolved_faq_id}"
            ),
        )
    )

    negative_response = api_client.query_chat(negative_question)
    negative_status = _optional_text(negative_response.get("status"))
    checks.append(
        SmokeCheck(
            name="negative_case",
            passed=negative_status == "escalated",
            detail=f"status={negative_status}",
        )
    )

    return SmokeReport(checks=checks)


def write_reports(
    output_dir: Path,
    *,
    base_url: str,
    reports: list[DatasetReport],
    combined_metrics: DatasetMetrics,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "datasets": [report.metrics.to_dict() for report in reports],
        "combined": combined_metrics.to_dict(),
    }

    written_paths: dict[str, Path] = {}
    for report in reports:
        path = output_dir / f"eval_{report.dataset_name}_results.json"
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        written_paths[report.dataset_name] = path

    summary_json_path = output_dir / "eval_summary.json"
    summary_json_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_md_path = output_dir / "eval_summary.md"
    summary_md_path.write_text(render_markdown_summary(summary_payload), encoding="utf-8")
    written_paths["summary_json"] = summary_json_path
    written_paths["summary_md"] = summary_md_path
    return written_paths


def render_markdown_summary(summary_payload: dict[str, Any]) -> str:
    rows = summary_payload["datasets"] + [summary_payload["combined"]]
    lines = [
        "# Eval Summary",
        "",
        f"Generated at: `{summary_payload['generated_at']}`",
        f"Base URL: `{summary_payload['base_url']}`",
        "",
        "| Dataset | Total | Passed | Accuracy | Matched Acc | Escalation Acc | False Escalations | False Matches | Top-3 Hit Rate | Normalization Acc |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {dataset} | {total} | {passed} | {accuracy} | {matched_accuracy} | "
            "{escalation_accuracy} | {false_escalations} | {false_matches} | {top_3_hit_rate} | "
            "{normalization_accuracy} |".format(
                dataset=row["dataset_name"],
                total=row["total_cases"],
                passed=row["passed_cases"],
                accuracy=_format_ratio(row["accuracy"]),
                matched_accuracy=_format_ratio(row["matched_accuracy"]),
                escalation_accuracy=_format_ratio(row["escalation_accuracy"]),
                false_escalations=row["false_escalations"],
                false_matches=row["false_matches"],
                top_3_hit_rate=_format_ratio(row["top_3_hit_rate"]),
                normalization_accuracy=_format_ratio(row["normalization_sensitive_accuracy"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def print_smoke_report(report: SmokeReport) -> None:
    print("[smoke]")
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"{marker} {check.name}: {check.detail}")


def print_eval_summary(report: DatasetReport) -> None:
    metrics = report.metrics
    print(f"[dataset] {report.dataset_name}")
    print(
        "total={total} passed={passed} accuracy={accuracy} matched_accuracy={matched_accuracy} "
        "escalation_accuracy={escalation_accuracy} false_escalations={false_escalations} "
        "false_matches={false_matches} top_3_hit_rate={top_3_hit_rate} "
        "normalization_accuracy={normalization_accuracy}".format(
            total=metrics.total_cases,
            passed=metrics.passed_cases,
            accuracy=_format_ratio(metrics.accuracy),
            matched_accuracy=_format_ratio(metrics.matched_accuracy),
            escalation_accuracy=_format_ratio(metrics.escalation_accuracy),
            false_escalations=metrics.false_escalations,
            false_matches=metrics.false_matches,
            top_3_hit_rate=_format_ratio(metrics.top_3_hit_rate),
            normalization_accuracy=_format_ratio(metrics.normalization_sensitive_accuracy),
        )
    )


def print_failure_details(report: DatasetReport) -> None:
    failures = [result for result in report.results if not result.passed]
    if not failures:
        print("failures=0")
        return

    print(f"failures={len(failures)}")
    for result in failures:
        print(
            f"- question={result.question} reason={result.failure_reason} "
            f"expected_status={result.expected_status} actual_status={result.actual_status} "
            f"expected_faq_id={result.expected_faq_id} actual_faq_id={result.actual_faq_id} "
            f"score={result.score}"
        )
        if result.actual_canonical_question:
            print(f"  top1={result.actual_canonical_question}")
        if result.debug:
            if result.debug.get("error"):
                print(f"  debug_error={result.debug['error']}")
            else:
                print(
                    "  normalized={normalized} threshold={threshold} top3={top3}".format(
                        normalized=result.debug.get("normalized_question"),
                        threshold=result.debug.get("threshold"),
                        top3=", ".join(
                            "{faq_id}:{score:.3f}:{canonical}".format(
                                faq_id=item.get("faq_id"),
                                score=float(item.get("score", 0.0)),
                                canonical=item.get("canonical_question"),
                            )
                            for item in result.debug.get("top_matches", [])[:3]
                        ),
                    )
                )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HTTP-based smoke and eval runner for Telecom FAQ Search.")
    subparsers = parser.add_subparsers(dest="command")

    smoke_parser = subparsers.add_parser("smoke", help="Run a fast API smoke check.")
    add_common_network_args(smoke_parser)
    smoke_parser.add_argument("--matched-question", default=DEFAULT_SMOKE_MATCHED_QUESTION)
    smoke_parser.add_argument("--matched-faq-id", type=int, default=None)
    smoke_parser.add_argument("--matched-canonical-question", default=DEFAULT_SMOKE_MATCHED_CANONICAL)
    smoke_parser.add_argument("--negative-question", default=DEFAULT_SMOKE_NEGATIVE_QUESTION)

    run_parser = subparsers.add_parser("run", help="Run eval datasets against the live API.")
    add_common_network_args(run_parser)
    run_parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Path to an eval dataset JSON file. Repeat to run multiple datasets. Defaults to data/eval/*.json.",
    )
    run_parser.add_argument("--mode", choices=("summary", "detailed"), default="summary")
    run_parser.add_argument("--with-debug", action="store_true")
    run_parser.add_argument("--save-responses", action="store_true")
    run_parser.add_argument("--output-dir", default="reports")

    return parser


def add_common_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-prefix", default=DEFAULT_API_PREFIX)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    command = args.command
    client = HttpApiClient(base_url=args.base_url, api_prefix=args.api_prefix, timeout=args.timeout)

    if command == "smoke":
        report = run_smoke(
            client,
            matched_question=args.matched_question,
            matched_faq_id=args.matched_faq_id,
            matched_canonical_question=args.matched_canonical_question,
            negative_question=args.negative_question,
        )
        print_smoke_report(report)
        return 0 if report.ok else 1

    dataset_paths = resolve_eval_paths(args.dataset or None)
    faq_lookup = build_faq_lookup(client)
    reports = [
        evaluate_dataset(
            client,
            dataset_path,
            faq_lookup=faq_lookup,
            with_debug=args.with_debug,
            save_responses=args.save_responses,
        )
        for dataset_path in dataset_paths
    ]
    combined_metrics = combine_reports(reports)
    for report in reports:
        print_eval_summary(report)
        if args.mode == "detailed":
            print_failure_details(report)
        print()

    print("[dataset] all")
    print(
        "total={total} passed={passed} accuracy={accuracy} matched_accuracy={matched_accuracy} "
        "escalation_accuracy={escalation_accuracy} false_escalations={false_escalations} "
        "false_matches={false_matches} top_3_hit_rate={top_3_hit_rate} "
        "normalization_accuracy={normalization_accuracy}".format(
            total=combined_metrics.total_cases,
            passed=combined_metrics.passed_cases,
            accuracy=_format_ratio(combined_metrics.accuracy),
            matched_accuracy=_format_ratio(combined_metrics.matched_accuracy),
            escalation_accuracy=_format_ratio(combined_metrics.escalation_accuracy),
            false_escalations=combined_metrics.false_escalations,
            false_matches=combined_metrics.false_matches,
            top_3_hit_rate=_format_ratio(combined_metrics.top_3_hit_rate),
            normalization_accuracy=_format_ratio(combined_metrics.normalization_sensitive_accuracy),
        )
    )

    written_paths = write_reports(
        Path(args.output_dir),
        base_url=args.base_url,
        reports=reports,
        combined_metrics=combined_metrics,
    )
    print()
    print(f"reports={written_paths['summary_json']}, {written_paths['summary_md']}")
    return 0 if combined_metrics.passed_cases == combined_metrics.total_cases else 1


def _parse_expected_faq_id(
    raw_value: Any,
    *,
    expected_status: str,
    expected_canonical_question: str | None,
    faq_lookup: dict[str, int],
    question: str,
) -> int | None:
    if expected_status == "escalated":
        return None

    parsed_id = _optional_int(raw_value)
    if parsed_id is not None:
        return parsed_id

    if expected_canonical_question:
        resolved = faq_lookup.get(expected_canonical_question)
        if resolved is not None:
            return resolved

    raise EvalError(
        "Matched eval case is missing expected_faq_id and could not resolve expected_canonical_question "
        f"for question '{question}'."
    )


def _is_top_3_hit(result: CaseResult) -> bool:
    if result.expected_status != "matched" or result.expected_faq_id is None:
        return False
    return result.expected_faq_id in {
        _optional_int(item.get("faq_id"))
        for item in result.top_matches[:3]
        if isinstance(item, dict)
    }


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
