# Project agent instructions

## Development lifecycle

- Use the `development-lifecycle` skill for ambiguous, cross-component, public-interface,
  architectural, security-sensitive, stateful, destructive, or production changes.
- Skip lifecycle artifacts for clearly local, low-risk changes.
- For structured or critical work, keep one contract at
  `.lifecycle/changes/<id>/change.json` and validate it with
  `python3 .lifecycle/check.py <path>`.
- Keep contracts concise. Git is the history; do not create a parallel attempt log.
- Use dependency graphs only when at least three meaningful work units justify one.
- Use Graphify only for multi-hop navigation or significant blast-radius analysis;
  verify important inferred relationships directly in the code.
- Treat full-access or YOLO tool permissions as execution capability, not approval for
  production, destructive, paid, or externally visible actions.
- Do not invoke BMAD or Superpowers unless the user explicitly requests them.

## Verification

- Run relevant repository checks and inspect the final diff.
- Report commands, exit codes, and remaining uncertainty. Claims are not evidence.
