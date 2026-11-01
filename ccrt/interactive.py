"""Small terminal workflow for reviewing candidate links with their source accounts."""

from collections import defaultdict


def _short(value, limit=110):
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _date(record):
    if record.date_start is None:
        return "unknown date"
    start, end = record.date_start.isoformat(), record.date_end.isoformat()
    return start if start == end else f"{start} to {end}"


def _place(record):
    raw = record.raw
    return _short(raw.get("where_description") or raw.get("location") or raw.get("where_coordinates"))


def _coordinates(record):
    if record.latitude is None or record.longitude is None:
        return "not supplied"
    return f"lat {record.latitude}, lon {record.longitude}"


def _account(record, emit):
    raw = record.raw
    emit(f"{record.source.upper()} {record.source_id} | {_date(record)} | {record.country}")
    place = raw.get("where_description") or raw.get("location") or raw.get("where_coordinates")
    emit(f"Place: {place or 'not supplied'}")
    emit(f"Coordinates: {_coordinates(record)}")
    emit(f"Actors: {record.actor1 or '?'} / {record.actor2 or '?'}")
    deaths = f"best {record.total_deaths_best}"
    if record.total_deaths_low is not None or record.total_deaths_high is not None:
        deaths += f" (low {record.total_deaths_low}, high {record.total_deaths_high})"
    emit(f"Event type: {record.event_type or '?'} | reported deaths: {deaths}")
    emit(f"Date precision: {record.date_precision} | location precision: {record.geo_precision}")
    for label, key in (
        ("Notes", "notes"),
        ("Source articles", "source_article"),
        ("Original sources", "source_original"),
        ("Source", "source"),
    ):
        if raw.get(key):
            emit(f"{label}: {raw[key]}")


def review_interactive(
    result, review, *, reviewer, save, left_id=None, show_all=False, ask=input, emit=print
):
    """Review UCDP/other left-side groups; call save after every decision.

    ``ask`` and ``emit`` are injectable so the terminal workflow can be tested.
    The caller owns loading the run, validating the review, and persisting it.
    """
    review.validate(result)
    if not reviewer.strip():
        raise ValueError("--reviewer needs a nonempty name")
    grouped = defaultdict(list)
    for candidate in result.candidates:
        grouped[candidate.left.source_id].append(candidate)
    if left_id is not None and left_id not in grouped:
        raise ValueError(f"no candidate group for left source ID {left_id}")
    decided = {decision.candidate_id: decision for decision in review.decisions}
    ids = sorted(
        (
            key
            for key, items in grouped.items()
            if key == left_id
            or show_all
            or any(decided[c.candidate_id].status == "unresolved" for c in items)
        ),
        key=lambda key: (-grouped[key][0].score, key),
    )
    if not ids:
        emit("No candidate groups to review. Use --all to revisit decisions.")
        return review

    emit("Scores rank nearby records; coordinates may represent shared place labels.")
    emit("Compare both source accounts before deciding.")
    position = ids.index(left_id) if left_id is not None else 0
    while True:
        items = grouped[ids[position]]
        left = items[0].left
        emit(f"\nGroup {position + 1}/{len(ids)} | {result.left.source.upper()} {left.source_id}")
        _account(left, emit)
        for number, candidate in enumerate(items, 1):
            right = candidate.right
            status = decided[candidate.candidate_id].status
            emit(
                f"  {number}. [{status}] {right.source_id} | score {candidate.score:.3f}"
                f" | {candidate.days_apart} days | {candidate.distance_km:.1f} km"
                f" | deaths {right.total_deaths_best} | {_date(right)} | {_place(right)}"
                f" | {_coordinates(right)}"
            )
        try:
            choice = ask("Number to inspect; n next, p previous, q quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            emit("\nReview saved. Re-run the command to continue.")
            return review
        if choice == "q":
            break
        if choice == "n":
            if position == len(ids) - 1:
                emit("End of review queue; returning to the first group.")
            position = (position + 1) % len(ids)
            continue
        if choice == "p":
            if position == 0:
                emit("Start of review queue; returning to the last group.")
            position = (position - 1) % len(ids)
            continue
        if not choice.isdecimal() or not 1 <= int(choice) <= len(items):
            emit("Choose a listed number, n, p, or q.")
            continue
        candidate = items[int(choice) - 1]
        decision = decided[candidate.candidate_id]
        emit("\nLeft account:")
        _account(candidate.left, emit)
        emit("\nCandidate account:")
        _account(candidate.right, emit)
        emit(f"Coordinate separation: {candidate.distance_km:.3f} km (limit {result.config.max_km:g} km)")
        emit(
            f"Date interval gap: {candidate.days_apart} days"
            f" (limit {result.config.max_days} days) | proximity score: {candidate.score:.3f}"
        )
        emit("Location precision codes are source specific, not kilometer uncertainty radii.")
        emit(f"Current: {decision.status}" + (f" | note: {decision.note}" if decision.note else ""))
        emit(f"Warnings: {', '.join(candidate.warnings) or 'none'}")
        try:
            action = ask("a accept, r reject, u unresolved, b back, q quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            emit("\nReview saved. Re-run the command to continue.")
            return review
        if action == "q":
            break
        if action == "b":
            continue
        statuses = {"a": "accepted", "r": "rejected", "u": "unresolved"}
        if action not in statuses:
            emit("Choose a, r, u, b, or q.")
            continue
        try:
            note = ask("Reason (optional; Enter keeps existing note): ").strip()
        except (EOFError, KeyboardInterrupt):
            emit("\nNo change saved for this candidate.")
            return review
        review = review.decide(
            candidate.candidate_id, statuses[action], reviewer=reviewer, note=note or decision.note
        )
        save(review)
        decided[candidate.candidate_id] = next(
            d for d in review.decisions if d.candidate_id == candidate.candidate_id
        )
        emit(f"Saved {statuses[action]} for {candidate.left.source_id} / {candidate.right.source_id}.")
    emit("Review saved. Re-run the command to continue.")
    return review
