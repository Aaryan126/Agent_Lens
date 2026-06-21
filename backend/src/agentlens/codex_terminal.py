from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from agentlens.adapters.codex_cli import CodexCliAdapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Codex from the terminal and mirror tool-call proposals into AgentLens."
    )
    parser.add_argument("prompt", nargs="*", help="Codex task. If omitted, prompts interactively.")
    parser.add_argument("--repo", default=".", help="Repository path for Codex and AgentLens.")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8787",
        help="AgentLens API URL. Defaults to the local guard.",
    )
    parser.add_argument("--session-id", default=None, help="Existing AgentLens session ID.")
    parser.add_argument("--model", default=None, help="Optional Codex model.")
    parser.add_argument(
        "--sandbox",
        default="read-only",
        choices=["read-only", "workspace-write"],
        help="Codex sandbox mode.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="Codex timeout in seconds.")
    parser.add_argument(
        "--show-json",
        action="store_true",
        help="Print raw Codex JSONL after the readable terminal summary.",
    )
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip() or input("Codex task> ").strip()
    if not prompt:
        raise SystemExit("No Codex task provided.")

    api_url = args.api_url.rstrip("/")
    repo = str(Path(args.repo).expanduser().resolve())
    session_id = args.session_id or _create_session(api_url, prompt, repo)

    print(f"AgentLens session: {session_id}")
    print(f"Dashboard API:     {api_url}")
    print("Running Codex locally...\n")

    result = CodexCliAdapter().run(
        prompt=prompt,
        session_id=session_id,
        cwd=repo,
        model=args.model,
        sandbox=args.sandbox,
        timeout_seconds=args.timeout,
    )

    _print_readable_codex_output(result.stdout)
    if result.stderr:
        print("\nCodex stderr:")
        print(result.stderr.strip())
    if args.show_json and result.stdout:
        print("\nRaw Codex JSONL:")
        print(result.stdout.strip())

    if not result.proposals:
        print("\nNo tool-call proposals were emitted by Codex.")
        raise SystemExit(result.returncode)

    print("\nMirroring proposals into AgentLens:")
    with httpx.Client(timeout=180) as client:
        for proposal in result.proposals:
            response = client.post(
                f"{api_url}/sessions/{session_id}/tool-calls",
                json=proposal.model_dump(mode="json"),
            )
            response.raise_for_status()
            gate = response.json()
            print(f"- {proposal.tool_name}: {gate['status']} ({gate['id']})")

    raise SystemExit(result.returncode)


def _create_session(api_url: str, prompt: str, repo: str) -> str:
    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{api_url}/sessions",
            json={"original_instruction": prompt, "repo_path": repo},
        )
        response.raise_for_status()
        return str(response.json()["id"])


def _print_readable_codex_output(stdout: str) -> None:
    lines = [line for line in stdout.splitlines() if line.strip()]
    printed = False
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = _event_text(event)
        if text:
            printed = True
            print(text)
    if not printed:
        print("Codex completed. No readable message events were emitted.")


def _event_text(event: dict[str, Any]) -> str | None:
    event_type = str(event.get("type") or event.get("event") or "")
    if event_type in {"message", "response.output_text.delta", "response.completed"}:
        content = event.get("content") or event.get("text") or event.get("message")
        if isinstance(content, str) and content.strip():
            return content.strip()

    item = event.get("item")
    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if event_type == "item.started" and item_type == "command_execution":
        command = item.get("command")
        return f"$ {command}" if command else None

    if event_type == "item.completed" and item_type == "command_execution":
        output = str(item.get("aggregated_output") or "").strip()
        if output:
            return output[-2000:]

    if item_type in {"message", "assistant_message"}:
        content = item.get("content") or item.get("text")
        if isinstance(content, str) and content.strip():
            return content.strip()

    return None


if __name__ == "__main__":
    main()
