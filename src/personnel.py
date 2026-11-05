"""Presentation identifiers from verified Munda Manager fighter UUIDs."""
import json
import re
import unicodedata
from uuid import UUID


def normal(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(value or '')).strip().casefold())


def gang_code(name):
    name = normal(name)
    for needle, code in (('c-nine','c9'),('slag eaters','se'),('kły sprawiedliwo','ks'),
                         ('ethernetans','et'),('helmaeth','he'),('patrol do spraw','pa')):
        if needle in name:
            return code
    words = re.findall(r'[^\W\d_]+', name, re.UNICODE)
    words = [w for w in words if w not in {'the','of','and','do','spraw','i'}]
    return ''.join(w[0] for w in words[:2]) if len(words)>1 else (words[0][:2] if words else '')


def valid_uuid(value):
    try:
        UUID(str(value))
        return bool(re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', str(value)))
    except (ValueError, TypeError, AttributeError):
        return False


def identity(store, fighter):
    mechanics = json.loads(fighter.get('mechanics_json') or '{}')
    explicit = {str(mechanics[k]) for k in ('Fighter ID','fighter_id','source_fighter_id') if valid_uuid(mechanics.get(k))}
    candidates = set(explicit)
    if not explicit:
        for row in store.db.execute('SELECT normalized_json FROM campaign_archive_records'):
            entry = json.loads(row[0])
            if (str(entry.get('gang_id')) == str(fighter.get('gang_id'))
                    and normal(entry.get('fighter_name_hint')) == normal(fighter.get('name'))
                    and valid_uuid(entry.get('fighter_id'))):
                candidates.add(str(entry['fighter_id']))
    # Case differences do not make two UUID identities, but retain source case.
    if len({c.casefold() for c in candidates}) != 1:
        return {'source_fighter_id':None, 'personnel_code':None,
                'personnel_code_status':'Munda Manager fighter UUID unavailable or ambiguous'}
    source_id = sorted(candidates)[0]
    prefix = gang_code(fighter.get('gang_name'))
    return {'source_fighter_id':source_id, 'personnel_code':f'{prefix}-MK/{source_id[-4:]}' if len(prefix)==2 else None,
            'personnel_code_status':'Munda Manager fighter UUID'}
