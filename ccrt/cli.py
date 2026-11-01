"""Small CLI using the same library APIs as notebooks."""

import argparse
import sys
from pathlib import Path

from ccrt._version import __version__
from ccrt.client import UCDPClient, UCDPError
from ccrt.config import ucdp_api_key
from ccrt.export import read_review_csv, write_csv, write_parquet, write_records_csv
from ccrt.interactive import review_interactive
from ccrt.loaders import load_acled_csv, load_csv, load_ucdp_csv
from ccrt.merge import MatchConfig, reconcile
from ccrt.report import format_review_report, summarize_review
from ccrt.review import Review
from ccrt.schema import canonical_json
from ccrt.storage import (
    atomic_write,
    load_dataset,
    load_review,
    load_run,
    save_dataset,
    save_review,
    save_run,
)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ccrt", description="Reviewable conflict record reconciliation")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    imp = commands.add_parser("import", help="Normalize a source CSV into a CCRT JSON bundle")
    imp.add_argument("source", choices=["ucdp", "acled", "generic"])
    imp.add_argument("input")
    imp.add_argument("output")
    imp.add_argument("--version", required=True, help="GED release or export snapshot label")
    imp.add_argument("--source-name", help="Source label for generic CSV")
    imp.add_argument(
        "--collect-errors", action="store_true", help="Retain invalid rows in the validation report"
    )
    fetch = commands.add_parser("fetch-ucdp", help="Fetch GED using UCDP_API_KEY or a local .env")
    fetch.add_argument("output")
    fetch.add_argument("--version", required=True)
    fetch.add_argument("--country", type=int, action="append", help="Gleditsch-Ward country ID; repeatable")
    fetch.add_argument("--start-date")
    fetch.add_argument("--end-date")
    fetch.add_argument("--max-pages", type=int, default=5000)
    fetch.add_argument(
        "--env-file", help="Read UCDP_API_KEY from this file when it is not set in the environment"
    )
    match = commands.add_parser("match", help="Create all candidate links and a review table")
    match.add_argument("left")
    match.add_argument("right")
    match.add_argument("output_dir")
    match.add_argument("--max-days", type=int, default=3)
    match.add_argument("--max-km", type=float, default=25)
    match.add_argument("--include-coarse-locations", action="store_true")
    match.add_argument("--country-alias", action="append", default=[], metavar="FROM=TO")
    review = commands.add_parser("review", help="Import edited review CSV or record one decision")
    review.add_argument("run")
    review.add_argument("output")
    review.add_argument("--existing", help="Continue a saved review JSON")
    method = review.add_mutually_exclusive_group(required=True)
    method.add_argument("--csv", help="Edited review CSV")
    method.add_argument("--candidate")
    review.add_argument("--status", choices=["accepted", "rejected", "unresolved"])
    review.add_argument("--reviewer", default="")
    review.add_argument("--note", default="")
    interactive = commands.add_parser(
        "review-interactive", help="Review source accounts in the terminal and save each decision"
    )
    interactive.add_argument("run", help="Match run.json")
    interactive.add_argument("output", help="Review JSON; created or resumed in place")
    interactive.add_argument("--from-existing", help="Seed a new review JSON from an earlier review")
    interactive.add_argument("--reviewer", required=True, help="Name recorded with decisions")
    interactive.add_argument("--left-id", help="Inspect one left-side source record and its candidates")
    interactive.add_argument("--all", action="store_true", help="Include already decided groups")
    tui = commands.add_parser("review-tui", help="Experimental full-screen terminal review dashboard")
    tui.add_argument("run", help="Match run.json")
    tui.add_argument("output", help="Review JSON; created or resumed in place")
    tui.add_argument("--from-existing", help="Seed a new review JSON from an earlier review")
    tui.add_argument("--reviewer", required=True, help="Name recorded with decisions")
    tui.add_argument("--left-id", help="Start at a left-side source record")
    report = commands.add_parser("report", help="Summarize review coverage and accepted-link diagnostics")
    report.add_argument("run", help="Match run.json")
    report.add_argument("--review", help="Saved review JSON; omitted means all unresolved")
    report.add_argument("--output", help="Also save a new JSON report")
    export = commands.add_parser("export", help="Export normalized data or a reviewed run")
    export.add_argument("input")
    export.add_argument("output")
    export.add_argument("--format", choices=["csv", "parquet", "review-csv"], required=True)
    export.add_argument("--review", help="Saved review JSON for review-csv")
    args = parser.parse_args(argv)
    try:
        if args.command in {"import", "fetch-ucdp", "review", "export"} and Path(args.output).exists():
            raise FileExistsError(f"output exists: {args.output}")
        if args.command == "import":
            options = {"version": args.version, "errors": "collect" if args.collect_errors else "raise"}
            if args.source == "generic":
                if not args.source_name:
                    raise ValueError("generic import requires --source-name")
                dataset = load_csv(args.input, args.source_name, **options)
            else:
                dataset = {"ucdp": load_ucdp_csv, "acled": load_acled_csv}[args.source](args.input, **options)
            save_dataset(dataset, args.output)
            print(f"Imported {len(dataset)} records; {len(dataset.issues)} validation issues")
        elif args.command == "fetch-ucdp":
            with UCDPClient(api_key=ucdp_api_key(args.env_file)) as client:
                dataset = client.fetch(
                    version=args.version,
                    countries=args.country,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    max_pages=args.max_pages,
                )
            save_dataset(dataset, args.output)
            print(f"Fetched {len(dataset)} records; {len(dataset.issues)} validation issues")
        elif args.command == "match":
            aliases = {}
            for value in args.country_alias:
                if "=" not in value:
                    raise ValueError("country aliases use FROM=TO")
                key, target = value.split("=", 1)
                aliases[key] = target
            result = reconcile(
                load_dataset(args.left),
                load_dataset(args.right),
                config=MatchConfig(args.max_days, args.max_km, args.include_coarse_locations, aliases),
            )
            directory = Path(args.output_dir)
            directory.mkdir(parents=True, exist_ok=False)
            save_run(result, directory / "run.json")
            save_review(Review.create(result), result, directory / "review.json")
            write_csv(result, directory / "candidates.csv")
            print(f"{len(result.candidates)} candidate links; {len(result.unlinked)} unlinked records")
        elif args.command == "review":
            result = load_run(args.run)
            if args.csv:
                if args.existing or args.status or args.reviewer or args.note:
                    raise ValueError("--csv cannot be combined with single-decision options")
                review = read_review_csv(args.csv, result)
            else:
                if not args.status:
                    raise ValueError("--candidate requires --status")
                review = load_review(args.existing, result) if args.existing else Review.create(result)
                review = review.decide(args.candidate, args.status, reviewer=args.reviewer, note=args.note)
            save_review(review, result, args.output)
            print(f"Saved {len(review.decisions)} review decisions")
        elif args.command in {"review-interactive", "review-tui"}:
            if args.command == "review-tui" and (not sys.stdin.isatty() or not sys.stdout.isatty()):
                raise ValueError("review-tui needs an interactive terminal")
            result = load_run(args.run)
            output = Path(args.output)
            if output.exists():
                if args.from_existing:
                    raise ValueError("output already exists; omit --from-existing to resume it")
                current = load_review(output, result)
            else:
                current = (
                    load_review(args.from_existing, result) if args.from_existing else Review.create(result)
                )
                save_review(current, result, output)

            def save(updated):
                save_review(updated, result, output, overwrite=True)

            if args.command == "review-tui":
                from ccrt.tui import run_tui

                run_tui(result, current, reviewer=args.reviewer, left_id=args.left_id, save=save)
            else:
                review_interactive(
                    result,
                    current,
                    reviewer=args.reviewer,
                    left_id=args.left_id,
                    show_all=args.all,
                    save=save,
                )
        elif args.command == "report":
            result = load_run(args.run)
            review = load_review(args.review, result) if args.review else None
            summary = summarize_review(result, review)
            if args.output:
                atomic_write(args.output, canonical_json(summary.to_dict()) + "\n")
            print(format_review_report(summary))
        else:
            if args.format == "review-csv":
                result = load_run(args.input)
                review = load_review(args.review, result) if args.review else None
                write_csv(result, args.output, review=review)
            else:
                if args.review:
                    raise ValueError("--review only applies to --format review-csv")
                dataset = load_dataset(args.input)
                writer = write_parquet if args.format == "parquet" else write_records_csv
                writer(dataset, args.output)
            print(f"Wrote {args.output}")
    except (OSError, ValueError, UCDPError, ImportError) as exc:
        parser.exit(2, f"ccrt: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
