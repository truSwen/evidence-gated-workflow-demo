"""V2 synthetic review state machine. No network, authentication or persistent writes."""
import copy
import hashlib
import json
import re
from datetime import date

FIELDS = ("company_name", "country", "open_roles")
DEFAULT_CONTEXT = {
    "policy_version": "evidence-review-v2.1", "reference_date": "2026-10-17",
    "max_age_days": 30, "allowed_tool": "crm.apply_local", "synthetic": True,
}
LIMITS = [
    "All companies, sources, values and CRM records are synthetic; URLs are never fetched.",
    "Consistency with fixture records does not establish real-world truth.",
    "The decision is interactive; the reviewer identity is simulated, not authenticated or signed.",
    "In-memory sequential execution only: no durable ledger, atomic transaction or concurrency guarantee.",
]


class InvalidInput(ValueError):
    pass


def canonical(value):
    """Bounded V2 JSON subset: printable ASCII strings, safe integers, bool/null, arrays/objects.

    Sorted ASCII object keys; array order preserved. No floats, Unicode, control chars,
    implicit type coercion. Semantic collections are sorted by the builder.
    """
    def check(v, depth=0):
        if depth > 12:
            raise InvalidInput("INVALID_INPUT")
        if v is None or type(v) is bool:
            return
        if type(v) is int and abs(v) <= 9007199254740991:
            return
        if isinstance(v, str) and len(v) <= 500 and all(32 <= ord(c) <= 126 for c in v):
            return
        if type(v) is list and len(v) <= 100:
            for item in v:
                check(item, depth + 1)
            return
        if type(v) is dict and len(v) <= 100:
            for k, item in v.items():
                if not isinstance(k, str) or not k or len(k) > 500 or not all(32 <= ord(c) <= 126 for c in k):
                    raise InvalidInput("INVALID_INPUT")
                check(item, depth + 1)
            return
        raise InvalidInput("INVALID_INPUT")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def exact(value, keys):
    return type(value) is dict and set(value) == set(keys)


def identifier(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r"[A-Za-z0-9-]{1,60}", value) is not None


def valid_date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value and len(value) == 10
    except (ValueError, TypeError):
        return False


def valid_record(record):
    return type(record) is dict and set(record) <= set(FIELDS) and all(valid_value(k, v) for k, v in record.items())


def valid_value(field, value):
    if value is None:
        return True
    if field == "open_roles":
        return type(value) is int and 0 <= value <= 10000
    return isinstance(value, str) and 0 < len(value) <= 100


def build_package(request, sources, context, crm):
    """Return an immutable-by-copy review document, or a structured refusal."""
    canonical({"request": request, "sources": sources, "context": context, "crm": crm})
    if not exact(request, ("request_id", "company_id", "requested_tool", "claims")):
        raise InvalidInput("INVALID_REQUEST")
    if not identifier(request["request_id"], "demo-request-") or not identifier(request["company_id"], "synthetic-company-"):
        raise InvalidInput("INVALID_REQUEST")
    if not exact(context, DEFAULT_CONTEXT) or context["synthetic"] is not True or not valid_date(context["reference_date"]) or type(context["max_age_days"]) is not int or not 0 <= context["max_age_days"] <= 90 or not isinstance(context["policy_version"], str) or not context["policy_version"] or context["allowed_tool"] != "crm.apply_local":
        raise InvalidInput("INVALID_CONTEXT")
    if type(sources) is not list or len(sources) > 10 or type(request["claims"]) is not list or not 1 <= len(request["claims"]) <= 3:
        raise InvalidInput("INVALID_REQUEST")
    claims = copy.deepcopy(request["claims"])
    if any(not exact(c, ("field", "value", "source_id")) or c["field"] not in FIELDS or not valid_value(c["field"], c["value"]) or not identifier(c["source_id"], "fixture-source-") for c in claims):
        raise InvalidInput("INVALID_CLAIM")
    claims.sort(key=lambda c: c["field"])
    if len({c["field"] for c in claims}) != len(claims):
        raise InvalidInput("DUPLICATE_FIELD")
    if any(not exact(s, ("id", "source_url", "observed_at", "facts")) or not identifier(s["id"], "fixture-source-") or not isinstance(s["source_url"], str) or not isinstance(s["observed_at"], str) or not valid_record(s["facts"]) for s in sources):
        raise InvalidInput("INVALID_SOURCE")
    if len({s["id"] for s in sources}) != len(sources):
        raise InvalidInput("DUPLICATE_SOURCE")
    if type(crm) is not dict or any(not identifier(k, "synthetic-company-") or not valid_record(v) for k, v in crm.items()):
        raise InvalidInput("INVALID_CRM")
    payload = copy.deepcopy(request)
    payload["claims"] = claims
    snapshot = {"sources": sorted(copy.deepcopy(sources), key=lambda s: s["id"]),
                "previous_record": copy.deepcopy(crm.get(request["company_id"], {}))}
    rows, issues = [], []
    if request["requested_tool"] != context["allowed_tool"]:
        issues.append("TOOL_DENIED")
    by_id = {s["id"]: s for s in sources}
    for c in claims:
        source = by_id.get(c["source_id"])
        code = "SUPPORTED"
        if not source:
            code = "MISSING_SOURCE"
        elif not re.fullmatch(r"https://example\.org/[A-Za-z0-9/_-]{1,120}", source["source_url"]):
            code = "INVALID_SOURCE_URL"
        elif not valid_date(source["observed_at"]):
            code = "INVALID_SOURCE_DATE"
        elif not 0 <= (date.fromisoformat(context["reference_date"]) - date.fromisoformat(source["observed_at"])).days <= context["max_age_days"]:
            code = "STALE_EVIDENCE"
        elif c["value"] is None or source["facts"].get(c["field"]) is None:
            code = "UNKNOWN_VALUE"
        elif source["facts"][c["field"]] != c["value"]:
            code = "UNSUPPORTED_CLAIM"
        # Any supplied source asserting a different value for this field prevents approval.
        # Malformed/old additional assertions cannot silently be ignored as corroboration.
        relevant = [s for s in snapshot["sources"] if c["field"] in s["facts"]]
        for other in relevant:
            if code != "SUPPORTED":
                break
            if not re.fullmatch(r"https://example\.org/[A-Za-z0-9/_-]{1,120}", other["source_url"]):
                code = "INVALID_SOURCE_URL"
            elif not valid_date(other["observed_at"]):
                code = "INVALID_SOURCE_DATE"
            elif not 0 <= (date.fromisoformat(context["reference_date"]) - date.fromisoformat(other["observed_at"])).days <= context["max_age_days"]:
                code = "STALE_EVIDENCE"
            elif other["facts"][c["field"]] is None:
                code = "UNKNOWN_VALUE"
            elif other["facts"][c["field"]] != c["value"]:
                code = "CONFLICTING_EVIDENCE"
        if code != "SUPPORTED":
            issues.append(code)
        rows.append({"field": c["field"], "previous_value": snapshot["previous_record"].get(c["field"]),
                     "proposed_value": c["value"], "source_id": c["source_id"],
                     "source_url": source["source_url"] if source else None,
                     "observed_at": source["observed_at"] if source else None,
                     "source_value": source["facts"].get(c["field"]) if source else None,
                     "validation": code, "supporting_assertions": relevant})
    binding = {"payload": payload, "evidence_snapshot": snapshot, "validation_context": copy.deepcopy(context)}
    return {"synthetic": True, **binding, "payload_digest": digest(payload),
            "evidence_digest": digest(snapshot), "context_digest": digest(context),
            "approval_digest": digest(binding), "fields": rows,
            "validation": {"valid": not issues, "issues": sorted(set(issues))},
            "scope": "Apply exactly the proposed fields to this synthetic company once; preserve other fields. No external action.",
            "limitations": list(LIMITS)}


class ReviewSession:
    """Session-owned review/decision records. Returned copies are not authorization state."""
    def __init__(self, request, sources, context=None, crm=None):
        self._request, self._sources = copy.deepcopy(request), copy.deepcopy(sources)
        self._context = copy.deepcopy(DEFAULT_CONTEXT if context is None else context)
        self._crm = copy.deepcopy({} if crm is None else crm)
        self._ledger, self._reviews, self._events = {}, {}, []
        self._decisions, self._writes = 0, 0
        self._last = {"status": "READY", "code": "NOT_PREPARED"}

    def replace_inputs(self, *, request=None, sources=None, context=None, crm=None):
        # Test/demo adapter only. It never replaces an existing review package.
        for key, value in (("_request", request), ("_sources", sources), ("_context", context), ("_crm", crm)):
            if value is not None:
                setattr(self, key, copy.deepcopy(value))

    def _event(self, review_id, status, code):
        self._events.append({"event_id": f"event-{len(self._events)+1:04d}", "review_id": review_id, "status": status, "code": code})
        self._last = {"status": status, "code": code}
        return self.view()

    def _package(self):
        return build_package(self._request, self._sources, self._context, self._crm)

    def prepare(self):
        rid = f"review-{len(self._reviews)+1:04d}"
        try:
            package = self._package()
        except InvalidInput as e:
            self._reviews[rid] = {"review_id": rid, "status": "BLOCKED", "package": None, "decision": None}
            return self._event(rid, "BLOCKED", str(e))
        previous = self._ledger.get(package["payload"]["request_id"])
        conflict = previous and previous["approval_digest"] != package["approval_digest"]
        # The previous-record snapshot changes after a successful application. Replays
        # use the original approved review, never a newly prepared package.
        status = "BLOCKED" if conflict or not package["validation"]["valid"] else "AWAITING_APPROVAL"
        self._reviews[rid] = {"review_id": rid, "status": status, "package": package, "decision": None}
        return self._event(rid, status, "IDEMPOTENCY_CONFLICT" if conflict else "REVIEW_READY" if status == "AWAITING_APPROVAL" else "EVIDENCE_BLOCKED")

    def _invalidate(self, review, code):
        review["status"] = "INVALIDATED"
        if review["decision"]:
            review["decision"]["status"] = "INVALIDATED"
        return self._event(review["review_id"], "INVALIDATED", code)

    def _matches(self, review):
        try:
            current = self._package()
            return current["validation"]["valid"] and current["approval_digest"] == review["package"]["approval_digest"]
        except InvalidInput:
            return False

    def decide(self, review_id, choice, reviewed_digest):
        review = self._reviews.get(review_id)
        if not review or review["status"] != "AWAITING_APPROVAL" or choice not in ("approve", "reject"):
            return self._event(review_id, "BLOCKED", "INVALID_TRANSITION")
        if reviewed_digest != review["package"]["approval_digest"] or not self._matches(review):
            return self._invalidate(review, "REVIEW_CHANGED")
        self._decisions += 1
        status = "APPROVED" if choice == "approve" else "REJECTED"
        review["status"] = status
        review["decision"] = {"decision_id": f"decision-{self._decisions:04d}", "review_id": review_id,
                              "status": status, "choice": choice, "approval_digest": reviewed_digest,
                              "actor": "simulated-interactive-reviewer"}
        return self._event(review_id, status, "EXPLICIT_APPROVAL" if choice == "approve" else "EXPLICIT_REJECTION")

    def execute(self, review_id):
        review = self._reviews.get(review_id)
        if not review or review["status"] not in ("APPROVED", "APPLIED"):
            return self._event(review_id, "BLOCKED", "APPROVAL_REQUIRED")
        package = review["package"]
        previous = self._ledger.get(package["payload"]["request_id"])
        if previous:
            # A changed live payload/evidence/context must not pass as a replay.
            try:
                current = self._package()
                original = copy.deepcopy(current)
                original["evidence_snapshot"]["previous_record"] = package["evidence_snapshot"]["previous_record"]
                binding = {k: original[k] for k in ("payload", "evidence_snapshot", "validation_context")}
                matches = (current["validation"]["valid"] and digest(binding) == package["approval_digest"]
                           and canonical(self._crm.get(package["payload"]["company_id"])) == canonical(previous["record"]))
            except InvalidInput:
                matches = False
            if previous["approval_digest"] != package["approval_digest"] or not matches:
                return self._invalidate(review, "IDEMPOTENCY_CONFLICT")
            return self._event(review_id, "REPLAYED", "ALREADY_APPLIED")
        if not self._matches(review):
            return self._invalidate(review, "REVIEW_CHANGED")
        request = package["payload"]
        record = copy.deepcopy(self._crm.get(request["company_id"], {}))
        record.update({c["field"]: c["value"] for c in request["claims"]})
        self._crm[request["company_id"]] = record
        self._ledger[request["request_id"]] = {"approval_digest": package["approval_digest"], "decision_id": review["decision"]["decision_id"], "record": copy.deepcopy(record)}
        self._writes += 1
        review["status"] = "APPLIED"
        review["decision"]["status"] = "CONSUMED"
        return self._event(review_id, "APPLIED", "LOCAL_WRITE_ONLY")

    def view(self):
        return copy.deepcopy({**self._last, "synthetic": True, "write_count": self._writes,
                              "local_crm": self._crm, "ledger": self._ledger,
                              "reviews": list(self._reviews.values()), "events": self._events})


def review_fixture(name):
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parent / "review-fixtures.json").read_text())
    data["context"] = copy.deepcopy(DEFAULT_CONTEXT)
    if name == "missing":
        data["sources"] = []
    elif name == "stale":
        data["sources"][0]["observed_at"] = "2020-01-01"
    elif name == "unknown":
        data["sources"][0]["facts"]["open_roles"] = None
    elif name == "conflict":
        data["sources"].append({"id": "fixture-source-002", "source_url": "https://example.org/second-fixture", "observed_at": "2026-10-16", "facts": {"open_roles": 5}})
    elif name != "valid":
        raise InvalidInput("INVALID_FIXTURE")
    return data
