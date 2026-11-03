"""Scoped native-author transport. Uses existing NCCE credentials; never starts models."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

DEFAULT_CONFIG = Path('C:/Codex/NCCE/.codex-review-bridge/config.json')
DEFAULT_ROOT = Path('C:/Codex/NCCE/.native-writing')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def call(config_path, action, body, root):
    config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
    base = config['base_url'].rstrip('/')
    url = urlparse(base)
    if url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('Expected a plain NCCE origin, without credentials or path')
    if not ((url.scheme == 'https' and url.hostname == 'ncce-private-preview.onrender.com') or
            (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost'))):
        raise ValueError('Native-author client is restricted to the existing NCCE preview or loopback')
    payload = {**body, 'thread_id': config['thread_id']}
    request = Request(base + '/api/native-author/' + action, data=json.dumps(payload, allow_nan=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + config['token']}, method='POST')
    try:
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get('error', 'Request rejected')
        except (ValueError, AttributeError):
            detail = 'Request rejected; the server may not have the native-author release yet'
        raise ValueError(('NCCE HTTP ' + str(exc.code) + ': ' + str(detail)).replace(config['token'], '[redacted]')) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('NCCE connection failed or response uncertain. Inspect status with the same IDs; do not regenerate or create another reservation.') from None
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if config['token'] in text:
        raise ValueError('Unexpected credential in response; not saved')
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    target = root / ('response-' + uuid.uuid4().hex + '.json')
    with target.open('x', encoding='utf-8') as handle:
        handle.write(text)
    summary = {k: result[k] for k in ('batch_id', 'draft_id', 'key', 'form', 'status', 'attempt', 'max_drafts', 'publish_hash') if k in result}
    summary.update(path=str(target), sha256=digest, sections=list(result),
                   notice='Read saved response sections with client.py read; no model was called by this helper.')
    return summary


def read(path, sha256, pointer='', offset=0):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError('Response hash mismatch')
    value = json.loads(raw)
    if pointer and not pointer.startswith('/'):
        raise ValueError('Use a JSON pointer')
    for token in pointer.split('/')[1:] if pointer else []:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if offset < 0 or offset > len(text):
        raise ValueError('Invalid offset')
    end = min(len(text), offset + 3000)
    return {'text': text[offset:end], 'next_offset': end, 'complete': end == len(text), 'section': pointer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('catalog')
    sub.add_parser('batches')
    p = sub.add_parser('context'); p.add_argument('--key', required=True)
    p = sub.add_parser('start'); p.add_argument('--forms', nargs='+'); p.add_argument('--keys', nargs='+'); p.add_argument('--max-drafts', type=int, required=True); p.add_argument('--request-key', required=True); p.add_argument('--replace-generated', action='store_true')
    p = sub.add_parser('prepare'); p.add_argument('--batch-id', required=True); p.add_argument('--key'); p.add_argument('--request-key', required=True)
    p = sub.add_parser('save'); p.add_argument('--draft-id', required=True); p.add_argument('--file', type=Path, required=True)
    p = sub.add_parser('publish'); p.add_argument('--draft-id', required=True); p.add_argument('--confirm-publish', required=True)
    p = sub.add_parser('status'); p.add_argument('--id', required=True)
    p = sub.add_parser('stop'); p.add_argument('--batch-id', required=True)
    p = sub.add_parser('abandon'); p.add_argument('--draft-id', required=True); p.add_argument('--reason', required=True)
    p = sub.add_parser('read'); p.add_argument('--file', type=Path, required=True); p.add_argument('--sha256', required=True); p.add_argument('--section', default=''); p.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == 'read':
            result = read(args.file, args.sha256, args.section, args.offset)
        else:
            body = {k: v for k, v in vars(args).items() if k not in ('action', 'config', 'root', 'file', 'replace_generated') and v is not None}
            if args.action == 'start':
                body['mode'] = 'replace_generated' if args.replace_generated else 'missing'
            if args.action == 'save':
                data = json.loads(args.file.read_text(encoding='utf-8-sig'))
                if not isinstance(data, dict) or set(data) != {'output', 'checks'}:
                    raise ValueError('Save file must contain exactly output and checks')
                body.update(data)
            result = call(args.config, args.action, body, args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
