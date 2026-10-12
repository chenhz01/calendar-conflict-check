#!/usr/bin/env python3
"""calendar-conflict-check: three-rule calendar conflict detector.

Given events with ISO-8601 start/end times, detects:
  1. overlap      — two events occupy the same time
  2. buffer       — gap between consecutive events below a minimum
  3. chain        — a run of events (gaps below buffer) totalling more
                    than a maximum consecutive-busy duration
Pure standard library. Deterministic. Offline. Exit 1 when any conflict.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

SEVERITY = {"overlap": 3, "buffer": 1, "chain": 2}


class CalendarError(Exception):
    """Raised for unreadable or malformed inputs."""


def parse_time(value):
    """Parse ISO-8601; 'Z' allowed; naive treated as UTC. Raises ValueError."""
    if not isinstance(value, str):
        raise ValueError("time must be an ISO-8601 string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_events(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise CalendarError("cannot read events file: %s" % exc)
    except json.JSONDecodeError as exc:
        raise CalendarError("events file is not valid JSON: %s" % exc)
    except UnicodeDecodeError:
        raise CalendarError("events file is not valid UTF-8")
    if not isinstance(data, list):
        raise CalendarError("events must be a JSON array")
    return data


def normalize_events(raw):
    """Validate and return list of dicts with parsed datetimes; collect errors."""
    events, errors = [], []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append({"index": idx, "error": "event is not an object"})
            continue
        eid = str(item.get("id", "<missing-id>"))
        try:
            start = parse_time(item.get("start"))
            end = parse_time(item.get("end"))
        except (ValueError, TypeError) as exc:
            errors.append({"index": idx, "id": eid, "error": "bad time: %s" % exc})
            continue
        if end <= start:
            errors.append({"index": idx, "id": eid, "error": "end is not after start"})
            continue
        events.append({"id": eid, "start": start, "end": end,
                       "title": str(item.get("title", eid))})
    events.sort(key=lambda e: (e["start"], e["end"]))
    return events, errors


def find_conflicts(events, buffer_minutes=10, max_consecutive_minutes=240):
    """Return (conflicts, chains) for sorted valid events."""
    if buffer_minutes < 0:
        raise CalendarError("buffer_minutes must be >= 0")
    if max_consecutive_minutes <= 0:
        raise CalendarError("max_consecutive_minutes must be > 0")
    buffer = buffer_minutes * 60.0
    conflicts, chains = [], []
    for prev, cur in zip(events, events[1:]):
        gap = (cur["start"] - prev["end"]).total_seconds()
        if gap < 0:
            conflicts.append({"type": "overlap", "a": prev["id"], "b": cur["id"],
                              "detail": "%s ends %s after %s starts" % (
                                  prev["id"], cur["start"].isoformat(), prev["id"])})
        elif gap < buffer:
            conflicts.append({"type": "buffer", "a": prev["id"], "b": cur["id"],
                              "detail": "gap %.1f min < %.0f min buffer" % (
                                  gap / 60.0, buffer_minutes)})
    # consecutive-run chains: events linked by gaps within buffer (overlaps
    # and exact back-to-back gaps included, so buffer=0 still chains)
    if events:
        chain = [events[0]]
        for cur in events[1:]:
            gap = (cur["start"] - chain[-1]["end"]).total_seconds()
            if gap <= buffer:
                chain.append(cur)
            else:
                chains.append(chain)
                chain = [cur]
        chains.append(chain)
    for chain in chains:
        span = (chain[-1]["end"] - chain[0]["start"]).total_seconds() / 60.0
        if len(chain) > 1 and span > max_consecutive_minutes:
            conflicts.append({
                "type": "chain", "a": chain[0]["id"], "b": chain[-1]["id"],
                "detail": "%d events, %.0f min busy > %d min limit" % (
                    len(chain), span, max_consecutive_minutes)})
    return conflicts, chains


def analyze(raw, buffer_minutes=10, max_consecutive_minutes=240):
    events, errors = normalize_events(raw)
    conflicts, chains = find_conflicts(events, buffer_minutes, max_consecutive_minutes)
    return {
        "events_total": len(raw),
        "events_valid": len(events),
        "conflicts": conflicts,
        "chains": [{"events": [e["id"] for e in c],
                    "span_minutes": round((c[-1]["end"] - c[0]["start"]).total_seconds() / 60.0, 1)}
                   for c in chains],
        "errors": errors,
    }


def format_report(report):
    lines = ["events: %d (%d valid), conflicts: %d, errors: %d" % (
        report["events_total"], report["events_valid"],
        len(report["conflicts"]), len(report["errors"]))]
    for c in report["conflicts"]:
        lines.append("CONFLICT [%s] %s <-> %s: %s" % (c["type"], c["a"], c["b"], c["detail"]))
    for e in report["errors"]:
        lines.append("ERROR %s" % json.dumps(e, ensure_ascii=False))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="calendar-conflict-check", description=__doc__)
    parser.add_argument("events", help="events JSON file (array of {id,start,end,title?})")
    parser.add_argument("--buffer", type=int, default=10, help="minimum gap minutes (default 10)")
    parser.add_argument("--max-consecutive", type=int, default=240,
                        help="max consecutive busy minutes (default 240)")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)
    try:
        raw = load_events(args.events)
        report = analyze(raw, args.buffer, args.max_consecutive)
    except CalendarError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str) if args.json else format_report(report))
    return 0 if not (report["conflicts"] or report["errors"]) else 1


if __name__ == "__main__":
    sys.exit(main())
