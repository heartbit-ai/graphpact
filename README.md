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
| Structured | One `change.json` | Contract → small slices → executed checks |
| Critical | The same `change.json` | Human gates → implementation → fresh review |

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
of the recorded risk, gates, task dependencies, acceptance evidence, and critical
review. It does not execute commands or authenticate human approvals.

Revision fields are commit-shaped recorded identifiers. The checker links a critical
review to the recorded evidence revision; it does not prove that a remote repository,
human identity, or command transcript is authentic.

## Add it to another repository

Copy these paths into the target repository:

```text
.agents/skills/development-lifecycle/
.claude/skills/development-lifecycle -> ../../.agents/skills/development-lifecycle
.lifecycle/change.example.json
.lifecycle/check.py
```

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

## Deliberate limits

- JSON-LD, SHACL, Prolog, and lifecycle-wide TLA+ are not part of V1.
- TLA+ is an explicit specialist option only for a genuinely critical concurrent
  or distributed protocol.
- Graphify is optional and useful for multi-hop navigation, not as proof of correctness.
- Git remains the audit trail; there is no append-only lifecycle database.
- A task graph is used only when dependencies or safe parallelism make it useful.

These limits are intentional safeguards against process becoming more complex than
the code change itself.

## Development

Run the dependency-free test suite:

```bash
python3 -m unittest discover -s tests -v
```
