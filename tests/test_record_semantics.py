"""Regression tests for audit-backed continuity placement (no production mutation)."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from record_semantics import SOURCE_NORMALIZATIONS, is_source_normalization, placement
from fighter_event_clock import build


def test_exactly_ten_audited_source_normalizations():
    assert {v[0] for v in SOURCE_NORMALIZATIONS.values()} == {28,30,33,36,37,38,39,40,41,42}
    assert len(SOURCE_NORMALIZATIONS)==10
    assert not is_source_normalization('unknown-source-event')


def test_continuity_does_not_modify_original_source_or_approved_text():
    for event_id, (bulk_row, _, _) in SOURCE_NORMALIZATIONS.items():
        record={
            'memory_type':'observation','source_event_ids':[event_id],
            'baseline':False,'memory_key':'some-original-key',
            'content':'Exact imported approved Markdown',
            'occurred_at':None,'observed_at':'2026-10-25T20:08:49+00:00',
        }
        original=dict(record)
        decision=placement(record)
        assert decision['class']=='continuity'
        assert decision['bulk_row']==bulk_row
        assert decision['incident_count']==0
        assert record==original


def test_known_normalization_not_a_new_experience_clock_tick():
    event_id=next(iter(SOURCE_NORMALIZATIONS))
    ordinary={'id':'a','memory_key':'first','memory_type':'observation','fighter_id':1,
              'baseline':False,'source_event_ids':['genuine-event'],
              'source_observation_ids':[],'occurred_at':None,'observed_at':'2026-10-01T12:00:00+00:00'}
    formatting={**ordinary,'id':'b','memory_key':'format','source_event_ids':[event_id],
                'observed_at':'2026-10-25T20:08:49+00:00'}
    clock=build([ordinary,formatting],fighter_id=1)
    assert clock['head']==1
    assert clock['positions']['first']==1
    assert clock['positions']['format']==0


def test_juvie_baseline_undated_and_other_baselines_unaffected():
    juvie={'memory_type':'observation','memory_key':'legacy:14','baseline':True,
           'source_event_ids':[],'content':'Previously approved fictional vignette'}
    assert placement(juvie)['class']=='undated_vignette'
    assert placement({**juvie,'memory_key':'legacy:15'}) is None
    assert placement({**juvie,'baseline':False}) is None


def test_reflection_does_not_become_continuity_by_citing_an_event():
    event_id=next(iter(SOURCE_NORMALIZATIONS))
    reflection={'memory_type':'reflection','memory_key':'reflection:backlog',
                'source_event_ids':[event_id],'baseline':False}
    assert placement(reflection) is None
