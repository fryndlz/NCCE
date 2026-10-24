"""Read-only adapter for the link-readable Krakamunda campaign workbook."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from snapshot import build_snapshot_from_sheets, read_xlsx_sheets

SHEET_ID = "1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00"
SHEET_TITLE = "Krakamunda Fetch-a-Munda LIVE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
MAX_WORKBOOK_BYTES = 20_000_000


def fetch_snapshot(timeout: int = 30) -> dict:
    """Fetch the workbook export and return a normalized mechanical snapshot.

    The request is a GET to the Sheet's link-readable XLSX export. This adapter has
    no write route, credentials, or token storage.
    """
    request = Request(EXPORT_URL, headers={"User-Agent": "NCCE-read-only-sync/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").casefold()
            if response.status != 200:
                raise RuntimeError(f"Google Sheets export returned HTTP {response.status}")
            if "spreadsheetml.sheet" not in content_type and "application/octet-stream" not in content_type:
                raise RuntimeError(f"Google Sheets returned an unexpected export type: {content_type or 'unknown'}")
            data = response.read(MAX_WORKBOOK_BYTES + 1)
    except HTTPError as exc:
        raise RuntimeError(f"Google Sheets export returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach the Google Sheets export: {exc}") from exc
    if len(data) > MAX_WORKBOOK_BYTES:
        raise RuntimeError("Google Sheets export exceeds the 20 MB safety limit")
    sheets = read_xlsx_sheets(data)
    snapshot = build_snapshot_from_sheets(sheets, captured_at=datetime.now(timezone.utc).isoformat())
    snapshot["source_metadata"] = {
        **snapshot.get("source_metadata", {}),
        "source_title": SHEET_TITLE,
        "source_url": SHEET_URL,
    }
    return snapshot
