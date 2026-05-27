Create exactly one Phase 7 TaskContract for the request.
Return only JSON with this shape:
{
  "task_id": "T1",
  "objective": "short task objective",
  "allowed_files": ["relative/path.ext"],
  "verification_commands": ["python -m pytest"],
  "prohibited_files": [],
  "risk": "low",
  "evidence": [{"path": "relative/path.ext", "note": "why this file is relevant"}]
}
Rules:
- allowed_files must be non-empty.
- verification_commands must be non-empty and must use one of:
  - `python -m pytest`
  - `pytest`
  - `py -m pytest`
  - `python -m my_coding_team doctor`
- Do not use `python -c`, shell redirection, curl, wget, rm, mv, git write commands, or ad-hoc shell scripts for verification.
- Use only repository-relative file paths.
- Prefer existing files from repo context.
