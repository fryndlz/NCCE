"""Generate a self-contained current NCCE writing-policy handoff ZIP on demand.

No private campaign DB or cached source secrets are exported; live campaign
facts must still be checked from the canonical Sheet. This endpoint cannot
autonomously learn: rules persist only after an explicit committed file edit.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
EXPORTED_FILES = (
    "skills/ncce-prose-portability/SKILL.md",
    "skills/ncce-prose-portability/HANDOFF.md",
    "skills/ncce-prose-portability/PROCESS.md",
    "skills/ncce-prose-portability/CHANGELOG.md",
    "config/literary_profiles.v2.json",
    "config/voice_registry.v1.json",
    "docs/writing_sources/WRITER_RUNTIME_CONTRACT.md",
    "docs/WRITER_IDENTITY_TAGS.md",
    "docs/VOICE_REGISTRY.md",
)


def build_portable_zip(root=ROOT):
    root = Path(root).resolve()
    from literary_policy import validate_policy
    data = json.loads((root / "config/literary_profiles.v2.json").read_text(encoding="utf-8"))
    validate_policy(data)
    manifest = {
        "packet_version": data["policy_version"],
        "purpose": "portable current writing policy; not a mechanical campaign snapshot",
        "exemplars": "eight source-labelled illustrative excerpts in config/literary_profiles.v2.json",
        "files": {},
    }
    content = {}
    for relative in EXPORTED_FILES:
        file = (root / relative).resolve()
        if root not in file.parents or not file.is_file():
            raise ValueError("Missing or unsafe portable writing source: " + relative)
        body = file.read_bytes()
        if len(body) > 1024 * 1024:
            raise ValueError("Portable writing policy source unexpectedly large: " + relative)
        content[relative] = body
        manifest["files"][relative] = hashlib.sha256(body).hexdigest()
    description = (
        "# NCCE writing packet, version " + data["policy_version"] + "\n\n"
        "Open skills/ncce-prose-portability/SKILL.md and HANDOFF.md first.\n"
        "This ZIP is generated from NCCE's currently deployed, versioned policy files.\n"
        "It includes eight illustrative excerpt records, not the complete historical\n"
        "example biographies. Fetch exact full examples from the cited Writing\n"
        "Exchange when authorized. No campaign data, private secrets or fresh\n"
        "fighter state is embedded. Runtime policy must match the latest owner\n"
        "decision before claiming a new version. No background cross-chat sync.\n"
    )
    content["README.md"] = description.encode("utf-8")
    manifest["files"]["README.md"] = hashlib.sha256(content["README.md"]).hexdigest()
    content["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2)+"\n").encode("utf-8")
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED, compresslevel=8) as bundle:
        for filename in sorted(content):
            bundle.writestr(filename, content[filename])
    return buffer.getvalue(), manifest
