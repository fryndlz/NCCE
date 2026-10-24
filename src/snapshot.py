"""Build normalized campaign snapshots from already-read Google Sheet values.

This module deliberately contains no Google credentials or write access. The eventual
Google adapter will supply the same tab -> rows mapping produced by the connector.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FIGHTER_HEADER = ["Name","Type","Class","Cost","XP","Kills","M","WS","BS","S","T","W","I","A","Ld","Cl","Wil","Int","Weapons","Wargear","Skills","Advancements","Effects","Status","Fighter Notes","Backstory"]


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_dict(header: list[Any], row: list[Any]) -> dict[str, Any]:
    padded = list(row) + [None] * max(0, len(header) - len(row))
    return {str(header[i]): padded[i] for i in range(len(header))}


def parse_key_value(rows: list[list[Any]]) -> dict[str, Any]:
    out = {}
    for row in rows[1:]:
        if len(row) >= 2 and row[0] not in (None, ""):
            out[str(row[0])] = row[1]
    return out


def parse_battles(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    header = rows[0]
    battles = []
    for source_row, row in enumerate(rows[1:], start=2):
        if not row or not any(v not in (None, "") for v in row):
            continue
        item = _row_dict(header, row)
        item["source_row"] = source_row
        battles.append(item)
    return battles


def parse_gang_tab(rows: list[list[Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    meta: dict[str, Any] = {"display_name": rows[0][0] if rows[0] else None}
    notes = None
    fighter_start = None
    for i, row in enumerate(rows):
        if row and row[0] == "FIGHTERS":
            fighter_start = i
            break
        if row and row[0] == "GANG NOTES":
            if i + 1 < len(rows) and rows[i + 1]:
                notes = rows[i + 1][0]
            continue
        if len(row) >= 2 and row[0] in {"Gang ID","Gang Type","Credits","Reputation","Rating","Alignment","Gang Colour","Last Updated","Created"}:
            meta[str(row[0])] = row[1]

    fighters: dict[str, dict[str, Any]] = {}
    if fighter_start is not None and fighter_start + 1 < len(rows):
        header = rows[fighter_start + 1]
        if header and header[0] == "Name":
            for row in rows[fighter_start + 2:]:
                if not row or row[0] in (None, ""):
                    continue
                f = _row_dict(header, row)
                fighters[str(f["Name"])] = f

    return {
        "gang_id": meta.get("Gang ID"),
        "name": meta.get("display_name"),
        "gang_type": meta.get("Gang Type"),
        "credits": _int(meta.get("Credits")),
        "reputation": _int(meta.get("Reputation")),
        "rating": _int(meta.get("Rating")),
        "alignment": meta.get("Alignment"),
        "colour": meta.get("Gang Colour"),
        "last_updated": meta.get("Last Updated"),
        "created": meta.get("Created"),
        "notes": notes,
        "fighters": fighters,
    }


def build_snapshot(*, campaign_rows, gangs_rows, territory_rows, battle_rows, gang_tabs, captured_at=None):
    gang_index = {}
    if gangs_rows:
        header = gangs_rows[0]
        for row in gangs_rows[1:]:
            if row:
                item = _row_dict(header, row)
                gang_index[str(item.get("Gang ID"))] = item

    territories = []
    if territory_rows:
        header = territory_rows[0]
        territories = [_row_dict(header, row) for row in territory_rows[1:] if row]

    parsed_tabs = {name: parse_gang_tab(rows) for name, rows in gang_tabs.items()}
    return {
        "snapshot_version": 1,
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
        "campaign": parse_key_value(campaign_rows),
        "gang_index": gang_index,
        "gangs": parsed_tabs,
        "territories": territories,
        "battles": parse_battles(battle_rows),
        "authority": {
            "structured_state": "authoritative",
            "battle_structured_fields": "authoritative",
            "free_text_notes": "contextual_evidence",
            "generated_narrative": "non_authoritative",
        },
    }
