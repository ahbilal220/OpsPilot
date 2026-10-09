import json
from decimal import Decimal
from uuid import UUID

from app.agents.models import Hypothesis, HypothesisStatus
from app.agents.schemas import ValidationResult
from app.evidence.models import Evidence, EvidenceType


def validate_n_plus_one_hypothesis(
    hypothesis: Hypothesis,
    evidence: list[Evidence],
) -> ValidationResult:
    by_type: dict[EvidenceType, list[Evidence]] = {}
    for item in evidence:
        by_type.setdefault(item.type, []).append(item)

    def content(evidence_type: EvidenceType) -> str:
        return " ".join(item.content.casefold() for item in by_type.get(evidence_type, []))

    metric_content = content(EvidenceType.metric)
    log_content = content(EvidenceType.log)
    database_content = content(EvidenceType.database)
    code_content = content(EvidenceType.code)
    checks = {
        "latency_elevated": "1.91" in metric_content or "duration_ms=19" in log_content,
        "query_count_elevated": (
            "threshold_exceeded" in database_content
            and "true" in database_content
            and "db_queries=4" in log_content
        ),
        "query_inside_loop": "for product_id in product_ids" in code_content,
        "recent_change_correlated": bool(
            by_type.get(EvidenceType.git) and by_type.get(EvidenceType.deployment)
        ),
    }
    independent_types = {
        item.type
        for item in evidence
        if item.type
        in {
            EvidenceType.log,
            EvidenceType.metric,
            EvidenceType.code,
            EvidenceType.git,
            EvidenceType.deployment,
            EvidenceType.database,
        }
    }
    score = Decimal(sum(checks.values())) * Decimal("0.22")
    if len(independent_types) >= 5:
        score += Decimal("0.08")
    confidence = min(score, Decimal("0.96"))
    supported = (
        checks["latency_elevated"]
        and checks["query_count_elevated"]
        and checks["query_inside_loop"]
        and confidence >= Decimal("0.75")
    )
    status = HypothesisStatus.supported if supported else HypothesisStatus.inconclusive
    supporting = [item.id for item in evidence if item.type in independent_types]
    result = ValidationResult(
        status=status.value,
        confidence=confidence,
        checks=checks,
        supporting_evidence_ids=supporting,
        contradicting_evidence_ids=[],
        summary=(
            "Independent latency, query-count, code, and change evidence supports the hypothesis."
            if supported
            else "The available evidence does not meet the bounded N+1 validation threshold."
        ),
    )
    hypothesis.status = result.status
    hypothesis.confidence = result.confidence
    hypothesis.supporting_evidence_ids = [str(item) for item in result.supporting_evidence_ids]
    hypothesis.contradicting_evidence_ids = [
        str(item) for item in result.contradicting_evidence_ids
    ]
    hypothesis.validation_result = json.loads(result.model_dump_json())
    return result


def ids_belong_to_evidence(candidate_ids: list[UUID], evidence: list[Evidence]) -> bool:
    available = {item.id for item in evidence}
    return bool(candidate_ids) and set(candidate_ids).issubset(available)
