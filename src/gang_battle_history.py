"""Factual gang history projected from active Battles records."""
from collections import Counter, defaultdict

from snapshot import battle_identity
from story_engine import _current_battle_event, normal


def project(battles, archived, gang_names, events):
    """Use the archive to corroborate participants while the Sheet controls inclusion."""
    names = defaultdict(set)
    for gang_id, name in gang_names.items():
        names[normal(name)].add(gang_id)

    def parties(record):
        return {normal(record[field]) for field in ("attacker", "defender") if record.get(field)}

    def signature(date, scenario):
        return str(date or "")[:10], normal(scenario)

    archive_index = {str(row["battle_id"]): row for row in archived}
    by_signature = defaultdict(list)
    for row in archived:
        by_signature[signature(row.get("documented_at"), row.get("scenario"))].append(row)

    def match(battle):
        key = battle_identity(battle)
        if key.startswith("id:"):
            return archive_index.get(key[3:])
        day, scenario = signature(battle.get("date"), battle.get("scenario"))
        known = parties(battle)
        candidates = [
            row for row in by_signature[(day, scenario)]
            if known <= (parties(row) | {normal(g["name"]) for g in row.get("gangs", [])})
        ]
        return candidates[0] if day and scenario and len(candidates) == 1 else None

    matches = [match(battle) for battle in battles]
    uses = Counter(row["battle_id"] for row in matches if row is not None)
    result = defaultdict(list)
    for battle, archive in zip(battles, matches):
        if archive is not None and uses[archive["battle_id"]] > 1:
            archive = None
        archive = archive or {}
        key = battle_identity(battle)
        participants = set(archive.get("gang_ids", [])) & gang_names.keys()
        for name in parties(battle) | {normal(battle.get("winner"))}:
            if len(names[name]) == 1:
                participants.update(names[name])
        winner_name = normal(battle.get("winner"))
        winner_ids = names[winner_name]
        winner_id = next(iter(winner_ids)) if len(winner_ids) == 1 else None
        if winner_name and winner_name == normal(archive.get("winner")):
            winner_id = winner_id or archive.get("winner_gang_id")
        anchor = _current_battle_event(battle, events)
        for gang_id in sorted(participants):
            outcome = "Won" if winner_id == gang_id else "Lost" if winner_id else "Outcome not recorded"
            # A named winner outside this campaign can still establish a defeat.
            if not winner_id and winner_name and winner_name != normal(gang_names[gang_id]):
                outcome = "Lost"
            result[gang_id].append({
                **battle,
                "battle_key": key,
                "history_id": f"id:{archive['battle_id']}" if archive else key,
                "archive_battle_id": archive.get("battle_id"),
                "source_locator": f"Battles!battle {key}",
                "provenance_class": "mechanical_fact",
                "source_event_ids": [anchor["event_id"]] if anchor else [],
                "territory": battle.get("territory") or archive.get("territory"),
                "gang_result": outcome,
                "opponents": sorted({gang_names[other] for other in participants - {gang_id}} |
                                    {battle[field] for field in ("attacker", "defender", "winner")
                                     if battle.get(field) and normal(battle[field]) != normal(gang_names[gang_id])}),
            })
    return result
