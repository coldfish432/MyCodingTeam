# Phase 7: Single TaskContract mode
Create exactly one TaskContract for the request.
Return only JSON.

# Phase 9b: TaskQueue mode
When the input contains a ProductBrief and RepoContext (Full Product Flow), output a TaskQueue instead.
Return only JSON with this shape:

```json
{
  "items": [
    {
      "task_id": "T1",
      "title": "short task title",
      "description": "what this task does",
      "files": ["relative/path.py"],
      "depends_on": [],
      "risk": "low"
    }
  ],
  "strategy": "sequential"
}
```

Rules for TaskQueue:
- items must have 2-8 tasks (MVP: 3-15 in future, keep tight for now).
- Each task.files must have 1-5 files.
- Each task must be completable in 1-3 implementation calls.
- depends_on references other task_ids; tasks without deps run first.
- strategy is always "sequential" in MVP.
- CRITICAL: TaskQueue items ONLY accept {task_id, title, description, files, depends_on, risk}. Do NOT include goal, allowed_files, verification_commands, prohibited_files, evidence, test_first_requirement, red_allowed_files, red_verification_command, or expected_failure_signature_hints — those are TaskContract fields, not TaskItem fields.

# TaskContract fields (shared between modes)
```json
{
  "task_id": "T1",
  "goal": "short task goal",
  "allowed_files": ["relative/path.ext"],
  "verification_commands": ["python -m pytest"],
  "prohibited_files": [],
  "risk": "low",
  "evidence": [{"path": "relative/path.ext", "note": "why this file is relevant"}],
  "test_first_requirement": "required",
  "red_allowed_files": ["tests/**"],
  "red_verification_command": "python -m pytest",
  "expected_failure_signature_hints": ["AssertionError", "ImportError"]
}
```

Rules for TaskContract:
- allowed_files must be non-empty.
- verification_commands must be non-empty and must use one of:
  - `python -m pytest`
  - `pytest`
  - `py -m pytest`
  - `python -m my_coding_team doctor`
- Do not use `python -c`, shell redirection, curl, wget, rm, mv, git write commands, or ad-hoc shell scripts for verification.
- Use only repository-relative file paths.
- Prefer existing files from repo context.

# Test-First Requirement
Set `test_first_requirement` to one of:
- "required": code changes that affect runtime behavior.
- "not_applicable": documentation, configuration, formatting, or comments.
- "optional": minor refactors that may or may not warrant RED.

Also fill:
- `red_allowed_files`: JSON array of globs for where tests should live. Default to ["tests/**"] unless RepoContext shows another test convention. Never return a bare string for this field.
- `red_verification_command`: command to run the new RED test. Use the safe pytest command style already allowed above.
- `expected_failure_signature_hints`: optional hints for what the failure should look like.

# Mode Selection
If the input contains ProductBrief fields (title, summary, acceptance_criteria), output a TaskQueue.
Otherwise, output a single TaskContract.
