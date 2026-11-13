"""One-shot, owner-authorized editorial correction request seeding.

NCCE_EDITORIAL_REVISION_BATCH is a transient Render environment variable
containing a JSON object:
  {"job_id": "<existing historical job UUID>",
   "items": [{"request_id": "<imported UUID>", "receipt": "exchange:..."}]}

Each item is independently checked by the canonical bulk revision path. No
prose changes or publications are performed here, and item IDs are retained
for an idempotent restart. Omit the variable to disable the operation.
"""
from __future__ import annotations

import json
import os
from uuid import UUID

import historical_backfill


def _validated_manifest(raw):
    payload=json.loads(raw)
    if not isinstance(payload,dict) or set(payload)!={'job_id','items'}:
        raise ValueError('Editorial batch requires job_id and items')
    job_id=str(UUID(payload['job_id']))
    items=payload['items']
    if not isinstance(items,list) or not 1 <= len(items) <= 100:
        raise ValueError('Editorial batch requires 1–100 items')
    seen=set()
    for x in items:
        if not isinstance(x,dict) or set(x)!={'request_id','receipt'}:
            raise ValueError('Editorial batch item requires request_id and receipt')
        rid=str(UUID(x['request_id']))
        if rid in seen or x['request_id']!=rid:
            raise ValueError('Duplicate or noncanonical editorial request ID')
        if not isinstance(x['receipt'],str) or not x['receipt'].startswith('exchange:'+rid+':'):
            raise ValueError('Receipt does not belong to requested imported entry')
        seen.add(rid)
    return job_id,items


def apply(store, raw, revise=None):
    """Create only new ordinary Queue correction requests; never mark them READY."""
    job_id,items=_validated_manifest(raw)
    revise=revise or historical_backfill.request_manual_revision
    outcome={'created':[], 'reused':[], 'blocked':[], 'total':len(items)}
    for item in items:
        original=item['request_id']
        marker='editorial_revision_seed:'+job_id+':'+original
        already=store.get_state(marker)
        if already:
            outcome['reused'].append({'parent':original,'request_id':already})
            continue
        try:
            result=revise(store,job_id,original,item['receipt'])
            if result['status'] not in ('PENDING','DEFERRED') or not result.get('request_id'):
                raise ValueError('No open correction request returned')
            store.set_state(marker,result['request_id'])
            outcome['reused' if result.get('reused') else 'created'].append(
                {'parent':original,'request_id':result['request_id']})
        except (ValueError,RuntimeError,KeyError) as exc:
            outcome['blocked'].append({'parent':original,'error':str(exc)[:350]})
    return outcome


def apply_from_environment(store):
    raw=os.environ.get('NCCE_EDITORIAL_REVISION_BATCH','').strip()
    if not raw:
        return None
    return apply(store,raw)
