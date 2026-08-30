#!/usr/bin/env python3
"""Chunked deploy helper for Iron Log.

The app is one large single-file HTML build. Pushing the whole file on every
tweak is slow and all-or-nothing, so the source of truth is a set of
line-aligned chunks under src/chunks/ plus a manifest holding the sha256 of
the assembled result.

    python3 tools/chunk.py split   WorkoutApp.html  -> src/chunks/*, manifest.json
    python3 tools/chunk.py build   src/chunks/*     -> WorkoutApp.html (hash-checked)
    python3 tools/chunk.py check   verify chunks assemble to the manifest hash

build refuses to write the target unless the reassembled bytes match
manifest["sha256"] exactly, so a half-finished chunk push can never publish a
broken app.
"""

import hashlib
import json
import os
import sys

TARGET = "WorkoutApp.html"
CHUNK_DIR = os.path.join("src", "chunks")
MANIFEST = os.path.join(CHUNK_DIR, "manifest.json")
CHUNK_BYTES = 24576  # ~24 KB, split only on line boundaries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def part_path(n: int) -> str:
    return os.path.join(CHUNK_DIR, "part-%03d.html" % n)


def split() -> int:
    with open(TARGET, "rb") as fh:
        data = fh.read()

    # Keep whole lines together so chunk diffs stay readable.
    parts, current = [], bytearray()
    for line in data.splitlines(keepends=True):
        if current and len(current) + len(line) > CHUNK_BYTES:
            parts.append(bytes(current))
            current = bytearray()
        current += line
    if current:
        parts.append(bytes(current))

    os.makedirs(CHUNK_DIR, exist_ok=True)
    for stale in os.listdir(CHUNK_DIR):
        if stale.startswith("part-"):
            os.remove(os.path.join(CHUNK_DIR, stale))

    for i, part in enumerate(parts, 1):
        with open(part_path(i), "wb") as fh:
            fh.write(part)

    manifest = {
        "target": TARGET,
        "parts": len(parts),
        "bytes": len(data),
        "sha256": sha256(data),
        "chunk_bytes": CHUNK_BYTES,
    }
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    assert b"".join(parts) == data, "round-trip failed"
    print("split %s into %d chunks (%d bytes, sha256 %s)"
          % (TARGET, len(parts), len(data), manifest["sha256"][:12]))
    return 0


def assemble():
    with open(MANIFEST) as fh:
        manifest = json.load(fh)

    blobs = []
    for i in range(1, manifest["parts"] + 1):
        path = part_path(i)
        if not os.path.exists(path):
            sys.exit("missing chunk %s (manifest expects %d parts)"
                     % (path, manifest["parts"]))
        with open(path, "rb") as fh:
            blobs.append(fh.read())

    data = b"".join(blobs)
    got = sha256(data)
    if got != manifest["sha256"]:
        sys.exit(
            "hash mismatch - refusing to publish\n"
            "  manifest: %s (%d bytes)\n"
            "  assembled: %s (%d bytes)\n"
            "Update manifest.json's sha256/bytes to match the chunks you changed."
            % (manifest["sha256"], manifest["bytes"], got, len(data))
        )
    return manifest, data


def build() -> int:
    manifest, data = assemble()
    existing = None
    if os.path.exists(TARGET):
        with open(TARGET, "rb") as fh:
            existing = fh.read()
    if existing == data:
        print("%s already matches the chunks - nothing to publish" % TARGET)
        return 0
    with open(TARGET, "wb") as fh:
        fh.write(data)
    print("published %s from %d chunks (%d bytes, sha256 %s)"
          % (TARGET, manifest["parts"], len(data), manifest["sha256"][:12]))
    return 0


def check() -> int:
    manifest, data = assemble()
    print("chunks are consistent: %d parts, %d bytes, sha256 %s"
          % (manifest["parts"], len(data), manifest["sha256"][:12]))
    return 0


COMMANDS = {"split": split, "build": build, "check": check}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit("usage: chunk.py {split|build|check}")
    raise SystemExit(COMMANDS[sys.argv[1]]())
