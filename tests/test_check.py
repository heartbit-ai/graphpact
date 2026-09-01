from __future__ import annotations

import copy
import importlib.util
import json
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
            "baseline_revision": "abc1234",
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
