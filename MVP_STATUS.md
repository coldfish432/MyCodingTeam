# My Coding Team MVP Status

Date: 2026-05-27

## Summary

Phase 0 through Phase 7 MVP is implemented. The project can start from the CLI,
route a request, return a direct-answer delivery package, inspect a workspace,
build a single-task contract, apply allowed-file changes, run contract
verification commands, review the result, and return a `DeliveryPackage`.

Runtime defaults to the OpenAI-compatible settings in `.env`:

- Model provider: openai_compatible
- Model: deepseek-v4-flash
- Base URL: https://api.deepseek.com
- API key: configured, not printed

## Completed Scope

- Phase 0: package skeleton, CLI, config, doctor, local dependencies.
- Phase 0.5: AgentScope v2 POC suite and documented findings.
- Phase 1: Pydantic schemas for workflow, tasks, review, and delivery.
- Phase 2: AgentScope adapter and permission builder, including read-only
  probe allow/deny rules and task contract permission rules.
- Phase 3: prompt loader, mock model, OpenAI-compatible model client, factory,
  and runtime helper utilities.
- Phase 4: intake routing and direct-answer workflow.
- Phase 5: PM orchestrator, budget guard, state-transition validation, and
  delivery construction.
- Phase 6: workspace inspection and read-only context scout.
- Phase 7: single-task planning, task implementation, QA verification,
  ReviewRoom, task runner, and lightweight workflow.

## Validation

Full test suite:

```text
python -m pytest
66 passed in 11.35s
```

CLI smoke:

```text
python -m my_coding_team --help
```

Result: passed. The CLI exposes `doctor`, `config`, and `run`.

Real LLM direct-answer smoke:

```text
python -m my_coding_team run "用一句话说明这个MVP的作用" --mode direct --budget 3
```

Result: passed. The command returned a successful `DeliveryPackage`.

Real LLM lightweight smoke:

```text
python -m my_coding_team run "把 README.md 改成一句话：MVP smoke passed" --mode lightweight --workspace <temp-git-repo> --budget 5
```

Result: passed. The workflow changed only `README.md`, normalized model output
to the safe verification command `python -m pytest`, ran verification, and
returned a successful `DeliveryPackage`.

Real LLM negative permission smoke:

```text
python tests/smoke/negative_real_llm_smoke.py
```

Result: passed. The smoke forced an unauthorized `outside.txt` change through
the real-LLM path; the workflow returned `blocked_by_permission_denied`,
`outside.txt` was not created, and the allowed file remained unchanged.

Real LLM negative verification smoke:

```text
python tests/smoke/negative_real_llm_smoke.py
```

Result: passed. The smoke forced a failing verification command through the
real-LLM path; the workflow did not deliver success and ended blocked with
`blocked_by_repair_limit`, while the verification result stayed `passed=false`.

## Not Included

- TDD RED-GREEN-REFACTOR.
- Full Product Flow.
- Multi-task queue execution.
- Review-only workflow.
- Browser verification.
- Split reviewer agents.
- DockerWorkspace integration.
- Branch finishing, PR creation, merge, reset, or cleanup automation.

## Known Limits

- MVP planning and implementation are single-task only.
- The task implementation step applies complete replacement file contents.
- QA verification intentionally allows only a small safe command set.
- PM routing is deterministic for MVP; real LLM is used by direct and
  lightweight execution paths.
- ReviewRoom is a conservative merged reviewer focused on verification failure
  and obvious contract boundary issues.
