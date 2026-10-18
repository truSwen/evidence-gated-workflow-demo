# Evidence Review & Approval V2: validation and delivery

Date: **18 October 2026**. Base `main`: `fd091057ee3517b9152fcedfaecf765075d2a58a`. The initial worktree was clean and the repository had no open PRs. Baseline: 16 Python tests and 12 JavaScript port/parity tests passed before implementation.

## Scope and authorization

Implement, test, document and open a PR; no automatic merge. The later owner request additionally authorized a separate publicly hosted V2 demonstration. This is the standalone synthetic sample only; no other Tribloc system is modified.

The V2 Pages project is `tribloc-evidence-review`, using development branch `feat/evidence-review-approval-v2` as its production branch. The original `tribloc-evidence-workflow` project is not a deployment target for this change. Public demo hosting and merging the source PR are separate actions.

## Executed validation

| Gate | Result | Evidence |
| --- | --- | --- |
| Python regression, review and local HTTP adapter | 30 tests passed, including all 16 original tests and 42 shared V2 action sequences exercised as subtests | [Python report](v2-python-tests.txt), `test_demo.py`, `test_review.py`, `test_http.py` |
| JavaScript and build | 61 tests passed: 12 original port tests, 48 V2 tests (42 shared parity cases plus 6 focused checks), 1 build test | [JavaScript report](v2-javascript-tests.txt) |
| Full cross-language agreement | 42 V2 cases compare complete outputs, all digests, prior snapshots, events, decisions and state; original 11 scenarios still compare complete outputs | `review.test.js`, `browser-port.test.js`, `tests/review-cases.json` |
| Local browser checks | 47 checks across Python UI and the static build | [Browser check record](v2-browser-checks.json) |
| Build | Clean five-file static allowlist; shared HTML/CSS preserved; no backend fetch adapter bundled | `build.test.js`, `build.js` |
| Hosted browser checks | 8 passed on the live V2 site; four assets match the local build byte-for-byte and deployed CSP checked | [Hosted check record](v2-hosted-checks.json) |
| Whitespace, documentation links, private-data/secret patterns | Checked before commit | Delivery PR |

The 47 browser checks include 20 interactive cases across the two adapters, all 11 legacy scenarios on each adapter (22), one keyboard-driven prepare/acknowledge/approve/execute flow, one mobile layout and one desktop layout check, plus two final reload/digest checks. A long decision digest initially overflowed the 390px mobile view; wrapping was corrected and the final mobile applied state had equal viewport/document widths. The 1280px layout had two columns and no horizontal overflow.

The HTTP checks exercise actual loopback requests: no write on Prepare/Approve, explicit execution, source invalidation, session separation, foreign Host/Origin refusal, command-field refusal and the exact file-serving allowlist. These are development-runner checks, not a hardened server assessment.

## Verified properties within the synthetic sequential model

- Prepare and explicit Approve do not write; only explicit execution can apply.
- Rejected or missing approval cannot execute, and a rejected review cannot later be approved.
- Changes to payload, cited value, source set, URL, observed date, context/version or prior CRM record invalidate approval.
- Conflicting, unknown, stale, missing and invalid source evidence blocks approval.
- Wrong review IDs/digests and a different request cannot borrow approval.
- Re-execution does not add a second write; changed-content ID reuse is refused.
- Existing review packages stay available by copy; modifying exported copies cannot alter authorization state.
- A fresh snapshot requires a fresh review and decision. Earlier decisions retain their own IDs/statuses.
- JavaScript serializes asynchronous transitions and refuses input replacement mid-transition; this covers only one tab.
- Legacy scenario state is separate from the interactive session.

## Reviewable screenshots

These are captured from the running static build, not mockups:

- [Prepared review package](v2-review.png)
- [Changed evidence invalidates approval, zero writes](v2-invalidated.png)
- [Mobile applied receipt](v2-mobile.png)
- [Live V2 prepared package](v2-live-review.png)
- [Live V2 invalidation, zero writes](v2-live-invalidated.png)

## Remaining limits and review guidance

**No known open P0/P1 within the implemented demo scope was identified during these checks. This is a self-assessment, not an independent review or full security audit.** Before merge, request an independent review of `review.py`, `review.js`, the shared-case expectations and the UI decision path, especially the replay normalization of the prior-record snapshot.

The actor is simulated; neither the checkbox nor a hash authenticates a person or proves informed reading. Session/event identifiers are local, not global audit identities. Browser visitors control their own code and tab. All data, CRM writes and sources are synthetic. URL labels are never fetched. Consistency does not establish real-world truth. No durable ledger, database transaction, cross-process synchronization, distributed race/TOCTOU protection or crash recovery exists. There are no real integrations or credentials. The local server has bounded in-memory sessions and is for loopback development only.

## Deployment record

Live V2: **https://tribloc-evidence-review.pages.dev/**. The validated implementation commit is `91b1f27247fa9bd9687806fb958fe0968a25c4a5`; its deployment URL is https://baa18a39.tribloc-evidence-review.pages.dev. Later commits add delivery evidence only. Build assets were copied from `dist/` into an isolated upload directory, with `wrangler.review.jsonc` copied there as the default `wrangler.jsonc`. There is no Git-triggered automatic deployment in this change. The exact asset hashes and eight live browser checks are recorded in `v2-hosted-checks.json`. The original V1 site remains a separate demo.


Deployment tooling notes: the first upload attempt with a custom `--config` path was refused by Pages before upload. The isolated default-config upload succeeded. The first extra asset-comparison attempt with Python urllib could not use its local certificate store; the system curl comparison succeeded with TLS verification enabled. Neither failure was counted as a passing check or worked around by disabling TLS.
