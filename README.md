# GraphPact

A small, vendor-neutral development lifecycle for coding agents. GraphPact combines
a lightweight change contract with an optional task graph, adding structure only
when a change needs it and staying out of the way for ordinary edits.

> **Status:** experimental V1 beta. Validate it on representative projects before
> treating it as an organizational control.

The same `SKILL.md` works with Codex, Claude Code, and Grok Build. There is no
daemon, global CLI, model API, workflow engine, or mandatory formal-method stack.

## How it behaves

| Change | Persistent artifact | Required path |
|---|---|---|
| Simple | None | Inspect → edit → test → inspect diff |
| Structured | One `change.json` | Grill → lots → execution selection → contract → small slices → executed checks |
| Critical | The same `change.json` | Grill → lots → execution selection → human gates → implementation → fresh review |

The lifecycle selects the tier from concrete risk signals. It can move upward
without ceremony. A downward override requires explicit approval, and protected
critical signals cannot be downgraded.

## Use it in this repository

Start your preferred coding agent in the repository and describe the change normally.
The skill can be selected automatically for non-trivial work, or invoked explicitly:

- Codex: `$development-lifecycle`
- Claude Code: `/development-lifecycle`
- Grok Build: `/development-lifecycle`

For a structured or critical change, the agent creates:

```text
.lifecycle/changes/<id>/change.json
```

Validate the contract with:

```bash
python3 .lifecycle/check.py .lifecycle/changes/<id>/change.json
```

The checker has no third-party dependencies. It validates the internal consistency
of the recorded field, risk, gates, task dependencies, acceptance evidence, and
critical review, and rejects unknown fields so typos do not pass silently. By
default it does not execute commands or touch Git.

To ground the recorded revisions against real history, pass a repository:

```bash
python3 .lifecycle/check.py --repo . .lifecycle/changes/<id>/change.json
```

In `--repo` mode the checker performs read-only Git lookups to confirm that the
baseline, base, evidence, and review revisions exist and that the completion
evidence descends from the baseline. It still never executes acceptance commands or
authenticates human approvals.

## Greenfield and brownfield

Every contract records `project.field`. The value changes what the lifecycle
protects.

| Field | Meaning | Extra guardrails |
|---|---|---|
| `greenfield` | New project or isolated component with no existing behavior to preserve | None; keep decisions reversible and build in small slices |
| `brownfield` | Change to a codebase with history, users, or established contracts | A recorded baseline, frozen invariants, and a continuity check |

Greenfield work optimizes for building the right thing cheaply. Brownfield work must
also prove that the change preserves behavior that already matters, because an agent
sees the code in front of it, not the invisible contracts that hold a live system
together. For a brownfield contract the checker requires:

- `project.baseline_revision` — the commit whose behavior must survive;
- `project.invariants` — the public interfaces, formats, and observable behaviors
  that must not break;
- at least one acceptance criterion marked `"continuity": true` — a
  characterization, golden-master, or regression check that pins current behavior
  before the change and stays green after it;
- optionally `project.rollback` — how to reverse the change if a staged rollout
  regresses.

A greenfield contract must omit those fields; there is nothing existing to protect.
The checker enforces this structure but cannot prove the invariants are complete or
the behavior truly preserved. The full protocol lives in
[`brownfield-continuity.md`](.agents/skills/development-lifecycle/references/brownfield-continuity.md).

Revision fields are commit-shaped recorded identifiers. The checker links a critical
review to the recorded evidence revision; it does not prove that a remote repository,
human identity, or command transcript is authentic.

## The grill

Structured and critical changes start with a grill: a short, bounded challenge that
surfaces unstated assumptions, ambiguous acceptance, rejected alternatives, and the
most plausible failure modes before any code is written. Its output is not thrown
away — it sharpens `objective`, `non_goals`, `project.invariants`, and acceptance, and
it divides the work into **lots** (`tasks`) with `depends_on` edges and `write_scope`
that the execution-mode selection below acts on. The full step lives in the lifecycle
skill.

## Automatic execution selection

After the grill and contract summary, GraphPact records one of three modes for the
lots it produced:

| Mode | Use |
|---|---|
| `sequential` | Default for local work, coupled tasks, and ordinary fixes |
| `parallel-read` | Independent read-only reconnaissance, even while the contract is draft |
| `parallel-worktrees` | Approved work with at least two dependency-independent, isolated, locally verifiable tasks |

Parallel writers never start directly from a vague goal. GraphPact first stabilizes
shared foundations, records a common Git base, and requires a mutable `write_scope`
plus a local `verification` command for every task in the plan. One coordinator
integrates branches in dependency order and runs the cross-task acceptance checks.

The checker validates the declared graph, task metadata, and literal scope
collisions. It cannot prove that two paths or interfaces are semantically
independent; the coordinator must verify that judgment in the code. The detailed
protocol is loaded only when needed from
[`parallel-worktrees.md`](.agents/skills/development-lifecycle/references/parallel-worktrees.md).

Claude Code and Grok Build can isolate writing subagents in worktrees. Codex-managed
worktree conversations are also supported, but normal Codex CLI subagents currently
share their parent's working directory; prepare and bind explicit worktrees before
using them as writers, or stay sequential.

## Add it to another repository

Copy these paths into the target repository:

```text
.agents/skills/development-lifecycle/
.claude/skills/development-lifecycle -> ../../.agents/skills/development-lifecycle
.lifecycle/change.example.json
.lifecycle/check.py
.lifecycle/VERSION
```

`.lifecycle/VERSION` records the GraphPact release you copied in. Print the running
version with `python3 .lifecycle/check.py --version`. Check for a newer tagged
release with:

```bash
python3 .lifecycle/check.py --check-update
```

This performs a read-only `git ls-remote` against the upstream repository (override
with `--source <url-or-path>`) and reports whether an update is available. It never
downloads or overwrites anything; applying an update stays a separate, deliberate
step.

Then merge the short lifecycle section from `AGENTS.md` into the target project's
instructions. Claude Code can import that file from `CLAUDE.md` with `@AGENTS.md`.
Grok Build reads Claude Code skills and `AGENTS.md` directly.

The checker requires Python 3.10 or later. Use `python3` on macOS/Linux, `python`
when that is the Python 3 command, or `py -3` on Windows. The Claude adapter is a
relative symlink; on Windows, copy the skill directory if symlink checkout is disabled.

Codex discovers repository skills under `.agents/skills`; Claude Code uses
`.claude/skills`; Grok Build supports Claude Code configuration. See the current
[Codex skill documentation](https://developers.openai.com/codex/skills),
[Claude Code skill documentation](https://code.claude.com/docs/en/skills), and
[Grok Build compatibility documentation](https://docs.x.ai/build/features/skills-plugins-marketplaces).

## Add Graphify to an ambitious repository

GraphPact treats a repository as ambitious when it is expected to be long-lived
and multi-component, or when architecture and blast-radius questions will recur.
Install Graphify for those repositories; skip it for small, local projects.

Follow the [project-scoped Graphify installation guide](.agents/skills/development-lifecycle/references/graphify-install.md).
It covers Codex, Claude Code, Grok Build, Windows, graph generation, and generated
files without adding a GraphPact-specific wrapper.

## Deliberate limits

- JSON-LD, SHACL, Prolog, and lifecycle-wide TLA+ are not part of V1.
- TLA+ is an explicit specialist option only for a genuinely critical concurrent
  or distributed protocol.
- Graphify is the default for ambitious repositories and optional elsewhere. It is
  a multi-hop navigation aid, not proof of correctness.
- Git remains the audit trail; there is no append-only lifecycle database.
- A task graph is used only when dependencies or safe parallelism make it useful.
- GraphPact selects and validates execution policy; it does not implement a custom
  multi-vendor scheduler, agent bus, or merge engine.

These limits are intentional safeguards against process becoming more complex than
the code change itself.

## Development

Run the dependency-free test suite:

```bash
python3 -m unittest discover -s tests -v
```
