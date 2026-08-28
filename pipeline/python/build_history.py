#!/usr/bin/env python3
"""Print a conservative candidate-date plan; optional execution is intentionally explicit."""
from __future__ import annotations
import argparse
import os
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def candidate_dates(start_year: int, end_year: int) -> list[date]:
    # Post-monsoon dates reduce, but cannot eliminate, cloud and seasonal ambiguity.
    dates = [date(year, 10, 15) for year in range(start_year, min(end_year, 2016) + 1)]
    for year in range(max(start_year, 2017), end_year + 1):
        dates.extend([date(year, 4, 15), date(year, 10, 15)])
    return dates

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=1985)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--execute", action="store_true", help="Run the Sentinel-2 processor for recent candidates after review")
    parser.add_argument("--project", default=os.environ.get("OPENIMJA_EE_PROJECT"), help="Earth Engine-enabled Google Cloud project")
    parser.add_argument("--auth-source", choices=["earthengine", "application-default"], default="earthengine")
    args = parser.parse_args()
    if args.execute and not args.project:
        parser.error("--project (or OPENIMJA_EE_PROJECT) is required with --execute")
    for candidate in candidate_dates(args.start_year, args.end_year):
        print(candidate.isoformat())
        if args.execute:
            processor = "pipeline/python/process_sentinel2.py" if candidate.year >= 2017 else "pipeline/python/process_landsat.py"
            subprocess.run(["python", processor, "--date", candidate.isoformat(), "--project", args.project, "--auth-source", args.auth_source], cwd=ROOT, check=False)
    if not args.execute:
        print("Candidate plan only. Review each output boundary and quality flag before publishing a historical series.")

if __name__ == "__main__":
    main()
