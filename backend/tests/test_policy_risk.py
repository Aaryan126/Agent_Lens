from pathlib import Path

from agentlens.config import AgentLensConfig, PolicyRule
from agentlens.policy import PolicyEngine
from agentlens.risk import SemanticRiskClassifier
from agentlens.schemas import PolicyAction, RiskLevel, ToolCallProposal


def test_safe_read_is_low_risk(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.read",
        params={"path": "README.md"},
        confidence=0.9,
    )
    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)
    assert risk.risk_level == RiskLevel.LOW
    assert risk.recommended_action == PolicyAction.AUTO_EXECUTE


def test_migration_delete_is_high_or_critical(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.delete",
        params={"path": "backend/migrations/001_sessions.py"},
        confidence=0.58,
    )
    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)
    assert risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert risk.recommended_action in {PolicyAction.REQUIRE_APPROVAL, PolicyAction.BLOCK_AND_ALERT}


def test_read_only_shell_command_is_low_risk(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="shell.run",
        params={"command": '/bin/zsh -lc "pwd && rg --files | sed s#/.*## | sort -u"'},
        confidence=0.8,
    )

    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)

    assert risk.risk_level == RiskLevel.LOW
    assert risk.recommended_action == PolicyAction.AUTO_EXECUTE


def test_destructive_shell_command_is_high_risk(tmp_path: Path) -> None:
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="shell.run",
        params={"command": "rm -rf backend/migrations"},
        confidence=0.8,
    )

    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)

    assert risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}


def test_javascript_imports_raise_blast_radius(tmp_path: Path) -> None:
    source = tmp_path / "frontend" / "app"
    source.mkdir(parents=True)
    (source / "page.tsx").write_text("import { helper } from '../lib/session';\n", encoding="utf-8")
    target = tmp_path / "frontend" / "lib"
    target.mkdir(parents=True)
    (target / "session.ts").write_text("export const helper = 1;\n", encoding="utf-8")
    proposal = ToolCallProposal(
        session_id="ses_test",
        tool_name="fs.write",
        params={"path": "frontend/lib/session.ts"},
    )

    risk = SemanticRiskClassifier(str(tmp_path)).assess(proposal)

    assert risk.risk_level == RiskLevel.MEDIUM
    assert any("code file" in item for item in risk.evidence)


def test_dependency_evidence_includes_config_references(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("See backend/src/agentlens/session.py\n", encoding="utf-8")
    classifier = SemanticRiskClassifier(str(tmp_path))

    evidence = classifier.dependency_evidence_for_paths(["backend/src/agentlens/session.py"])

    assert evidence["backend/src/agentlens/session.py"]["config_references"] == ["README.md"]


def test_policy_precedence_over_risk() -> None:
    config = AgentLensConfig(
        policies=[
            PolicyRule(
                name="safe reads",
                condition={"tool_in": ["fs.read"]},
                action=PolicyAction.AUTO_EXECUTE,
            )
        ]
    )
    proposal = ToolCallProposal(session_id="ses_test", tool_name="fs.read", params={})
    decision = PolicyEngine(config).evaluate(proposal)
    assert decision.action == PolicyAction.AUTO_EXECUTE
    assert decision.matched_policy == "safe reads"
