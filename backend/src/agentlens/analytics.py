from __future__ import annotations

from collections import Counter

from agentlens.schemas import CountBucket, DriftRecord, Gate, LedgerAnalytics, TrustScore


def build_ledger_analytics(session_id: str, gates: list[Gate]) -> LedgerAnalytics:
    total = len(gates)
    auto_executed = sum(1 for gate in gates if gate.status == "auto_executed")
    human_interventions = sum(1 for gate in gates if gate.status != "auto_executed")
    trust_score = auto_executed / total if total else 0.0

    status_counts = Counter(str(gate.status) for gate in gates)
    risk_counts = Counter(str(gate.risk_assessment.risk_level) for gate in gates)
    drift_history = [
        DriftRecord(
            gate_id=gate.id,
            risk_level=gate.risk_assessment.risk_level,
            status=gate.status,
            drift_flag=gate.intelligence_card.drift_flag,
        )
        for gate in gates
        if gate.intelligence_card and gate.intelligence_card.drift_flag
    ]

    return LedgerAnalytics(
        session_id=session_id,
        trust_score=TrustScore(
            score=trust_score,
            auto_executed=auto_executed,
            human_interventions=human_interventions,
            total_actions=total,
        ),
        approval_patterns=_buckets(status_counts),
        risk_distribution=_buckets(risk_counts),
        drift_history=drift_history,
    )


def _buckets(counter: Counter[str]) -> list[CountBucket]:
    return [CountBucket(name=name, count=count) for name, count in sorted(counter.items())]
