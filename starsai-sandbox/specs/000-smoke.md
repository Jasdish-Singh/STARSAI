# Spec 000-smoke

## Goal
Verify orchestration loop: spec → code → review → gate.

## Inputs
None.

## Outputs
- `src/000-smoke/hello.py` — script that prints `STARSAI sandbox alive`.

## Acceptance criteria
- File exists.
- `py hello.py` exits 0 and stdout contains exact string `STARSAI sandbox alive`.
- No imports beyond stdlib.
- ≤ 5 lines.

## Constraints
- Python 3.11+.
- Write nothing outside `src/000-smoke/`.
