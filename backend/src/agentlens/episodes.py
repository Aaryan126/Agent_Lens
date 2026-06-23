from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from agentlens.schemas import (
    ActionDescriptor,
    Gate,
    GateStatus,
    ReviewEpisode,
    RiskLevel,
    Session,
    TraceEvent,
)

TARGET_HINT_RE = re.compile(r"(?<![\w./-])[\w./-]+\.[A-Za-z0-9_.-]+(?![\w./-])")
READ_COMMANDS = {"cat", "find", "git", "head", "ls", "nl", "pwd", "rg", "sed", "sort", "tail", "wc"}
RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@dataclass(frozen=True)
class EpisodeRecord:
    trace: TraceEvent | None
    gate: Gate | None
    prompt: str
    target: str
    family: str
    kind: str


def build_review_episodes(
    *,
    session: Session,
    traces: list[TraceEvent],
    gates: list[Gate],
) -> list[ReviewEpisode]:
    gate_by_proposal = {gate.proposal_id: gate for gate in gates}
    handled_gate_ids: set[str] = set()
    records: list[EpisodeRecord] = []

    for trace in sorted(traces, key=lambda item: item.created_at):
        gate = gate_by_proposal.get(trace.proposal_id)
        if gate:
            handled_gate_ids.add(gate.id)
        records.append(_record_for(session, trace, gate))

    for gate in sorted(gates, key=lambda item: item.created_at):
        if gate.id in handled_gate_ids:
            continue
        records.append(_record_for(session, None, gate))

    groups: list[list[EpisodeRecord]] = []
    group_keys: list[tuple[str, str, str, str]] = []
    for record in records:
        key = (record.prompt, record.target, record.family, record.kind)
        if groups and group_keys[-1] == key:
            groups[-1].append(record)
            continue
        groups.append([record])
        group_keys.append(key)

    return [_episode_from_group(session.id, index, group) for index, group in enumerate(groups)]


def _record_for(session: Session, trace: TraceEvent | None, gate: Gate | None) -> EpisodeRecord:
    prompt = _prompt_for(session, trace)
    target = _target_for(prompt, trace, gate)
    family = _family_for(trace, gate)
    kind = _kind_for(trace, gate, family)
    return EpisodeRecord(trace=trace, gate=gate, prompt=prompt, target=target, family=family, kind=kind)


def _episode_from_group(session_id: str, index: int, group: list[EpisodeRecord]) -> ReviewEpisode:
    primary_gate = _primary_gate(group)
    traces = [record.trace for record in group if record.trace is not None]
    gates = [record.gate for record in group if record.gate is not None]
    first = group[0]
    descriptor = _descriptor_for_group(group, primary_gate)
    status = primary_gate.status if primary_gate else GateStatus.AUTO_EXECUTED
    risk_level = _risk_for_group(group)
    confidence = _confidence_for_group(group)
    created_values = [item.created_at for item in [*traces, *gates] if item.created_at]
    updated_values = [
        item.resolved_at or item.created_at
        for item in gates
        if item.resolved_at or item.created_at
    ] or created_values
    episode_id = _episode_id(session_id, index, first.kind, first.target, gates, traces)
    return ReviewEpisode(
        id=episode_id,
        session_id=session_id,
        prompt=first.prompt,
        kind=first.kind,
        status=status,
        risk_level=risk_level,
        confidence=confidence,
        primary_gate_id=primary_gate.id if primary_gate else None,
        trace_ids=[trace.id for trace in traces],
        gate_ids=[gate.id for gate in gates],
        descriptor=descriptor,
        summary=_summary_for_group(group, descriptor, primary_gate),
        counts={
            "traces": len(traces),
            "gates": len(gates),
            "pending": sum(1 for gate in gates if gate.status == GateStatus.PENDING),
            "auto_executed": sum(1 for gate in gates if gate.status == GateStatus.AUTO_EXECUTED),
        },
        created_at=min(created_values) if created_values else None,
        updated_at=max(updated_values) if updated_values else None,
    )


def _episode_id(
    session_id: str,
    index: int,
    kind: str,
    target: str,
    gates: list[Gate],
    traces: list[TraceEvent],
) -> str:
    anchor = gates[0].id if gates else traces[0].id if traces else str(index)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", target).strip("_")[:36] or "target"
    return f"epi_{session_id[-8:]}_{index:03d}_{kind}_{slug}_{anchor[-8:]}"


def _primary_gate(group: list[EpisodeRecord]) -> Gate | None:
    gates = [record.gate for record in group if record.gate is not None]
    if not gates:
        return None
    return sorted(
        gates,
        key=lambda gate: (
            gate.status != GateStatus.PENDING,
            -RISK_RANK.get(gate.risk_assessment.risk_level, 0),
            gate.created_at,
        ),
    )[0]


def _risk_for_group(group: list[EpisodeRecord]) -> RiskLevel:
    risks = [
        record.gate.risk_assessment.risk_level
        for record in group
        if record.gate is not None
    ]
    if not risks:
        return RiskLevel.LOW
    return max(risks, key=lambda risk: RISK_RANK.get(risk, 0))


def _confidence_for_group(group: list[EpisodeRecord]) -> float | None:
    scores = [
        record.gate.intelligence_card.confidence
        for record in group
        if record.gate is not None and record.gate.intelligence_card is not None
    ]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _prompt_for(session: Session, trace: TraceEvent | None) -> str:
    prompt = trace.params.get("agentlens_prompt") if trace else None
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return session.original_instruction.strip() or "AgentLens session"


def _family_for(trace: TraceEvent | None, gate: Gate | None) -> str:
    tool = trace.tool_name if trace else "gate"
    if tool == "fs.write":
        return "edit"
    if tool == "fs.delete":
        return "delete"
    if tool in {"fs.read", "git.status", "run_tests"}:
        return "inspect"
    if tool == "shell.run":
        return "inspect" if _shell_reads(trace) else "command"
    if gate and gate.risk_assessment.affected_files:
        return "file_action"
    return tool.replace(".", "_")


def _kind_for(trace: TraceEvent | None, gate: Gate | None, family: str) -> str:
    if gate is None:
        return "observation_batch"
    if gate.status == GateStatus.AUTO_EXECUTED and family == "inspect":
        return "inspection_batch"
    if gate.status == GateStatus.AUTO_EXECUTED and gate.risk_assessment.risk_level == RiskLevel.LOW:
        return "observation_batch"
    if trace and trace.provider_metadata.get("passive") is True:
        return "observation_batch"
    return "decision"


def _descriptor_for_group(group: list[EpisodeRecord], primary_gate: Gate | None) -> ActionDescriptor:
    first = group[0]
    target = first.target
    raw_detail = _raw_detail_for_group(group)
    technical_detail = _technical_detail_for_group(group)
    action = _plain_action(first.family, target, first.kind)
    title = _title_for(first.family, target, first.kind)
    evidence = _evidence_summary(group, primary_gate)
    return ActionDescriptor(
        human_title=title,
        plain_action=action,
        target_label=target,
        technical_detail=technical_detail,
        raw_detail=raw_detail,
        evidence_summary=evidence,
    )


def _plain_action(family: str, target: str, kind: str) -> str:
    if kind == "inspection_batch":
        return f"gathering context from {target}"
    if family == "edit":
        return f"editing {target}"
    if family == "delete":
        return f"deleting {target}"
    if family == "inspect":
        return f"inspecting {target}"
    if family == "command":
        return f"running a command that touches {target}"
    return f"working on {target}"


def _title_for(family: str, target: str, kind: str) -> str:
    if kind == "inspection_batch":
        return f"Inspected {target}"
    if kind == "observation_batch":
        return f"Observed activity on {target}"
    if family == "edit":
        return f"Edit {target}"
    if family == "delete":
        return f"Delete {target}"
    if family == "inspect":
        return f"Inspect {target}"
    if family == "command":
        return f"Command touching {target}"
    return f"Action on {target}"


def _summary_for_group(
    group: list[EpisodeRecord],
    descriptor: ActionDescriptor,
    primary_gate: Gate | None,
) -> str:
    trace_count = sum(1 for record in group if record.trace is not None)
    gate_count = sum(1 for record in group if record.gate is not None)
    if group[0].kind == "inspection_batch":
        return (
            f"Codex gathered context from {descriptor.target_label}; "
            f"{trace_count} read-only event{'s' if trace_count != 1 else ''} collapsed."
        )
    if group[0].kind == "observation_batch":
        return (
            f"AgentLens observed {trace_count or gate_count} already-executed event"
            f"{'' if (trace_count or gate_count) == 1 else 's'} involving {descriptor.target_label}."
        )
    if primary_gate and primary_gate.intelligence_card:
        card_summary = _clean_sentence(primary_gate.intelligence_card.summary)
        if card_summary and "agent wants to run" not in card_summary.lower():
            return card_summary
    status = primary_gate.status if primary_gate else GateStatus.PENDING
    risk = primary_gate.risk_assessment.risk_level if primary_gate else RiskLevel.LOW
    return (
        f"Codex is {descriptor.plain_action}. AgentLens grouped {trace_count} trace"
        f"{'' if trace_count == 1 else 's'} and {gate_count} gate"
        f"{'' if gate_count == 1 else 's'}; the primary decision is {status} with {risk} risk."
    )


def _evidence_summary(group: list[EpisodeRecord], primary_gate: Gate | None) -> str:
    if primary_gate and primary_gate.risk_assessment.evidence:
        return "; ".join(primary_gate.risk_assessment.evidence[:3])
    reasons = [
        record.trace.stated_reason
        for record in group
        if record.trace is not None and record.trace.stated_reason
    ]
    if reasons:
        return _clean_sentence(reasons[0])
    return "No specific evidence recorded beyond the captured tool metadata."


def _technical_detail_for_group(group: list[EpisodeRecord]) -> str | None:
    tools = sorted({record.trace.tool_name for record in group if record.trace is not None})
    return ", ".join(tools) if tools else None


def _raw_detail_for_group(group: list[EpisodeRecord]) -> str | None:
    commands = [
        str(record.trace.params.get("command") or record.trace.params.get("cmd"))
        for record in group
        if record.trace is not None
        and (record.trace.params.get("command") or record.trace.params.get("cmd"))
    ]
    if commands:
        return commands[0]
    paths = [
        str(record.trace.params.get("path"))
        for record in group
        if record.trace is not None and record.trace.params.get("path")
    ]
    return paths[0] if paths else None


def _target_for(prompt: str, trace: TraceEvent | None, gate: Gate | None) -> str:
    candidates: list[str] = []
    if gate:
        candidates.extend(gate.risk_assessment.affected_files)
    if trace:
        params = trace.params
        paths = params.get("paths")
        if isinstance(paths, list):
            candidates.extend(str(path) for path in paths)
        for key in ("path", "file", "target", "grant_root"):
            value = params.get(key)
            if isinstance(value, str):
                candidates.append(value)
        hints = params.get("target_hints")
        if isinstance(hints, list):
            candidates.extend(str(item) for item in hints)
        command = params.get("command") or params.get("cmd")
        if isinstance(command, str):
            candidates.extend(_targets_from_text(command))
    candidates.extend(_targets_from_text(prompt))
    for candidate in candidates:
        target = _clean_target(candidate)
        if target:
            return target
    if trace and trace.tool_name == "shell.run":
        return "shell command"
    return "external state"


def _targets_from_text(value: str) -> list[str]:
    return [match.strip("`'\".,:;()[]{}<>") for match in TARGET_HINT_RE.findall(value)]


def _clean_target(value: str) -> str | None:
    text = value.strip().strip("'\"")
    if not text or text in {".", "external state"}:
        return None
    if text.startswith((">", "2>", "1>", "&>")) or text in {"/dev/null", "2>/dev/null"}:
        return None
    if text.startswith("-") or "://" in text:
        return None
    if text.endswith("/dev/null") or ">/dev/null" in text:
        return None
    path = Path(text)
    if path.is_absolute():
        parts = list(path.parts)
        if len(parts) > 1:
            return "/".join(parts[-3:])
    return text


def _shell_reads(trace: TraceEvent | None) -> bool:
    if trace is None:
        return False
    command = str(trace.params.get("command") or trace.params.get("cmd") or "")
    command = _strip_redirections(command)
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if len(tokens) >= 3 and Path(tokens[0]).name in {"bash", "sh", "zsh"} and tokens[1] == "-lc":
        try:
            tokens = shlex.split(_strip_redirections(tokens[2]))
        except ValueError:
            return False
    if not tokens:
        return False
    executable = Path(tokens[0]).name
    return executable in READ_COMMANDS


def _strip_redirections(command: str) -> str:
    return re.sub(r"(?:^|\s)(?:\d?>|&>)\s*\S+", " ", command).strip()


def _clean_sentence(value: str | None) -> str:
    if not value:
        return ""
    cleaned = " ".join(value.split())
    return cleaned if not cleaned or cleaned[-1] in ".!?" else f"{cleaned}."
