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
- Do not include markdown fences.
