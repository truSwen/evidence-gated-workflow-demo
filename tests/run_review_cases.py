"""Shared action-sequence runner for full-result JS/Python parity."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review import DEFAULT_CONTEXT, ReviewSession
ROOT = Path(__file__).resolve().parent


def run_case(case):
    data = json.loads((ROOT.parent / "review-fixtures.json").read_text())
    data["context"] = copy.deepcopy(DEFAULT_CONTEXT)
    session = ReviewSession(data["request"], data["sources"], data["context"], data["crm"])
    results = []
    view = session.view()
    for action in case["steps"]:
        op = action["op"]
        rid = action.get("review_id", view["reviews"][-1]["review_id"] if view["reviews"] else "review-0001")
        if op == "mutate":
            target = data
            for key in action["path"][:-1]:
                target = target[key]
            target[action["path"][-1]] = copy.deepcopy(action["value"])
            session.replace_inputs(**data)
            continue
        if op == "tamper_return":
            view["reviews"][-1]["status"] = "APPROVED"
            view["reviews"][-1]["package"]["evidence_snapshot"]["sources"][0]["facts"]["open_roles"] = 100
            continue
        if op == "prepare":
            view = session.prepare()
        elif op in ("approve", "reject"):
            pack = view["reviews"][-1]["package"] if view["reviews"] else None
            fingerprint = action.get("digest", pack["approval_digest"] if pack else "missing")
            view = session.decide(rid, op, fingerprint)
        elif op == "execute":
            view = session.execute(rid)
        else:
            raise ValueError("Unknown test action")
        results.append(view)
    return results


if __name__ == "__main__":
    cases = json.loads((ROOT / "review-cases.json").read_text())
    print(json.dumps({case["name"]: run_case(case) for case in cases}, sort_keys=True))
