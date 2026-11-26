"""Synthetic fixtures are isolated here; never imported by website or production data."""
import sys, unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from data_contracts import TeamSnapshot,TeamMember,TeamPurpose,RetrievalStatus,ValueState,EquipmentSlot,EquipmentState,EquipmentReference
from pvp_statistics import summarize_pvp

def member(player,index,character,weapon,armor,accessory):
    return TeamMember(team_snapshot_id='fixture-snapshot',player_id=player,member_index=index,
        character_state=ValueState.PRESENT,character_id=character,equipment={
          EquipmentSlot.WEAPON:EquipmentReference(EquipmentState.EQUIPPED,weapon),
          EquipmentSlot.ARMOR:EquipmentReference(EquipmentState.EQUIPPED,armor),
          EquipmentSlot.ACCESSORY:EquipmentReference(EquipmentState.EQUIPPED,accessory)})
def snapshot(player,members):
    return TeamSnapshot(snapshot_id='fixture-snapshot',player_id=player,purpose=TeamPurpose.PVP_DEFENSE,
        retrieved_at='2026-11-18T00:00:00+08:00',status=RetrievalStatus.SUCCESS,members=tuple(members))
class StatisticsTests(unittest.TestCase):
    def test_unique_player_denominator_and_actual_combinations(self):
        a=snapshot('fixture-a',[member('fixture-a',0,'fixture-unit','w1','a1','x1'),member('fixture-a',1,'fixture-unit','w2','a2','x2')])
        b=snapshot('fixture-b',[member('fixture-b',0,'fixture-other','w2','a1','x2')])
        result=summarize_pvp([a,b]);unit=next(x for x in result['characters'] if x['id']=='fixture-unit')
        self.assertEqual(result['validPlayerCount'],2);self.assertEqual(unit['playerCount'],1)
        self.assertEqual(unit['appearanceCount'],2);self.assertEqual(unit['playerUsageRate'],.5)
        self.assertEqual({(x['weaponId'],x['armorId'],x['accessoryId']) for x in result['combinations']},{('w1','a1','x1'),('w2','a2','x2'),('w2','a1','x2')})
        self.assertIsNone(result['winRate'])
    def test_failed_reads_do_not_become_empty_successful_samples(self):
        bad=replace(snapshot('fixture-b',[]),status=RetrievalStatus.FAILED,members=None)
        result=summarize_pvp([bad]);self.assertEqual(result['validPlayerCount'],0)
        self.assertEqual(result['failedObservationCount'],1);self.assertEqual(result['sourceStatus'],'unavailable')
    def test_newer_failed_read_does_not_reuse_an_old_success(self):
        old=snapshot('fixture-a',[member('fixture-a',0,'fixture-unit','w1','a1','x1')])
        latest=replace(old,retrieved_at='2026-11-18T01:00:00+08:00',status=RetrievalStatus.FAILED,members=None)
        result=summarize_pvp([old,latest]);self.assertEqual(result['validPlayerCount'],0)
        self.assertEqual(result['failedLatestPlayerCount'],1)
    def test_unknown_slot_excludes_combination_without_inventing_equipment(self):
        m=member('fixture-a',0,'fixture-unit','w1','a1','x1');equipment=dict(m.equipment)
        equipment[EquipmentSlot.ARMOR]=EquipmentReference(EquipmentState.UNKNOWN)
        result=summarize_pvp([snapshot('fixture-a',[replace(m,equipment=equipment)])])
        self.assertEqual(result['combinations'],[]);self.assertEqual(result['unknownEquipmentSlotCount'],1)
if __name__=='__main__':unittest.main()
