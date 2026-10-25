from scripts.technical_review_gate import evaluate, record_sha

HEAD = "a" * 40
OLD = "b" * 40


def record(sha: str, recommendation: str, association: str = "OWNER", bot: bool = False) -> dict:
    body = (f"## Technical review: S25 at {sha}\n\nBase x.\n\n"
            f"**Recommendation.** {recommendation}\n")
    return {"association": association, "bot": bot, "body": body, "url": f"https://example/{sha[:3]}"}


def test_no_record_is_pending() -> None:
    assert evaluate(HEAD, [], [])[0] == "pending"


def test_record_for_head_recommending_merge_passes() -> None:
    state, description, url = evaluate(HEAD, [], [record(HEAD, "Ready to merge.")])
    assert state == "success" and "ready to merge" in description and url == "https://example/aaa"


def test_record_for_an_older_head_does_not_count() -> None:
    state, description, _ = evaluate(HEAD, [], [record(OLD, "Ready to merge.")])
    assert state == "pending" and "bbbbbbb" in description


def test_latest_record_for_head_decides() -> None:
    comments = [record(HEAD, "Ready to merge."), record(HEAD, "Changes required: TR-1.")]
    assert evaluate(HEAD, [], comments)[0] == "failure"
    assert evaluate(HEAD, [], comments[::-1])[0] == "success"


def test_awaiting_evidence_stays_pending() -> None:
    assert evaluate(HEAD, [], [record(HEAD, "Awaiting evidence or approval.")])[0] == "pending"


def test_record_without_recommendation_fails() -> None:
    body = f"## Technical review: S25 at {HEAD}\n\nNo verdict.\n"
    assert evaluate(HEAD, [], [{"association": "OWNER", "bot": False, "body": body}])[0] == "failure"


def test_bots_and_outsiders_cannot_pass_the_gate() -> None:
    assert evaluate(HEAD, [], [record(HEAD, "Ready to merge.", bot=True)])[0] == "pending"
    assert evaluate(HEAD, [], [record(HEAD, "Ready to merge.", association="NONE")])[0] == "pending"


def test_exempt_label_passes() -> None:
    assert evaluate(HEAD, ["no-technical-review"], [])[0] == "success"


def test_heading_must_be_the_first_line_and_name_a_full_sha() -> None:
    assert record_sha(f"\n## Technical review: S25 at {HEAD}\n") == HEAD
    assert record_sha(f"Quote:\n## Technical review: S25 at {HEAD}\n") is None
    assert record_sha("## Technical review: S25 at abc1234\n") is None
