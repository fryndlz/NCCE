"""Durable request-scoped checkpoints for the trusted Historical Backfill relay."""
from hashlib import sha256
import json
import re

import exchange_automation as exchange
from writing_exchange import digest, packed

PROTOCOL = 1
CHECKS = ("mechanics", "chronology", "lore", "character", "style", "format", "length")
PHASES = {"draft", "review", "approved", "hold"}
MAX_DRAFTS = 3
MAX_REVIEWS = 9
_HASH = re.compile(r"[a-f0-9]{64}")
_HEADING = re.compile(r"\A\*\*(\S[^\r\n*]*?)\*\*[ \t]*\r?\n[ \t]*\r?\n([\s\S]*\S)\s*\Z")


def draft_hash(text):
    return sha256(text.encode("utf-8")).hexdigest()


def checkpoint(store, request_id):
    record = store.db.execute(
        """SELECT version,checkpoint_json FROM historical_backfill_qa
           WHERE request_id=? ORDER BY version DESC LIMIT 1""",
        (request_id,),
    ).fetchone()
    if record is None:
        return {"version": 0, "state": None}
    return {"version": record["version"], "state": json.loads(record["checkpoint_json"])}


def dispatch(store, packet):
    return {**packet, "qa_protocol": PROTOCOL, "context_hash": digest(packet["context"]),
            "checkpoint": checkpoint(store, packet["request"]["request_id"])}


def _passing_checks(checks):
    return (isinstance(checks, dict) and set(checks) == set(CHECKS)
            and all(isinstance(reason, str) and 0 < len(reason.strip()) <= 500
                    for reason in checks.values()))


def _format_valid(form, draft):
    match = _HEADING.fullmatch(draft)
    if not match:
        return False
    if form == "fighter_memory":
        return len(draft) <= 350
    return form == "fighter_reflection" and 60 <= len(match[2].split()) <= 130


def _validate_state(state, item, previous):
    if not isinstance(state, dict) or state.get("phase") not in PHASES:
        raise ValueError("Invalid bulk QA checkpoint phase")
    allowed = {"phase", "draft", "original", "issues", "draft_attempts", "review_attempts",
               "retry_at", "error", "context_hash", "guidance_hash", "checks", "draft_hash"}
    if set(state) - allowed or len(packed(state).encode("utf-8")) > 85000:
        raise ValueError("Invalid bulk QA checkpoint data")
    for key in ("draft", "original", "error"):
        if not isinstance(state.get(key, ""), str) or len(state.get(key, "")) >= 30000:
            raise ValueError("Invalid saved bulk draft or error")
    for key, limit in (("draft_attempts", MAX_DRAFTS), ("review_attempts", MAX_REVIEWS)):
        value = state.get(key)
        if type(value) is not int or not previous.get(key, 0) <= value <= limit:
            raise ValueError("Invalid or decreasing bulk attempt counter")
    due = state.get("retry_at", 0)
    issues = state.get("issues", [])
    if (type(due) is not int or due < 0 or not isinstance(issues, list) or len(issues) > 20
            or any(not isinstance(issue, str) or len(issue) > 1000 for issue in issues)):
        raise ValueError("Invalid bulk retry checkpoint")
    if previous and state.get("original", "") != previous.get("original", ""):
        raise ValueError("Original draft is immutable")
    if previous.get("phase") == "approved":
        raise ValueError("An approved checkpoint is immutable")
    if state["phase"] == "hold" and not state.get("error"):
        raise ValueError("HOLD requires an actionable reason")
    if state["phase"] != "approved":
        return
    draft = state.get("draft", "")
    if (previous.get("phase") != "review" or previous.get("draft") != draft
            or state["review_attempts"] < 1
            or state["review_attempts"] != previous.get("review_attempts")
            or state.get("issues") or not _format_valid(item["form"], draft)
            or state.get("draft_hash") != draft_hash(draft)
            or not isinstance(state.get("guidance_hash"), str)
            or not _HASH.fullmatch(state["guidance_hash"])
            or previous.get("guidance_hash") != state["guidance_hash"]
            or not _passing_checks(state.get("checks"))):
        raise ValueError("Approval requires all seven checks for the exact reviewed draft and guidance")


def save(store, payload):
    with store._lock:
        item = store.db.execute(
            """SELECT i.*,j.state AS job_state FROM historical_backfill_items i
               JOIN historical_backfill_jobs j USING(job_id)
               WHERE i.job_id=? AND i.request_id=?""",
            (payload.get("job_id"), payload.get("request_id")),
        ).fetchone()
        if not item or item["job_state"] != "ACTIVE" or item["state"] != "WRITING":
            raise ValueError("Only dispatched items in an active bulk job accept QA checkpoints")
        if payload.get("source_revision") != item["source_revision"]:
            raise ValueError("QA checkpoint source revision does not match")
        packet = json.loads(item["packet_json"])
        state = payload.get("state")
        if not isinstance(state, dict) or state.get("context_hash") != digest(packet["context"]):
            raise ValueError("QA checkpoint context hash does not match")
        current = checkpoint(store, item["request_id"])
        if type(payload.get("version")) is not int or payload["version"] != current["version"]:
            return {"status": "stale", **current}
        _validate_state(state, item, current["state"] or {})
        version = current["version"] + 1
        if state["phase"] == "approved":
            candidate = json.loads(item["snapshot_json"])["target"]
            title_error = exchange.fighter_memory_title_error(store, candidate, state["draft"])
            if title_error:
                raise ValueError(title_error)
        with store.db:
            store.db.execute(
                "INSERT INTO historical_backfill_qa VALUES(?,?,?,?)",
                (item["request_id"], version, packed(state), exchange.now()),
            )
            if state["phase"] == "hold":
                store.db.execute(
                    """UPDATE historical_backfill_items SET state='HOLD',writer_text_md=?,error=?
                       WHERE request_id=?""",
                    (state.get("draft") or state.get("original", ""), state["error"], item["request_id"]),
                )
        return {"status": "saved", "version": version}


def approved(store, packet, draft):
    review = checkpoint(store, packet["request"]["request_id"])["state"]
    return bool(review and review["phase"] == "approved"
                and review["context_hash"] == digest(packet["context"])
                and review.get("draft_hash") == draft_hash(draft)
                and review.get("draft") == draft
                and _passing_checks(review.get("checks")))
