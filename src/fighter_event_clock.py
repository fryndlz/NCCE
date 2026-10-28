"""Logical time: distinct supported changes relevant to one fighter, never wall time."""
from datetime import datetime, timezone

HALF_LIFE_EVENTS=10
POLICY_VERSION='fighter-events-v1'

def policy():
    return {'version':POLICY_VERSION,'scope':'fighter_relevant_changes',
            'unit':'one distinct supported factual change','recency_half_life_events':HALF_LIFE_EVENTS,
            'recency_formula':f'2 ** (-subsequent_relevant_events / {HALF_LIFE_EVENTS})',
            'fixed_expiry':False,'wall_clock_decay':False,'access_reinforcement':False,
            'derived_entries_advance_clock':False,
            'formation_anchor':'latest cited factual event; baseline is position zero',
            'design_document':'docs/FIGHTER_EVENT_CLOCK.md'}

def timestamp(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError,ValueError):return None

def build(memories,store=None,fighter_id=None):
    """Only observation causes advance time. Reflections/thoughts cite that clock.

    Timestamps order facts; elapsed durations are never measured. Corrections map
    to the original event identity. Rewriting or re-importing prose cannot tick.
    """
    cache={}; roots={}; points={}
    def record(event_id):
        if event_id not in cache:
            row=store.db.execute('SELECT event_id,supersedes_event_id,occurred_at,observed_at FROM campaign_events WHERE event_id=?',(event_id,)).fetchone() if store else None
            cache[event_id]=dict(row) if row else {}
        return cache[event_id]
    def root(event_id):
        if event_id in roots:return roots[event_id]
        current=event_id;seen={};path=[]
        while current not in seen:
            if current in roots:
                canonical=roots[current];break
            seen[current]=len(path);path.append(current)
            parent=record(current).get('supersedes_event_id')
            if not parent:
                canonical=current;break
            current=parent
        else:
            # Only the cycle, not a preceding tail, determines its identity.
            canonical=min(path[seen[current]:])
        for item in path:roots[item]=canonical
        return canonical
    relevant=[m for m in memories if fighter_id is None or m.get('fighter_id') in (None,fighter_id)]
    for memory in relevant:
        if memory.get('memory_type')!='observation' or memory.get('baseline') or memory.get('is_baseline'):continue
        for event_id in memory.get('source_event_ids',[]):
            token=root(event_id);original=record(token)
            occurred=timestamp(memory.get('occurred_at') or original.get('occurred_at'))
            stamp=occurred or timestamp(original.get('observed_at') or memory.get('observed_at'))
            # Unknown ordering is explicit and stable, not 'now'.
            order=(stamp or datetime.min.replace(tzinfo=timezone.utc),token)
            preferred=(0 if occurred else 1,order)
            if token not in points or preferred<points[token]:points[token]=preferred
    ordered=sorted(points,key=lambda token:points[token][1])
    positions={token:index+1 for index,token in enumerate(ordered)}
    by_id={m.get('id') or m.get('memory_id'):m for m in relevant}
    def position(memory,seen=None):
        if memory.get('baseline') or memory.get('is_baseline'):return 0
        seen=set() if seen is None else seen
        identity=memory.get('id') or memory.get('memory_id') or memory.get('memory_key')
        if identity in seen:return 0
        seen.add(identity)
        result=[positions.get(root(eid),0) for eid in memory.get('source_event_ids',[])]
        result += [position(by_id[mid],seen.copy()) for mid in memory.get('source_observation_ids',[]) if mid in by_id]
        return max(result,default=0)
    return {'basis':'fighter_relevant_events','policy_version':POLICY_VERSION,
            'head':len(ordered),'ordered_event_ids':ordered,
            'positions':{m['memory_key']:position(m) for m in relevant if m.get('memory_key')}}

def measure(memory,clock):
    anchor=clock['positions'].get(memory.get('memory_key'),0)
    distance=max(0,clock['head']-anchor)
    return {'event_position':anchor,'subsequent_relevant_events':distance,
            'recency':2**(-distance/HALF_LIFE_EVENTS)}
