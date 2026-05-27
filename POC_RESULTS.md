# Phase 0.5 POC Results

Date: 2026-05-27

## Summary

Phase 0.5 is complete against the installed local dependency set. Four original assumptions pass directly; one hard-gate assumption needs an implementation adjustment before Phase 1/2:

- `PermissionMode.EXPLORE` in AgentScope 2.0.0 denies `Bash` at the tool level, even for read-only commands. Use `PermissionMode.DEFAULT` plus explicit allow rules for read-only Bash commands, or keep EXPLORE agents limited to `Read`, `Grep`, and `Glob`.

## Environment

- Python: 3.14.2
- AgentScope: 2.0.0
- Pydantic: 2.13.4
- Dependency location: `D:\Mycode\myCodingTeam\.venv`
- Package cache location: `D:\Mycode\myCodingTeam\.pip-cache`
- `.env`: present with `LLM_MODEL`, `LLM_BASE_URL`, and `LLM_API_KEY`; secret values were not printed or committed.
- Real API smoke: passed with the configured OpenAI-compatible model; the response body and API key were not printed.

## POC Checks

1. Single Agent + Bash
   - Test: `tests/poc/test_poc_agent_basics.py`
   - Result: partially passed with a documented mismatch
   - Evidence: `Agent.reply_stream()` executed a scripted `Bash` call for `cd` in default mode and returned the current working directory in tool-result events.
   - Mismatch: `PermissionMode.EXPLORE` denied the same Bash tool call with `Permission denied for Bash (explore mode is read-only)`.
   - Impact: agents that need shell-based read-only probes cannot use plain EXPLORE mode with `Bash`.
   - Alternative: use `Read/Grep/Glob` in EXPLORE, or use DEFAULT/DONT_ASK with tightly scoped `Bash` allow rules for approved read-only commands.

2. PermissionRule blocks out-of-scope write
   - Test: `tests/poc/test_poc_permissions.py`
   - Result: passed
   - Evidence: `PermissionMode.DONT_ASK` with `Write` allow rules limited to `tests/**` denied a write attempt to `src/foo.py`; the file was not created.

3. HITL confirmation and resume
   - Test: `tests/poc/test_poc_hitl.py`
   - Result: passed
   - Evidence: `reply_stream()` emitted `RequireUserConfirmEvent`, then resumed with `UserConfirmResultEvent` and completed the confirmed `Bash` call.

4. AgentState persistence
   - Test: `tests/poc/test_poc_state.py`
   - Result: passed
   - Evidence: `AgentState.model_dump_json()` and `AgentState.model_validate_json()` preserved session, summary, and context.

5. LocalWorkspace lifecycle
   - Test: `tests/poc/test_poc_workspace.py`
   - Result: passed
   - Evidence: `LocalWorkspace.initialize()` created the workspace layout and `close()` marked it inactive.

6. Read-only Bash probe under DONT_ASK
   - Test: `tests/poc/test_poc_readonly_probe.py`
   - Result: passed
   - Evidence: `git status --short` ran successfully under explicit read-only Bash allow rules; `rm -rf <path>` was denied and did not remove the target file; `git checkout main` was denied because the whitelist is per subcommand.
   - Note: AgentScope 2.0.0's built-in safety layer emits `RequireUserConfirmEvent` for `rm -rf` regardless of `allow_rules` contents; only an explicit `deny_rules` entry preempts it into a hard denial. The reusable helpers therefore come in pairs: `build_readonly_probe_rules()` (allow whitelist) and `build_readonly_probe_deny_rules()` (destructive blacklist), and both must be passed together for unattended read-only agents.

## Notes

- POC tests use a deterministic scripted `ChatModelBase` implementation to force exact tool-call paths. This avoids making the POC depend on model prompt-following variance while still exercising real AgentScope `Agent`, `Toolkit`, built-in tools, permission engine, events, state, and workspace code.
- AgentScope 2.0.0 API mismatch found: EXPLORE cannot be used with Bash, including read-only shell commands. Update adapter/permission design before relying on Bash inside read-only agents.
