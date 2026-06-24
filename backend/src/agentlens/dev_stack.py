from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass(frozen=True)
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]


class DevStack:
    def __init__(
        self,
        *,
        repo: Path,
        project_root: Path,
        api_host: str,
        api_port: int,
        frontend_port: int,
        proxy_port: int,
        upstream_port: int,
        codex_binary: str,
        launch_codex: bool,
        open_dashboard: bool,
    ) -> None:
        self.repo = repo
        self.project_root = project_root
        self.backend_dir = project_root / "backend"
        self.frontend_dir = project_root / "frontend"
        self.api_host = api_host
        self.api_port = api_port
        self.frontend_port = frontend_port
        self.proxy_port = proxy_port
        self.upstream_port = upstream_port
        self.codex_binary = codex_binary
        self.launch_codex = launch_codex
        self.open_dashboard = open_dashboard
        self.children: list[ManagedProcess] = []

    @property
    def api_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.frontend_port}"

    @property
    def proxy_url(self) -> str:
        return f"ws://127.0.0.1:{self.proxy_port}"

    def codex_command(self) -> list[str]:
        return [
            self.codex_binary,
            "--ask-for-approval",
            "untrusted",
            "--sandbox",
            "workspace-write",
            "--remote",
            self.proxy_url,
        ]

    def run(self) -> None:
        self._validate_paths()
        self._start_guard()
        self._wait_for_http(f"{self.api_url}/health", "AgentLens API")
        self._start_frontend()
        self._wait_for_http(self.frontend_url, "AgentLens frontend")
        self._start_proxy()
        self._wait_for_port(f"http://127.0.0.1:{self.proxy_port}", "AgentLens Codex proxy")
        self._print_ready()
        if self.open_dashboard:
            webbrowser.open(self.frontend_url)
        if self.launch_codex:
            self._run_codex()
        else:
            self._wait_forever()

    def stop(self) -> None:
        for child in reversed(self.children):
            if child.process.poll() is not None:
                continue
            print(f"Stopping {child.name}...")
            child.process.terminate()
        deadline = time.monotonic() + 8
        for child in reversed(self.children):
            remaining = max(0.1, deadline - time.monotonic())
            try:
                child.process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                print(f"Killing {child.name}...")
                child.process.kill()
        self.children.clear()

    def _validate_paths(self) -> None:
        if not self.backend_dir.exists():
            raise SystemExit(f"Backend directory not found: {self.backend_dir}")
        if not self.frontend_dir.exists():
            raise SystemExit(f"Frontend directory not found: {self.frontend_dir}")
        if not self.repo.exists():
            raise SystemExit(f"Repo path not found: {self.repo}")

    def _start_guard(self) -> None:
        env = os.environ.copy()
        env.setdefault("AGENTLENS_STORAGE_BACKEND", "local_jsonl")
        env["AGENTLENS_PROJECT_ROOT"] = str(self.repo)
        env.setdefault("AGENTLENS_AUDIT_LOG_PATH", "local_data/agentlens_audit.jsonl")
        env["AGENTLENS_CORS_ORIGINS"] = ",".join(
            [
                self.frontend_url,
                f"http://127.0.0.1:{self.frontend_port}",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        )
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agentlens.api:app",
            "--host",
            self.api_host,
            "--port",
            str(self.api_port),
        ]
        self._spawn("local guard", command, cwd=self.backend_dir, env=env)

    def _start_frontend(self) -> None:
        env = os.environ.copy()
        env["NEXT_PUBLIC_AGENTLENS_API_URL"] = self.api_url
        env["AGENTLENS_DISABLE_HOOKS"] = "1"
        command = ["npm", "run", "dev", "--", "--port", str(self.frontend_port)]
        self._spawn("frontend", command, cwd=self.frontend_dir, env=env)

    def _start_proxy(self) -> None:
        command = [
            sys.executable,
            "-m",
            "agentlens.codex_proxy",
            "--repo",
            str(self.repo),
            "--api-url",
            self.api_url,
            "--dashboard-url",
            self.frontend_url,
            "--proxy-port",
            str(self.proxy_port),
            "--upstream-port",
            str(self.upstream_port),
            "--codex-binary",
            self.codex_binary,
        ]
        env = os.environ.copy()
        env["AGENTLENS_DISABLE_HOOKS"] = "1"
        self._spawn("codex proxy", command, cwd=self.backend_dir, env=env)

    def _spawn(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> None:
        print(f"Starting {name}...")
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.children.append(ManagedProcess(name=name, process=process))

    def _wait_for_http(self, url: str, name: str) -> None:
        deadline = time.monotonic() + 30
        with httpx.Client(timeout=2) as client:
            while time.monotonic() < deadline:
                self._raise_if_child_failed()
                try:
                    response = client.get(url)
                    if response.status_code < 500:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
        raise RuntimeError(f"Timed out waiting for {name} at {url}")

    def _wait_for_port(self, url: str, name: str) -> None:
        host, port_text = url.removeprefix("http://").split(":", 1)
        port = int(port_text)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            self._raise_if_child_failed()
            try:
                with socket.create_connection((host, port), timeout=1):
                    return
            except OSError:
                time.sleep(0.25)
        raise RuntimeError(f"Timed out waiting for {name} at {url}")

    def _raise_if_child_failed(self) -> None:
        for child in self.children:
            code = child.process.poll()
            if code is not None:
                raise RuntimeError(f"{child.name} exited early with code {code}")

    def _print_ready(self) -> None:
        command = " ".join(["AGENTLENS_DISABLE_HOOKS=1", *self.codex_command()])
        print()
        print("AgentLens local stack is ready.")
        print(f"Dashboard: {self.frontend_url}")
        print(f"API:       {self.api_url}")
        print(f"Proxy:     {self.proxy_url}")
        print()
        print("Codex command:")
        print(f"  {command}")
        print()

    def _run_codex(self) -> None:
        env = os.environ.copy()
        env["AGENTLENS_DISABLE_HOOKS"] = "1"
        print("Launching Codex TUI. Press Ctrl+C to stop Codex and AgentLens.")
        result = subprocess.run(self.codex_command(), cwd=self.repo, env=env, check=False)
        if result.returncode != 0:
            print()
            print(f"Codex exited with code {result.returncode}. AgentLens services are still running.")
            print("Reconnect Codex with:")
            print(f"  {' '.join(['AGENTLENS_DISABLE_HOOKS=1', *self.codex_command()])}")
            print("Press Ctrl+C here to stop the AgentLens stack.")
            self._wait_forever()

    def _wait_forever(self) -> None:
        print("Stack is running. Press Ctrl+C to stop.")
        while True:
            self._raise_if_child_failed()
            time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the local AgentLens guard, frontend, Codex proxy, and optional Codex TUI."
    )
    parser.add_argument("--repo", default=".", help="Repository path to supervise.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="AgentLens project root containing backend/ and frontend/.",
    )
    parser.add_argument("--api-host", default="127.0.0.1", help="Local guard API host.")
    parser.add_argument("--api-port", type=int, default=8787, help="Local guard API port.")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Next.js frontend port.")
    parser.add_argument("--proxy-port", type=int, default=8791, help="Codex proxy port.")
    parser.add_argument("--upstream-port", type=int, default=8792, help="Codex app-server port.")
    parser.add_argument("--codex-binary", default="codex", help="Codex binary path.")
    parser.add_argument(
        "--no-codex",
        action="store_true",
        help="Start guard/frontend/proxy only and print the Codex command.",
    )
    parser.add_argument(
        "--open-dashboard",
        action="store_true",
        help="Open the AgentLens dashboard in the default browser after services are ready.",
    )
    args = parser.parse_args()

    stack = DevStack(
        repo=Path(args.repo).expanduser().resolve(),
        project_root=Path(args.project_root).expanduser().resolve(),
        api_host=args.api_host,
        api_port=args.api_port,
        frontend_port=args.frontend_port,
        proxy_port=args.proxy_port,
        upstream_port=args.upstream_port,
        codex_binary=args.codex_binary,
        launch_codex=not args.no_codex,
        open_dashboard=args.open_dashboard,
    )

    def handle_signal(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_signal)
    try:
        stack.run()
    except KeyboardInterrupt:
        print("\nStopping AgentLens local stack...")
    finally:
        stack.stop()


if __name__ == "__main__":
    main()
