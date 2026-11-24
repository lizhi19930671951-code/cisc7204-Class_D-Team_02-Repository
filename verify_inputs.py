"""Verify the full set of source inputs against the study's release manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verify():
    from prepare_data import trip_members
    manifest = json.loads((ROOT / "raw_manifest.json").read_text(encoding="utf-8"))
    unavailable = []
    trips={Path(entry["path"]).name:entry for entry in manifest if "2023-citibike-tripdata/" in entry["path"]}
    seen=set()
    for name, source in trip_members(ROOT/"data/raw"):
        if name not in trips or name in seen:
            unavailable.append(name)
            continue
        seen.add(name)
        if isinstance(source,Path):
            with source.open("rb") as handle:
                digest=hashlib.file_digest(handle,"sha256").hexdigest()
        else:
            digest=hashlib.file_digest(source,"sha256").hexdigest()
        if digest!=trips[name]["sha256"]:
            unavailable.append(name)
    unavailable.extend(sorted(set(trips).difference(seen)))
    for entry in manifest:
        if "2023-citibike-tripdata/" in entry["path"]:
            continue
        path = ROOT / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            unavailable.append(entry["path"])
            continue
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != entry["sha256"]:
            unavailable.append(entry["path"])
    if unavailable:
        raise SystemExit("Missing or different source inputs:\n" + "\n".join(unavailable))
    print(f"All {len(manifest)} source inputs match the study release.")


if __name__ == "__main__":
    verify()
