"""Sensitivity analysis on exhaustively labeled, bounded inputs."""

import argparse
import csv
import json
from dataclasses import asdict

from ccrt import MatchConfig, load_dataset, reconcile
from ccrt.evaluation import evaluate_candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("truth_csv", help="All true pairs: left_id,right_id")
    parser.add_argument(
        "--exhaustive",
        action="store_true",
        required=True,
        help="Acknowledge that unlabeled pairs in these inputs are negative",
    )
    args = parser.parse_args()
    with open(args.truth_csv, newline="", encoding="utf-8") as stream:
        truth = {(row["left_id"], row["right_id"]) for row in csv.DictReader(stream)}
    left, right = load_dataset(args.left), load_dataset(args.right)
    reports = []
    for max_days, max_km, coarse in ((0, 1, False), (3, 25, False), (3, 25, True)):
        config = MatchConfig(max_days=max_days, max_km=max_km, include_coarse_locations=coarse)
        result = reconcile(left, right, config=config)
        reports.append(
            {
                "config": config.to_dict(),
                "run_id": result.run_id,
                **asdict(evaluate_candidates(result, truth)),
            }
        )
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
