# Install Graphify for a project

Use this path for a repository expected to be long-lived and multi-component, or
when architecture and blast-radius questions will recur. Skip it for small, local
projects. Obtain approval before installing software or changing project files.

## Install the CLI once per workstation

Graphify requires Python 3.10 or later. Install its official package with `uv`:

```bash
uv tool install graphifyy
```

The supported alternative is `pipx install graphifyy`. The PyPI package has two
`y` characters; the command is `graphify`. If the command is not found after a
`uv` installation, run `uv tool update-shell` and reopen the terminal.

## Register it in the target repository

Run from the repository root:

```bash
graphify install --project --platform agents
graphify install --project --platform claude
```

The first command installs the generic Agent Skill under `.agents/skills` for
Codex and compatible agents. The second installs the Claude project integration,
which is also read by Grok Build. On Windows, replace `claude` with `windows`.

Inspect the generated diff before committing it. Depending on the platform,
Graphify can add skill files, update `CLAUDE.md`, and create `.claude/settings.json`
for its hooks. Do not use strict mode unless the user explicitly asks for it.

## Build and maintain the graph

Build the initial graph from the coding agent:

- Codex: `$graphify .`
- Claude Code and Grok Build: `/graphify .`

Use the same command with `--update` after meaningful architecture changes. Add
`graphify-out/` to `.gitignore` unless the team explicitly chooses to version the
generated graph.

Use Graphify for multi-hop navigation and blast-radius exploration. Verify
important inferred edges in source code; a graph is not completion evidence.

Source: [official Graphify installation guide](https://github.com/Graphify-Labs/graphify#install).
