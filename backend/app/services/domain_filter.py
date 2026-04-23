from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..normalization import collapse_spaces, domain_dir


class CandidateLike(Protocol):
    score: float


@dataclass(frozen=True)
class DomainFilterRules:
    domain_keyword_groups: dict[str, tuple[str, ...]]
    offtopic_patterns: dict[str, tuple[str, ...]]
    garbage_exact: tuple[str, ...]
    garbage_contains: tuple[str, ...]


@dataclass(frozen=True)
class DomainFilterResult:
    domain_score: float
    domain_reason: str | None
    ood_reason: str | None
    domain_signals: list[str]
    domain_keyword_hits: list[str]
    offtopic_rule_hit: str | None
    garbage_rule_hit: str | None
    is_in_domain: bool


def _rules_path() -> Path:
    return domain_dir() / "filter_rules.json"


def _normalize_phrase(value: str) -> str:
    return collapse_spaces(str(value).strip().lower().replace("ё", "е"))


def _normalize_mapping(payload: dict[str, list[str]] | dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    normalized: dict[str, tuple[str, ...]] = {}
    for key, values in payload.items():
        phrases = tuple(
            phrase
            for phrase in (_normalize_phrase(item) for item in values)
            if phrase
        )
        if phrases:
            normalized[_normalize_phrase(key)] = phrases
    return normalized


@lru_cache
def load_domain_filter_rules() -> DomainFilterRules:
    payload = json.loads(_rules_path().read_text(encoding="utf-8"))
    return DomainFilterRules(
        domain_keyword_groups=_normalize_mapping(payload.get("domain_keyword_groups", {})),
        offtopic_patterns=_normalize_mapping(payload.get("offtopic_patterns", {})),
        garbage_exact=tuple(
            phrase
            for phrase in (_normalize_phrase(item) for item in payload.get("garbage_exact", []))
            if phrase
        ),
        garbage_contains=tuple(
            phrase
            for phrase in (_normalize_phrase(item) for item in payload.get("garbage_contains", []))
            if phrase
        ),
    )


class DomainFilter:
    def __init__(
        self,
        settings: Settings,
        rules: DomainFilterRules | None = None,
    ) -> None:
        self.settings = settings
        self.rules = rules or load_domain_filter_rules()

    def evaluate(
        self,
        *,
        raw_query: str,
        normalized_query: str,
        candidates: list[CandidateLike],
        is_follow_up: bool = False,
    ) -> DomainFilterResult:
        query = _normalize_phrase(normalized_query)
        raw = raw_query.strip()
        tokens = [token for token in query.split() if token]
        top1_score = candidates[0].score if candidates else 0.0
        top2_score = candidates[1].score if len(candidates) > 1 else 0.0
        margin = top1_score - top2_score if candidates else 0.0

        keyword_hits, keyword_groups = self._collect_domain_hits(query)
        offtopic_rule_hit = self._first_matching_rule(query, self.rules.offtopic_patterns)
        garbage_rule_hit = self._detect_garbage_rule(
            raw_query=raw,
            normalized_query=query,
            tokens=tokens,
            keyword_hits=keyword_hits,
            top1_score=top1_score,
            is_follow_up=is_follow_up,
        )

        domain_signals: list[str] = []
        if top1_score >= self.settings.domain_threshold:
            domain_signals.append("top1 score reached domain threshold")
        elif top1_score >= max(self.settings.domain_threshold - 0.08, 0.0):
            domain_signals.append("top1 score close to domain threshold")
        else:
            domain_signals.append("retrieval weak for telecom domain")

        if keyword_groups:
            domain_signals.append(
                f"telecom keyword groups hit: {', '.join(sorted(keyword_groups))}"
            )
        else:
            domain_signals.append("no telecom keyword hits")

        if margin >= self.settings.soft_match_min_margin:
            domain_signals.append("top1 margin over top2 is informative")

        if is_follow_up:
            domain_signals.append("follow-up context available")

        if offtopic_rule_hit:
            domain_signals.append(f"off-topic rule hit: {offtopic_rule_hit}")

        if garbage_rule_hit:
            domain_signals.append(f"garbage rule hit: {garbage_rule_hit}")

        keyword_support = min(0.22 + 0.12 * len(keyword_groups), 0.58) if keyword_groups else 0.0
        retrieval_support = top1_score
        domain_score = max(keyword_support, retrieval_support)

        if keyword_groups and top1_score >= max(self.settings.domain_threshold - 0.08, 0.0):
            domain_score = max(domain_score, min(top1_score + 0.08, 1.0))
        if is_follow_up and top1_score >= max(self.settings.domain_threshold - 0.10, 0.0):
            domain_score = max(domain_score, 0.45)

        if offtopic_rule_hit and not keyword_groups:
            domain_score = max(0.0, domain_score - 0.55)
        elif offtopic_rule_hit:
            domain_score = max(0.0, domain_score - 0.20)

        if garbage_rule_hit and not is_follow_up:
            domain_score = max(0.0, domain_score - 0.35)

        is_in_domain = self._is_in_domain(
            top1_score=top1_score,
            keyword_groups=keyword_groups,
            offtopic_rule_hit=offtopic_rule_hit,
            garbage_rule_hit=garbage_rule_hit,
            is_follow_up=is_follow_up,
            domain_score=domain_score,
        )
        domain_reason = self._build_domain_reason(
            is_in_domain=is_in_domain,
            top1_score=top1_score,
            keyword_groups=keyword_groups,
            is_follow_up=is_follow_up,
        )
        ood_reason = self._build_ood_reason(
            is_in_domain=is_in_domain,
            offtopic_rule_hit=offtopic_rule_hit,
            garbage_rule_hit=garbage_rule_hit,
            keyword_groups=keyword_groups,
        )

        return DomainFilterResult(
            domain_score=round(domain_score, 3),
            domain_reason=domain_reason,
            ood_reason=ood_reason,
            domain_signals=domain_signals,
            domain_keyword_hits=keyword_hits,
            offtopic_rule_hit=offtopic_rule_hit,
            garbage_rule_hit=garbage_rule_hit,
            is_in_domain=is_in_domain,
        )

    def _collect_domain_hits(self, query: str) -> tuple[list[str], set[str]]:
        hits: list[str] = []
        groups: set[str] = set()
        for group, phrases in self.rules.domain_keyword_groups.items():
            for phrase in phrases:
                if _contains_phrase(query, phrase):
                    hits.append(phrase)
                    groups.add(group)
        return hits, groups

    def _first_matching_rule(self, query: str, patterns: dict[str, tuple[str, ...]]) -> str | None:
        for group, phrases in patterns.items():
            if any(_contains_phrase(query, phrase) for phrase in phrases):
                return group
        return None

    def _detect_garbage_rule(
        self,
        *,
        raw_query: str,
        normalized_query: str,
        tokens: list[str],
        keyword_hits: list[str],
        top1_score: float,
        is_follow_up: bool,
    ) -> str | None:
        if not raw_query.strip():
            return "empty_raw_query"
        if not normalized_query:
            return "empty_after_normalization"
        if normalized_query in self.rules.garbage_exact:
            return "garbage_exact"
        if any(fragment in normalized_query for fragment in self.rules.garbage_contains):
            return "garbage_contains"
        if not any(char.isalnum() for char in raw_query):
            return "non_alnum_only"
        if (
            not is_follow_up
            and len(tokens) <= 1
            and len(normalized_query) <= 3
            and not keyword_hits
            and top1_score < max(self.settings.domain_threshold - 0.05, 0.0)
        ):
            return "too_short_noisy"
        return None

    def _is_in_domain(
        self,
        *,
        top1_score: float,
        keyword_groups: set[str],
        offtopic_rule_hit: str | None,
        garbage_rule_hit: str | None,
        is_follow_up: bool,
        domain_score: float,
    ) -> bool:
        if offtopic_rule_hit and not keyword_groups and top1_score < self.settings.domain_threshold + 0.05:
            return False
        if garbage_rule_hit and not keyword_groups and not is_follow_up and top1_score < self.settings.domain_threshold:
            return False
        if top1_score >= self.settings.domain_threshold:
            return True
        if keyword_groups and top1_score >= max(self.settings.domain_threshold - 0.08, 0.0):
            return True
        if len(keyword_groups) >= 2:
            return True
        if is_follow_up and top1_score >= max(self.settings.domain_threshold - 0.10, 0.0) and not offtopic_rule_hit:
            return True
        return domain_score >= 0.45 and not (offtopic_rule_hit and not keyword_groups)

    def _build_domain_reason(
        self,
        *,
        is_in_domain: bool,
        top1_score: float,
        keyword_groups: set[str],
        is_follow_up: bool,
    ) -> str | None:
        if not is_in_domain:
            return None
        if top1_score >= self.settings.domain_threshold and keyword_groups:
            return "retrieval and telecom keyword signals confirm in-domain intent"
        if top1_score >= self.settings.domain_threshold:
            return "retrieval remains close enough to telecom domain"
        if keyword_groups:
            return "telecom keywords keep query in-domain despite weak match"
        if is_follow_up:
            return "follow-up context keeps the query inside telecom domain"
        return "query remains telecom-related"

    def _build_ood_reason(
        self,
        *,
        is_in_domain: bool,
        offtopic_rule_hit: str | None,
        garbage_rule_hit: str | None,
        keyword_groups: set[str],
    ) -> str | None:
        if is_in_domain:
            return None
        if offtopic_rule_hit:
            return f"off-topic pattern matched: {offtopic_rule_hit}"
        if garbage_rule_hit:
            return f"garbage or noisy query matched: {garbage_rule_hit}"
        if not keyword_groups:
            return "retrieval weak and no telecom keyword support"
        return "query stayed below telecom-domain confidence threshold"


def _contains_phrase(query: str, phrase: str) -> bool:
    if not query or not phrase:
        return False
    haystack = f" {query} "
    needle = f" {phrase} "
    return needle in haystack
