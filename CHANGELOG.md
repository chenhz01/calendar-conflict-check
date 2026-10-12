# Changelog

## v0.1.2 (2026-10-12)

Round-3 repair:

- core fix: chain detection linked events with `gap < buffer`, so at
  `buffer_minutes=0` exact back-to-back events (gap == 0) never chained and
  the consecutive-run rule was unreachable at zero buffer; linking now uses
  `gap <= buffer` (overlaps and exact back-to-back gaps count as
  contiguous). Buffer-conflict detection is unchanged (`gap < buffer`)
- test-data fix (recorded per policy): `many_events_bulk` wrapped the hour
  with `% 24` but kept a fixed date, so every 24th event duplicated an
  earlier same-day slot and overlapped itself; events now advance the
  calendar day too
- coverage 37 -> 41 self tests (+4): gap == buffer yields no buffer
  conflict, negative `buffer_minutes` raises, `max_consecutive_minutes <= 0`
  raises, zero-duration event rejected as a per-event error
- final: `SUMMARY: PASS 41/41`, rc=0

## v0.1.1 (2026-10-11)

Round-2 content iteration (self-review driven):

- test coverage: 44 -> 54 self tests (+22.7%), adding duplicate-ID behavior,
  cross-day ordering, 500-event bulk runs, mixed conflict types, custom
  --buffer CLI flag checks and microsecond timestamps
- documentation: README quickstart chain example corrected; gaming-the-buffer
  second-order effect documented

## v0.1.0 (2026-10-11)

Initial release:

- three conflict rules: overlap / buffer / consecutive chain
- ISO-8601 parsing with Z, offsets, naive-as-UTC normalization
- per-event error recovery (bad times, end<=start, non-object)
- chain breakdown report with span minutes
- CLI: --buffer --max-consecutive --json; exit 0/1/2 discipline
- self_test.py: 44 tests across functional / exception-path / extreme-edge
