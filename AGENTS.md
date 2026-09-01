# Project agent instructions

## GraphPact development lifecycle

- Use the `development-lifecycle` skill for ambiguous, cross-component, public-interface,
  architectural, security-sensitive, stateful, destructive, or production changes.
- Skip lifecycle artifacts for clearly local, low-risk changes.
- For structured or critical work, keep one contract at
  `.lifecycle/changes/<id>/change.json` and validate it with
  `python3 .lifecycle/check.py <path>`.
- Keep contracts concise. Git is the history; do not create a parallel attempt log.
- Use dependency graphs only when at least three meaningful work units justify one.
- Select `sequential`, `parallel-read`, or `parallel-worktrees` after clarifying the
  goal. Parallel writes require an approved contract, independent tasks, disjoint
  mutable scopes, local verification, one recorded Git base, and real worktree
  isolation; otherwise stay sequential.
- When `parallel-worktrees` is selected, follow the lifecycle skill's conditional
  worktree reference. Keep one integration owner and do not assume ordinary Codex
  CLI subagents have separate checkouts.
- For an ambitious, long-lived or multi-component repository, use a project-scoped
  Graphify installation by default. If absent, propose the installation documented
  by the lifecycle skill and obtain approval; do not block work if it is declined.
- Use Graphify for multi-hop navigation or significant blast-radius analysis and
  verify important inferred relationships directly in the code.
- Treat full-access or YOLO tool permissions as execution capability, not approval for
  production, destructive, paid, or externally visible actions.
- Do not invoke BMAD or Superpowers unless the user explicitly requests them.

## Verification

- Run relevant repository checks and inspect the final diff.
- Report commands, exit codes, and remaining uncertainty. Claims are not evidence.
