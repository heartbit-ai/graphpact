---
name: development-lifecycle
description: Plan and execute ambiguous, cross-component, high-impact, or risky code changes with a compact contract, proportional gates, and observable evidence. Skip clearly local low-risk edits unless explicitly requested.
---

# GraphPact Development Lifecycle

Use the smallest path that safely fits the change.

## Select the tier

- **Simple:** clear, local, reversible, no public interface or sensitive effect.
- **Structured:** cross-component, dependency, public API, or architectural impact.
  A code change plus its directly related test does not count as cross-component.
- **Critical:** authentication or permissions, secrets, payment-domain code, data
  migration, destructive, production, paid or external action, or
  concurrent/distributed state.

Up-tier freely. Down-tier only after explicit human confirmation and record it in
`risk.downgrade`. Never downgrade authentication/permissions, secrets, payments,
data migrations, destructive actions, production actions, or external side effects.

## Simple changes

Do not create a lifecycle artifact. Inspect the relevant code, make the smallest
coherent edit, run the repository's checks, inspect the diff, and report the
observable result.

## Implementation quality

- Follow existing project conventions and reuse proven boundaries before adding
  a dependency, abstraction, or framework.
- Deliver the contracted behavior completely. Do not leave placeholders, false
  success paths, permanent test doubles, swallowed errors, or unreported partial
  implementations.
- Never weaken tests, types, linters, security controls, or error handling merely
  to make a change pass.
- Keep edits within the agreed scope. Avoid opportunistic refactors and remove
  debug code, dead code, and comments that only restate the implementation.
- Prefer direct, readable code. Add an abstraction only for demonstrated reuse,
  a real domain boundary, or a concrete safety invariant.

## Structured and critical changes

1. Read `.lifecycle/change.example.json` and create
   `.lifecycle/changes/<id>/change.json`.
2. Ask only for decisions that materially change scope, safety, or acceptance.
   Research uncertain and time-sensitive facts from authoritative sources.
3. Present a concise human summary of the objective, exclusions, risk, and
   acceptance criteria. Set `approvals.contract` only after confirmation.
4. Use an ordered task list. Add dependency edges only when at least three
   meaningful units are dependent or can run in parallel; the graph must be acyclic.
5. Select `execution.mode` automatically and explain the choice:
   - `parallel-read` for independent read-only reconnaissance, including before
     contract approval;
   - `parallel-worktrees` only after approval when at least two substantial tasks
     are dependency-independent, shared foundations are stable, declared mutable
     scopes do not overlap, local and join checks are known, one recorded Git base
     is available, and the active client can isolate every writer;
   - `sequential` otherwise. This is the safe default, especially for local fixes.
6. For `parallel-worktrees`, add `write_scope` and `verification` to every task,
   record `execution.base_revision`, then read and follow
   [references/parallel-worktrees.md](references/parallel-worktrees.md). Never
   treat a normal subagent as isolated unless the active tool actually binds it to
   a separate checkout.
7. Implement in small coherent slices. After a failed attempt, change the
   diagnosis before retrying. After three failed attempts, set the contract to
   `blocked` and report what is needed to continue.
8. Run `.lifecycle/check.py` after contract changes and before claiming completion.
9. Record executed commands and their actual exit codes as evidence. Agent claims,
   intended commands, and unexecuted checks are not evidence.

Treat a repository as ambitious when it is expected to be long-lived and
multi-component, or when architecture and blast-radius questions will recur. For
such a repository, use a project-scoped Graphify installation by default. If it is
absent, read [references/graphify-install.md](references/graphify-install.md),
propose its project-scoped installation, and obtain approval before installing
software. If installation is declined or unavailable, continue with direct
navigation and state the limitation; do not block the code change.

Build or update the graph before multi-hop dependency analysis or significant
blast-radius exploration. Treat inferred edges as hypotheses and verify important
ones in the code. For local questions, prefer direct reads and search. Graphify is
never completion evidence.

## Critical gates

- Technical full-access or YOLO permissions do not authorize production,
  destructive, paid, or externally visible actions. Obtain explicit confirmation
  immediately before those actions and record it in `approvals.critical_actions`.
- Before completion, obtain an independent fresh-context review when available.
  Otherwise request human review. Record its result and the reviewed revision in
  `review`.
- Use TLA+ only when a real critical concurrent or distributed protocol has
  invariants that tests cannot cover, and only with explicit human choice and
  competent review. Never treat automatically generated TLA+ as proof.

Approval and review fields are declarations, not authenticated proof. Never set them
without observing the corresponding human confirmation or review. The checker
validates their consistency but cannot establish who performed an action.

## Human interface

The JSON contract is the machine record, not the conversation format. Translate it
to the user's language on request. Preview material contract changes in plain
language before changing an approved contract.
