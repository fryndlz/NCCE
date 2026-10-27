"""Run the frontend branch locally with an isolated copy of campaign data.

Listens only on loopback. No model credentials are inherited. Sheet sync remains
read-only and all derived state/Workshop edits go to the preview database.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'data' / 'chronicle.cogitator-preview.db'


def main():
    source = ROOT / 'data' / 'chronicle.db'
    if not PREVIEW.exists() and source.exists():
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(PREVIEW) as target:
            original.backup(target)
    os.environ.update({
        'NCCE_DB_PATH': str(PREVIEW), 'NCCE_HOST': '127.0.0.1',
        'PORT': os.environ.get('NCCE_PREVIEW_PORT', '8877'),
        'NCCE_REQUIRE_AUTH': '1', 'NCCE_ACCESS_PASSWORD': secrets.token_urlsafe(24),
        'NCCE_SESSION_SECRET': secrets.token_urlsafe(48), 'NCCE_SECURE_COOKIES': '0',
        'NCCE_OPENAI_API_KEY': '', 'OPENAI_API_KEY': '',
        'NCCE_AUTO_WRITE_ENABLED': '0', 'NCCE_OPEN_BROWSER': '0',
    })
    sys.path.insert(0, str(ROOT / 'src'))
    import server
    from access import make_session_token

    class LoopbackPreview(server.H):
        def do_GET(self):
            self._preview_bootstrap = self.path.split('?', 1)[0] == '/' and not self._authenticated()
            if self._preview_bootstrap:
                self._preview_token = make_session_token(server.SESSION_KEY)
                if 'Cookie' in self.headers:
                    del self.headers['Cookie']
                self.headers['Cookie'] = 'ncce_session=' + self._preview_token
            super().do_GET()

        def end_headers(self):
            if getattr(self, '_preview_bootstrap', False):
                self.send_header('Set-Cookie', 'ncce_session=' + self._preview_token + '; Path=/; HttpOnly; SameSite=Lax')
            super().end_headers()

    server.H = LoopbackPreview
    print('Cogitator branch preview: http://127.0.0.1:' + os.environ['PORT'] + '/', flush=True)
    print('Isolated database: ' + str(PREVIEW) + '; model calls disabled.', flush=True)
    server.main()


if __name__ == '__main__':
    main()
