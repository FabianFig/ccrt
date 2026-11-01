import subprocess
import sys
from pathlib import Path

from conftest import EXAMPLES

from ccrt import Review, reconcile
from ccrt.storage import load_review, load_run, save_review, save_run


def run(*args):
    return subprocess.run([sys.executable, "-m", "ccrt", *map(str, args)], capture_output=True, text=True)


def test_complete_workflow(tmp_path):
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    assert run("import", "ucdp", EXAMPLES / "ucdp_synthetic.csv", left, "--version", "26.1").returncode == 0
    assert (
        run("import", "acled", EXAMPLES / "acled_synthetic.csv", right, "--version", "snapshot").returncode
        == 0
    )
    output = tmp_path / "matches"
    response = run("match", left, right, output)
    assert response.returncode == 0, response.stderr
    assert "3 candidate links" in response.stdout
    result = load_run(output / "run.json")
    reviewed = tmp_path / "reviewed.json"
    response = run(
        "review",
        output / "run.json",
        reviewed,
        "--candidate",
        result.candidates[0].candidate_id,
        "--status",
        "accepted",
        "--reviewer",
        "Fabian",
    )
    assert response.returncode == 0, response.stderr
    report = tmp_path / "reviewed.csv"
    assert (
        run("export", output / "run.json", report, "--format", "review-csv", "--review", reviewed).returncode
        == 0
    )
    assert "accepted" in report.read_text()
    assert run("export", left, tmp_path / "records.csv", "--format", "csv").returncode == 0
    assert run("match", left, right, output).returncode == 2


def test_errors_without_traceback(tmp_path):
    response = run("import", "ucdp", Path("missing.csv"), tmp_path / "out.json", "--version", "26.1")
    assert response.returncode == 2
    assert "Traceback" not in response.stderr
    assert not (tmp_path / "out.json").exists()


def test_interactive_review_saves_and_resumes(tmp_path):
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    assert run("import", "ucdp", EXAMPLES / "ucdp_synthetic.csv", left, "--version", "26.1").returncode == 0
    assert (
        run("import", "acled", EXAMPLES / "acled_synthetic.csv", right, "--version", "snapshot").returncode
        == 0
    )
    matches = tmp_path / "matches"
    assert run("match", left, right, matches).returncode == 0
    result = load_run(matches / "run.json")
    output = tmp_path / "session.json"
    command = [
        sys.executable,
        "-m",
        "ccrt",
        "review-interactive",
        str(matches / "run.json"),
        str(output),
        "--reviewer",
        "Fabian",
        "--left-id",
        "U1",
    ]
    first = subprocess.run(command, input="1\na\nsame report\nq\n", capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "Candidate account:" in first.stdout
    assert first.stdout.count("Coordinates: lat ") >= 2
    assert "Coordinate separation:" in first.stdout
    assert "proximity score:" in first.stdout
    candidate_id = next(c.candidate_id for c in result.candidates if c.left.source_id == "U1")
    decision = next(d for d in load_review(output, result).decisions if d.candidate_id == candidate_id)
    assert (decision.status, decision.reviewer, decision.note) == ("accepted", "Fabian", "same report")
    second = subprocess.run(command, input="1\nr\nseparate event\nq\n", capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    decision = next(d for d in load_review(output, result).decisions if d.candidate_id == candidate_id)
    assert (decision.status, decision.note) == ("rejected", "separate event")
    navigation = subprocess.run(command, input="n\nq\n", capture_output=True, text=True)
    assert navigation.returncode == 0, navigation.stderr
    assert navigation.stdout.count("Group ") >= 2
    assert "UCDP U2" in navigation.stdout


def test_tui_requires_terminal_before_creating_review(tmp_path):
    output = tmp_path / "session.json"
    response = run("review-tui", "missing-run.json", output, "--reviewer", "Fabian")
    assert response.returncode == 2
    assert "interactive terminal" in response.stderr
    assert not output.exists()


def test_review_report_cli(source_pair, tmp_path):
    import json

    result = reconcile(*source_pair)
    run_path, review_path, report_path = (
        tmp_path / name for name in ("run.json", "review.json", "report.json")
    )
    save_run(result, run_path)
    review = Review.create(result).decide(result.candidates[0].candidate_id, "accepted", reviewer="Fabian")
    save_review(review, result, review_path)
    response = run("report", run_path, "--review", review_path, "--output", report_path)
    assert response.returncode == 0, response.stderr
    assert "Reviewed 1/3" in response.stdout
    payload = json.loads(report_path.read_text())
    assert (payload["accepted_count"], payload["unresolved_count"]) == (1, 2)
    assert load_review(review_path, result) == review
    assert run("report", run_path, "--review", review_path, "--output", report_path).returncode == 2
