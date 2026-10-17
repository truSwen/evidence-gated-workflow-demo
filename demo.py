"""Synthetic, deterministic workflow demo. Standard library only; no external APIs."""
import argparse
import copy
import hashlib
import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 17)
SCENARIOS = {
    "approval_required": "Approval required",
    "approved": "Approved local write",
    "missing_source": "Missing source",
    "unsupported_claim": "Unsupported claim",
    "forbidden_tool": "Out-of-scope tool",
    "stale_evidence": "Stale evidence",
    "retry_success": "Transient failure, then recovery",
    "retry_exhausted": "Retry limit reached",
    "replay": "Idempotent replay",
    "approval_mismatch": "Approval does not match payload",
    "conflict": "Request ID reused with changed payload",
}
ROLE_TOOLS = {
    "researcher": {"evidence.lookup"},
    "verifier": {"evidence.validate"},
    "operator": {"crm.apply_local"},
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def permitted(role, tool):
    return tool in ROLE_TOOLS.get(role, set())


def fixtures():
    return json.loads((ROOT / "fixtures.json").read_text())


def workflow(request, sources, *, approval=None, ledger=None, crm=None,
             transient_failures=0, max_attempts=2):
    """Run a bounded workflow. All writes affect only the supplied in-memory CRM."""
    if ledger is None:
        ledger = {}
    if crm is None:
        crm = {}
    trace = []
    fingerprint = digest(request)
    result = {"status": "REQUESTED", "code": "", "trace": trace,
              "payload_digest": fingerprint, "request": request,
              "reference_date": AS_OF.isoformat(), "write_count": 0,
              "evidence": sources, "synthetic": True}

    def step(role, event, detail):
        trace.append({"role": role, "event": event, "detail": detail})

    def stop(status, code, detail):
        result.update(status=status, code=code)
        step("controller", status, detail)
        result["local_crm"] = copy.deepcopy(crm)
        result["ledger_entries"] = len(ledger)
        return result

    step("controller", "REQUESTED", "Fixed synthetic request received; no external action.")
    if not permitted("operator", request.get("requested_tool")):
        return stop("BLOCKED", "TOOL_DENIED", "Requested tool is outside the operator allowlist.")
    step("controller", "SCOPED", "Only evidence lookup, validation and a local fixture write are allowed.")
    if max_attempts < 1 or max_attempts > 3:
        return stop("BLOCKED", "INVALID_RETRY_POLICY", "Retry budget must be between 1 and 3.")
    for attempt in range(1, max_attempts + 1):
        step("researcher", "LOOKUP_ATTEMPT", f"Synthetic lookup attempt {attempt}/{max_attempts}.")
        if attempt > transient_failures:
            break
    else:
        return stop("BLOCKED", "RETRY_EXHAUSTED", "No write: evidence lookup exhausted its retry budget.")
    step("researcher", "COLLECTED", "Loaded local fixture records; no websites were fetched.")

    by_id = {s["id"]: s for s in sources}
    for claim in request["claims"]:
        source = by_id.get(claim["source_id"])
        if not source or not source.get("source_url", "").startswith("https://"):
            return stop("BLOCKED", "SOURCE_MISSING", "A claim has no usable fixture source reference.")
        try:
            observed = date.fromisoformat(source["observed_at"])
        except (ValueError, KeyError, TypeError):
            return stop("BLOCKED", "INVALID_SOURCE_DATE", "The fixture source date is invalid.")
        age = (AS_OF - observed).days
        if not 0 <= age <= 30:
            return stop("BLOCKED", "STALE_EVIDENCE", "Evidence is outside the 30-day demo freshness window.")
        if source["facts"].get(claim["field"]) != claim["value"]:
            return stop("BLOCKED", "UNSUPPORTED_CLAIM", "Claim does not match its cited fixture field.")
    step("verifier", "VALIDATED", "References, field values and fixture dates match. This is consistency, not real-world truth validation.")
    if not approval:
        return stop("AWAITING_APPROVAL", "APPROVAL_REQUIRED", "Validation passed; the local fixture write remains blocked.")
    if approval.get("payload_digest") != fingerprint or not approval.get("actor"):
        return stop("BLOCKED", "APPROVAL_MISMATCH", "Approval is not bound to this exact payload.")
    step("controller", "APPROVED", "Local demo approval matches the payload digest; no identity authentication is performed.")
    previous = ledger.get(request["request_id"])
    if previous:
        if previous["digest"] != fingerprint:
            return stop("BLOCKED", "IDEMPOTENCY_CONFLICT", "This request ID already belongs to a different payload.")
        return stop("REPLAYED", "ALREADY_APPLIED", "The same request was already applied; no second write.")
    record = {c["field"]: c["value"] for c in request["claims"]}
    crm[request["company_id"]] = record
    ledger[request["request_id"]] = {"digest": fingerprint, "record": record}
    result["write_count"] = 1
    step("operator", "APPLIED", "One write to an in-memory synthetic CRM record. No external CRM was contacted.")
    return stop("APPLIED", "LOCAL_WRITE_ONLY", "Completed within the local demo boundary.")


def run_scenario(name):
    if name not in SCENARIOS:
        raise ValueError("Unknown scenario")
    data = fixtures()
    request, sources = data["request"], data["sources"]
    ledger, crm = {}, {}
    options = {}
    if name == "missing_source":
        sources[0]["source_url"] = ""
    elif name == "unsupported_claim":
        request["claims"][1]["value"] = 999
    elif name == "forbidden_tool":
        request["requested_tool"] = "email.send"
    elif name == "stale_evidence":
        sources[0]["observed_at"] = "2020-01-01"
    elif name in {"retry_success", "retry_exhausted"}:
        options["transient_failures"] = 1 if name == "retry_success" else 3
    approval = None if name == "approval_required" else {
        "actor": "synthetic-demo-reviewer", "payload_digest": digest(request)}
    if name == "approval_mismatch":
        approval["payload_digest"] = "does-not-match"
    first = None
    if name in {"replay", "conflict"}:
        first = workflow(request, sources, approval=approval, ledger=ledger, crm=crm)
        if name == "conflict":
            request = copy.deepcopy(request)
            request["company_id"] = "synthetic-company-002"
            approval = {"actor": "synthetic-demo-reviewer", "payload_digest": digest(request)}
    result = workflow(request, sources, approval=approval, ledger=ledger, crm=crm, **options)
    result.update(scenario=name, title=SCENARIOS[name], total_writes=(first or {}).get("write_count", 0) + result["write_count"])
    if first:
        result["previous_run"] = {"status": first["status"], "write_count": first["write_count"]}
    return result


class Handler(BaseHTTPRequestHandler):
    def send(self, status, content, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path in {"/", "/index.html"}:
            self.send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self.send(404, b"Not found", "text/plain")

    def do_POST(self):
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if self.path != "/api/run" or self.headers.get("Origin") not in allowed | {None}:
            self.send(403, b"Forbidden", "text/plain")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2048 or self.headers.get("Content-Type") != "application/json":
                raise ValueError("Invalid request")
            name = json.loads(self.rfile.read(size))["scenario"]
            result = run_scenario(name)
        except (ValueError, KeyError, TypeError):
            self.send(400, b"Invalid scenario request", "text/plain")
            return
        self.send(200, json.dumps(result).encode(), "application/json")

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="approval_required")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.serve:
        server = HTTPServer(("127.0.0.1", args.port), Handler)
        print(f"Local synthetic demo: http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
    else:
        print(json.dumps(run_scenario(args.scenario), indent=2))
