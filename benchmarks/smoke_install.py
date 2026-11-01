"""Exercise an installed wheel outside its checkout, with optional table support.

Run using a fresh environment's Python from a directory outside this repository:
    /tmp/ccrt-smoke/bin/python /path/to/repo/benchmarks/smoke_install.py
Then install the wheel's tables extra and repeat with --tables.
"""

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import ccrt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", action="store_true")
    args = parser.parse_args()
    checkout = Path(__file__).resolve().parents[1]
    installed = Path(ccrt.__file__).resolve()
    if installed.is_relative_to(checkout):
        raise RuntimeError("smoke test imported the checkout; use a fresh wheel installation")
    if not args.tables:
        assert importlib.util.find_spec("pandas") is None, "core smoke environment contains pandas"
        assert importlib.util.find_spec("pyarrow") is None, "core smoke environment contains PyArrow"
    console = Path(sys.executable).parent / ("ccrt.exe" if os.name == "nt" else "ccrt")
    child_env = dict(os.environ)
    child_env.pop("PYTHONPATH", None)

    with tempfile.TemporaryDirectory(prefix="ccrt-installed-workflow-") as directory:
        work = Path(directory)

        def run(*arguments):
            completed = subprocess.run(
                [str(console), *map(str, arguments)],
                cwd=work,
                env=child_env,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                raise RuntimeError(f"ccrt {' '.join(map(str, arguments))}: {completed.stderr}")
            return completed.stdout

        assert "Reviewable" in run("--help")
        assert run("--version").strip() == ccrt.__version__
        run(
            "import",
            "ucdp",
            checkout / "examples/ucdp_synthetic.csv",
            work / "ucdp.json",
            "--version",
            "26.1",
        )
        run(
            "import",
            "acled",
            checkout / "examples/acled_synthetic.csv",
            work / "acled.json",
            "--version",
            "smoke",
        )
        run("match", work / "ucdp.json", work / "acled.json", work / "matches")
        result = ccrt.load_run(work / "matches/run.json")
        assert len(result.candidates) == 3
        candidate = next(
            c for c in result.candidates if (c.left.source_id, c.right.source_id) == ("U1", "A1")
        )
        run(
            "review",
            work / "matches/run.json",
            work / "review.json",
            "--candidate",
            candidate.candidate_id,
            "--status",
            "accepted",
            "--reviewer",
            "Smoke test",
        )
        run(
            "report",
            work / "matches/run.json",
            "--review",
            work / "review.json",
            "--output",
            work / "report.json",
        )
        report = json.loads((work / "report.json").read_text())
        assert (report["accepted_count"], report["unresolved_count"]) == (1, 2)
        run(
            "export",
            work / "matches/run.json",
            work / "review.csv",
            "--format",
            "review-csv",
            "--review",
            work / "review.json",
        )
        with (work / "review.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert sum(row["status"] == "accepted" for row in rows) == 1
        assert sum(row["status"] == "unlinked" for row in rows) == 4
        run("export", work / "ucdp.json", work / "records.csv", "--format", "csv")
        if args.tables:
            from ccrt.export import read_parquet

            run("export", work / "ucdp.json", work / "ucdp.parquet", "--format", "parquet")
            original = ccrt.load_dataset(work / "ucdp.json")
            assert read_parquet(work / "ucdp.parquet") == original
            assert len(original.to_pandas()) == len(original)

    subprocess.run([sys.executable, "-m", "pip", "check"], check=True, env=child_env)
    mode = "core + tables" if args.tables else "core"
    print(f"Installed-package workflow passed ({mode}): {installed}")


if __name__ == "__main__":
    main()
