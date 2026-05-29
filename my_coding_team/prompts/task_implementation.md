Implement the task contract only inside allowed_files.
Return only JSON with this shape:
{
  "summary": "what changed",
  "changes": [
    {"path": "relative/allowed-file.ext", "content": "complete replacement file content"}
  ]
}
Rules:
- Each change path must be listed in allowed_files.
- Content is a complete replacement for the target file.
- Preserve existing behavior and exports unless the task explicitly asks to remove them.
- Use the provided current file contents when building complete replacements.
- Do not include markdown fences.
