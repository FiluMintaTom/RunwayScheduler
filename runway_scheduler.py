"""
Smart Airport Runway Scheduling System - greedy algorithm (core logic, no GUI).

Problem
-------
Given n arriving flights and m runways, assign every flight a runway and a
landing time so that:
  * each landing lies within the flight's window [earliest, latest],
  * consecutive landings on the same runway respect the wake-turbulence
    separation between the leader and the follower (depends on their
    categories H = Heavy, M = Medium, L = Light).

Greedy strategy (earliest-feasible-landing)
-------------------------------------------
1. Sort flights by earliest acceptable landing time (ties: deadline, code).
2. For each flight, in that order, compute the earliest landing time it could
   achieve on every runway, given the separation from the last aircraft that
   landed there.
3. Commit the flight to the runway that gives the earliest feasible time
   (ties: lowest runway number). If no runway can land it by its deadline,
   the flight is reported as unscheduled.

Complexity
----------
Let n = number of flights and m = number of runways.
  Time:  O(n log n) for sorting + O(n * m) for evaluating runways  => O(n log n + n*m)
  Space: O(n + m) for the schedule state and results.
         O(n * m) if the full step-by-step trace (all candidate options) is kept
         for visualisation.

Note: the greedy rule is fast and gives a good, intuitive schedule, but it is
a heuristic. It is not guaranteed to minimise total delay for every input; this
is discussed in the report.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

CATEGORIES = ("H", "M", "L")  # Heavy, Medium, Light

# Minimum separation (minutes) between a leader (row) and a follower (column).
# Illustrative values - replace with the airport's own separation minima.
SEPARATION = {
    ("H", "H"): 2, ("H", "M"): 3, ("H", "L"): 4,
    ("M", "H"): 2, ("M", "M"): 2, ("M", "L"): 3,
    ("L", "H"): 2, ("L", "M"): 2, ("L", "L"): 2,
}


@dataclass(frozen=True)
class Flight:
    code: str
    category: str   # 'H', 'M' or 'L'
    earliest: float  # earliest acceptable landing time (minutes)
    latest: float    # deadline: latest acceptable landing time (minutes)


@dataclass(frozen=True)
class Assignment:
    flight: Flight
    runway: int      # 0-based runway index
    time: float      # assigned landing time (minutes)
    delay: float     # time - earliest


@dataclass(frozen=True)
class Step:
    flight: Flight
    options: List[Tuple[int, float]]   # (runway, feasible landing time) per runway
    assignment: Optional[Assignment]   # None if the flight could not be scheduled
    message: str


@dataclass(frozen=True)
class ScheduleResult:
    assignments: List[Assignment]
    unscheduled: List[Flight]
    steps: List[Step]


def make_flight(code, category, earliest, latest) -> Flight:
    """Validate raw user input and build a Flight. Raises ValueError on bad input."""
    code = str(code).strip().upper()
    category = str(category).strip().upper()
    if not code:
        raise ValueError("Flight code cannot be empty.")
    if category not in CATEGORIES:
        raise ValueError("Wake category must be H, M or L.")
    try:
        e = float(earliest)
        l = float(latest)
    except (TypeError, ValueError):
        raise ValueError("Landing times must be numbers (minutes).") from None
    if not (math.isfinite(e) and math.isfinite(l)):
        raise ValueError("Landing times must be finite numbers.")
    if e < 0 or l < 0:
        raise ValueError("Landing times cannot be negative.")
    if e > l:
        raise ValueError("Earliest landing cannot be after the latest (deadline).")
    return Flight(code, category, e, l)


def schedule(flights: List[Flight], num_runways: int) -> ScheduleResult:
    """Greedy earliest-feasible-landing schedule. See module docstring."""
    if num_runways < 1:
        raise ValueError("At least one runway is required.")
    codes = [f.code for f in flights]
    if len(codes) != len(set(codes)):
        raise ValueError("Flight codes must be unique.")

    # Step 1: sort by earliest acceptable time (ties by deadline, then code).
    order = sorted(flights, key=lambda f: (f.earliest, f.latest, f.code))

    last_time: List[Optional[float]] = [None] * num_runways
    last_cat: List[Optional[str]] = [None] * num_runways

    assignments: List[Assignment] = []
    unscheduled: List[Flight] = []
    steps: List[Step] = []

    for f in order:
        # Step 2: earliest feasible landing time on every runway.
        options: List[Tuple[int, float]] = []
        for r in range(num_runways):
            if last_time[r] is None:
                t = f.earliest
            else:
                t = max(f.earliest, last_time[r] + SEPARATION[(last_cat[r], f.category)])
            options.append((r, t))

        # Step 3: commit to the earliest option that meets the deadline.
        feasible = [(r, t) for r, t in options if t <= f.latest]
        if feasible:
            r, t = min(feasible, key=lambda rt: (rt[1], rt[0]))
            a = Assignment(f, r, t, t - f.earliest)
            assignments.append(a)
            last_time[r] = t
            last_cat[r] = f.category
            message = f"assigned to RWY {r + 1} at {t:g} min (delay {a.delay:g})"
        else:
            a = None
            unscheduled.append(f)
            message = f"no runway can land it by its deadline of {f.latest:g}; unscheduled"

        steps.append(Step(f, options, a, message))

    return ScheduleResult(assignments, unscheduled, steps)
