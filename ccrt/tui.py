"""Optional full-screen terminal dashboard for reviewing candidate links.

The module uses only the standard-library curses package and can be removed
without changing the matching or review data formats.
"""

from __future__ import annotations

import sys
import textwrap
from collections import defaultdict

from ccrt.interactive import _coordinates, _date

try:
    import curses as _curses
except ImportError:  # Optional on platforms without curses.
    _curses = None


class ReviewDashboard:
    """Navigation and decisions, independent of the terminal renderer."""

    def __init__(self, result, review, *, reviewer, save, left_id=None):
        review.validate(result)
        if not reviewer.strip():
            raise ValueError("--reviewer needs a nonempty name")
        self.result = result
        self.review = review
        self.reviewer = reviewer
        self.save = save
        self.groups = defaultdict(list)
        for candidate in result.candidates:
            self.groups[candidate.left.source_id].append(candidate)
        if left_id is not None and left_id not in self.groups:
            raise ValueError(f"no candidate group for left source ID {left_id}")
        self.decisions = {decision.candidate_id: decision for decision in review.decisions}
        self.show_all = False
        self.group_ids = []
        self.group_index = 0
        self.candidate_index = 0
        self.detail_scroll = 0
        self.message = "Arrows: groups/candidates  a/r/u: decide  e: note  f: filter  g: jump  q: quit"
        self.refresh(start=left_id)

    def refresh(self, *, start=None):
        current = start or (self.group_ids[self.group_index] if self.group_ids else None)
        self.group_ids = sorted(
            (
                key
                for key, items in self.groups.items()
                if key == current
                or self.show_all
                or any(self.decisions[c.candidate_id].status == "unresolved" for c in items)
            ),
            key=lambda key: (-self.groups[key][0].score, key),
        )
        self.group_index = self.group_ids.index(current) if current in self.group_ids else 0
        self.candidate_index = 0
        self.detail_scroll = 0

    @property
    def candidates(self):
        return self.groups[self.group_ids[self.group_index]] if self.group_ids else []

    @property
    def candidate(self):
        return self.candidates[self.candidate_index] if self.candidates else None

    def move_group(self, delta):
        if self.group_ids:
            self.group_index = (self.group_index + delta) % len(self.group_ids)
            self.candidate_index = 0
            self.detail_scroll = 0

    def move_candidate(self, delta):
        if self.candidates:
            self.candidate_index = (self.candidate_index + delta) % len(self.candidates)
            self.detail_scroll = 0

    def jump(self, left_id):
        if left_id not in self.groups:
            self.message = f"No candidate group for {left_id}"
            return
        self.refresh(start=left_id)
        self.message = f"Jumped to {left_id}"

    def toggle_filter(self):
        self.show_all = not self.show_all
        self.refresh()
        self.message = "Showing all groups" if self.show_all else "Showing unresolved groups"

    def decide(self, status, *, note=None):
        candidate = self.candidate
        if candidate is None:
            return
        old = self.decisions[candidate.candidate_id]
        updated = self.review.decide(
            candidate.candidate_id,
            status,
            reviewer=self.reviewer,
            note=old.note if note is None else note,
        )
        self.save(updated)
        self.review = updated
        self.decisions[candidate.candidate_id] = next(
            decision for decision in updated.decisions if decision.candidate_id == candidate.candidate_id
        )
        self.message = f"Saved {status}: {candidate.left.source_id}/{candidate.right.source_id}"

    def set_note(self, note):
        candidate = self.candidate
        if candidate is not None:
            self.decide(self.decisions[candidate.candidate_id].status, note=note)


def _put(screen, y, x, value, width, attr=0):
    if width < 1 or y < 0 or x < 0:
        return
    try:
        screen.addnstr(y, x, str(value).replace("\n", " "), width, attr)
    except Exception as exc:
        # curses.error is raised when a terminal rejects a bottom-right write.
        if _curses is None or not isinstance(exc, _curses.error):
            raise


def _field(lines, label, value, width):
    value = " ".join(str("not supplied" if value is None or value == "" else value).split())
    prefix = f"{label}: "
    lines.extend(textwrap.wrap(prefix + value, width=max(12, width), subsequent_indent="  ") or [prefix])


def _account_lines(lines, record, width):
    raw = record.raw
    lines.append(f"{record.source.upper()} {record.source_id}")
    _field(lines, "Date", _date(record), width)
    _field(lines, "Place", raw.get("where_description") or raw.get("location"), width)
    _field(lines, "Coordinates", _coordinates(record), width)
    _field(lines, "Actor 1", record.actor1, width)
    _field(lines, "Actor 2", record.actor2, width)
    _field(lines, "Deaths", record.total_deaths_best, width)
    _field(lines, "Location precision", record.geo_precision, width)
    for label, key in (
        ("Notes", "notes"),
        ("Source articles", "source_article"),
        ("Original sources", "source_original"),
    ):
        if raw.get(key):
            _field(lines, label, raw[key], width)
    lines.append("")


def detail_lines(dashboard, width):
    candidate = dashboard.candidate
    if candidate is None:
        return ["No candidate groups in this view. Press f to show all groups."]
    decision = dashboard.decisions[candidate.candidate_id]
    lines = []
    _account_lines(lines, candidate.left, width)
    _account_lines(lines, candidate.right, width)
    lines.append("COMPARISON")
    _field(
        lines,
        "Distance",
        f"{candidate.distance_km:.3f} km (limit {dashboard.result.config.max_km:g} km)",
        width,
    )
    _field(
        lines,
        "Date gap",
        f"{candidate.days_apart} days (limit {dashboard.result.config.max_days} days)",
        width,
    )
    _field(lines, "Proximity score", f"{candidate.score:.3f} (ranking only)", width)
    _field(lines, "Warnings", ", ".join(candidate.warnings) or "none", width)
    _field(lines, "Decision", decision.status, width)
    _field(lines, "Reviewer note", decision.note, width)
    lines.append("")
    lines.extend(
        textwrap.wrap(
            "Events can share coordinates. Check the dates, actors, and notes.",
            width=max(12, width),
        )
    )
    return lines


def _draw(screen, dashboard, curses):
    height, width = screen.getmaxyx()
    screen.erase()
    if height < 20 or width < 95:
        _put(screen, 0, 0, "CCRT review dashboard", width - 1, curses.A_BOLD)
        _put(screen, 2, 0, "Resize terminal to at least 95 columns x 20 rows. Press q to quit.", width - 1)
        screen.refresh()
        return
    left_width = 23
    middle_width = 39
    detail_x = left_width + middle_width + 2
    detail_width = width - detail_x - 1
    visible = height - 6
    counts = defaultdict(int)
    for decision in dashboard.review.decisions:
        counts[decision.status] += 1
    accent = curses.color_pair(1) if curses.has_colors() else 0
    _put(screen, 0, 0, " CCRT/Review ", width - 1, curses.A_REVERSE | curses.A_BOLD | accent)
    _put(
        screen,
        1,
        1,
        f"Reviewer {dashboard.reviewer}  |  {counts['accepted']} accepted  {counts['rejected']} rejected"
        f"  {counts['unresolved']} unresolved  |  {len(dashboard.group_ids)} groups",
        width - 2,
    )
    _put(screen, 3, 1, "UCDP EVENTS", left_width - 2, curses.A_BOLD)
    _put(screen, 3, left_width + 1, "ACLED CANDIDATES", middle_width - 2, curses.A_BOLD)
    _put(screen, 3, detail_x, "SOURCE ACCOUNTS", detail_width, curses.A_BOLD)
    for y in range(3, height - 2):
        _put(screen, y, left_width, "|", 1)
        _put(screen, y, detail_x - 1, "|", 1)
    if dashboard.group_ids:
        start = max(0, dashboard.group_index - visible // 2)
        start = min(start, max(0, len(dashboard.group_ids) - visible))
        for offset, index in enumerate(range(start, min(start + visible, len(dashboard.group_ids)))):
            group_id = dashboard.group_ids[index]
            pending = sum(
                dashboard.decisions[c.candidate_id].status == "unresolved" for c in dashboard.groups[group_id]
            )
            marker = ">" if index == dashboard.group_index else " "
            value = f"{marker} {group_id}  ({pending} open)"
            attr = curses.A_REVERSE if index == dashboard.group_index else 0
            _put(screen, 4 + offset, 1, value, left_width - 2, attr)
        candidates = dashboard.candidates
        start = max(0, dashboard.candidate_index - visible // 2)
        start = min(start, max(0, len(candidates) - visible))
        for offset, index in enumerate(range(start, min(start + visible, len(candidates)))):
            candidate = candidates[index]
            status = dashboard.decisions[candidate.candidate_id].status
            code = {"accepted": "A", "rejected": "R", "unresolved": "?"}[status]
            marker = ">" if index == dashboard.candidate_index else " "
            value = (
                f"{marker} {code} {candidate.right.source_id}  {candidate.score:.3f}"
                f"  {candidate.distance_km:.1f}km"
            )
            attr = curses.A_REVERSE if index == dashboard.candidate_index else 0
            if curses.has_colors() and index != dashboard.candidate_index:
                attr = curses.color_pair({"accepted": 2, "rejected": 3, "unresolved": 4}[status])
            _put(screen, 4 + offset, left_width + 1, value, middle_width - 2, attr)
    lines = detail_lines(dashboard, detail_width)
    max_scroll = max(0, len(lines) - visible)
    dashboard.detail_scroll = min(dashboard.detail_scroll, max_scroll)
    for offset, line in enumerate(lines[dashboard.detail_scroll : dashboard.detail_scroll + visible]):
        _put(screen, 4 + offset, detail_x, line, detail_width)
    _put(
        screen,
        height - 2,
        0,
        " Left/Right group  Up/Down candidate  PgUp/PgDn scroll  a/r/u decide  e note  f filter  g jump  q quit ",
        width - 1,
        curses.A_REVERSE,
    )
    _put(screen, height - 1, 1, dashboard.message, width - 2)
    screen.refresh()


def _prompt(screen, curses, label):
    height, width = screen.getmaxyx()
    screen.move(height - 1, 0)
    screen.clrtoeol()
    _put(screen, height - 1, 0, label, width - 1)
    screen.refresh()
    curses.echo()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    try:
        value = screen.getstr(height - 1, min(len(label), width - 2), 1000)
        return value.decode("utf-8", errors="replace").strip()
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass


def _loop(screen, dashboard, curses):
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK
        for number, foreground in (
            (1, curses.COLOR_CYAN),
            (2, curses.COLOR_GREEN),
            (3, curses.COLOR_RED),
            (4, curses.COLOR_YELLOW),
        ):
            curses.init_pair(number, foreground, background)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    screen.keypad(True)
    while True:
        _draw(screen, dashboard, curses)
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (curses.KEY_LEFT, ord("h")):
            dashboard.move_group(-1)
        elif key in (curses.KEY_RIGHT, ord("l")):
            dashboard.move_group(1)
        elif key in (curses.KEY_UP, ord("k")):
            dashboard.move_candidate(-1)
        elif key in (curses.KEY_DOWN, ord("j")):
            dashboard.move_candidate(1)
        elif key == curses.KEY_PPAGE:
            dashboard.detail_scroll = max(0, dashboard.detail_scroll - 8)
        elif key == curses.KEY_NPAGE:
            dashboard.detail_scroll += 8
        elif key in (ord("a"), ord("r"), ord("u")):
            dashboard.decide({ord("a"): "accepted", ord("r"): "rejected", ord("u"): "unresolved"}[key])
        elif key == ord("e") and dashboard.candidate is not None:
            dashboard.set_note(_prompt(screen, curses, "Reviewer note (blank clears): "))
        elif key == ord("f"):
            dashboard.toggle_filter()
        elif key == ord("g"):
            value = _prompt(screen, curses, "UCDP/source ID: ")
            if value:
                dashboard.jump(value)


def run_tui(result, review, *, reviewer, save, left_id=None):
    """Start the optional dashboard in an interactive terminal."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("review-tui needs an interactive terminal; use review-interactive for pipes")
    if _curses is None:
        raise ValueError("review-tui requires a terminal with Python curses support") from None
    dashboard = ReviewDashboard(result, review, reviewer=reviewer, save=save, left_id=left_id)
    try:
        _curses.wrapper(lambda screen: _loop(screen, dashboard, _curses))
    except KeyboardInterrupt:
        return
    except _curses.error as exc:
        raise ValueError(f"terminal could not start review-tui: {exc}") from exc
