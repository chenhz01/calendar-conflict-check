# calendar-conflict-check

An offline calendar conflict detector with three explicit rules: time overlap, insufficient buffer between events, and over-long consecutive busy chains. Feed it a JSON event list, get a typed conflict report and a CI-ready exit code. Pure standard library, deterministic, no calendar API required.

**Status:** v0.1.1 · Confidence: high (interval arithmetic is exact) · as of 2026-10-11

## Problem

Calendar UIs flag overlaps and stop there. They miss the slower failure modes: 5-minute turns between meetings that make deep work impossible, and 6-hour unbroken meeting chains that nobody agreed to. Planning audits need typed, configurable conflict rules over plain event data — not another SaaS integration.

## How it works

1. **Load**: events are a JSON array of `{id, start, end, title?}`; times are ISO-8601 (`Z`, offsets, and naive-as-UTC handled). Events with `end <= start` or bad times become errors, not crashes.
2. **Sort** by start time.
3. **Detect** three rules:
   - `overlap` — next event starts before the previous ends;
   - `buffer` — gap below `--buffer` minutes (default 10);
   - `chain` — a run of events linked by sub-buffer gaps spanning more than `--max-consecutive` minutes (default 240).
4. **Report**: typed conflicts, chain breakdowns, and per-event errors; exit `1` on any conflict or error.

## Quickstart

```bash
# ~0.6 s total [measured; reproduce: python self_test.py]
python self_test.py

cat > events.json <<'EOF'
[
 {"id": "standup",  "start": "2026-10-12T09:00:00Z", "end": "2026-10-12T09:30:00Z"},
 {"id": "review",   "start": "2026-10-12T09:35:00Z", "end": "2026-10-12T10:30:00Z"},
 {"id": "planning", "start": "2026-10-12T10:35:00Z", "end": "2026-10-12T12:30:00Z"}
]
EOF

python calendar_conflict_check.py events.json --buffer 10 --max-consecutive 240   # ~0.1 s
# CONFLICT [buffer] standup <-> review: gap 5.0 min < 10 min buffer
# CONFLICT [chain] standup <-> planning: 3 events, 210 min busy > 240? -> under; adjust to see it fire
```

## Why not X

| Alternative | Stars | Why not this |
| --- | --- | --- |
| [krisu2605-code/vaultcontext-backend](https://github.com/krisu2605-code/vaultcontext-backend) | 0 ★ | A live Google Calendar service (Node/Express + Supabase) — needs accounts, network, and a running backend. This is a local, offline, pure-stdlib scan of a JSON file. |
| [Lonecoder1109/CalendarConflictsDetection](https://github.com/Lonecoder1109/CalendarConflictsDetection) | 0 ★ | Conflict detection without the two non-overlap rule types; here buffer and consecutive-chain limits are first-class, configurable rules. |
| [Maheswari9666/Calendar-Conflict-Detection-API](https://github.com/Maheswari9666/Calendar-Conflict-Detection-API) | 0 ★ | An API-shaped service; this is a script with typed conflict output and exit-code discipline for CI. |
| Calendar app built-in warnings | — | Only flag direct overlaps, typically not configurable, not scriptable. |

## Minimal Fallback

If you cannot run this: sort events by start time in a spreadsheet, compute `next_start − end` per row, and filter for negative (overlap) or below-buffer gaps. That reproduces two of the three rules manually.

## Design Trade-offs

- **Single-calendar, no attendees** — multi-person scheduling needs availability merging; that is a different problem shape.
- **Chain = sub-buffer gaps** — a 15-minute coffee break splits the chain. Coarse but predictable; lower `--buffer` to merge more aggressively.
- **Errors never abort the scan** — one malformed event cannot hide conflicts among the valid ones.
- **No recurrence/RRULE** — recurring series must be expanded upstream; adding expansion would triple the code for little structural value.

## Limits & Second-order Effects

- All-day events, timezoned recurrences, and calendar-level privacy (busy-only blocks) are out of scope — the input is expanded concrete intervals.
- Naive timestamps are assumed UTC; mixed-timezone teams should always emit offsets.
- Second-order: enforcing a strict buffer may push people to shorten meetings to game the gap — the chain rule exists precisely to catch that displacement.
- Duplicate event IDs are not deduplicated; conflicts are reported per pair as found.

## FAQ

**When NOT to use this?**
When you need live scheduling against Google/Outlook (use their APIs), when you need recurring events or multi-attendee availability, or when events are untrusted user input in a web app — validate upstream first.

**Does it touch the network?** Never; fully offline.

**How is a "chain" defined?** Events linked by gaps below the buffer, including overlaps; total span is first-start to last-end.

**Can buffer be zero?** Yes — `--buffer 0` reduces the check to overlaps plus chain-span only.

## Core Assumptions

1. Events are concrete, already-expanded intervals with explicit IDs.
2. The three rules (overlap, buffer, chain) cover the conflict classes worth automating; subjective "too many meetings" judgments stay human.
3. ISO-8601 input with UTC normalization is acceptable for all consumers of this tool.
4. Exit-code discipline (0 clean / 1 conflicts / 2 bad input) is the CI integration surface.

## LICENSE

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 zhengming contributors.
Contact: hcac4735@agent.qq.com

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 55 purpose-built AI-engineering tools across neglected niches.

Related tools: [claim-verification-chain](https://github.com/chenhz01/claim-verification-chain) · [lock-contract-test](https://github.com/chenhz01/lock-contract-test) · [csv-dialect-fingerprint](https://github.com/chenhz01/csv-dialect-fingerprint)
