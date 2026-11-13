"""One-shot editorial correction seeding unit checks: no production state."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from editorial_revision_seed import apply, _validated_manifest


A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
JOB='cccccccc-cccc-4ccc-8ccc-cccccccccccc'


class FakeStore:
    def __init__(self): self.items={}
    def get_state(self,k): return self.items.get(k)
    def set_state(self,k,v): self.items[k]=v


def manifest(*ids):
    return json.dumps({'job_id':JOB,'items':[
        {'request_id':rid,'receipt':'exchange:'+rid+':fixedhash'}
        for rid in ids]})


def test_two_guarded_revisions_idempotent():
    store=FakeStore()
    calls=[]
    def revise(s,job,rid,receipt):
        assert s is store and job==JOB and receipt.startswith('exchange:'+rid+':')
        calls.append(rid)
        return {'request_id':'new-'+rid,'status':'PENDING','reused':False}
    one=apply(store,manifest(A,B),revise)
    assert len(one['created'])==2 and not one['blocked']
    two=apply(store,manifest(A,B),revise)
    assert len(two['reused'])==2 and len(calls)==2


def test_invalid_or_conflicting_payload_fails_closed():
    for raw in [manifest(A,A),
                json.dumps({'job_id':JOB,'items':[{'request_id':A,'receipt':'exchange:'+B+':bad'}]}),
                json.dumps({'job_id':JOB,'items':[]}),
                '{"unexpected":true}']:
        try: _validated_manifest(raw)
        except ValueError: pass
        else: raise AssertionError('Invalid manifest accepted')


def test_one_blocked_does_not_poison_other_items():
    store=FakeStore()
    def revise(s,job,rid,receipt):
        if rid==A: raise ValueError('Source changed; manual reconciliation')
        return {'request_id':'new-'+rid,'status':'PENDING'}
    result=apply(store,manifest(A,B),revise)
    assert len(result['created'])==1 and result['created'][0]['parent']==B
    assert len(result['blocked'])==1 and result['blocked'][0]['parent']==A
    assert store.get_state('editorial_revision_seed:'+JOB+':'+A) is None


if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn();print('PASS',name)
