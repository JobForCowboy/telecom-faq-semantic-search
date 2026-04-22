import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


MULTISPACE_PATTERN = re.compile(r"\s+")
NON_WORD_PATTERN = re.compile(r"[^\w\s]+", re.UNICODE)


@dataclass(frozen=True)
class PreparedVariant:
    question: str
    normalized_question: str


@dataclass(frozen=True)
class ReplacementRule:
    source: str
    target: str
    pattern: re.Pattern[str]


def data_dir() -> Path:
    current = Path(__file__).resolve()
    candidates = [
        current.parent.parent.parent / "data",
        current.parent.parent / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def normalization_dir() -> Path:
    return data_dir() / "normalization"


def kb_dir() -> Path:
    return data_dir() / "kb"


def eval_dir() -> Path:
    return data_dir() / "eval"


def _load_json_mapping(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    normalized: dict[str, str] = {}
    for key, value in payload.items():
        source = collapse_spaces(str(key).strip().lower().replace("ё", "е"))
        target = collapse_spaces(str(value).strip().lower().replace("ё", "е"))
        if not source or not target:
            continue
        normalized[source] = target
    return normalized


def collapse_spaces(text: str) -> str:
    return MULTISPACE_PATTERN.sub(" ", text).strip()


def _compile_rule(source: str, target: str) -> ReplacementRule:
    pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.UNICODE)
    return ReplacementRule(source=source, target=target, pattern=pattern)


@lru_cache
def load_replacement_rules() -> tuple[ReplacementRule, ...]:
    sources: list[dict[str, str]] = [
        _load_json_mapping(normalization_dir() / "abbreviations.json"),
        _load_json_mapping(normalization_dir() / "typos.json"),
    ]
    merged: dict[str, str] = {}
    for mapping in sources:
        merged.update(mapping)

    ordered = sorted(merged.items(), key=lambda item: (-len(item[0]), item[0]))
    return tuple(_compile_rule(source, target) for source, target in ordered)


class TextNormalizer:
    def __init__(self, rules: tuple[ReplacementRule, ...] | None = None) -> None:
        self.rules = rules or load_replacement_rules()

    def normalize(self, text: str) -> str:
        normalized = collapse_spaces(text.strip().lower().replace("ё", "е"))
        normalized = normalized.replace("-", " ")
        normalized = normalized.replace("/", " ")
        normalized = NON_WORD_PATTERN.sub(" ", normalized)
        normalized = collapse_spaces(normalized)
        for rule in self.rules:
            normalized = rule.pattern.sub(rule.target, normalized)
        return collapse_spaces(normalized)


@lru_cache
def get_text_normalizer() -> TextNormalizer:
    return TextNormalizer()


def prepare_variants(
    canonical_question: str,
    variants: list[str],
    normalizer: TextNormalizer | None = None,
) -> list[PreparedVariant]:
    text_normalizer = normalizer or get_text_normalizer()
    ordered = [canonical_question, *variants]
    prepared: list[PreparedVariant] = []
    seen: set[str] = set()

    for raw_variant in ordered:
        cleaned = collapse_spaces(str(raw_variant).strip())
        if not cleaned:
            continue
        normalized = text_normalizer.normalize(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        prepared.append(
            PreparedVariant(
                question=cleaned,
                normalized_question=normalized,
            )
        )

    return prepared
