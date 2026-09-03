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
  migration, destructive, production, paid or external action, concurrent/distributed
  state, personal data (`pii`), data loss, input validation and injection surfaces,
  or supply-chain and dependency provenance.

Record risk with `risk.signals`. Add a project-local advisory signal with an `x-`
prefix (for example `x-performance`); it is accepted but does not raise the tier.

Up-tier freely. Down-tier only after explicit human confirmation and record it in
`risk.downgrade`. Protected critical signals — everything critical except
`concurrency-distributed` — can never be downgraded.

## Classify the field

Every structured or critical contract records `project.field`.

- **Greenfield:** a new project, package, or isolated component with no existing
  behavior or consumers to preserve. Build a walking skeleton, keep early decisions
  reversible, and work in small complete slices. Do not set `baseline_revision`,
  `invariants`, or a continuity criterion; there is nothing existing to protect.
- **Brownfield:** any change to a codebase that already has history, users, or
  established, often undocumented, contracts. The goal is not only the new behavior
  but the continuity of everything that already works.

For a brownfield change, extra guardrails must emerge in the contract:

- record `project.baseline_revision`, the commit whose behavior must survive;
- list `project.invariants`, the public interfaces, data formats, and observable
  behaviors that must not break, freezing the invariant core;
- add at least one continuity acceptance criterion (`"continuity": true`) that pins
  current behavior with a characterization, golden-master, or regression check
  before the change and stays green after it;
- when the change must alter existing behavior, prefer a reversible incremental
  rollout and record `project.rollback`.

Investigate before editing, scope each change to its delta, and verify twice: the
change meets its criterion and it does not regress the baseline. Read
[references/brownfield-continuity.md](references/brownfield-continuity.md) for the
full protocol. The checker enforces that a brownfield contract carries a baseline,
invariants, and a continuity check, and that a greenfield contract omits them; it
cannot prove the invariants are complete or the behavior truly preserved.

## Grill the change first

For structured and critical work, grill the change before locking the contract:
a short, proportional challenge that surfaces what a careful reviewer would raise
before any code is written. Unstated or ambiguous intent is the main cause of
confidently wrong changes, and reasoning harder does not reliably catch it — an
explicit step does. Keep it evidence-seeking, not an interrogation:

- **Explore before asking.** Resolve navigational gaps by reading the code, history,
  and tests. Reserve questions for informational gaps only the user holds: expected
  behavior, business rules, and design intent.
- **Surface the few high-value uncertainties**, not every possibility: unstated
  assumptions, ambiguous acceptance, alternatives you are rejecting and why, and — as
  a short pre-mortem — the most plausible way this change fails or breaks existing
  behavior.
- **Engage the user only for user-only inputs.** A missing input that only the user
  can supply — an intended behavior, a business rule, a target or environment, an
  irreversible choice — is what triggers a question; a gap you can close by reading
  code never is. A missing input that would change the scope or the division into
  lots must be resolved before you lock the contract.
- **Then route by reversibility, reusing the tier.** Even for a user-only gap, state
  the assumption and proceed for cheap, reversible decisions; ask for costly ones;
  block for irreversible or protected-signal actions until confirmed.
- **Stay bounded.** Prefer one round of the key questions, then stop. Running headless
  with no one to answer, record the assumption and proceed on the safest
  interpretation; never invent an answer silently.

The grill is also where the work becomes divisible. Feed its output straight into the
contract: unstated scope becomes `non_goals`, a brownfield failure mode becomes a
`project.invariant`, and a resolved ambiguity becomes an acceptance criterion. The
clarified change and the failure modes and couplings you found then define the
**lots** — the `tasks`: each coherent work unit is one task, the couplings set the
dependency edges, and the seams set each task's `write_scope`. That decomposition is
what makes the `execution.mode` choice sound (see below). Record the key questions
and accepted assumptions concisely in the optional `grill` array; do not keep a
running transcript. Only after the grill do you present the summary and set
`approvals.contract`.

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
   `.lifecycle/changes/<id>/change.json`. Record `project.field` and, for a
   brownfield change, its baseline, invariants, and continuity check before
   implementing (see Classify the field).
2. Grill the change (see Grill the change first). Research uncertain and
   time-sensitive facts from authoritative sources, and ask only for decisions that
   materially change scope, safety, or acceptance.
3. Present a concise human summary of the objective, exclusions, risk, and
   acceptance criteria, informed by the grill. Set `approvals.contract` only after
   confirmation.
4. Divide the grilled change into lots: an ordered task list where each task is one
   coherent work unit. Add dependency edges only when at least three meaningful units
   are dependent or can run in parallel; the graph must be acyclic.
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
8. Run `.lifecycle/check.py <path>` after contract changes and before claiming
   completion. It rejects unknown fields, so fix typos it reports. To ground the
   recorded revisions against real history, run `.lifecycle/check.py --repo . <path>`;
   it verifies that `baseline_revision`, `base_revision`, evidence, and review
   revisions exist and that the completion evidence descends from the baseline.
9. Record executed commands and their actual exit codes as evidence. For a
   brownfield `done` contract, all successful evidence shares one completion
   revision, that revision must be after the baseline, and a failing run recorded at
   it blocks completion. Agent claims and unexecuted checks are not evidence.

Graphify is an optional navigation aid, not a requirement. If it is already
available, use it for multi-hop dependency or blast-radius analysis, treat inferred
edges as hypotheses, and verify important ones in the code. When a repository is
long-lived and multi-component and the user wants that depth, read
[references/graphify-install.md](references/graphify-install.md) and propose its
project-scoped installation; otherwise use direct reads and search and do not
interrupt work to install tooling. Graphify is never completion evidence.

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
