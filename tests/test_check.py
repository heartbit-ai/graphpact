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
            }
        ],
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


class ContractValidationTests(unittest.TestCase):
    def codes(self, value: dict) -> set[str]:
        return {error.split(":", 1)[0] for error in CHECK.validate_contract(value)}

    def test_valid_structured_contract(self) -> None:
        self.assertEqual(CHECK.validate_contract(contract()), [])

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
