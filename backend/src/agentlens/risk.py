from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

from agentlens.schemas import (
    BlastRadius,
    PolicyAction,
    Reversibility,
    RiskAssessment,
    RiskLevel,
    ToolCallProposal,
)


class DependencyGraph:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)
        self.importers: dict[str, set[str]] = {}
        self._build_python_import_graph()
        self._build_javascript_import_graph()

    def dependents_for_path(self, path: str) -> set[str]:
        target = Path(path)
        stem = target.stem
        normalized = path.replace("/", ".").removesuffix(".py").strip(".")
        dependents: set[str] = set()
        for imported_name, files in self.importers.items():
            if imported_name == stem or imported_name.endswith(f".{stem}") or imported_name in normalized:
                dependents.update(files)
        return dependents

    def _build_python_import_graph(self) -> None:
        if not self.repo_path.exists():
            return
        for file_path in self.repo_path.rglob("*.py"):
            if any(part.startswith(".") or part == "__pycache__" for part in file_path.parts):
                continue
            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            rel = str(file_path.relative_to(self.repo_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.importers.setdefault(alias.name, set()).add(rel)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.importers.setdefault(node.module, set()).add(rel)

    def _build_javascript_import_graph(self) -> None:
        if not self.repo_path.exists():
            return
        patterns = ("*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs", "*.cjs")
        import_pattern = re.compile(
            r"(?:import\s+(?:[^'\"]+\s+from\s+)?|require\()\s*['\"]([^'\"]+)['\"]"
        )
        for pattern in patterns:
            for file_path in self.repo_path.rglob(pattern):
                if any(part in {"node_modules", ".next", "dist", "build"} for part in file_path.parts):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                rel = str(file_path.relative_to(self.repo_path))
                for match in import_pattern.finditer(text):
                    imported = match.group(1)
                    self.importers.setdefault(imported, set()).add(rel)
                    self.importers.setdefault(Path(imported).stem, set()).add(rel)


class SemanticRiskClassifier:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)
        self.graph = DependencyGraph(repo_path)

    def assess(self, proposal: ToolCallProposal) -> RiskAssessment:
        reversibility = self._reversibility(proposal)
        affected_files = self._affected_files(proposal)
        blast_radius, evidence = self._blast_radius(proposal, affected_files)
        risk_level = self._risk_level(reversibility, blast_radius)
        return RiskAssessment(
            proposal_id=proposal.id,
            reversibility=reversibility,
            blast_radius=blast_radius,
            risk_level=risk_level,
            recommended_action=self._recommended_action(reversibility, blast_radius),
            evidence=evidence,
            affected_files=affected_files,
        )

    def _reversibility(self, proposal: ToolCallProposal) -> Reversibility:
        tool = proposal.tool_name
        params = {key: str(value).lower() for key, value in proposal.params.items()}
        joined = " ".join(params.values())

        if tool in {"fs.read", "git.status", "run_tests"}:
            return Reversibility.LOW
        if tool == "shell.run" and self._is_read_only_shell_command(proposal.params):
            return Reversibility.LOW
        if tool == "fs.delete":
            return Reversibility.HIGH
        if tool == "db.query" and any(term in joined for term in ["drop table", "truncate", "delete from"]):
            return Reversibility.HIGH
        if tool in {"api.call", "shell.run"} and any(
            term in joined for term in ["curl", "webhook", "deploy", "push", "rm -rf"]
        ):
            return Reversibility.HIGH
        return Reversibility.MEDIUM

    def _affected_files(self, proposal: ToolCallProposal) -> list[str]:
        path = proposal.params.get("path")
        paths = [str(path)] if path else []
        if proposal.tool_name == "shell.run":
            paths.extend(self._paths_from_shell_command(proposal.params))
        return sorted(set(paths))

    def _blast_radius(
        self, proposal: ToolCallProposal, affected_files: list[str]
    ) -> tuple[BlastRadius, list[str]]:
        evidence: list[str] = []
        joined = " ".join(str(value).lower() for value in proposal.params.values())

        if any(fragment in joined for fragment in ["/prod", "/migrations", "drop table", "deploy"]):
            evidence.append("action touches production, migrations, deployment, or destructive DB terms")
            return BlastRadius.HIGH, evidence

        dependent_count = 0
        for path in affected_files:
            dependents = self.graph.dependents_for_path(path)
            dependent_count += len(dependents)
            if dependents:
                evidence.append(f"{path} is referenced by {len(dependents)} code file(s)")
            config_refs = self._config_references(path)
            if config_refs:
                evidence.append(f"{path} is referenced by config/docs: {', '.join(config_refs[:4])}")

        if dependent_count >= 5:
            return BlastRadius.HIGH, evidence
        if dependent_count >= 1:
            return BlastRadius.MEDIUM, evidence

        if proposal.tool_name in {"api.call", "db.query"}:
            evidence.append("external API or database action can affect state outside this repo")
            return BlastRadius.MEDIUM, evidence

        if proposal.tool_name == "shell.run":
            if self._is_read_only_shell_command(proposal.params):
                evidence.append("shell command appears read-only")
                return BlastRadius.LOW, evidence
            shell_evidence = self._shell_evidence(proposal.params)
            evidence.extend(shell_evidence)
            if shell_evidence:
                return BlastRadius.MEDIUM, evidence

        evidence.append("no broad dependency or external-state evidence found")
        return BlastRadius.LOW, evidence

    def dependency_evidence_for_paths(self, paths: list[str]) -> dict[str, dict[str, object]]:
        evidence: dict[str, dict[str, object]] = {}
        for path in paths:
            normalized = str(path)
            full_path = self.repo_path / normalized
            refs = sorted(self.graph.dependents_for_path(normalized))
            config_refs = self._config_references(normalized)
            summary_parts = []
            if refs:
                summary_parts.append(f"{len(refs)} code reference(s)")
            if config_refs:
                summary_parts.append(f"{len(config_refs)} config/doc reference(s)")
            if not summary_parts:
                summary_parts.append("no references found")
            evidence[normalized] = {
                "referenced_by": refs,
                "config_references": config_refs,
                "exists": full_path.exists(),
                "summary": ", ".join(summary_parts),
            }
        return evidence

    def _risk_level(self, reversibility: Reversibility, blast_radius: BlastRadius) -> RiskLevel:
        if reversibility == Reversibility.HIGH and blast_radius == BlastRadius.HIGH:
            return RiskLevel.CRITICAL
        if reversibility == Reversibility.HIGH or blast_radius == BlastRadius.HIGH:
            return RiskLevel.HIGH
        if reversibility == Reversibility.MEDIUM or blast_radius == BlastRadius.MEDIUM:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _recommended_action(
        self, reversibility: Reversibility, blast_radius: BlastRadius
    ) -> PolicyAction:
        if reversibility == Reversibility.LOW and blast_radius == BlastRadius.LOW:
            return PolicyAction.AUTO_EXECUTE
        if reversibility == Reversibility.HIGH and blast_radius == BlastRadius.HIGH:
            return PolicyAction.BLOCK_AND_ALERT
        return PolicyAction.REQUIRE_APPROVAL

    def _is_read_only_shell_command(self, params: dict) -> bool:
        command = str(params.get("command") or params.get("cmd") or "").strip()
        if not command:
            return False

        lowered = command.lower()
        write_markers = [
            ">",
            ">>",
            " tee ",
            " rm ",
            " rm -",
            " mv ",
            " cp ",
            " touch ",
            " mkdir ",
            " rmdir ",
            " chmod ",
            " chown ",
            " apply_patch",
            " git add",
            " git commit",
            " git push",
            " npm install",
            " uv sync",
            " pip install",
            " curl ",
            " wget ",
        ]
        padded = f" {lowered} "
        if any(marker in padded for marker in write_markers):
            return False

        inner = self._extract_shell_inner_command(command)
        command_words = [
            part
            for part in re.split(r"\s*(?:&&|\|\||\||;)\s*", inner)
            if part.strip()
        ]
        if not command_words:
            return False

        read_only = {
            "cat",
            "find",
            "git",
            "head",
            "ls",
            "nl",
            "pwd",
            "rg",
            "sed",
            "sort",
            "tail",
            "wc",
        }
        for part in command_words:
            try:
                tokens = shlex.split(part)
            except ValueError:
                return False
            if not tokens:
                return False
            executable = Path(tokens[0]).name
            if executable not in read_only:
                return False
            if executable == "git" and len(tokens) > 1:
                if tokens[1] not in {"diff", "log", "rev-parse", "show", "status"}:
                    return False
        return True

    def _extract_shell_inner_command(self, command: str) -> str:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return command
        if len(tokens) >= 3 and Path(tokens[0]).name in {"bash", "sh", "zsh"} and tokens[1] == "-lc":
            return tokens[2]
        return command

    def _paths_from_shell_command(self, params: dict) -> list[str]:
        command = self._extract_shell_inner_command(str(params.get("command") or params.get("cmd") or ""))
        try:
            tokens = shlex.split(command)
        except ValueError:
            return []
        candidates: list[str] = []
        path_flags = {"-f", "--file", "-o", "--output"}
        for index, token in enumerate(tokens):
            if token in path_flags and index + 1 < len(tokens):
                candidates.append(tokens[index + 1])
            elif "/" in token or token.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yaml", ".yml")):
                if not token.startswith("-") and "://" not in token and "#" not in token:
                    candidates.append(token.strip("'\""))
        return [item for item in candidates if item not in {"&&", "||", "|", ";"}]

    def _config_references(self, path: str) -> list[str]:
        if not self.repo_path.exists() or not path:
            return []
        needle = path.lower()
        stem = Path(path).name.lower()
        references: list[str] = []
        config_names = {
            "package.json",
            "pyproject.toml",
            "render.yaml",
            "Dockerfile",
            "README.md",
            ".env.example",
            "agentlens.config.yaml",
        }
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file() or any(part in {"node_modules", ".git", ".next"} for part in file_path.parts):
                continue
            if file_path.name not in config_names and file_path.suffix.lower() not in {".md", ".yaml", ".yml", ".toml", ".json"}:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if needle in text or (stem and stem in text):
                references.append(str(file_path.relative_to(self.repo_path)))
        return sorted(set(references))

    def _shell_evidence(self, params: dict) -> list[str]:
        command = str(params.get("command") or params.get("cmd") or "").lower()
        evidence: list[str] = []
        checks = [
            ("rm", "shell command may delete files"),
            ("mv", "shell command may move files"),
            ("cp", "shell command may copy files"),
            ("touch", "shell command may create files"),
            ("mkdir", "shell command may create directories"),
            ("git add", "shell command mutates git index"),
            ("git commit", "shell command creates a commit"),
            ("git push", "shell command mutates remote repository state"),
            ("npm install", "shell command changes dependencies"),
            ("pip install", "shell command changes dependencies"),
            ("uv sync", "shell command changes dependencies/environment"),
            ("curl", "shell command may call external network"),
            ("deploy", "shell command may deploy externally"),
        ]
        for marker, message in checks:
            if marker in command:
                evidence.append(message)
        if ">" in command or ">>" in command:
            evidence.append("shell command redirects output to a file")
        return evidence
