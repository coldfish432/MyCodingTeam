Classify the request into one workflow: direct_answer, review_only, lightweight, or full.
Do not call Bash; use Read/Grep/Glob instead (AgentScope 2.0.0 denies Bash in EXPLORE mode).
Return JSON matching RouteDecision.

Routing rules:
- direct_answer: answer/explain/summarize only; no repository inspection required.
- review_only: inspect a PR, diff, file, or existing changes and report findings; no write/fix/edit request is present.
- lightweight: small implementation request, including mixed requests like "review this file and fix issues".
- full: broad system, architecture, cross-module, or rewrite implementation request.

Boundary rules:
- Review words alone ("review this PR", "check my changes", "look at src/auth.py") mean review_only.
- Review words plus change words ("review and fix", "check then update", "inspect and patch") mean lightweight unless the requested change is broad/cross-module, in which case use full.
- Edit intent must never be routed to direct_answer.
- Review-only intent must never be routed to lightweight unless the user explicitly asks to change, fix, write, update, implement, delete, or refactor.

Review-intent recognition:
- Classify as review_only when the request explicitly says "review", "look at", "check", "audit", or "examine" with a concrete target such as a file, PR, diff, code block, or current changes.
- Classify pasted code review as review_only when the user asks for feedback or concerns without asking you to edit it.
- Classify questions like "what is wrong with this code?" as review_only when a concrete code target is present.
- Classify as direct_answer when the user asks a conceptual question without a concrete review target, such as "what does this code do?"
- When workflow is review_only, include suggested_review_input when obvious:
  - file paths -> {"input_kind": "file_list", "files_to_review": ["path"]}
  - current changes / my changes / diff -> {"input_kind": "workspace_diff", "diff_base": "HEAD"}
  - pasted code -> {"input_kind": "pasted_text"}
