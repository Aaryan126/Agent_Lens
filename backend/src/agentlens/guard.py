from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AgentLens as a local-first guard for Codex sessions."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Local API host.")
    parser.add_argument("--port", type=int, default=8787, help="Local API port.")
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository path used for local risk/dependency analysis.",
    )
    parser.add_argument(
        "--audit-log",
        default="local_data/agentlens_audit.jsonl",
        help="Local JSONL audit log path.",
    )
    parser.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        help="Allowed dashboard origin. Can be passed multiple times.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        *args.cors_origin,
    ]
    os.environ.setdefault("AGENTLENS_STORAGE_BACKEND", "local_jsonl")
    os.environ.setdefault("AGENTLENS_PROJECT_ROOT", str(repo))
    os.environ.setdefault("AGENTLENS_AUDIT_LOG_PATH", args.audit_log)
    os.environ.setdefault("AGENTLENS_CORS_ORIGINS", ",".join(origins))

    local_api = f"http://{args.host}:{args.port}"
    print("AgentLens local guard is starting.")
    print(f"Repo: {repo}")
    print(f"API:  {local_api}")
    print(f"History: {Path(args.audit_log).expanduser().resolve()}")
    print("Dashboard:")
    print("  # from the Agent_Lens project root")
    print("  cd frontend")
    print(f"  NEXT_PUBLIC_AGENTLENS_API_URL={local_api} npm run dev")
    print("Then open http://localhost:3000 and use Start Supervision.")

    uvicorn.run("agentlens.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
