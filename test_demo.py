import unittest
from demo import AS_OF, digest, fixtures, permitted, run_scenario, workflow


class WorkflowTests(unittest.TestCase):
    def assert_blocked_without_write(self, scenario, code):
        result = run_scenario(scenario)
        self.assertEqual((result["status"], result["code"]), ("BLOCKED", code))
        self.assertEqual(result["write_count"], 0)
        self.assertEqual(result["local_crm"], {})
        self.assertEqual(result["ledger_entries"], 0)

    def test_validation_does_not_authorise_a_write(self):
        result = run_scenario("approval_required")
        self.assertEqual(result["status"], "AWAITING_APPROVAL")
        self.assertEqual(result["write_count"], 0)
        self.assertEqual(result["local_crm"], {})
        self.assertEqual(result["ledger_entries"], 0)

    def test_approved_payload_is_written_once(self):
        result = run_scenario("approved")
        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual(result["write_count"], 1)
        self.assertEqual(result["ledger_entries"], 1)
        self.assertEqual(result["local_crm"]["synthetic-company-001"]["open_roles"], 2)

    def test_missing_source_cannot_reach_write(self):
        self.assert_blocked_without_write("missing_source", "SOURCE_MISSING")

    def test_claim_must_match_the_cited_field(self):
        self.assert_blocked_without_write("unsupported_claim", "UNSUPPORTED_CLAIM")

    def test_out_of_scope_tool_cannot_reach_write(self):
        self.assert_blocked_without_write("forbidden_tool", "TOOL_DENIED")

    def test_stale_evidence_cannot_reach_write(self):
        self.assert_blocked_without_write("stale_evidence", "STALE_EVIDENCE")

    def test_approval_for_another_payload_is_rejected(self):
        self.assert_blocked_without_write("approval_mismatch", "APPROVAL_MISMATCH")

    def test_repeated_request_does_not_duplicate_write(self):
        result = run_scenario("replay")
        self.assertEqual(result["status"], "REPLAYED")
        self.assertEqual(result["write_count"], 0)
        self.assertEqual(result["total_writes"], 1)
        self.assertEqual(len(result["local_crm"]), 1)

    def test_reused_id_cannot_apply_a_changed_payload(self):
        result = run_scenario("conflict")
        self.assertEqual(result["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(result["total_writes"], 1)
        self.assertNotIn("synthetic-company-002", result["local_crm"])

    def test_transient_failure_recovers_inside_retry_budget(self):
        result = run_scenario("retry_success")
        self.assertEqual(result["status"], "APPLIED")
        attempts = [e for e in result["trace"] if e["event"] == "LOOKUP_ATTEMPT"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(result["write_count"], 1)

    def test_retry_exhaustion_is_bounded_and_does_not_write(self):
        self.assert_blocked_without_write("retry_exhausted", "RETRY_EXHAUSTED")
        result = run_scenario("retry_exhausted")
        self.assertEqual(sum(e["event"] == "LOOKUP_ATTEMPT" for e in result["trace"]), 2)

    def test_research_role_cannot_use_the_write_tool(self):
        self.assertTrue(permitted("researcher", "evidence.lookup"))
        self.assertFalse(permitted("researcher", "crm.apply_local"))
        self.assertFalse(permitted("unknown", "crm.apply_local"))

    def test_future_dated_evidence_is_rejected(self):
        data = fixtures()
        data["sources"][0]["observed_at"] = "2027-01-01"
        result = workflow(data["request"], data["sources"])
        self.assertEqual(result["code"], "STALE_EVIDENCE")
        self.assertEqual(result["local_crm"], {})

    def test_invalid_source_date_is_rejected(self):
        data = fixtures()
        data["sources"][0]["observed_at"] = "not-a-date"
        result = workflow(data["request"], data["sources"])
        self.assertEqual(result["code"], "INVALID_SOURCE_DATE")
        self.assertEqual(result["local_crm"], {})

    def test_missing_approval_actor_is_rejected(self):
        data = fixtures()
        result = workflow(data["request"], data["sources"], approval={"payload_digest": digest(data["request"])})
        self.assertEqual(result["code"], "APPROVAL_MISMATCH")
        self.assertEqual(result["local_crm"], {})

    def test_invalid_retry_budget_is_rejected(self):
        data = fixtures()
        for budget in (0, 4):
            with self.subTest(budget=budget):
                result = workflow(data["request"], data["sources"], max_attempts=budget)
                self.assertEqual(result["code"], "INVALID_RETRY_POLICY")
                self.assertEqual(result["local_crm"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
