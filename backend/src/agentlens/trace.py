from __future__ import annotations

import subprocess
from pathlib import Path

from agentlens.schemas import GitSnapshot, ToolCallProposal, TraceEvent

MAX_GIT_SNAPSHOT_CHARS = 12_000


class TraceEngine:
    def capture(self, proposal: ToolCallProposal, repo_path: str) -> TraceEvent:
        return TraceEvent(
            session_id=proposal.session_id,
            proposal_id=proposal.id,
            tool_name=proposal.tool_name,
            params=proposal.params,
            stated_reason=proposal.stated_reason,
            git_snapshot=self._git_snapshot(repo_path),
        )

    def _git_snapshot(self, repo_path: str) -> GitSnapshot:
        path = Path(repo_path)
        if not path.exists():
            return GitSnapshot(available=False, error=f"repo path does not exist: {repo_path}")

        try:
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            diff = subprocess.run(
                ["git", "diff", "--", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            return GitSnapshot(available=False, error=str(exc))

        if status.returncode != 0:
            return GitSnapshot(available=False, error=status.stderr.strip() or "git unavailable")

        return GitSnapshot(
            status_short=self._truncate(status.stdout),
            diff=self._truncate(diff.stdout),
        )

    def _truncate(self, value: str) -> str:
        if len(value) <= MAX_GIT_SNAPSHOT_CHARS:
            return value
        return f"{value[:MAX_GIT_SNAPSHOT_CHARS]}\n...[truncated]"
