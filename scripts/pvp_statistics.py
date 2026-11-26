"""Statistics over validated observations only. No source fetching or production fixtures."""
from collections import defaultdict
from datetime import datetime
from data_contracts import TeamSnapshot, TeamPurpose, RetrievalStatus, EquipmentSlot, EquipmentState, ValueState, validate_team_snapshot

def summarize_pvp(snapshots: list[TeamSnapshot]) -> dict:
    latest = {}; failed = 0
    for snapshot in snapshots:
        validate_team_snapshot(snapshot)
        if snapshot.purpose is not TeamPurpose.PVP_DEFENSE:
            continue
        if snapshot.status is not RetrievalStatus.SUCCESS:
            failed += 1
        previous = latest.get(snapshot.player_id)
        if previous:
            when = datetime.fromisoformat(snapshot.retrieved_at.replace('Z', '+00:00'))
            old = datetime.fromisoformat(previous.retrieved_at.replace('Z', '+00:00'))
            if when == old and snapshot != previous:
                raise ValueError('conflicting player snapshots at identical time')
            if when <= old:
                continue
        latest[snapshot.player_id] = snapshot
    latest_attempt_count = len(latest)
    failed_latest = sum(s.status is not RetrievalStatus.SUCCESS for s in latest.values())
    latest = {p:s for p,s in latest.items() if s.status is RetrievalStatus.SUCCESS}
    character_players = defaultdict(set); equipment_players = defaultdict(set)
    character_appearances = defaultdict(int); equipment_appearances = defaultdict(int)
    combinations = defaultdict(int); unknown_equipment = 0
    slots = (EquipmentSlot.WEAPON, EquipmentSlot.ARMOR, EquipmentSlot.ACCESSORY)
    for player, snapshot in latest.items():
        for member in snapshot.members or ():
            if member.character_state is not ValueState.PRESENT:
                continue
            character = member.character_id
            character_players[character].add(player); character_appearances[character] += 1
            complete = True; equipment_ids = []
            for slot in slots:
                ref = member.equipment[slot]
                if ref.state is EquipmentState.UNKNOWN:
                    complete = False; unknown_equipment += 1
                elif ref.state is EquipmentState.EQUIPPED:
                    equipment_players[ref.equipment_id].add(player); equipment_appearances[ref.equipment_id] += 1
                equipment_ids.append(ref.equipment_id if ref.state is EquipmentState.EQUIPPED else None)
            # Only three slots belonging to this exact member occurrence are combined.
            if complete:
                combinations[(character, *equipment_ids)] += 1
    denominator = len(latest)
    def usage(players, appearances):
        return [{'id':key,'playerCount':len(value),'appearanceCount':appearances[key],
                 'playerUsageRate':len(value)/denominator if denominator else None}
                for key,value in sorted(players.items())]
    return {'sourceStatus':'available' if denominator else 'unavailable',
            'validPlayerCount':denominator,'observedPlayerCount':latest_attempt_count,'failedLatestPlayerCount':failed_latest,'failedObservationCount':failed,'unknownEquipmentSlotCount':unknown_equipment,
            'rateUnit':'fraction','characters':usage(character_players,character_appearances),
            'equipment':usage(equipment_players,equipment_appearances),
            'combinations':[{'characterId':key[0],'weaponId':key[1],'armorId':key[2],'accessoryId':key[3],'appearanceCount':count}
                            for key,count in sorted(combinations.items(),key=lambda x:str(x[0]))],
            'winRate':None,'winRateStatus':'battle-results-not-available'}
