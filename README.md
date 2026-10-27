# Smart Airport Runway Scheduling System

A GUI application that schedules aircraft landings on one or more runways using a **greedy algorithm**. It is built for the *Design and Analysis of Algorithms* course, Assignment 2 (GUI-Based Algorithm Implementation).

## Problem

Arriving flights each have a window of acceptable landing times (earliest time and deadline) and a wake-turbulence category (Heavy, Medium or Light). Consecutive landings on the same runway must be separated by a minimum time that depends on the categories of the two aircraft. The system must assign each flight a runway and a landing time that fits its window, or report it as unschedulable.

## Algorithm

Greedy earliest-feasible-landing:

1. Sort flights by earliest acceptable landing time (ties: deadline, then code).
2. For each flight, compute the earliest feasible landing time on every runway, including separation from the last aircraft on that runway.
3. Assign the flight to the runway with the earliest feasible time. If no runway meets the deadline, mark it unscheduled.

**Time complexity:** O(n log n + n·m), where n is the number of flights and m the number of runways.
**Space complexity:** O(n + m) for the schedule state (O(n·m) if the full step trace is kept).

The greedy rule is a fast heuristic and is not guaranteed to minimise total delay for every input. This is discussed in the report.

## Features

- Three built-in scenarios (sample, busy morning, random) and custom flight entry with validation.
- Interactive runway timeline: one lane per runway, colour-coded by wake category, zoom slider, horizontal scrolling.
- Hover over a landing for details; click it to select that flight in the list.
- Playback controls: Play / Pause, Step, Reset, and an adjustable playback speed.
- Current flight highlighted with its earliest time and deadline.
- Live statistics: scheduled, unscheduled, total and average delay.
- Tabs for the step-by-step log, final results, and an in-app explanation of the algorithm.
- Export results to CSV.
- Keyboard shortcuts: Space (play/pause), Right arrow (next step), R (reset).

## Requirements

- Python 3.8 or newer.
- tkinter (included with the standard Python installers on Windows and macOS; on Linux, install `python3-tk`).

No third-party packages are needed.

## How to run

```bash
python runway_gui.py
```

On macOS or Linux you may need `python3 runway_gui.py`.

## How to run the tests

```bash
python -m unittest -v test_runway_scheduler
```

The test suite has 25 tests covering normal cases (separation, runway selection, delays, input-order independence) and boundary cases (empty input, zero runways, deadline exactly met, deadline missed, overflow, duplicate codes, invalid input).

## Project structure

```
runway_scheduler.py       Core greedy algorithm (no GUI dependency)
runway_gui.py             Tkinter graphical interface
test_runway_scheduler.py  Unit tests (normal and boundary cases)
README.md                 This file
```

## Author

- Name: Filu Minta Tom
- Registration number: AJC24CC012
- Course: Design and Analysis of Algorithms
