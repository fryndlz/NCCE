"""Lossless private job storage and bounded local reads. No network or models."""
import hashlib
import json
import re
from pathlib import Path

PAGE_OUTPUT_LIMIT = 8000


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


class JobPackets:
    def __init__(self, folder, role):
        if role not in ('reviewer', 'storytech'):
            raise ValueError('Unknown packet role')
        self.folder = Path(folder) / 'packets'
        self.role = role

    def path(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,99}', job_id):
            raise ValueError('Invalid packet job identity')
        target = self.folder / (self.role + '-' + job_id + '.json')
        if target.resolve().parent != self.folder.resolve():
            raise ValueError('Packet must stay in its private folder')
        return target

    def save(self, job, turn_id, secrets=()):
        if not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 120:
            raise ValueError('Actual native turn identity required')
        if any(k in job for k in ('lease', 'lease_hash', 'token', 'worker_id', 'authorization')):
            raise ValueError('Transport secrets must not enter a job packet')
        target = self.path(job['job_id'])
        envelope = {'version': 1, 'role': self.role, 'turn_id': turn_id, 'job': job}
        envelope['content_sha256'] = hashlib.sha256(packed(envelope).encode('utf-8')).hexdigest()
        text = packed(envelope)
        if any(secret and secret in text for secret in secrets):
            raise ValueError('Transport secret detected; packet was not saved')
        self.folder.mkdir(exist_ok=True)
        if target.exists():
            raise ValueError('Saved packet is immutable; inspect it instead of reclaiming')
        temporary = target.with_suffix('.tmp')
        created = False
        try:
            with temporary.open('x', encoding='utf-8', newline='\n') as out:
                created = True
                out.write(text)
                out.flush()
                import os
                os.fsync(out.fileno())
            temporary.replace(target)
        finally:
            if created and temporary.exists():
                temporary.unlink()
        return self.info(job['job_id'])

    def load(self, job_id, expected_hash=None):
        path = self.path(job_id)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_hash and expected_hash != digest:
            raise ValueError('Saved packet hash changed; do not assess incomplete or altered input')
        value = json.loads(raw)
        if value.get('version') != 1 or value.get('role') != self.role or value.get('job', {}).get('job_id') != job_id:
            raise ValueError('Packet identity does not match')
        content = {k:v for k,v in value.items() if k != 'content_sha256'}
        if value.get('content_sha256') != hashlib.sha256(packed(content).encode('utf-8')).hexdigest():
            raise ValueError('Saved packet is corrupt; do not assess altered input')
        return value, digest, len(raw)

    def info(self, job_id):
        envelope, digest, size = self.load(job_id)
        job = envelope['job']
        fields = list(job)
        sections = [{'pointer': '/' + k.replace('~', '~0').replace('/', '~1'),
                     'characters': len(packed(job[k]))} for k in fields[:32] if len(k) <= 160]
        result = {'job': {'job_id': job_id, 'kind': job.get('kind', 'review')},
                'turn_id': envelope['turn_id'], 'packet': {'path': str(self.path(job_id)),
                'sha256': digest, 'bytes': size, 'section_count': len(fields), 'sections': sections},
                'instructions': 'Read every packet section using read-packet --job-id JOB --sha256 HASH --section POINTER --offset 0. Follow next_offset until complete=true. Read the root with --section empty-string if more than 32 sections. Do not claim again.'}
        while len(json.dumps(result, ensure_ascii=True)) > PAGE_OUTPUT_LIMIT - 128 and sections:
            sections.pop()
        result['packet']['index_complete'] = len(sections) == len(fields)
        return result

    def read(self, job_id, expected_hash, pointer='', offset=0, limit=4000):
        if not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-f]{64}', expected_hash):
            raise ValueError('Use the full hash from packet-info')
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 4000:
            raise ValueError('Invalid packet page; limit is 1–4000 characters')
        if not isinstance(pointer, str) or len(pointer) > 300 or pointer and not pointer.startswith('/'):
            raise ValueError('Use a JSON pointer into the saved job')
        envelope, digest, _ = self.load(job_id, expected_hash)
        selected = envelope['job']
        for part in pointer.split('/')[1:] if pointer else []:
            if re.search(r'~(?![01])', part):
                raise ValueError('Invalid JSON pointer escape')
            part = part.replace('~1', '/').replace('~0', '~')
            if isinstance(selected, dict) and part in selected:
                selected = selected[part]
            elif isinstance(selected, list) and re.fullmatch(r'0|[1-9][0-9]*', part) and int(part) < len(selected):
                selected = selected[int(part)]
            else:
                raise ValueError('Packet section not found')
        text = packed(selected)
        if offset > len(text):
            raise ValueError('Packet page offset is beyond the section')
        end = min(len(text), offset + limit)
        while True:
            result = {'job_id': job_id, 'sha256': digest, 'section': pointer,
                      'offset': offset, 'next_offset': end, 'total_characters': len(text),
                      'complete': end == len(text), 'text': text[offset:end]}
            if len(json.dumps(result, ensure_ascii=True)) <= PAGE_OUTPUT_LIMIT:
                return result
            end = offset + max(1, (end - offset) // 2)
