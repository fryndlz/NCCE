"""Manage editorial NCCE voice tags without changing application Python or campaign DB.

Usage:
    python scripts/voice_registry_cli.py validate
    python scripts/voice_registry_cli.py list
    python scripts/voice_registry_cli.py register --gang "Patrol ..." --faction "Palanite Enforcers" --source "Owner-authored gang backstory"
    python scripts/voice_registry_cli.py approve --gang "Patrol ..." --register "..." --tags precinct,customs --source "Approved editorial brief"
    python scripts/voice_registry_cli.py add-fighter --gang "Patrol ..." --fighter "..." --register "..." --tags ... --source "..."
All changes are made to a versioned JSON source file and require deployment to
affect newly prepared NCCE packets; accepted/in-flight prose is never rewritten.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from voice_layers import REGISTRY_PATH, validate_registry


def split_tags(value):
    tags = [x.strip() for x in (value or "").split(",") if x.strip()]
    if len(tags) != len(set(tags)):
        raise ValueError("Duplicate tags")
    return tags


def update_registry(path, operation, **kwargs):
    path = Path(path)
    data = validate_registry(json.loads(path.read_text(encoding="utf-8")))
    new = deepcopy(data)
    gang = kwargs.get("gang", "").strip()
    source = kwargs.get("source", "").strip()
    if operation == "register":
        if not gang or not kwargs.get("faction", "").strip() or not source:
            raise ValueError("A gang name, roster faction and cited source are required")
        if gang in new["gangs"] or gang in new["aliases"]:
            raise ValueError("Gang already registered")
        new["gangs"][gang] = {
            "faction": kwargs["faction"].strip(), "tags": [],
            "register": "", "source": source,
            "provenance": "owner_submitted_pending_review",
            "review_status": "pending_editorial",
        }
        new["excluded_gangs"] = [name for name in new["excluded_gangs"] if name != gang]
    elif operation == "approve":
        if gang not in new["gangs"]:
            raise ValueError("Register this gang first")
        if not kwargs.get("register", "").strip() or not source:
            raise ValueError("Approved gang register and citation required")
        profile = new["gangs"][gang]
        profile.update({
            "register": kwargs["register"].strip(),
            "tags": split_tags(kwargs.get("tags", "")),
            "source": source,
            "provenance": "owner_editorial_approved",
            "review_status": "approved",
        })
    elif operation == "add-fighter":
        if gang not in new["gangs"] or new["gangs"][gang].get("review_status") != "approved":
            raise ValueError("Approve gang profile before adding fighters")
        fighter = kwargs.get("fighter", "").strip()
        if not fighter or not kwargs.get("register", "").strip() or not source:
            raise ValueError("Fighter, register and cited source required")
        key = gang + "::" + fighter
        if key in new["individuals"]:
            raise ValueError("Fighter already has a profile; update with reviewed revision instead")
        new["individuals"][key] = {
            "tags": split_tags(kwargs.get("tags", "")),
            "register": kwargs["register"].strip(),
            "source": source, "provenance": "owner_editorial_approved",
            "review_status": "approved",
        }
    else:
        raise ValueError("Unknown operation")
    validate_registry(new)
    # Registry changes are staged in a Git branch and explicitly reviewed.
    # The app never modifies its own policy data on a campaign refresh.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("validate")
    subs.add_parser("list")
    for name in ("register", "approve", "add-fighter"):
        p = subs.add_parser(name)
        p.add_argument("--gang", required=True)
        p.add_argument("--source", required=True)
        if name == "register":
            p.add_argument("--faction", required=True)
        else:
            p.add_argument("--register", required=True)
            p.add_argument("--tags", default="")
        if name == "add-fighter":
            p.add_argument("--fighter", required=True)
    args = parser.parse_args()
    try:
        if args.command in ("validate", "list"):
            data = validate_registry(json.loads(args.registry.read_text(encoding="utf-8")))
            if args.command == "validate":
                print("Valid voice registry: schema", data["schema_version"], "gangs", len(data["gangs"]))
            else:
                for name, profile in sorted(data["gangs"].items()):
                    print(f"{name}: {profile.get('review_status','approved')}")
                for name in sorted(data["excluded_gangs"]):
                    print(f"{name}: excluded / pending future onboarding")
        else:
            result = update_registry(args.registry, args.command, **vars(args))
            print("Updated registry:", args.command, args.gang, "gangs:", len(result["gangs"]))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
