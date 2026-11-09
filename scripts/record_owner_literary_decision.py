"""Version a scoped owner-approved NCCE prose finding, never by hidden memory.

This operator runs only when the owner explicitly establishes a durable change
and an agent has ALREADY edited and reviewed the relevant source file(s).
It records the decision, verifies edited files exist, bumps the machine policy
version, and creates a new commit-ready change. Git commit/deploy/repackaging
are separate explicit steps.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from literary_policy import validate_policy

SCOPES = ("universal", "form", "genre", "faction", "gang", "individual", "workflow")
POLICY = ROOT / "config" / "literary_profiles.v2.json"
CHANGELOG = ROOT / "skills" / "ncce-prose-portability" / "CHANGELOG.md"
DECISIONS = ROOT / "skills" / "ncce-prose-portability" / "decisions.jsonl"


def record_owner_decision(*, root=ROOT, expected_version, new_version,
                          scope, decision, source, changed_files):
    root = Path(root).resolve()
    if scope not in SCOPES:
        raise ValueError("Unknown rule scope")
    if not decision.strip() or not source.strip() or not changed_files:
        raise ValueError("Need owner's explicit decision, source and edited files")
    current = root / "config" / "literary_profiles.v2.json"
    data = json.loads(current.read_text(encoding="utf-8"))
    validate_policy(data)
    if data["policy_version"] != expected_version or not new_version or new_version == expected_version:
        raise ValueError("Version mismatch or missing version bump")
    old = tuple(int(s) for s in expected_version.split("."))
    nxt = tuple(int(s) for s in new_version.split("."))
    if len(old) != 3 or len(nxt) != 3 or nxt <= old:
        raise ValueError("New version must be a higher semantic version")
    references = []
    for name in changed_files:
        path = (root / name).resolve()
        if (root not in path.parents or not path.is_file() or
            name in ("config/literary_profiles.v2.json",
                     "skills/ncce-prose-portability/CHANGELOG.md",
                     "skills/ncce-prose-portability/decisions.jsonl")):
            raise ValueError("Missing/unsafe/non-independent changed reference: " + name)
        references.append({"file": name, "sha256": sha256(path.read_bytes()).hexdigest()})
    item = {"at": datetime.now(timezone.utc).isoformat(), "kind": "owner_authoritative_decision",
            "scope": scope, "source": source.strip(), "decision": decision.strip(),
            "supersedes_version": expected_version, "new_version": new_version,
            "edited_references": references,
            "note": "Written by an explicitly invoked operator. Review the Git diff and rebuild the ZIP."}
    data["policy_version"] = new_version
    validate_policy(data)
    changelog_path = root / "skills/ncce-prose-portability/CHANGELOG.md"
    decision_path = root / "skills/ncce-prose-portability/decisions.jsonl"
    if not changelog_path.is_file():
        raise ValueError("Changelog missing")
    old_changelog = changelog_path.read_text(encoding="utf-8")
    # Build complete output before committing any of it.
    lines = f"\n## {new_version} — {item['at'][:10]} — {scope}\n\n- {decision.strip()}\n- Owner source: {source.strip()}\n- Supersedes {expected_version}; edited references: {', '.join(x['file'] for x in references)}.\n"
    current.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    changelog_path.write_text(old_changelog + lines, encoding="utf-8")
    with decision_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-version", required=True)
    p.add_argument("--new-version", required=True)
    p.add_argument("--scope", choices=SCOPES, required=True)
    p.add_argument("--decision", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--changed-file", action="append", required=True)
    args = p.parse_args()
    result=record_owner_decision(expected_version=args.expected_version,
        new_version=args.new_version, scope=args.scope, decision=args.decision,
        source=args.source, changed_files=args.changed_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
