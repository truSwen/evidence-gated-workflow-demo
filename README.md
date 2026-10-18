# Evidence Review & Approval V2

**[Try the synthetic V2 demo](https://tribloc-evidence-review.pages.dev/)** · [Original V1 demo](https://tribloc-evidence-workflow.pages.dev/)

Review **why** a field is proposed before approving **what** gets written. This small public portfolio sample presents a human-readable evidence package, records an explicit Approve or Reject decision, then rechecks the bound snapshot before one in-memory synthetic CRM update.

All companies, values, dates and sources are invented. Source agreement is fixture consistency, not proof of real-world truth. The decision is interactive, but the reviewer identity and CRM are simulated. No LLM, real CRM, MCP connection, external research, credentials or internal Tribloc code is involved.

## The interactive flow

1. **Reset session with fixture** chooses supported, conflicting, missing, stale or unknown evidence. Loading the page or choosing a fixture never approves or writes.
2. **Prepare & review** captures the proposed action, prior values, sources and validation context. Valid evidence reaches `AWAITING_APPROVAL` with zero writes. Invalid or uncertain evidence produces `BLOCKED` with per-field reasons and disabled decision controls.
3. Inspect each field's prior/proposed value, source value, cited ID, URL label, observed date and any other supplied assertion. Read the uncertainty, scope and limitations.
4. Acknowledge the exact displayed package, then choose **Approve**, or choose **Reject**. Approval records a decision only; it does not write. Rejection is terminal for that review.
5. **Execute approved local change** revalidates current inputs and compares the exact binding. A match writes once. A mismatch gives `INVALIDATED` and zero additional writes. A new snapshot requires a new review and decision.

The latest package is human-readable. Earlier packages remain in the expandable history. Returned documents are copies; modifying a displayed/exported copy does not change the session's approval state. Event, review and decision identifiers are deterministic and unique **within a session**, not globally unique identities or signatures.

## Evidence review package

`review.py` and `review.js` independently implement the same package:

- Exact request ID, synthetic company ID, tool/action and proposed fields.
- Prior record values (absence is shown as unknown/no prior value).
- Per-field cited source, supplied value, URL label and observation date.
- All supplied sources, including contradictory, missing-value, stale or invalid assertions relevant to proposed fields; none silently acts as corroboration.
- Per-field validation and explicit blocking reasons.
- Versioned policy, fixed reference date and freshness window.
- Exact one-write scope and remaining limitations.
- Payload, evidence, context and combined approval digests.

Only `crm.apply_local` is allowed. Supported fields are `company_name`, `country` and `open_roles`. Updates preserve unmentioned supported fields. Source URL labels must be bounded paths under `https://example.org/`; they are displayed as text and never fetched. Source freshness is relative to **17 October 2026**, with an inclusive 30-day default window. Unknown values are not negative facts. Supplied contradictory assertions block approval; this sample does not resolve them automatically or detect contradictions in natural language.

## Snapshot binding and canonicalization

```text
payload_digest  = SHA256(canonical(payload))
evidence_digest = SHA256(canonical(evidence_snapshot))
context_digest  = SHA256(canonical(validation_context))
approval_digest = SHA256(canonical({
    payload, evidence_snapshot, validation_context
}))
```

The evidence snapshot includes **all supplied sources and the prior company record**. The final digest hashes the complete structured binding, not concatenated hash strings. Changes to a proposed value, source value, source set, source URL, observed date, prior record or policy context invalidate the old decision. Matching field values alone cannot authorize a changed source snapshot.

The V2 canonical JSON domain is deliberately narrow: printable ASCII strings, safe integers up to `2^53-1` in magnitude, booleans, null, bounded arrays and plain objects. Floats, non-ASCII/control characters and unsupported values are refused. Zero is normalized to `0`. Object keys sort by ASCII order; separators are `,` and `:` with no spaces; JSON quote/backslash escaping is used; SHA-256 hashes UTF-8 bytes. Array order is preserved generally. The package builder sorts claims by unique field name and sources by unique source ID before hashing; duplicate fields/IDs are refused. Reordering those collections has no semantic effect. This is a documented demo subset, not a general JSON canonicalization standard.

An approved review becomes `APPLIED`, with its decision marked `CONSUMED`. Re-executing the same approved review checks the live payload, sources, context and applied record, then returns `REPLAYED` without another write. Reusing the request ID with different content is blocked. A newly prepared package after an application includes the now-changed prior record and cannot borrow the old decision. Reset deliberately starts an empty demonstration ledger.

## Run locally

Python 3.10+; standard library only:

```sh
python3 demo.py --serve --port 8765
```

Open **http://127.0.0.1:8765/**. This UI calls a session-owned Python review engine. The server binds only to loopback, serves an explicit asset list, refuses foreign Host/Origin values and caps command bodies. It is still a development runner, not an authenticated or hardened service. Up to 32 in-memory sessions are retained; the oldest can be evicted on a new reset. Restarting the runner clears all sessions. Reload creates a new session.

Programmatic Python use:

```python
from review import ReviewSession, review_fixture

session = ReviewSession(**review_fixture("valid"))
prepared = session.prepare()  # AWAITING_APPROVAL, zero writes
review = prepared["reviews"][-1]
# An application presents review["package"] before making this explicit decision.
session.decide(review["review_id"], "approve", review["package"]["approval_digest"])
result = session.execute(review["review_id"])
assert result["write_count"] == 1
```

This snippet simulates a caller's decision. It does not authenticate a human or prove that they read the package.

## Static browser build

Node.js 22+:

```sh
npm ci --ignore-scripts
npm run build
python3 -m http.server 8771 --bind 127.0.0.1 --directory dist
```

Open **http://127.0.0.1:8771/**. The built version runs entirely in the visitor's tab with no evaluation backend; reload resets all state. JavaScript serializes its asynchronous transitions and refuses input swaps during hashing. This is only in-tab sequential consistency, not protection against real distributed races.

Both versions serve the **same `index.html`, `style.css` and `app.js` UI**. Their `/entry.js` selects an explicit Python HTTP adapter or browser adapter. `build.js` bundles `browser-entry.js` and emits only HTML, stylesheet, bundle, headers and 404 page. It no longer extracts inline UI code or rewrites fetch calls with string replacement. A build test checks the clean asset allowlist and identical HTML/CSS.

The separate Pages project `tribloc-evidence-review` serves the V2 development branch. The repository's `main` branch and original V1 site are separate from that publication; public V2 hosting does not mean this PR was merged. Deployment details are recorded in [V2 validation and delivery](docs/V2_VALIDATION.md).

## Reproduce validation

```sh
python3 -m unittest -v
npm test
```

The V2 shared cases assert independently specified states, blocking codes and write counts, then compare **complete Python and JavaScript results**, including all packages, digests, decisions, events and CRM/ledger state. The original 16 Python tests and all 11 complete legacy scenario outputs remain regression checks. Negative cases cover missing/rejected approval, changed payload/source/snapshot/context, stale/invalid/unknown/conflicting evidence, wrong review/request binding, duplicate application, changed-content ID reuse and tampered return copies.

See [V2 validation and delivery](docs/V2_VALIDATION.md) for exact executed counts, browser evidence, remaining limits and review guidance. Historical V1 reports remain historical evidence, not current V2 test results.

## Three-minute demo path

- **0:00–0:45:** Reset with Supported changes. Prepare. Show the company/request, prior and proposed `open_roles` value, source URL/date, validation and uncertainty. The write counter stays zero.
- **0:45–1:20:** Acknowledge the package and Approve. Show the decision ID and zero writes. Execute; one local write appears. Execute again to show replay without a second write.
- **1:20–2:20:** Reset, Prepare, acknowledge and Approve. Click Change source observation date, then Execute. The old package still shows the reviewed date, but execution is `INVALIDATED` with zero writes. Prepare again; the new date and digest require a fresh acknowledgement and decision.
- **2:20–3:00:** Reset and Prepare, then Reject. Approval/execution become unavailable. Finally reset with Conflicting sources and Prepare: conflicting assertions are visible and approval is disabled.

Legacy automated scenarios are behind a separate disclosure. Their simulated approvals and isolated CRM state cannot authorize the V2 interactive session.

## Boundaries

This is a newly implemented public example, not extracted private project architecture or evidence of a client deployment. No real customer data, model results, authenticated reviewer, signature, CRM delivery or external research is claimed. In-memory checks do not establish durable idempotency, transactional atomicity, concurrency safety, cross-system TOCTOU protection or crash recovery. Browser users control their own tab and can edit code; the checkbox is an interaction aid, not an authentication/security boundary. Passing tests are bounded reproducible checks, not a full security audit.

Architecture, scope and acceptance direction: **Benjamin Zsigri**. Implementation assisted by AI.

[Discuss a scoped project on Contra](https://contra.com/benjamin_zsigri_g05naerx/services)
