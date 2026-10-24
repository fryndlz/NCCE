"""Build normalized campaign snapshots from already-read Google Sheet values.

This module deliberately contains no Google credentials or write access. The eventual
Google adapter will supply the same tab -> rows mapping produced by the connector.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from datetime import datetime, timezone
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET
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
        raw = _row_dict(header, row)
        aliases = {
            "date": "Date", "scenario": "Scenario", "attacker": "Attacker",
            "defender": "Defender", "winner": "Winner", "territory": "Territory",
            "territory_claimer": "Territory Claimer", "notes": "Notes",
        }
        item = {key: raw.get(label) for key, label in aliases.items()}
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
            if row and any(value not in (None, "") for value in row):
                item = _row_dict(header, row)
                if item.get("Gang ID") not in (None, ""):
                    gang_index[str(item.get("Gang ID"))] = item

    territories = []
    if territory_rows:
        header = territory_rows[0]
        territories = [_row_dict(header, row) for row in territory_rows[1:] if row and any(value not in (None, "") for value in row)]

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


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column_index(cell_reference: str) -> int:
    letters = "".join(character for character in cell_reference if character.isalpha()).upper()
    result = 0
    for character in letters:
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _cell_value(cell: ET.Element, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(cell.itertext())
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return None
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError):
            raise ValueError("XLSX contains an invalid shared-string index")
    if cell_type == "b":
        return value == "1"
    if cell_type in {"str", "e"}:
        return value
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value


def read_xlsx_sheets(data: bytes, *, max_uncompressed_bytes: int = 32_000_000) -> dict[str, list[list[Any]]]:
    """Read cell values from a Google Sheets XLSX export using Python's stdlib."""
    try:
        archive = ZipFile(BytesIO(data))
    except (BadZipFile, OSError) as exc:
        raise ValueError("Google Sheets returned an invalid XLSX workbook") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > 200 or sum(info.file_size for info in infos) > max_uncompressed_bytes:
            raise ValueError("Google Sheets workbook exceeds the supported size limits")
        names = {info.filename for info in infos}
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise ValueError("XLSX workbook is missing its workbook index")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {}
        for relationship in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship"):
            if relationship.attrib.get("TargetMode") == "External":
                continue
            target = relationship.attrib.get("Target", "")
            if target.startswith("/"):
                path = target.lstrip("/")
            else:
                path = str(PurePosixPath("xl") / target)
            targets[relationship.attrib["Id"]] = str(PurePosixPath(path))

        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{_MAIN_NS}}}si"):
                shared_strings.append("".join(node.text or "" for node in item.iter(f"{{{_MAIN_NS}}}t")))

        output = {}
        sheets = workbook.findall(f".//{{{_MAIN_NS}}}sheets/{{{_MAIN_NS}}}sheet")
        if not sheets:
            raise ValueError("XLSX workbook contains no worksheets")
        for sheet in sheets:
            title = sheet.attrib.get("name")
            relation_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
            path = targets.get(relation_id)
            if not title or not path or path not in names or not path.startswith("xl/worksheets/"):
                raise ValueError("XLSX workbook contains an invalid worksheet reference")
            root = ET.fromstring(archive.read(path))
            row_map = {}
            max_row = 0
            for row in root.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
                row_number = int(row.attrib.get("r", "0"))
                if row_number < 1:
                    continue
                values = {}
                max_column = 0
                for cell in row.findall(f"{{{_MAIN_NS}}}c"):
                    column = _column_index(cell.attrib.get("r", "A1"))
                    values[column] = _cell_value(cell, shared_strings)
                    max_column = max(max_column, column + 1)
                row_map[row_number] = (values, max_column)
                max_row = max(max_row, row_number)
            rows = []
            for row_number in range(1, max_row + 1):
                values, max_column = row_map.get(row_number, ({}, 0))
                row = [None] * max_column
                for column, value in values.items():
                    row[column] = value
                rows.append(row)
            output[title] = rows
        return output


def build_snapshot_from_sheets(sheets: dict[str, list[list[Any]]], captured_at=None) -> dict:
    """Normalize the current Krakamunda tabs into the story engine's snapshot shape."""
    required = {"Campaign", "Gangs", "Territories", "Battles"}
    missing = required - set(sheets)
    if missing:
        raise ValueError("Campaign workbook is missing required tabs: " + ", ".join(sorted(missing)))
    system_tabs = required | {"MAIN"}
    gang_tabs = {name: rows for name, rows in sheets.items() if name not in system_tabs}
    snapshot = build_snapshot(
        campaign_rows=sheets["Campaign"],
        gangs_rows=sheets["Gangs"],
        territory_rows=sheets["Territories"],
        battle_rows=sheets["Battles"],
        gang_tabs=gang_tabs,
        captured_at=captured_at,
    )

    # MAIN's Data Dump contains stable territory IDs. Join only those IDs into
    # rows whose owner/name pair is unique; ambiguous labels stay unlinked.
    main_rows = sheets.get("MAIN", [])
    dump = None
    for row in main_rows:
        if len(row) > 1 and row[0] == "Data Dump" and isinstance(row[1], str):
            import json
            try:
                dump = json.loads(row[1])
            except json.JSONDecodeError:
                dump = None
            break
    if isinstance(dump, dict):
        territory_ids: dict[tuple[str, str], set[str]] = {}
        for member in dump.get("members", []):
            for gang in member.get("gangs", []):
                gang_id = str(gang.get("id") or "")
                for territory in gang.get("territories", []):
                    territory_id = territory.get("id")
                    name = territory.get("name")
                    if gang_id and territory_id and name:
                        key = (gang_id, _normal_text(name))
                        territory_ids.setdefault(key, set()).add(str(territory_id))
        for territory in snapshot["territories"]:
            owner = str(territory.get("Gang ID") or "")
            name = territory.get("Territory")
            candidates = territory_ids.get((owner, _normal_text(name)), set())
            if len(candidates) == 1:
                territory["territory_id"] = next(iter(candidates))
        records_by_id = {}
        for territory in snapshot["territories"]:
            source_id = territory.get("territory_id")
            if source_id:
                records_by_id.setdefault(str(source_id), []).append(territory)
        for source_id, records in records_by_id.items():
            duplicate_ordinals = {}
            for territory in records:
                if len(records) == 1:
                    territory["source_territory_key"] = source_id
                else:
                    # The source repeats a territory ID on multiple rows. Preserve
                    # every current row with a stable projection key, but leave the
                    # raw ID duplicated so the diff layer treats ownership as ambiguous.
                    signature = "|".join(str(territory.get(key) or "") for key in ("Gang ID", "Territory", "Card", "Default", "Ruined"))
                    duplicate_ordinals[signature] = duplicate_ordinals.get(signature, 0) + 1
                    territory["source_territory_key"] = f"{source_id}#row:{_normal_text(signature)}:{duplicate_ordinals[signature]}"
        snapshot["source_metadata"] = {
            "campaign_id": (dump.get("campaign") or {}).get("id"),
            "campaign_updated_at": (dump.get("campaign") or {}).get("updated_at"),
            "territory_ids_available": sum("territory_id" in row for row in snapshot["territories"]),
        }
    return snapshot


def _normal_text(value: Any) -> str:
    import re
    import unicodedata
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip().casefold())
