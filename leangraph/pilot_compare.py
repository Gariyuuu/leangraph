"""Compare two runs of one configuration on the tasks both completed (used for dev-split pilots).

    python -m leangraph.pilot_compare pilot pilot_v2 --config direct

Descriptive only: pilots are small and exist to catch harness and prompt problems before test runs.
Harness-error traces are excluded (see analyze.load_traces); their counts are reported.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from . import analyze
from .errors import classify_attempt


def summarize(traces: dict[str, dict], ids: list[str]) -> dict:
    first = Counter()
    restated = 0
    for i in ids:
        atts = traces[i].get("attempts") or []
        if not atts:
            continue
        a = atts[0]
        first["VERIFIED" if (a.get("certificate") or {}).get("verified") else classify_attempt(a)["primary"]] += 1
        restated += ":= by" in (a.get("raw") or "")[:40]
    verified = sum(bool(traces[i].get("verified")) for i in ids)
    failed_first = sum(v for k, v in first.items() if k != "VERIFIED")
    return {"n": len(ids), "verified": verified, "first_error_classes": dict(first.most_common()),
            "lean3_share_of_first_errors": (first["lean3_syntax"] / failed_first) if failed_first else None,
            "replies_restating_assign_by": restated}


def compare(run_a: str, run_b: str, config: str) -> dict:
    ta = analyze.load_traces(run_a).get(config, {})
    err_a = analyze.HARNESS_ERRORS.get(config, 0)
    tb = analyze.load_traces(run_b).get(config, {})
    err_b = analyze.HARNESS_ERRORS.get(config, 0)
    common = sorted(set(ta) & set(tb))
    return {
        "config": config, "common_tasks": len(common),
        run_a: {**summarize(ta, common), "harness_errors_unresolved": err_a},
        run_b: {**summarize(tb, common), "harness_errors_unresolved": err_b},
        "solved_only_by": {run_a: [i for i in common if ta[i].get("verified") and not tb[i].get("verified")],
                           run_b: [i for i in common if tb[i].get("verified") and not ta[i].get("verified")]},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--config", default="direct")
    a = ap.parse_args()
    print(json.dumps(compare(a.run_a, a.run_b, a.config), indent=1))
