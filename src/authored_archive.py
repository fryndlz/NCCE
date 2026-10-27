"""Read-only story excerpts; full source documents remain intact in lore_sources."""
from __future__ import annotations
import re


def stories(store):
    result = []
    for row in store.db.execute('SELECT * FROM lore_sources ORDER BY id'):
        text = str(row['content'] or '').replace('\r\n', '\n')
        if not ('C-NINE' in str(row['title']).upper() or 'GEOTHERMAL PROSPECT DETAIL C-9' in text):
            continue
        for slug, title, stop in (
            ('prospect', 'The Prospect', r'^\s*CYCLE\s+1\s*$'),
            ('deep-answers', 'The Deep Answers', r'^\s*DOWNTIME\s*$'),
        ):
            start = re.search(r'^' + re.escape(title.upper()) + r'\s*$', text, re.M)
            if not start:
                continue
            end = re.search(stop, text[start.end():], re.M)
            # Do not accidentally swallow incident reports or personnel files if
            # an expected source boundary is missing.
            if not end:
                continue
            content = text[start.end():start.end()+end.start()].strip()
            result.append({'id':f"{row['id']}:{slug}", 'title':title,
                           'content':content, 'source_type':row['source_type'],
                           'source_url':row['source_url'], 'source_id':row['id'],
                           'source_locator':title.upper(), 'provenance_class':'canon_authored'})
    return result
