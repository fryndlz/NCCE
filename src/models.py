from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class FighterState:
    name: str
    gang: str
    fields: dict[str, Any]

@dataclass
class GangState:
    gang_id: str
    name: str
    gang_type: str
    credits: int | None
    reputation: int | None
    rating: int | None
    alignment: str | None
    fighters: dict[str, FighterState] = field(default_factory=dict)
    notes: str | None = None

@dataclass
class BattleRecord:
    source_row: int
    date: str
    scenario: str
    attacker: str | None
    defender: str | None
    winner: str | None
    territory: str | None
    territory_claimer: str | None
    notes: str | None

@dataclass
class CampaignSnapshot:
    captured_at: str
    campaign: dict[str, Any]
    gangs: dict[str, GangState]
    territories: list[dict[str, Any]]
    battles: list[BattleRecord]
