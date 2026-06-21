# AgentLens Agent Instructions

## Project Objective

AgentLens is a judgment layer for AI coding agents. It intercepts proposed tool calls, captures trace context, evaluates semantic risk, asks for human approval when needed, and records an auditable session ledger.

The core product value is the intelligence layer: semantic risk, counterfactual trajectory, goal drift, calibrated confidence, and concise translation.

## Working Rules

- Read `prd.md`, `plan.md`, and `implementation.md` before making non-trivial changes.
- Prefer the existing architecture and schemas over adding parallel abstractions.
- Keep changes phase-aligned. Do not jump to Slack, Codex, or ledger polish before the local end-to-end path remains healthy.
- Treat tests as part of the feature. Add or update tests for changed behavior.
- Use real OpenAI integration tests for intelligence behavior when `OPENAI_API_KEY` is configured.
- Keep pure unit tests independent of external APIs.
- Never commit `.env`, local databases, caches, logs, or generated test artifacts.

## Documentation Contract

After meaningful code changes:

- Update `implementation.md` with what changed, current status, and known gaps.
- Update `plan.md` when phase status, scope, or validation criteria change.
- Update `README.md` when setup, commands, environment variables, architecture, or public behavior changes.

## Coding Practices

- Use typed Python and Pydantic schemas for public boundaries.
- Keep side effects behind narrow interfaces.
- Make risky behavior explicit through enums and structured results.
- Keep policy evaluation deterministic and testable.
- Keep LLM calls behind typed ports so they can be tested and replaced.
- Do not store or render hidden chain-of-thought. Store visible rationale, tool metadata, summaries, and code evidence.

