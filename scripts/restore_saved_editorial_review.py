"""Operator-only, owner-requested saved-review repair. Never starts model work."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from store import Store
from workshop_experiments import restore_saved_review


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--database',required=True)
    p.add_argument('--job-id',required=True)
    p.add_argument('--turn-id',required=True)
    p.add_argument('--review-file',required=True)
    a=p.parse_args()
    database=Path(a.database)
    if not database.is_file():raise ValueError('An existing database is required')
    review=json.loads(Path(a.review_file).read_text(encoding='utf-8-sig'))
    store=Store(database)
    try:
        state=restore_saved_review(store,a.job_id,review,a.turn_id)
        print(json.dumps({'run_id':state['run_id'],'status':state['status'],
            'writer_reserved':state['writer_reserved'],'writer_limit':state['writer_limit'],
            'reviewer_reserved':state['reviewer_reserved'],'reviewer_limit':state['reviewer_limit'],
            'message':'Saved review restored; no writing/review call, activation or allowance increase.'}))
    finally:store.close()


if __name__=='__main__':main()
