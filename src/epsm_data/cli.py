"""Inspect LoD2 completeness or check the catalogue against its sanity fixture."""

import argparse
import json
from importlib.resources import files
from pathlib import Path

from .catalogue import Catalogue
from .library import _object
from .sanity import check_catalogue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="Explicit catalogue JSON file or directory")
    parser.add_argument("--source-cache", help="Explicit source-cache manifest file or directory")
    parser.add_argument("--check-sources", action="store_true", help="Verify the pinned local source cache")
    parser.add_argument("--online", action="store_true", help="Also check upstream releases; requires --check-sources")
    parser.add_argument("--timeout", type=float, default=3, help="Per-source network timeout in seconds")
    parser.add_argument("--sanity", action="store_true", help="Report forward sanity checks against the maintained fixture")
    parser.add_argument("--fixture", help="Explicit sanity fixture directory; requires --sanity")
    parser.add_argument("--check", action="store_true", help="Exit nonzero for errors or missing required values; review findings remain visible")
    args = parser.parse_args(argv)
    if args.fixture and not args.sanity:
        parser.error("--fixture requires --sanity")
    if args.online and not args.check_sources:
        parser.error("--online requires --check-sources")
    if args.check_sources and args.sanity:
        parser.error("Choose --check-sources or --sanity")
    try:
        if args.check_sources:
            report = Catalogue.load(args.path, source_cache=args.source_cache).check_sources(
                online=args.online, timeout=args.timeout)
            failed = report["status"] not in {"local_verified", "same", "verified"}
        elif args.sanity:
            target = Path(args.path) if args.path else files("epsm_data.datasets.lod2").joinpath("catalogue.json")
            if args.path and target.is_dir():
                target = target / "catalogue.json"
            payload = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=_object)
            if payload.get("schema_version") == 2:
                payload = Catalogue(payload, source_cache=args.source_cache)
            report = check_catalogue(payload, fixture=args.fixture)
            failed = report["summary"]["blocking_count"] > 0
        else:
            report = Catalogue.load(args.path, source_cache=args.source_cache).summary()
            failed = report["incomplete_slots"] or report.get("missing_families")
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return int(bool(args.check and failed))


if __name__ == "__main__":
    raise SystemExit(main())
