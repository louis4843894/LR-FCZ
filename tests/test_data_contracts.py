import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from data_contracts import (  # noqa: E402
    EquipmentReference,
    EquipmentSlot,
    EquipmentState,
    GuildMembership,
    RetrievalStatus,
    TeamMember,
    TeamPurpose,
    TeamSnapshot,
    ValueState,
    validate_guild_team_links,
    validate_team_snapshot,
    validate_unique_source_records,
)


class TeamContractTests(unittest.TestCase):
    def make_member(self, player_id="test-player"):
        return TeamMember(
            team_snapshot_id="team-test",
            player_id=player_id,
            member_index=0,
            character_state=ValueState.PRESENT,
            character_id="test-character",
            equipment={
                EquipmentSlot.WEAPON: EquipmentReference(
                    EquipmentState.EQUIPPED, "test-weapon"
                ),
                EquipmentSlot.ARMOR: EquipmentReference(EquipmentState.UNKNOWN),
                EquipmentSlot.ACCESSORY: EquipmentReference(
                    EquipmentState.NOT_EQUIPPED
                ),
            },
        )

    def make_team(self, **overrides):
        values = {
            "snapshot_id": "team-test",
            "player_id": "test-player",
            "purpose": TeamPurpose.PVP_DEFENSE,
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "status": RetrievalStatus.SUCCESS,
            "members": (self.make_member(),),
        }
        values.update(overrides)
        return TeamSnapshot(**values)

    def test_failed_or_unavailable_read_cannot_become_an_empty_team(self):
        with self.assertRaisesRegex(ValueError, "must not contain members"):
            validate_team_snapshot(
                self.make_team(status=RetrievalStatus.FAILED, members=())
            )

        with self.assertRaisesRegex(ValueError, "distinguish an empty roster"):
            validate_team_snapshot(self.make_team(members=None))

    def test_pvp_and_guild_battle_purposes_remain_distinct(self):
        validate_team_snapshot(self.make_team())

        with self.assertRaisesRegex(ValueError, "guild and membership snapshot"):
            validate_team_snapshot(
                self.make_team(purpose=TeamPurpose.GUILD_BATTLE_DEFENSE)
            )

        validate_team_snapshot(
            self.make_team(
                purpose=TeamPurpose.GUILD_BATTLE_DEFENSE,
                guild_id="test-guild",
                membership_snapshot_id="roster-test",
            )
        )

    def test_team_member_and_equipment_ids_are_bound_to_the_team_owner(self):
        with self.assertRaisesRegex(ValueError, "different player"):
            validate_team_snapshot(self.make_team(members=(self.make_member("other"),)))

        bad_member = self.make_member()
        bad_member = TeamMember(
            **{
                **bad_member.__dict__,
                "equipment": {
                    **bad_member.equipment,
                    EquipmentSlot.ARMOR: EquipmentReference(
                        EquipmentState.NOT_EQUIPPED, "test-armor"
                    ),
                },
            }
        )
        with self.assertRaisesRegex(ValueError, "only valid when equipment state"):
            validate_team_snapshot(self.make_team(members=(bad_member,)))

    def test_unknown_and_not_equipped_are_not_collapsed(self):
        member = self.make_member()
        self.assertEqual(
            member.equipment[EquipmentSlot.ARMOR].state,
            EquipmentState.UNKNOWN,
        )
        self.assertEqual(
            member.equipment[EquipmentSlot.ACCESSORY].state,
            EquipmentState.NOT_EQUIPPED,
        )
        validate_team_snapshot(self.make_team(members=(member,)))

    def test_guild_roster_and_team_observations_can_have_different_snapshots(self):
        membership = GuildMembership(
            snapshot_id="roster-test",
            guild_id="test-guild",
            player_id="test-player",
            observed_at="2026-01-01T00:00:00+00:00",
            source_record_identity="test-membership-row",
        )
        team = self.make_team(
            purpose=TeamPurpose.GUILD_BATTLE_DEFENSE,
            guild_id="test-guild",
            membership_snapshot_id="roster-test",
        )

        validate_guild_team_links((membership,), (team,))

    def test_duplicate_snapshot_and_source_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_unique_source_records(
                (
                    ("snapshot-test", "source-row"),
                    ("snapshot-test", "source-row"),
                )
            )


if __name__ == "__main__":
    unittest.main()
