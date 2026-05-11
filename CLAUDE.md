@AI.md

## Workflow

- Treat `@AI.md` as the source of truth; do not restate project facts here.
- Honor `@.claude/settings.json` permissions: deny rules cover `config.yaml`, `.env*`, `terraform/**/*.tfvars`, `terraform/**/*.tfstate*`, `terraform apply|destroy`, `opencontext deploy|destroy|configure`, and destructive `git`. Surface blocked work to the user; do not route around denials.
- Expect the `PostToolUse` hook to run `uv run ruff format` on any `.py` file you `Edit`/`Write`; do not fight that formatting.
- Load matching glob rules from `@.claude/rules/` (`plugin-development.md`, `infrastructure.md`, `testing.md`, `code-style.md`) before editing files in their scope.
- Use `@.claude/skills/` (`add-plugin`, `deploy-aws`, `debug-lambda`, `fix-coverage`) and `@.claude/agents/` (`test-writer`, `plugin-validator`) for the workflows they cover instead of improvising.
- Before declaring a task done: CI-equivalent `ruff check` and the full `pytest --cov-fail-under=80` must pass; PRs target `develop`.

## Memory

Propose appending to `@AI.md` only when you discover a durable, repo-wide constraint that is missing there — never for ephemeral task notes.

## Context Hygiene

- As the final step of any agentic task, after tests pass and before closing the task, scan for anything non-obvious you discovered: architectural decisions made, constraints encountered, non-obvious file relationships, gotchas debugged, commands that only work a certain way.
- If any such discovery would have saved you time had it been in `AI.md` at the start of the session, add it there.
- Add to `AI.md` only — never bloat this file with project facts.
- Write additions as pointers or single-line facts, not paragraphs.
- Do not add things that are obvious from the code, already documented in `docs/`, generic best practices, or specific to just the current task.
- If nothing non-obvious was discovered, make no changes — do not add placeholder or "session notes" content.
- Never restructure or reformat existing `AI.md` content during an update — append only, to the most relevant existing section.
