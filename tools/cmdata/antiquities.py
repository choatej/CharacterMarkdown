"""Antiquities: every antiquity once, with its lead timer, and helpers for expiring leads.

The export stores each antiquity twice: inside its set, and again in ``activeLeads`` when it has
a lead. Here every antiquity appears once (``Antiquities.antiquities``) and the leads are derived
from it (``Antiquities.leads()``), so nothing is repeated in the JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clean import none_if_blank
from .util import as_dict, records

WEEK_SECONDS = 7 * 24 * 60 * 60


@dataclass
class Antiquity:
    id: int
    name: str
    # the set it belongs to; antiquities that belong to no set have set_id 0 / None
    set_id: int | None = None
    # quality uses the game's numeric scale; no name is given because it is not confirmed
    quality: int | None = None
    discovered: bool | None = None
    completed: bool | None = None
    repeatable: bool | None = None
    goals_done: int | None = None
    goals_total: int | None = None
    times_recovered: int | None = None
    has_lead: bool = False
    # when the lead runs out, as a Unix time (approximate: export time + seconds remaining)
    lead_expires_at: int | None = None
    lead_seconds_remaining: int | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any], set_id: int | None = None) -> Antiquity:
        return cls(
            id=raw.get("id", 0),
            name=str(raw.get("name", "")),
            set_id=set_id,
            quality=raw.get("quality"),
            discovered=raw.get("isDiscovered"),
            completed=raw.get("isCompleted"),
            repeatable=raw.get("isRepeatable"),
            goals_done=raw.get("numAchieved"),
            goals_total=raw.get("numGoals"),
            times_recovered=raw.get("numRecovered"),
            has_lead=bool(raw.get("hasLead")),
            lead_expires_at=raw.get("leadExpiresAt"),
            lead_seconds_remaining=raw.get("leadSecondsRemaining"),
        )


@dataclass
class AntiquitySet:
    id: int
    # None for the group of antiquities that belong to no set
    name: str | None
    total: int
    discovered: int | None = None
    completed: int | None = None


@dataclass
class Antiquities:
    total: int | None = None
    discovered: int | None = None
    completed: int | None = None
    sets_total: int | None = None
    sets_completed: int | None = None
    sets: list[AntiquitySet] = field(default_factory=list)
    antiquities: list[Antiquity] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Antiquities:
        summary = as_dict(raw.get("summary"))
        by_id: dict[int, Antiquity] = {}
        sets = []
        for group in records(raw.get("sets")):
            set_id = group.get("id") or None
            members = [Antiquity.from_raw(a, set_id) for a in records(group.get("antiquities"))]
            for member in members:
                by_id.setdefault(member.id, member)
            declared = group.get("numAntiquities")
            sets.append(
                AntiquitySet(
                    id=group.get("id", 0),
                    name=none_if_blank(group.get("name")),
                    total=declared if declared else len(members),
                    discovered=group.get("discoveredAntiquities"),
                    completed=group.get("completedAntiquities"),
                )
            )
        # a lead that is not inside any set (should not happen) must not be lost
        for lead in records(raw.get("activeLeads")):
            by_id.setdefault(lead.get("id", 0), Antiquity.from_raw(lead))
        return cls(
            total=summary.get("totalAntiquities"),
            discovered=summary.get("discoveredAntiquities"),
            completed=summary.get("completedAntiquities"),
            sets_total=summary.get("totalSets"),
            sets_completed=summary.get("completedSets"),
            sets=sets,
            antiquities=list(by_id.values()),
        )

    def leads(self) -> list[Antiquity]:
        """Antiquities with an active lead, soonest to expire first (no timer last)."""
        leads = [a for a in self.antiquities if a.has_lead]
        return sorted(
            leads,
            key=lambda a: (
                a.lead_seconds_remaining is None,
                a.lead_seconds_remaining or 0,
                a.name,
            ),
        )

    def leads_expiring_within(self, seconds: int = WEEK_SECONDS) -> list[Antiquity]:
        """Leads that run out within `seconds` of the export (default: one week)."""
        return [
            a
            for a in self.leads()
            if a.lead_seconds_remaining is not None and 0 < a.lead_seconds_remaining <= seconds
        ]
