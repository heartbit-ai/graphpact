#!/usr/bin/env python3
"""Check the internal consistency of a lifecycle change record."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TIERS = {"simple": 0, "structured": 1, "critical": 2}
STATES = {"draft", "contracted", "implementing", "verifying", "blocked", "done"}
EXECUTION_MODES = {"sequential", "parallel-read", "parallel-worktrees"}
PROJECT_FIELDS = {"greenfield", "brownfield"}
STRUCTURED = {"cross-component", "public-api", "dependency", "architecture"}
CRITICAL = {
    "auth-permissions",
    "secrets",
    "payments",
    "data-migration",
    "destructive-action",
    "production-action",
    "paid-action",
    "external-side-effect",
    "concurrency-distributed",
}
PROTECTED = CRITICAL - {"concurrency-distributed"}
LIVE_ACTIONS = {
    "destructive-action",
    "production-action",
    "paid-action",
    "external-side-effect",
}
ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
REVISION = re.compile(r"^[0-9a-f]{7,64}$")
AddError = Callable[[str, str], None]


def validate_contract(document: Any) -> list[str]:
    errors: list[str] = []

    def add(code: str, message: str) -> None:
        errors.append(f"{code}: {message}")

    if not isinstance(document, dict):
        return ["DOC001: contract must be a JSON object"]
    required = {
        "id",
        "state",
        "objective",
        "project",
        "risk",
        "acceptance",
        "execution",
        "tasks",
    }
    for key in sorted(required - document.keys()):
        add("DOC002", f"missing field '{key}'")
    if errors:
        return errors

    check_id(document["id"], "id", add)
    state = document["state"]
    if not isinstance(state, str) or state not in STATES:
        add("STATE001", f"unknown state '{state}'")
        state = "draft"
    if not nonempty(document["objective"]):
        add("DOC003", "objective must be a non-empty string")
    if "non_goals" in document:
        check_string_list(document["non_goals"], "non_goals", add)

    tier, signals = check_risk(document["risk"], add)
    verifications, continuity_ids = check_acceptance(document["acceptance"], add)
    field = check_project(document["project"], add)
    if field == "brownfield" and not continuity_ids:
        add(
            "PROJECT007",
            "brownfield changes require at least one continuity acceptance criterion",
        )
    if field == "greenfield" and continuity_ids:
        add(
            "PROJECT008",
            "continuity acceptance criteria are only valid for brownfield changes",
        )
    tasks = check_tasks(document["tasks"], add)
    check_execution(document["execution"], state, tasks, add)

    approvals = document.get("approvals", {})
    contract_approved = False
    action_approved = False
    if not isinstance(approvals, dict):
        add("GATE001", "approvals must be an object")
    else:
        contract_approved = approvals.get("contract") is True
        action_approved = approvals.get("critical_actions") is True
        for key in ("contract", "critical_actions"):
            if key in approvals and not isinstance(approvals[key], bool):
                add("GATE002", f"approvals.{key} must be boolean")
    if state != "draft" and not contract_approved:
        add("GATE003", f"state '{state}' requires a recorded contract approval")
    if (
        state in {"implementing", "verifying", "done"}
        and signals & LIVE_ACTIONS
        and not action_approved
    ):
        add(
            "GATE004",
            "live destructive, production, paid, or external actions need approval",
        )

    successful = check_evidence(document.get("evidence", []), verifications, add)
    if state == "done":
        for acceptance_id in sorted(set(verifications) - set(successful)):
            add(
                "EVIDENCE001",
                f"acceptance '{acceptance_id}' lacks matching successful evidence",
            )
        if len(set(successful.values())) > 1:
            add("EVIDENCE009", "completed evidence must refer to one revision")

    review = document.get("review")
    independent = False
    result = "pending"
    review_revision = None
    if review is not None:
        if not isinstance(review, dict):
            add("REVIEW001", "review must be an object")
        else:
            independent = review.get("independent") is True
            result = review.get("result")
            review_revision = review.get("revision")
            if "independent" in review and not isinstance(review["independent"], bool):
                add("REVIEW002", "review.independent must be boolean")
            if not isinstance(result, str) or result not in {
                "pending",
                "passed",
                "failed",
            }:
                add("REVIEW003", "review.result must be pending, passed, or failed")
            if "findings" in review:
                check_string_list(review["findings"], "review.findings", add)
    if state == "done" and result == "failed":
        add("REVIEW004", "a failed review blocks completion")
    if (
        state == "done"
        and tier == "critical"
        and not (independent and result == "passed")
    ):
        add(
            "REVIEW005", "a critical completed change needs a passed independent review"
        )
    if (
        state == "done"
        and tier == "critical"
        and (
            not isinstance(review_revision, str)
            or review_revision not in set(successful.values())
        )
    ):
        add("REVIEW006", "critical review.revision must match successful evidence")
    return errors


def check_risk(value: Any, add: AddError) -> tuple[str, set[str]]:
    if not isinstance(value, dict):
        add("RISK001", "risk must be an object")
        return "simple", set()
    tier = value.get("tier")
    if not isinstance(tier, str) or tier not in TIERS:
        add("RISK002", f"unknown risk tier '{tier}'")
        tier = "simple"
    raw = value.get("signals")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        add("RISK003", "risk.signals must be an array of strings")
        signals: set[str] = set()
    else:
        signals = set(raw)
        if len(signals) != len(raw):
            add("RISK004", "risk.signals must be unique")
        for signal in sorted(signals - STRUCTURED - CRITICAL):
            add("RISK005", f"unknown risk signal '{signal}'")
    if not nonempty(value.get("rationale")):
        add("RISK006", "risk.rationale must be a non-empty string")

    inferred = (
        "critical"
        if signals & CRITICAL
        else "structured"
        if signals & STRUCTURED
        else "simple"
    )
    if TIERS[tier] < TIERS[inferred]:
        if signals & PROTECTED:
            add("RISK007", "protected critical signals cannot be downgraded")
        downgrade = value.get("downgrade")
        if not (
            isinstance(downgrade, dict)
            and downgrade.get("approved") is True
            and nonempty(downgrade.get("rationale"))
        ):
            add(
                "RISK008",
                f"downgrade from {inferred} to {tier} needs recorded approval",
            )
    elif "downgrade" in value:
        add("RISK009", "risk.downgrade is only valid below the inferred tier")
    return tier, signals


def check_project(value: Any, add: AddError) -> str | None:
    if not isinstance(value, dict):
        add("PROJECT001", "project must be an object")
        return None
    field = value.get("field")
    if not isinstance(field, str) or field not in PROJECT_FIELDS:
        add("PROJECT002", f"unknown project field '{field}'")
        field = None

    if field == "brownfield":
        baseline = value.get("baseline_revision")
        if not isinstance(baseline, str) or not REVISION.fullmatch(baseline):
            add(
                "PROJECT003",
                "brownfield requires a commit-shaped project.baseline_revision",
            )
        invariants = value.get("invariants")
        if (
            not isinstance(invariants, list)
            or not invariants
            or any(not nonempty(item) for item in invariants)
        ):
            add(
                "PROJECT005",
                "brownfield requires project.invariants as a non-empty array of "
                "non-empty strings",
            )
        elif len(set(invariants)) != len(invariants):
            add("PROJECT011", "project.invariants must be unique")
        if "rollback" in value and not nonempty(value.get("rollback")):
            add("PROJECT009", "project.rollback must be a non-empty string")
    elif field == "greenfield":
        if "baseline_revision" in value:
            add(
                "PROJECT004",
                "project.baseline_revision is only valid for brownfield changes",
            )
        if "invariants" in value:
            add(
                "PROJECT006",
                "project.invariants is only valid for brownfield changes",
            )
        if "rollback" in value:
            add("PROJECT010", "project.rollback is only valid for brownfield changes")
    return field


def check_acceptance(value: Any, add: AddError) -> tuple[dict[str, str], set[str]]:
    if not isinstance(value, list) or not value:
        add("ACCEPT001", "acceptance must be a non-empty array")
        return {}, set()
    verifications: dict[str, str] = {}
    continuity_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            add("ACCEPT002", f"acceptance[{index}] must be an object")
            continue
        acceptance_id = item.get("id")
        check_id(acceptance_id, f"acceptance[{index}].id", add)
        if isinstance(acceptance_id, str) and acceptance_id in verifications:
            add("ACCEPT003", f"duplicate acceptance id '{acceptance_id}'")
        continuity = item.get("continuity", False)
        if "continuity" in item and not isinstance(continuity, bool):
            add("ACCEPT005", f"acceptance[{index}].continuity must be boolean")
            continuity = False
        if not nonempty(item.get("criterion")) or not nonempty(
            item.get("verification")
        ):
            add("ACCEPT004", f"acceptance[{index}] needs criterion and verification")
        elif isinstance(acceptance_id, str):
            verifications[acceptance_id] = item["verification"]
            if continuity is True:
                continuity_ids.add(acceptance_id)
    return verifications, continuity_ids


def check_tasks(value: Any, add: AddError) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        add("TASK001", "tasks must be a non-empty array")
        return {}
    graph: dict[str, list[str]] = {}
    tasks: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            add("TASK002", f"tasks[{index}] must be an object")
            continue
        task_id = item.get("id")
        check_id(task_id, f"tasks[{index}].id", add)
        if not nonempty(item.get("outcome")):
            add("TASK003", f"tasks[{index}].outcome must be non-empty")
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(dep, str) for dep in dependencies
        ):
            add("TASK004", f"tasks[{index}].depends_on must be an array of ids")
            dependencies = []
        elif len(set(dependencies)) != len(dependencies):
            add("TASK005", f"tasks[{index}].depends_on must be unique")
        write_scope = item.get("write_scope")
        if write_scope is not None:
            if (
                not isinstance(write_scope, list)
                or not write_scope
                or any(not nonempty(scope) for scope in write_scope)
            ):
                add(
                    "TASK010",
                    f"tasks[{index}].write_scope must be a non-empty array of strings",
                )
            elif len(set(write_scope)) != len(write_scope):
                add("TASK011", f"tasks[{index}].write_scope must be unique")
        verification = item.get("verification")
        if verification is not None and not nonempty(verification):
            add("TASK012", f"tasks[{index}].verification must be non-empty")
        if isinstance(task_id, str):
            if task_id in graph:
                add("TASK006", f"duplicate task id '{task_id}'")
            graph[task_id] = dependencies
            tasks[task_id] = {
                "depends_on": dependencies,
                "write_scope": write_scope,
                "verification": verification,
            }
    if len(graph) < 3 and any(graph.values()):
        add("TASK007", "omit dependency edges when fewer than three tasks exist")
    for task_id, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph:
                add(
                    "TASK008",
                    f"task '{task_id}' depends on unknown task '{dependency}'",
                )
    if has_cycle(graph):
        add("TASK009", "task dependency graph contains a cycle")
    return tasks


def check_execution(
    value: Any, state: str, tasks: dict[str, dict[str, Any]], add: AddError
) -> None:
    if not isinstance(value, dict):
        add("EXEC001", "execution must be an object")
        return
    mode = value.get("mode")
    if not isinstance(mode, str) or mode not in EXECUTION_MODES:
        add("EXEC002", f"unknown execution mode '{mode}'")
        return
    if not nonempty(value.get("rationale")):
        add("EXEC003", "execution.rationale must be a non-empty string")
    if mode != "parallel-worktrees":
        if "base_revision" in value:
            add(
                "EXEC004",
                "execution.base_revision is only valid for parallel-worktrees",
            )
        return

    base_revision = value.get("base_revision")
    if not isinstance(base_revision, str) or not REVISION.fullmatch(base_revision):
        add(
            "EXEC005",
            "parallel-worktrees requires a commit-shaped execution.base_revision",
        )
    if state == "draft":
        add("EXEC006", "parallel-worktrees requires a ratified contract")

    graph = {task_id: task["depends_on"] for task_id, task in tasks.items()}
    parallel_pairs = independent_pairs(graph)
    if not parallel_pairs:
        add(
            "EXEC007",
            "parallel-worktrees requires at least two dependency-independent tasks",
        )
    for task_id, task in tasks.items():
        if not (
            isinstance(task["write_scope"], list)
            and task["write_scope"]
            and all(nonempty(scope) for scope in task["write_scope"])
        ):
            add(
                "EXEC008",
                f"task '{task_id}' in a parallel-worktrees plan requires write_scope",
            )
        if not nonempty(task["verification"]):
            add(
                "EXEC009",
                f"task '{task_id}' in a parallel-worktrees plan requires verification",
            )

    for left, right in parallel_pairs:
        left_scope = tasks[left]["write_scope"]
        right_scope = tasks[right]["write_scope"]
        if not isinstance(left_scope, list) or not isinstance(right_scope, list):
            continue
        overlap = sorted(set(left_scope) & set(right_scope))
        if overlap:
            add(
                "EXEC010",
                f"independent tasks '{left}' and '{right}' share write scope "
                f"'{overlap[0]}'",
            )


def independent_pairs(graph: dict[str, list[str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    task_ids = sorted(graph)
    for index, left in enumerate(task_ids):
        for right in task_ids[index + 1 :]:
            if not depends_on(graph, left, right) and not depends_on(
                graph, right, left
            ):
                pairs.append((left, right))
    return pairs


def depends_on(graph: dict[str, list[str]], task_id: str, dependency: str) -> bool:
    pending = list(graph.get(task_id, []))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == dependency:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(graph.get(current, []))
    return False


def check_evidence(
    value: Any, verifications: dict[str, str], add: AddError
) -> dict[str, str]:
    if not isinstance(value, list):
        add("EVIDENCE002", "evidence must be an array")
        return {}
    successful: dict[str, str] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            add("EVIDENCE003", f"evidence[{index}] must be an object")
            continue
        acceptance_id = item.get("acceptance_id")
        expected = (
            verifications.get(acceptance_id) if isinstance(acceptance_id, str) else None
        )
        if expected is None:
            add("EVIDENCE004", f"evidence[{index}] references unknown acceptance")
        if item.get("command") != expected:
            add(
                "EVIDENCE005",
                f"evidence[{index}].command does not match planned verification",
            )
        exit_code = item.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            add("EVIDENCE006", f"evidence[{index}].exit_code must be an integer")
        revision = item.get("revision")
        revision_valid = isinstance(revision, str) and REVISION.fullmatch(revision)
        if not revision_valid:
            add(
                "EVIDENCE007",
                f"evidence[{index}].revision must be a commit-shaped identifier",
            )
        timestamp_valid = valid_timestamp(item.get("observed_at"))
        if not timestamp_valid:
            add(
                "EVIDENCE008",
                f"evidence[{index}].observed_at must be a non-future ISO timestamp",
            )
        if (
            expected is not None
            and item.get("command") == expected
            and exit_code == 0
            and revision_valid
            and timestamp_valid
        ):
            successful[acceptance_id] = revision
    return successful


def has_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        cyclic = any(dep in graph and visit(dep) for dep in graph[node])
        visiting.remove(node)
        visited.add(node)
        return cyclic

    return any(visit(node) for node in graph)


def check_id(value: Any, path: str, add: AddError) -> None:
    if not isinstance(value, str) or not ID.fullmatch(value):
        add("ID001", f"{path} must match {ID.pattern}")


def check_string_list(value: Any, path: str, add: AddError) -> None:
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        add("DOC004", f"{path} must be an array of non-empty strings")
    elif len(set(value)) != len(value):
        add("DOC005", f"{path} must contain unique values")


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed <= datetime.now(
        timezone.utc
    ) + timedelta(minutes=5)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {Path(argv[0]).name} PATH/TO/change.json", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"LOAD001: {exc}", file=sys.stderr)
        return 2
    errors = validate_contract(document)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"OK: {path} (field={document['project']['field']}, "
        f"tier={document['risk']['tier']}, "
        f"state={document['state']}, mode={document['execution']['mode']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
