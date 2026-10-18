import copy
import json
import unittest
from pathlib import Path
from review import DEFAULT_CONTEXT, InvalidInput, ReviewSession, build_package, canonical, digest
from tests.run_review_cases import run_case
ROOT = Path(__file__).resolve().parent


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "review-fixtures.json").read_text())

    def test_shared_negative_and_positive_sequences(self):
        for case in json.loads((ROOT / "tests/review-cases.json").read_text()):
            with self.subTest(case=case["name"]):
                results = iter(run_case(case))
                for step in case["steps"]:
                    if step["op"] in ("mutate", "tamper_return"):
                        continue
                    actual = next(results)
                    self.assertEqual(actual["status"], step["status"])
                    self.assertEqual(actual["code"], step["code"])
                    self.assertEqual(actual["write_count"], step["writes"])
                    if "issue" in step:
                        self.assertIn(step["issue"], actual["reviews"][-1]["package"]["validation"]["issues"])
                    ids = [e["event_id"] for e in actual["events"]]
                    self.assertEqual(len(ids), len(set(ids)))
                    decisions = [r["decision"]["decision_id"] for r in actual["reviews"] if r["decision"]]
                    self.assertEqual(len(decisions), len(set(decisions)))

    def test_canonical_known_vector(self):
        self.assertEqual(canonical({"z":[None, True, 7],"a":"quote\"slash\\"}), '{"a":"quote\\"slash\\\\","z":[null,true,7]}')
        self.assertEqual(digest({"a":1}), "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862")

    def test_nondeterministic_value_types_refused(self):
        for value in (1.5, float("nan"), float("inf"), "é", "\n", 9007199254740992):
            with self.assertRaises(InvalidInput):
                canonical(value)

    def test_semantic_order_is_canonical(self):
        d = self.data
        one = build_package(d["request"], d["sources"], DEFAULT_CONTEXT, d["crm"])
        d["request"]["claims"].reverse()
        two = build_package(d["request"], d["sources"], dict(reversed(list(DEFAULT_CONTEXT.items()))), d["crm"])
        self.assertEqual(one, two)

    def test_malformed_claim_is_structured_refusal(self):
        for field in ([], {}, 2, None):
            d = copy.deepcopy(self.data)
            d["request"]["claims"][0]["field"] = field
            self.assertEqual(ReviewSession(**d).prepare()["code"], "INVALID_CLAIM")

    def test_review_copy_and_inputs_are_isolated(self):
        d = self.data
        s = ReviewSession(**d)
        v = s.prepare()
        original = copy.deepcopy(v)
        d["sources"][0]["observed_at"] = "2020-01-01"
        v["reviews"][0]["package"]["payload"]["company_id"] = "synthetic-company-forged"
        self.assertEqual(s.view(), original)
        self.assertEqual(s.view()["write_count"], 0)

    def test_partial_update_preserves_other_record_fields(self):
        d = self.data
        d["request"]["claims"] = [d["request"]["claims"][1]]
        s = ReviewSession(**d)
        r = s.prepare()["reviews"][-1]
        s.decide(r["review_id"], "approve", r["package"]["approval_digest"])
        v = s.execute(r["review_id"])
        self.assertEqual(v["local_crm"]["synthetic-company-001"], {"company_name": "Orchard Demo Co", "country": "GB", "open_roles": 2})

    def test_prior_review_stays_visible_after_new_snapshot(self):
        d = self.data
        s = ReviewSession(**d)
        v = s.prepare()
        old = copy.deepcopy(v["reviews"][0])
        d["sources"][0]["observed_at"] = "2026-10-15"
        s.replace_inputs(sources=d["sources"])
        v = s.prepare()
        self.assertEqual(v["reviews"][0], old)
        self.assertNotEqual(v["reviews"][1]["package"]["approval_digest"], old["package"]["approval_digest"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
