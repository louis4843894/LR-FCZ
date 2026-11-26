"""Source-neutral contracts for player, guild, and team observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Mapping


class TeamPurpose(str, Enum):
    PVP_DEFENSE = "pvp_defense"
    GUILD_BATTLE_DEFENSE = "guild_battle_defense"
    UNKNOWN = "unknown"


class RetrievalStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class ValueState(str, Enum):
    PRESENT = "present"
    NOT_PRESENT = "not_present"
    UNKNOWN = "unknown"


class EquipmentState(str, Enum):
    EQUIPPED = "equipped"
    NOT_EQUIPPED = "not_equipped"
    UNKNOWN = "unknown"


class EquipmentSlot(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"


@dataclass(frozen=True)
class GuildMembership:
    snapshot_id: str
    guild_id: str
    player_id: str
    observed_at: str
    source_record_identity: str


@dataclass(frozen=True)
class EquipmentReference:
    state: EquipmentState
    equipment_id: str | None = None


@dataclass(frozen=True)
class TeamMember:
    team_snapshot_id: str
    player_id: str
    member_index: int
    character_state: ValueState
    character_id: str | None
    equipment: Mapping[EquipmentSlot, EquipmentReference]
    awakening: str | int | float | bool | None = None
    talents: str | int | float | bool | None = None


@dataclass(frozen=True)
class TeamSnapshot:
    snapshot_id: str
    player_id: str
    purpose: TeamPurpose
    retrieved_at: str
    status: RetrievalStatus
    members: tuple[TeamMember, ...] | None
    guild_id: str | None = None
    membership_snapshot_id: str | None = None


def _require_text(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _require_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")


def validate_membership(membership: GuildMembership) -> None:
    _require_text(membership.snapshot_id, "snapshot_id")
    _require_text(membership.guild_id, "guild_id")
    _require_text(membership.player_id, "player_id")
    _require_text(membership.source_record_identity, "source_record_identity")
    _require_timestamp(membership.observed_at, "observed_at")


def validate_team_snapshot(snapshot: TeamSnapshot) -> None:
    _require_text(snapshot.snapshot_id, "snapshot_id")
    _require_text(snapshot.player_id, "player_id")
    _require_timestamp(snapshot.retrieved_at, "retrieved_at")

    if not isinstance(snapshot.purpose, TeamPurpose):
        raise ValueError("team purpose is not confirmed or explicitly unknown")
    if not isinstance(snapshot.status, RetrievalStatus):
        raise ValueError("team retrieval status is invalid")
    if snapshot.status is not RetrievalStatus.SUCCESS:
        if snapshot.members is not None:
            raise ValueError("failed or unavailable team must not contain members")
        return

    if snapshot.members is None:
        raise ValueError("successful team must distinguish an empty roster from unknown")
    if snapshot.purpose is TeamPurpose.GUILD_BATTLE_DEFENSE and (
        not snapshot.guild_id or not snapshot.membership_snapshot_id
    ):
        raise ValueError(
            "guild-battle defense requires a confirmed guild and membership snapshot"
        )
    if snapshot.purpose is TeamPurpose.PVP_DEFENSE and (
        snapshot.guild_id is not None or snapshot.membership_snapshot_id is not None
    ):
        raise ValueError("PvP defense must not be labeled as a guild-battle snapshot")

    seen_indexes: set[int] = set()
    required_slots = set(EquipmentSlot)
    for member in snapshot.members:
        if member.team_snapshot_id != snapshot.snapshot_id:
            raise ValueError("team member references a different team snapshot")
        if member.player_id != snapshot.player_id:
            raise ValueError("team member references a different player")
        if (
            not isinstance(member.member_index, int)
            or isinstance(member.member_index, bool)
            or member.member_index < 0
            or member.member_index in seen_indexes
        ):
            raise ValueError("team member index is invalid or duplicated")
        seen_indexes.add(member.member_index)
        if not isinstance(member.character_state, ValueState):
            raise ValueError("character state is invalid")
        if member.character_state is ValueState.PRESENT:
            _require_text(member.character_id or "", "character_id")
        elif member.character_id is not None:
            raise ValueError("unknown or absent character must not carry a character_id")
        if (
            not all(isinstance(slot, EquipmentSlot) for slot in member.equipment)
            or set(member.equipment) != required_slots
        ):
            raise ValueError("each team member must represent all three equipment slots")
        for slot, reference in member.equipment.items():
            if not isinstance(reference, EquipmentReference):
                raise ValueError(f"{slot.value} equipment reference is invalid")
            if not isinstance(reference.state, EquipmentState):
                raise ValueError(f"{slot.value} equipment state is invalid")
            if reference.state is EquipmentState.EQUIPPED:
                _require_text(reference.equipment_id or "", f"{slot.value}_id")
            elif reference.equipment_id is not None:
                raise ValueError(
                    f"{slot.value} ID is only valid when equipment state is equipped"
                )


def validate_guild_team_links(
    memberships: Iterable[GuildMembership],
    snapshots: Iterable[TeamSnapshot],
) -> None:
    membership_keys: set[tuple[str, str, str]] = set()
    for membership in memberships:
        validate_membership(membership)
        key = (membership.snapshot_id, membership.guild_id, membership.player_id)
        if key in membership_keys:
            raise ValueError(f"duplicate guild membership observation: {key!r}")
        membership_keys.add(key)

    for snapshot in snapshots:
        validate_team_snapshot(snapshot)
        if (
            snapshot.status is RetrievalStatus.SUCCESS
            and snapshot.purpose is TeamPurpose.GUILD_BATTLE_DEFENSE
            and snapshot.guild_id is not None
            and snapshot.membership_snapshot_id is not None
            and (
                snapshot.membership_snapshot_id,
                snapshot.guild_id,
                snapshot.player_id,
            )
            not in membership_keys
        ):
            raise ValueError(
                "guild-battle team player is not linked to the observed guild membership"
            )


def validate_unique_source_records(
    rows: Iterable[tuple[str, str]],
) -> None:
    seen: set[tuple[str, str]] = set()
    for snapshot_id, source_record_identity in rows:
        _require_text(snapshot_id, "snapshot_id")
        _require_text(source_record_identity, "source_record_identity")
        key = (snapshot_id, source_record_identity)
        if key in seen:
            raise ValueError(f"duplicate snapshot/source record identity: {key!r}")
        seen.add(key)
