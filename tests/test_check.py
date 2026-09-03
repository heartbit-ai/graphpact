from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / ".lifecycle" / "check.py"
SPEC = importlib.util.spec_from_file_location("lifecycle_check", CHECK_PATH)
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def contract() -> dict:
    return {
        "id": "safe-refactor",
        "state": "contracted",
        "objective": "Refactor the public API without changing its behavior.",
        "project": {
            "field": "brownfield",
            "baseline_revision": "ba5e123",
            "invariants": ["The public API signature and responses stay compatible"],
        },
        "risk": {
            "tier": "structured",
            "signals": ["public-api"],
            "rationale": "The change affects a public interface.",
        },
        "acceptance": [
            {
                "id": "api-compatible",
                "criterion": "Existing API behavior remains compatible.",
                "verification": "python3 -m unittest discover -s tests -v",
                "continuity": True,
            }
        ],
        "execution": {
            "mode": "sequential",
            "rationale": "The implementation and tests share one local write path.",
        },
        "tasks": [{"id": "update-code", "outcome": "Refactor implementation"}],
        "approvals": {"contract": True, "critical_actions": False},
    }


def evidence(command: str | None = None) -> dict:
    return {
        "acceptance_id": "api-compatible",
        "command": command or "python3 -m unittest discover -s tests -v",
        "exit_code": 0,
        "revision": "abc1234",
        "observed_at": "2026-08-31T12:00:00+02:00",
    }


def greenfield_contract() -> dict:
    value = contract()
    value["objective"] = "Build a new standalone tool from scratch."
    value["project"] = {"field": "greenfield"}
    value["acceptance"] = [
        {
            "id": "tool-works",
            "criterion": "The new tool performs its primary action.",
            "verification": "python3 -m unittest discover -s tests -v",
        }
    ]
    return value


def worktree_plan() -> dict:
    value = contract()
    value["execution"] = {
        "mode": "parallel-worktrees",
        "rationale": "API and UI consume a stabilized contract independently.",
        "base_revision": "abc1234",
    }
    value["tasks"] = [
        {
            "id": "foundation",
            "outcome": "Stabilize the shared contract.",
            "depends_on": [],
            "write_scope": ["domain:contract"],
            "verification": "test foundation",
        },
        {
            "id": "api",
            "outcome": "Implement the API.",
            "depends_on": ["foundation"],
            "write_scope": ["files:src/api/**"],
            "verification": "test api",
        },
        {
            "id": "ui",
            "outcome": "Implement the UI.",
            "depends_on": ["foundation"],
            "write_scope": ["files:src/ui/**"],
            "verification": "test ui",
        },
    ]
    return value


def make_git_repo(directory: str) -> tuple[str, str]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", directory, *args],
            capture_output=True,
            text=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com",
            },
        )
        return result.stdout.strip()

    run("init", "-q")
    (Path(directory) / "a.txt").write_text("a", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "first")
    first = run("rev-parse", "HEAD")
    (Path(directory) / "b.txt").write_text("b", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "second")
    second = run("rev-parse", "HEAD")
    return first, second


def make_tagged_repo(directory: str, *tags: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def run(*args: str) -> None:
        subprocess.run(
            ["git", "-C", directory, *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

    run("init", "-q")
    run("commit", "-q", "--allow-empty", "-m", "init")
    for tag in tags:
        run("tag", tag)


class ContractValidationTests(unittest.TestCase):
    def codes(self, value: dict) -> set[str]:
        return {error.split(":", 1)[0] for error in CHECK.validate_contract(value)}

    def test_valid_structured_contract(self) -> None:
        self.assertEqual(CHECK.validate_contract(contract()), [])

    def test_minimal_greenfield_contract_is_valid(self) -> None:
        self.assertEqual(CHECK.validate_contract(greenfield_contract()), [])

    def test_project_field_must_be_known(self) -> None:
        value = contract()
        value["project"]["field"] = "legacy"
        self.assertIn("PROJECT002", self.codes(value))

    def test_missing_project_is_reported(self) -> None:
        value = contract()
        del value["project"]
        self.assertIn("DOC002", self.codes(value))

    def test_brownfield_requires_baseline_invariants_and_continuity(self) -> None:
        value = contract()
        value["project"] = {"field": "brownfield"}
        value["acceptance"][0].pop("continuity")
        codes = self.codes(value)
        self.assertIn("PROJECT003", codes)
        self.assertIn("PROJECT005", codes)
        self.assertIn("PROJECT007", codes)

    def test_brownfield_invariants_must_be_non_empty_and_unique(self) -> None:
        value = contract()
        value["project"]["invariants"] = []
        self.assertIn("PROJECT005", self.codes(value))
        value["project"]["invariants"] = ["same", "same"]
        self.assertIn("PROJECT011", self.codes(value))

    def test_greenfield_forbids_brownfield_guardrails(self) -> None:
        value = greenfield_contract()
        value["project"]["baseline_revision"] = "abc1234"
        value["project"]["invariants"] = ["should not be here"]
        value["project"]["rollback"] = "revert"
        value["acceptance"][0]["continuity"] = True
        codes = self.codes(value)
        self.assertIn("PROJECT004", codes)
        self.assertIn("PROJECT006", codes)
        self.assertIn("PROJECT008", codes)
        self.assertIn("PROJECT010", codes)

    def test_continuity_flag_must_be_boolean(self) -> None:
        value = contract()
        value["acceptance"][0]["continuity"] = "yes"
        self.assertIn("ACCEPT005", self.codes(value))

    def test_brownfield_rollback_must_be_non_empty_when_present(self) -> None:
        value = contract()
        value["project"]["rollback"] = "   "
        self.assertIn("PROJECT009", self.codes(value))

    def test_failing_run_at_completion_revision_blocks_done(self) -> None:
        value = contract()
        value["state"] = "done"
        passing = evidence()
        failing = evidence()
        failing["exit_code"] = 1
        value["evidence"] = [passing, failing]
        self.assertIn("EVIDENCE010", self.codes(value))

    def test_single_revision_rule_is_order_independent(self) -> None:
        value = contract()
        value["state"] = "done"
        value["acceptance"].append(
            {
                "id": "types-pass",
                "criterion": "Types remain valid.",
                "verification": "python3 -m compileall .",
            }
        )
        first = evidence()
        second = evidence("python3 -m compileall .")
        second["acceptance_id"] = "types-pass"
        second["revision"] = "def5678"
        value["evidence"] = [first, second]
        self.assertIn("EVIDENCE009", self.codes(value))
        value["evidence"] = [second, first]
        self.assertIn("EVIDENCE009", self.codes(value))

    def test_brownfield_evidence_must_be_after_baseline(self) -> None:
        value = contract()
        value["state"] = "done"
        item = evidence()
        item["revision"] = value["project"]["baseline_revision"]
        value["evidence"] = [item]
        self.assertIn("PROJECT012", self.codes(value))

    def test_unknown_keys_are_rejected(self) -> None:
        value = contract()
        value["oops"] = 1
        value["risk"]["signalz"] = ["typo"]
        codes = self.codes(value)
        self.assertEqual(
            [error for error in CHECK.validate_contract(value) if error.startswith("DOC006")],
            [
                "DOC006: unexpected field 'contract.oops'",
                "DOC006: unexpected field 'risk.signalz'",
            ],
        )
        self.assertIn("DOC006", codes)

    def test_write_scope_containment_overlap_is_detected(self) -> None:
        value = worktree_plan()
        value["tasks"][2]["write_scope"] = ["files:src/api/customer/**"]
        self.assertIn("EXEC010", self.codes(value))

    def test_sibling_write_scopes_do_not_overlap(self) -> None:
        self.assertEqual(CHECK.validate_contract(worktree_plan()), [])

    def test_new_critical_signal_is_protected(self) -> None:
        value = contract()
        value["risk"] = {
            "tier": "structured",
            "signals": ["pii"],
            "rationale": "Touches personal data.",
            "downgrade": {"approved": True, "rationale": "requested"},
        }
        self.assertIn("RISK007", self.codes(value))

    def test_extension_signal_is_accepted(self) -> None:
        value = contract()
        value["risk"]["signals"] = ["public-api", "x-telemetry"]
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_unknown_signal_without_extension_prefix_is_rejected(self) -> None:
        value = contract()
        value["risk"]["signals"] = ["public-api", "bogus"]
        self.assertIn("RISK005", self.codes(value))

    def test_blocked_state_does_not_require_approval(self) -> None:
        value = contract()
        value["state"] = "blocked"
        value["approvals"]["contract"] = False
        self.assertNotIn("GATE003", self.codes(value))

    def test_task_status_must_be_known(self) -> None:
        value = contract()
        value["tasks"][0]["status"] = "wip"
        self.assertIn("TASK013", self.codes(value))

    def test_done_requires_every_task_resolved_when_status_used(self) -> None:
        value = contract()
        value["state"] = "done"
        value["evidence"] = [evidence()]
        value["tasks"] = [
            {"id": "one", "outcome": "First", "status": "done"},
            {"id": "two", "outcome": "Second", "status": "pending"},
        ]
        self.assertIn("TASK014", self.codes(value))
        value["tasks"][1]["status"] = "dropped"
        self.assertNotIn("TASK014", self.codes(value))

    def test_git_grounding_accepts_descendant_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, second = make_git_repo(directory)
            value = contract()
            value["state"] = "done"
            value["project"]["baseline_revision"] = first
            item = evidence()
            item["revision"] = second
            value["evidence"] = [item]
            self.assertEqual(CHECK.validate_contract(value, repo=Path(directory)), [])

    def test_git_grounding_flags_missing_and_non_descendant_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, second = make_git_repo(directory)
            missing = contract()
            missing["state"] = "done"
            missing["project"]["baseline_revision"] = first
            item = evidence()
            item["revision"] = "deadbee"
            missing["evidence"] = [item]
            self.assertIn(
                "GIT002", self.repo_codes(missing, Path(directory))
            )

            reversed_history = contract()
            reversed_history["state"] = "done"
            reversed_history["project"]["baseline_revision"] = second
            older = evidence()
            older["revision"] = first
            reversed_history["evidence"] = [older]
            self.assertIn(
                "GIT003", self.repo_codes(reversed_history, Path(directory))
            )

    def repo_codes(self, value: dict, repo: Path) -> set[str]:
        return {
            error.split(":", 1)[0] for error in CHECK.validate_contract(value, repo=repo)
        }

    def test_version_file_matches_module(self) -> None:
        version_file = (ROOT / ".lifecycle" / "VERSION").read_text().strip()
        self.assertEqual(version_file, CHECK.__version__)
        self.assertRegex(CHECK.__version__, r"^\d+\.\d+\.\d+")

    def test_version_flag_reports_version(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECK_PATH), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(CHECK.__version__, result.stdout)

    def test_grill_field_is_optional_and_accepted(self) -> None:
        self.assertEqual(CHECK.validate_contract(contract()), [])
        value = contract()
        value["grill"] = ["Assumed the API contract covers error codes; confirmed."]
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_grill_field_must_be_non_empty_strings(self) -> None:
        value = contract()
        value["grill"] = []
        self.assertIn("GRILL001", self.codes(value))
        value["grill"] = ["ok", "  "]
        self.assertIn("GRILL001", self.codes(value))

    def test_grill_entries_must_be_unique(self) -> None:
        value = contract()
        value["grill"] = ["same", "same"]
        self.assertIn("GRILL002", self.codes(value))

    def test_parse_version(self) -> None:
        self.assertEqual(CHECK.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(CHECK.parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(CHECK.parse_version("v0.1.0-beta"), (0, 1, 0))
        self.assertIsNone(CHECK.parse_version("nightly"))
        self.assertIsNone(CHECK.parse_version(None))

    def test_latest_upstream_version_picks_highest_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            make_tagged_repo(directory, "v0.1.0", "v0.2.0", "v0.10.0", "not-a-version")
            self.assertEqual(
                CHECK.latest_upstream_version(directory), "v0.10.0"
            )

    def update_check(self, source: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            return CHECK.run_update_check(source)

    def test_update_check_up_to_date_and_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            make_tagged_repo(directory, f"v{CHECK.__version__}")
            self.assertEqual(self.update_check(directory), 0)
        with tempfile.TemporaryDirectory() as directory:
            make_tagged_repo(directory, "v999.0.0")
            self.assertEqual(self.update_check(directory), 0)

    def test_update_check_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.update_check(str(Path(directory) / "missing")), 2)
        with tempfile.TemporaryDirectory() as directory:
            make_tagged_repo(directory)
            self.assertEqual(self.update_check(directory), 2)

    def test_underclassified_risk_requires_approved_downgrade(self) -> None:
        value = contract()
        value["risk"]["tier"] = "simple"
        self.assertIn("RISK008", self.codes(value))

    def test_concurrency_can_be_downgraded_with_approval(self) -> None:
        value = contract()
        value["risk"] = {
            "tier": "structured",
            "signals": ["concurrency-distributed"],
            "rationale": "The state is isolated.",
            "downgrade": {
                "approved": True,
                "rationale": "Human-reviewed bounded state.",
            },
        }
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_protected_signal_cannot_be_downgraded(self) -> None:
        value = contract()
        value["risk"] = {
            "tier": "structured",
            "signals": ["production-action"],
            "rationale": "Touches production.",
            "downgrade": {"approved": True, "rationale": "Requested."},
        }
        self.assertIn("RISK007", self.codes(value))

    def test_dependency_edges_need_three_tasks_and_must_be_acyclic(self) -> None:
        value = contract()
        value["tasks"] = [
            {"id": "first", "outcome": "First", "depends_on": ["third"]},
            {"id": "second", "outcome": "Second", "depends_on": ["first"]},
            {"id": "third", "outcome": "Third", "depends_on": ["second"]},
        ]
        self.assertIn("TASK009", self.codes(value))
        value["tasks"] = [
            {"id": "first", "outcome": "First", "depends_on": []},
            {"id": "second", "outcome": "Second", "depends_on": ["first"]},
        ]
        self.assertIn("TASK007", self.codes(value))

    def test_parallel_read_is_valid_before_contract_approval(self) -> None:
        value = contract()
        value["state"] = "draft"
        value["approvals"]["contract"] = False
        value["execution"] = {
            "mode": "parallel-read",
            "rationale": "Independent codebase reconnaissance can run read-only.",
        }
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_valid_parallel_worktree_plan(self) -> None:
        value = contract()
        value["execution"] = {
            "mode": "parallel-worktrees",
            "rationale": "API and UI can consume the stabilized contract independently.",
            "base_revision": "abc1234",
        }
        value["tasks"] = [
            {
                "id": "foundation",
                "outcome": "Stabilize the shared customer contract.",
                "depends_on": [],
                "write_scope": ["domain:customer-contract"],
                "verification": "python3 -m unittest tests.test_contract",
            },
            {
                "id": "api",
                "outcome": "Implement the customer API.",
                "depends_on": ["foundation"],
                "write_scope": ["files:src/api/customer/**"],
                "verification": "python3 -m unittest tests.test_customer_api",
            },
            {
                "id": "ui",
                "outcome": "Implement the customer UI.",
                "depends_on": ["foundation"],
                "write_scope": ["files:src/ui/customer/**"],
                "verification": "npm test -- customer-ui",
            },
            {
                "id": "join",
                "outcome": "Verify the integrated customer lifecycle.",
                "depends_on": ["api", "ui"],
                "write_scope": ["files:tests/customer-e2e/**"],
                "verification": "python3 -m unittest tests.test_customer_e2e",
            },
        ]
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_parallel_worktrees_rejects_unratified_or_sequential_plan(self) -> None:
        value = contract()
        value["state"] = "draft"
        value["approvals"]["contract"] = False
        value["execution"] = {
            "mode": "parallel-worktrees",
            "rationale": "Attempt parallel execution too early.",
            "base_revision": "abc1234",
        }
        codes = self.codes(value)
        self.assertIn("EXEC006", codes)
        self.assertIn("EXEC007", codes)
        self.assertIn("EXEC008", codes)
        self.assertIn("EXEC009", codes)

    def test_parallel_worktrees_rejects_overlapping_write_scopes(self) -> None:
        value = contract()
        value["execution"] = {
            "mode": "parallel-worktrees",
            "rationale": "Two independent implementations are proposed.",
            "base_revision": "abc1234",
        }
        value["tasks"] = [
            {
                "id": "api",
                "outcome": "Implement the customer API.",
                "write_scope": ["schema:customer"],
                "verification": "python3 -m unittest tests.test_api",
            },
            {
                "id": "ui",
                "outcome": "Implement the customer UI.",
                "write_scope": ["schema:customer"],
                "verification": "npm test -- customer-ui",
            },
            {
                "id": "join",
                "outcome": "Integrate the feature.",
                "depends_on": ["api", "ui"],
                "write_scope": ["files:tests/customer-e2e/**"],
                "verification": "python3 -m unittest tests.test_customer_e2e",
            },
        ]
        self.assertIn("EXEC010", self.codes(value))

    def test_parallel_worktrees_requires_a_recorded_base_revision(self) -> None:
        value = contract()
        value["execution"] = {
            "mode": "parallel-worktrees",
            "rationale": "Two independent tasks are proposed.",
        }
        value["tasks"] = [
            {
                "id": task_id,
                "outcome": f"Implement {task_id}.",
                "write_scope": [f"files:src/{task_id}/**"],
                "verification": f"test {task_id}",
            }
            for task_id in ("api", "ui", "audit")
        ]
        self.assertIn("EXEC005", self.codes(value))

    def test_done_requires_matching_successful_evidence(self) -> None:
        value = contract()
        value["state"] = "done"
        self.assertIn("EVIDENCE001", self.codes(value))
        value["evidence"] = [evidence("true")]
        codes = self.codes(value)
        self.assertIn("EVIDENCE005", codes)
        self.assertIn("EVIDENCE001", codes)

    def test_revision_and_timestamp_are_constrained(self) -> None:
        value = contract()
        value["state"] = "done"
        item = evidence()
        item["revision"] = "not-a-commit"
        item["observed_at"] = "2099-01-01T00:00:00Z"
        value["evidence"] = [item]
        codes = self.codes(value)
        self.assertIn("EVIDENCE007", codes)
        self.assertIn("EVIDENCE008", codes)

    def test_completed_evidence_uses_one_revision(self) -> None:
        value = contract()
        value["state"] = "done"
        value["acceptance"].append(
            {
                "id": "types-pass",
                "criterion": "Types remain valid.",
                "verification": "python3 -m compileall .",
            }
        )
        second = evidence("python3 -m compileall .")
        second["acceptance_id"] = "types-pass"
        second["revision"] = "def5678"
        value["evidence"] = [evidence(), second]
        self.assertIn("EVIDENCE009", self.codes(value))

    def test_failed_review_blocks_structured_completion(self) -> None:
        value = contract()
        value["state"] = "done"
        value["evidence"] = [evidence()]
        value["review"] = {"independent": True, "result": "failed", "findings": ["Bug"]}
        self.assertIn("REVIEW004", self.codes(value))

    def test_critical_done_requires_independent_passed_review(self) -> None:
        value = contract()
        value["state"] = "done"
        value["risk"] = {
            "tier": "critical",
            "signals": ["concurrency-distributed"],
            "rationale": "Concurrent state transition.",
        }
        value["evidence"] = [evidence()]
        self.assertIn("REVIEW005", self.codes(value))
        value["review"] = {
            "independent": True,
            "result": "passed",
            "revision": "abc1234",
            "findings": [],
        }
        self.assertEqual(CHECK.validate_contract(value), [])
        value["review"]["revision"] = "def5678"
        self.assertIn("REVIEW006", self.codes(value))

    def test_paid_action_requires_separate_approval(self) -> None:
        value = contract()
        value["state"] = "implementing"
        value["risk"] = {
            "tier": "critical",
            "signals": ["paid-action"],
            "rationale": "The operation incurs a charge.",
        }
        self.assertIn("GATE004", self.codes(value))

    def test_payment_domain_code_does_not_imply_a_live_paid_action(self) -> None:
        value = contract()
        value["state"] = "implementing"
        value["risk"] = {
            "tier": "critical",
            "signals": ["payments"],
            "rationale": "Changes payment-domain code but performs no payment.",
        }
        self.assertEqual(CHECK.validate_contract(value), [])

    def test_malformed_types_return_errors_instead_of_crashing(self) -> None:
        value = contract()
        value["state"] = []
        value["risk"]["tier"] = []
        value["acceptance"][0]["id"] = []
        self.assertGreater(len(CHECK.validate_contract(value)), 0)

    def test_example_and_cli(self) -> None:
        example = json.loads((ROOT / ".lifecycle" / "change.example.json").read_text())
        self.assertEqual(CHECK.validate_contract(example), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "change.json"
            path.write_text(json.dumps(contract()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECK_PATH), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            invalid = copy.deepcopy(contract())
            invalid["state"] = "done"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECK_PATH), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
