"""Inspect the frozen LoD2 catalogue and report missing physical values."""

import argparse
import json

from .catalogue import Catalogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="Explicit catalogue JSON file or directory")
    parser.add_argument(
        "--check", action="store_true", help="Exit nonzero when required LoD2 values are missing"
    )
    args = parser.parse_args()
    report = Catalogue.load(args.path).summary()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.check and (report["incomplete_slots"] or report.get("missing_families")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
