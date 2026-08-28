#!/usr/bin/env python3
"""Manually advance a QA-passing scene from processed to reviewed to published."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from lifecycle import can_transition, should_update_latest

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "data/latest/imja-tsho.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="Scene record beneath data/processed/imja-tsho/scenes")
    parser.add_argument("--to", choices=["reviewed", "published"], required=True)
    parser.add_argument("--note", required=True, help="Human review rationale, retained in state history")
    args = parser.parse_args()
    path = args.record.resolve()
    if ROOT not in path.parents:
        parser.error("record must be inside this repository")
    record = json.loads(path.read_text())
    current = record["observation_state"]
    if not can_transition(current, args.to, record["rejection_reasons"]):
        parser.error(f"invalid transition {current} -> {args.to}")
    record["observation_state"] = args.to
    record.setdefault("state_history", []).append({"state": args.to, "at": now(), "note": args.note})
    path.write_text(json.dumps(record, indent=2) + "\n")
    if args.to == "published":
        existing = json.loads(LATEST.read_text()) if LATEST.exists() else None
        if should_update_latest(existing, record):
            LATEST.write_text(json.dumps({"lake_id": record["lake_id"], "status": "valid_observation", "as_of": now(), "latest_observation": record, "limitations_url": "../../docs/limitations.md"}, indent=2) + "\n")
    print(json.dumps({"record": str(path.relative_to(ROOT)), "state": args.to}, indent=2))


if __name__ == "__main__":
    main()
