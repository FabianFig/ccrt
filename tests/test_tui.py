from conftest import EXAMPLES

from ccrt.loaders import load_acled_csv, load_ucdp_csv
from ccrt.merge import reconcile
from ccrt.review import Review
from ccrt.tui import ReviewDashboard, detail_lines


def test_dashboard_navigation_decision_and_detail():
    left = load_ucdp_csv(EXAMPLES / "ucdp_synthetic.csv", version="26.1")
    right = load_acled_csv(EXAMPLES / "acled_synthetic.csv", version="snapshot")
    result = reconcile(left, right)
    saved = []
    dashboard = ReviewDashboard(
        result, Review.create(result), reviewer="Fabian", save=saved.append, left_id="U1"
    )
    assert dashboard.candidate.left.source_id == "U1"
    lines = detail_lines(dashboard, 60)
    assert any("Coordinates:" in line for line in lines)
    assert any("Distance:" in line for line in lines)
    candidate_id = dashboard.candidate.candidate_id
    dashboard.decide("accepted")
    assert next(d for d in saved[-1].decisions if d.candidate_id == candidate_id).status == "accepted"
    assert dashboard.decisions[candidate_id].status == "accepted"
    dashboard.set_note("Narratives describe the same attack")
    assert dashboard.decisions[candidate_id].note == "Narratives describe the same attack"
    assert len(saved) == 2
    dashboard.move_group(1)
    assert dashboard.candidate.left.source_id == "U2"
    dashboard.jump("U1")
    assert dashboard.candidate.left.source_id == "U1"
    dashboard.toggle_filter()
    assert dashboard.show_all
