"""Exercise a small disposable job through the real HTTP handler and SQLite."""
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

from test_historical_backfill import ROOT, TEXT, bulk, exchange, fixture


def main():
    tmp, store, gang = fixture()
    token = "disposable-local-bulk-relay-token-" + "0" * 32
    try:
        exchange.prepare(store, client_states=[])
        origin = next(p["request"] for p in exchange.outbox(store)
                      if p["request"]["form"] == "gang_origin" and p["request"]["entity_key"] == gang)
        assert exchange.deliver(store, {**origin, "status":"READY", "writer_text_md":TEXT})["status"] == "imported"
        candidates = exchange.candidates(store)
        selected = next(c for c in bulk.plan(store, candidates)[0] if bulk._eligible(store, c, {gang}))
        fixture_date = "2026-10-23"
        with store.db:
            store.db.execute(
                "UPDATE story_memories SET occurred_at=? WHERE fighter_id=? AND memory_key=? AND active=1",
                (fixture_date + "T12:00:00Z", *selected["key"]),
            )
        job = bulk.create(store, [gang], start_date=fixture_date, end_date=fixture_date,
                          owner_authorized=True, autonomous_writer_authorized=True, max_items=1)
        assert job["discovered"] == job["queued"] == 1, job
        initial = bulk.summary(store, job["job_id"], include_items=True)
        request_id = initial["items"][0]["request_id"]
        ledger_count = store.db.execute("SELECT COUNT(*) FROM campaign_events").fetchone()[0]
        with patch.dict(os.environ, {"NCCE_DB_PATH":str(Path(tmp.name) / "http-bootstrap.db"),
                                    "NCCE_REQUIRE_AUTH":"0", "NCCE_EXCHANGE_TOKEN":token}):
            import server
            original = server.store
            server.store = store
            try:
                with server.ThreadingHTTPServer(("127.0.0.1", 0), server.H) as http:
                    thread = threading.Thread(target=http.serve_forever, daemon=True)
                    thread.start()
                    try:
                        subprocess.run(["node", str(ROOT / "tests/test_autonomous_bulk_e2e.cjs"),
                                        f"http://127.0.0.1:{http.server_port}", token, job["job_id"], request_id],
                                       cwd=ROOT, check=True, timeout=75)
                    finally:
                        http.shutdown()
                        thread.join()
            finally:
                server.store = original
                original.close()
        assert store.db.execute("SELECT COUNT(*) FROM campaign_events").fetchone()[0] == ledger_count
        assert store.db.execute(
            "SELECT COUNT(*) FROM writing_exchange_requests WHERE request_id=? AND state='IMPORTED'",
            (request_id,),
        ).fetchone()[0] == 1
    finally:
        store.close()
        tmp.cleanup()


if __name__ == "__main__":
    main()
