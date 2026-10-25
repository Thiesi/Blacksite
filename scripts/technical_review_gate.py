"""Merge gate for the technical review (docs/plan/04-technical-review.md §8).

Sets the commit status `technical-review` on a pull request's head from
the decision records posted on it. The gate enforces the procedure: a
current record recommending merge must exist for the exact head. It does
not review anything itself.

Run by `.github/workflows/technical-review-gate.yml` with `GH_TOKEN`,
`GITHUB_REPOSITORY` and `PR_NUMBER` set; `evaluate` is pure and tested.
"""

import json
import os
import re
import subprocess
import sys
from typing import Any

CONTEXT = "technical-review"
EXEMPT_LABEL = "no-technical-review"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
HEADING = re.compile(r"^## Technical review: .+ at ([0-9a-f]{40})\b")
RECOMMENDATION = re.compile(r"^\*\*Recommendation\.\*\*\s*(.+)$", re.MULTILINE)


def record_sha(body: str) -> str | None:
    """The head SHA a decision record names in its first line, if any."""
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    match = HEADING.match(first)
    return match.group(1) if match else None


def evaluate(head: str, labels: list[str], comments: list[dict[str, Any]]) -> tuple[str, str, str | None]:
    """(status state, description, URL of the deciding record)."""
    if EXEMPT_LABEL in labels:
        return "success", f"Exempt: labelled {EXEMPT_LABEL}", None
    records = [c for c in comments
               if c.get("association") in TRUSTED and not c.get("bot") and record_sha(c.get("body", ""))]
    current = [c for c in records if record_sha(c["body"]) == head]
    if not current:
        older = f"; last record is for {record_sha(records[-1]['body'])[:7]}" if records else ""
        return "pending", f"Awaiting a technical review of {head[:7]}{older}", None
    record = current[-1]
    match = RECOMMENDATION.search(record["body"])
    verdict = match.group(1).strip().lower() if match else ""
    if verdict.startswith("ready to merge"):
        return "success", f"Technical review of {head[:7]}: ready to merge", record.get("url")
    if verdict.startswith("changes required"):
        return "failure", f"Technical review of {head[:7]}: changes required", record.get("url")
    if verdict.startswith("awaiting"):
        return "pending", f"Technical review of {head[:7]}: awaiting evidence or approval", record.get("url")
    return "failure", f"Technical review of {head[:7]} has no recognised recommendation", record.get("url")


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    repo, number = os.environ["GITHUB_REPOSITORY"], os.environ["PR_NUMBER"]
    pr = json.loads(gh("api", f"repos/{repo}/pulls/{number}"))
    pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{repo}/issues/{number}/comments"))
    comments = [{"association": c["author_association"], "bot": c["user"]["type"] == "Bot",
                 "body": c["body"] or "", "url": c["html_url"]} for page in pages for c in page]
    head = pr["head"]["sha"]
    state, description, url = evaluate(head, [label["name"] for label in pr["labels"]], comments)
    url = url or f"https://github.com/{repo}/blob/main/docs/plan/04-technical-review.md"
    gh("api", f"repos/{repo}/statuses/{head}", "-f", f"state={state}", "-f", f"context={CONTEXT}",
       "-f", f"description={description[:140]}", "-f", f"target_url={url}")
    print(f"{head} {state}: {description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
