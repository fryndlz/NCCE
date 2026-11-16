#!/usr/bin/env python3
"""Read-only final QA for memory titles. Never modifies imported NCCE prose."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from exchange_automation import fighter_memory_title_error


class ReadOnly:
    def __init__(self, db):
        self.db=db


def audit(db_path, job_id=None):
    db=sqlite3.connect('file:'+str(Path(db_path).resolve())+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    store=ReadOnly(db)
    if job_id:
        rows=db.execute("""
            SELECT request_id AS identifier, entity_key AS fighter_id,
                   writer_text_md AS content, state AS state
              FROM historical_backfill_items
             WHERE job_id=? AND state IN ('WRITING','READY','IMPORTED')
               AND trim(coalesce(writer_text_md,'')) <> ''
             ORDER BY ordinal
        """,(job_id,)).fetchall()
    else:
        rows=db.execute("""
            SELECT memory_id AS identifier, fighter_id, content, writer_status AS state
              FROM story_memories
             WHERE active=1 AND memory_type != 'reflection'
               AND trim(coalesce(content,'')) <> ''
             ORDER BY fighter_id, memory_id
        """).fetchall()
    errors=[]
    for row in rows:
        candidate={'form':'fighter_memory','entity_key':str(row['fighter_id'])}
        issue=fighter_memory_title_error(store,candidate,row['content'])
        if issue:
            errors.append({'id':str(row['identifier']),
                           'fighter_id':str(row['fighter_id']),
                           'state':str(row['state']),'reason':issue})
    result={'scope':job_id or 'all_active_memories','scanned':len(rows),
            'violations':len(errors),'findings':errors,
            'pass':not errors}
    db.close()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,help='Path to existing NCCE SQLite database')
    parser.add_argument('--job-id',help='Optional finite historical backfill job UUID')
    args=parser.parse_args()
    result=audit(args.db,args.job_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['pass'] else 1


if __name__=='__main__':
    raise SystemExit(main())
