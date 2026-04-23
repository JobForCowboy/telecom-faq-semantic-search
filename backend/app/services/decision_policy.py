from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import Settings
from ..schemas import ChatQueryResponse, RetrievalMatchResponse
from .domain_filter import DomainFilter, DomainFilterResult


if TYPE_CHECKING:
    from .chat import MatchCandidate


@dataclass(frozen=True)
class DecisionPolicyResult:
    response: ChatQueryResponse
    domain_filter: DomainFilterResult


class DecisionPolicy:
    def __init__(
        self,
        settings: Settings,
        domain_filter: DomainFilter | None = None,
    ) -> None:
        self.settings = settings
        self.domain_filter = domain_filter or DomainFilter(settings)

    def decide(
        self,
        *,
        raw_query: str,
        normalized_query: str,
        candidates: list["MatchCandidate"],
        conversation_id: str = "",
        conversation_message_count: int = 0,
        is_follow_up: bool = False,
    ) -> DecisionPolicyResult:
        top_matches = self._serialize_matches(candidates)
        top1 = candidates[0] if candidates else None
        top2 = candidates[1] if len(candidates) > 1 else None
        top_score = top1.score if top1 is not None else None
        top2_score = top2.score if top2 is not None else None
        match_margin = (top_score - top2_score) if top_score is not None and top2_score is not None else None

        decision_path = [
            f"retrieval returned {len(candidates)} candidate(s)",
        ]
        domain_result = self.domain_filter.evaluate(
            raw_query=raw_query,
            normalized_query=normalized_query,
            candidates=candidates,
            is_follow_up=is_follow_up,
        )
        decision_path.extend(domain_result.domain_signals)

        if top1 is not None and top1.score >= self.settings.effective_match_threshold:
            decision_path.append("top1 score reached match threshold")
            response = self._build_response(
                status="matched",
                answer=top1.answer,
                candidate=top1,
                top_matches=top_matches,
                conversation_id=conversation_id,
                conversation_message_count=conversation_message_count,
                is_follow_up=is_follow_up,
                domain_result=domain_result,
                top_score=top_score,
                top2_score=top2_score,
                match_margin=match_margin,
                decision_path=decision_path,
            )
            return DecisionPolicyResult(response=response, domain_filter=domain_result)

        decision_path.append("match threshold not met")
        soft_match_reason = self._evaluate_soft_match(
            top1=top1,
            top2=top2,
            domain_result=domain_result,
            decision_path=decision_path,
        )
        if soft_match_reason is not None and top1 is not None:
            decision_path.append("soft match applied")
            response = self._build_response(
                status="matched",
                answer=top1.answer,
                candidate=top1,
                top_matches=top_matches,
                conversation_id=conversation_id,
                conversation_message_count=conversation_message_count,
                is_follow_up=is_follow_up,
                domain_result=domain_result,
                top_score=top_score,
                top2_score=top2_score,
                match_margin=match_margin,
                decision_path=decision_path,
                soft_match_used=True,
                soft_match_reason=soft_match_reason,
            )
            return DecisionPolicyResult(response=response, domain_filter=domain_result)

        if domain_result.is_in_domain:
            decision_path.append("query considered telecom-related, escalate to operator")
            response = self._build_response(
                status="escalated",
                answer=self.settings.fallback_message,
                candidate=top1,
                top_matches=top_matches,
                conversation_id=conversation_id,
                conversation_message_count=conversation_message_count,
                is_follow_up=is_follow_up,
                domain_result=domain_result,
                top_score=top_score,
                top2_score=top2_score,
                match_margin=match_margin,
                decision_path=decision_path,
            )
            return DecisionPolicyResult(response=response, domain_filter=domain_result)

        decision_path.append("query considered out of telecom domain")
        response = self._build_response(
            status="out_of_domain",
            answer=self.settings.out_of_domain_message,
            candidate=None,
            top_matches=top_matches,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
            domain_result=domain_result,
            top_score=top_score,
            top2_score=top2_score,
            match_margin=match_margin,
            decision_path=decision_path,
        )
        return DecisionPolicyResult(response=response, domain_filter=domain_result)

    def _evaluate_soft_match(
        self,
        *,
        top1: "MatchCandidate" | None,
        top2: "MatchCandidate" | None,
        domain_result: DomainFilterResult,
        decision_path: list[str],
    ) -> str | None:
        if not self.settings.soft_match_enabled:
            decision_path.append("soft match disabled")
            return None
        if top1 is None:
            decision_path.append("soft match skipped: no top1 candidate")
            return None
        if top1.score < self.settings.soft_match_min_score:
            decision_path.append("soft match skipped: top1 below soft-match minimum")
            return None
        if not domain_result.is_in_domain:
            decision_path.append("soft match skipped: query not in telecom domain")
            return None
        if not domain_result.domain_keyword_hits:
            decision_path.append("soft match skipped: no telecom keyword support")
            return None
        if domain_result.offtopic_rule_hit:
            decision_path.append("soft match skipped: off-topic rule hit")
            return None
        if domain_result.garbage_rule_hit:
            decision_path.append("soft match skipped: garbage rule hit")
            return None

        margin = top1.score - top2.score if top2 is not None else top1.score
        if margin < self.settings.soft_match_min_margin:
            decision_path.append("soft match skipped: top1 margin too small")
            return None

        return (
            "top1 slightly below hard threshold, but telecom signals are strong "
            "and top1 clearly beats top2"
        )

    def _build_response(
        self,
        *,
        status: str,
        answer: str,
        candidate: "MatchCandidate" | None,
        top_matches: list[RetrievalMatchResponse],
        conversation_id: str,
        conversation_message_count: int,
        is_follow_up: bool,
        domain_result: DomainFilterResult,
        top_score: float | None,
        top2_score: float | None,
        match_margin: float | None,
        decision_path: list[str],
        soft_match_used: bool = False,
        soft_match_reason: str | None = None,
    ) -> ChatQueryResponse:
        return ChatQueryResponse(
            status=status,  # type: ignore[arg-type]
            decision_type=status if status != "clarification_required" else None,  # type: ignore[arg-type]
            answer=answer,
            score=top_score,
            matched_faq_id=candidate.faq_id if candidate else None,
            matched_question=candidate.matched_question if candidate else None,
            top_matches=top_matches,
            conversation_id=conversation_id,
            conversation_message_count=conversation_message_count,
            is_follow_up=is_follow_up,
            domain_score=domain_result.domain_score,
            domain_reason=domain_result.domain_reason,
            ood_reason=domain_result.ood_reason,
            domain_signals=list(domain_result.domain_signals),
            domain_keyword_hits=list(domain_result.domain_keyword_hits),
            offtopic_rule_hit=domain_result.offtopic_rule_hit,
            garbage_rule_hit=domain_result.garbage_rule_hit,
            soft_match_used=soft_match_used,
            soft_match_reason=soft_match_reason,
            top_score=top_score,
            top2_score=top2_score,
            match_margin=match_margin,
            decision_path=list(decision_path),
        )

    def _serialize_matches(self, candidates: list["MatchCandidate"]) -> list[RetrievalMatchResponse]:
        return [
            RetrievalMatchResponse(
                faq_id=item.faq_id,
                canonical_question=item.canonical_question,
                matched_question=item.matched_question,
                score=item.score,
            )
            for item in candidates
        ]
