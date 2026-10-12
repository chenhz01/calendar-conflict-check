#!/usr/bin/env python3
"""Self-test for calendar-conflict-check. Pure stdlib. Run: python self_test.py"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calendar_conflict_check as ccc  # noqa: E402

TESTS = []


def test(name):
    def deco(fn):
        TESTS.append((name, fn))
        return fn
    return deco


def ev(eid, start, end, title=None):
    e = {"id": eid, "start": start, "end": end}
    if title:
        e["title"] = title
    return e


def expect_cal_error(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ccc.CalendarError:
        return
    raise AssertionError("expected CalendarError")


def wf(text, name="f"):
    d = tempfile.mkdtemp()
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return d, p


def cleanup(d):
    shutil.rmtree(d)


def types(conflicts):
    return sorted(c["type"] for c in conflicts)


# ---------------- functional unit tests ----------------

@test("parse_z_suffix")
def _():
    t = ccc.parse_time("2026-01-01T10:00:00Z")
    assert t.hour == 10


@test("parse_offset_normalized")
def _():
    a = ccc.parse_time("2026-01-01T18:00:00+08:00")
    b = ccc.parse_time("2026-01-01T10:00:00Z")
    assert a == b


@test("parse_naive_as_utc")
def _():
    assert ccc.parse_time("2026-01-01T10:00:00") == ccc.parse_time("2026-01-01T10:00:00Z")


@test("overlap_detected")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T09:30:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events)
    assert types(r["conflicts"]) == ["overlap"]


@test("exact_adjacency_no_overlap_no_buffer")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=0)
    assert r["conflicts"] == []


@test("buffer_violation_detected")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:05:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10)
    assert types(r["conflicts"]) == ["buffer"]


@test("buffer_respected_no_conflict")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:15:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10)
    assert r["conflicts"] == []


@test("chain_over_limit_detected")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:05:00Z", "2026-01-01T11:00:00Z"),
              ev("c", "2026-01-01T11:05:00Z", "2026-01-01T12:00:00Z"),
              ev("d", "2026-01-01T12:05:00Z", "2026-01-01T13:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10, max_consecutive_minutes=200)
    assert "chain" in types(r["conflicts"])


@test("chain_under_limit_no_conflict")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:05:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10, max_consecutive_minutes=200)
    assert types(r["conflicts"]) == ["buffer"]


@test("overlap_counts_into_chain")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T09:30:00Z", "2026-01-01T12:00:00Z"),
              ev("c", "2026-01-01T12:00:00Z", "2026-01-01T14:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10, max_consecutive_minutes=120)
    assert "chain" in types(r["conflicts"]) and "overlap" in types(r["conflicts"])


@test("unsorted_input_handled")
def _():
    events = [ev("b", "2026-01-01T09:30:00Z", "2026-01-01T11:00:00Z"),
              ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")]
    r = ccc.analyze(events)
    assert "overlap" in types(r["conflicts"])


@test("chains_reported_with_span")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:30:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10)
    assert len(r["chains"]) == 2 and r["chains"][0]["events"] == ["a"]


@test("format_report_lines")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T09:30:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events)
    text = ccc.format_report(r)
    assert "CONFLICT [overlap]" in text


@test("cli_end_to_end_exit_1")
def _():
    d, p = wf(json.dumps([ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
                          ev("b", "2026-01-01T09:30:00Z", "2026-01-01T11:00:00Z")]))
    try:
        assert ccc.main([p]) == 1
    finally:
        cleanup(d)


@test("cli_clean_exit_0")
def _():
    d, p = wf(json.dumps([ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
                          ev("b", "2026-01-01T11:00:00Z", "2026-01-01T12:00:00Z")]))
    try:
        assert ccc.main([p]) == 0
    finally:
        cleanup(d)


@test("title_preserved_in_events")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "Standup")]
    e, errs = ccc.normalize_events(events)
    assert e[0]["title"] == "Standup" and errs == []


# ---------------- exception-path tests ----------------

@test("bad_time_string_flagged")
def _():
    r = ccc.analyze([ev("a", "not-a-time", "2026-01-01T10:00:00Z")])
    assert len(r["errors"]) == 1 and r["events_valid"] == 0


@test("numeric_time_flagged")
def _():
    r = ccc.analyze([{"id": "a", "start": 1, "end": 2}])
    assert len(r["errors"]) == 1


@test("end_before_start_flagged")
def _():
    r = ccc.analyze([ev("a", "2026-01-01T10:00:00Z", "2026-01-01T09:00:00Z")])
    assert any("end is not after start" in e["error"] for e in r["errors"])


@test("end_equals_start_flagged")
def _():
    r = ccc.analyze([ev("a", "2026-01-01T10:00:00Z", "2026-01-01T10:00:00Z")])
    assert len(r["errors"]) == 1


@test("non_object_event_flagged")
def _():
    r = ccc.analyze(["meeting"])
    assert any("not an object" in e["error"] for e in r["errors"])


@test("events_not_array_raises")
def _():
    d, p = wf('{"nope": true}')
    try:
        expect_cal_error(ccc.load_events, p)
    finally:
        cleanup(d)


@test("corrupt_json_raises")
def _():
    d, p = wf("{oops")
    try:
        expect_cal_error(ccc.load_events, p)
    finally:
        cleanup(d)


@test("missing_file_raises")
def _():
    expect_cal_error(ccc.load_events, os.path.join(tempfile.mkdtemp(), "gone.json"))


@test("negative_buffer_raises")
def _():
    expect_cal_error(ccc.find_conflicts, [], -1, 240)


@test("zero_max_consecutive_raises")
def _():
    expect_cal_error(ccc.find_conflicts, [], 10, 0)


# ---------------- extreme-edge tests ----------------

@test("empty_event_list")
def _():
    r = ccc.analyze([])
    assert r["conflicts"] == [] and r["events_valid"] == 0


@test("single_event_no_conflicts")
def _():
    r = ccc.analyze([ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")])
    assert r["conflicts"] == [] and len(r["chains"]) == 1


@test("unicode_titles_ok")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "周会 🚀")]
    e, errs = ccc.normalize_events(events)
    assert errs == [] and e[0]["title"] == "周会 🚀"


@test("microsecond_times_ok")
def _():
    events = [ev("a", "2026-01-01T09:00:00.123456Z", "2026-01-01T10:00:00Z")]
    e, errs = ccc.normalize_events(events)
    assert errs == []


@test("many_events_bulk")
def _():
    events = []
    hour = 0
    for i in range(500):
        day = 1 + hour // 24
        s = "2026-01-%02dT%02d:00:00Z" % (day, hour % 24)
        e_ = "2026-01-%02dT%02d:30:00Z" % (day, hour % 24)
        events.append(ev("e%d" % i, s, e_))
        hour += 1
    r = ccc.analyze(events, buffer_minutes=0, max_consecutive_minutes=100000)
    assert r["events_valid"] == 500 and r["conflicts"] == []


@test("back_to_back_all_day_chain")
def _():
    events = [ev("m%d" % i,
                 "2026-01-01T%02d:00:00Z" % (8 + i),
                 "2026-01-01T%02d:00:00Z" % (9 + i))
              for i in range(8)]
    r = ccc.analyze(events, buffer_minutes=0, max_consecutive_minutes=300)
    assert "chain" in types(r["conflicts"])


@test("duplicate_ids_not_deduplicated")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("a", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=0)
    assert r["events_valid"] == 2


@test("cross_day_events_ordered")
def _():
    events = [ev("late", "2026-01-02T09:00:00Z", "2026-01-02T10:00:00Z"),
              ev("early", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")]
    e, errs = ccc.normalize_events(events)
    assert e[0]["id"] == "early" and errs == []


@test("gap_equal_buffer_no_buffer_conflict")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T10:10:00Z", "2026-01-01T11:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10, max_consecutive_minutes=1000)
    assert r["conflicts"] == []


@test("negative_buffer_raises")
def _():
    expect_cal_error(ccc.find_conflicts,
                     [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")], -1)


@test("zero_max_consecutive_raises")
def _():
    expect_cal_error(ccc.find_conflicts,
                     [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z")],
                     0, 0)


@test("zero_duration_event_rejected")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T09:00:00Z")]
    e, errs = ccc.normalize_events(events)
    assert e == [] and len(errs) == 1


@test("json_report_parseable")
def _():
    d, p = wf(json.dumps([ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
                          ev("b", "2026-01-01T09:30:00Z", "2026-01-01T11:00:00Z")]))
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ccc.main([p, "--json"])
        data = json.loads(buf.getvalue())
        assert data["conflicts"][0]["type"] == "overlap"
    finally:
        cleanup(d)


@test("custom_buffer_cli_flag")
def _():
    d, p = wf(json.dumps([ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
                          ev("b", "2026-01-01T10:05:00Z", "2026-01-01T11:00:00Z")]))
    try:
        assert ccc.main([p, "--buffer", "2"]) == 0
        assert ccc.main([p, "--buffer", "10"]) == 1
    finally:
        cleanup(d)


@test("mixed_conflict_types_all_reported")
def _():
    events = [ev("a", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z"),
              ev("b", "2026-01-01T09:50:00Z", "2026-01-01T11:00:00Z"),
              ev("c", "2026-01-01T11:02:00Z", "2026-01-01T12:00:00Z")]
    r = ccc.analyze(events, buffer_minutes=10, max_consecutive_minutes=1000)
    kinds = types(r["conflicts"])
    assert "overlap" in kinds and "buffer" in kinds


def main():
    passed = failed = 0
    for name, fn in TESTS:
        try:
            fn()
            passed += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("FAIL %s: %r" % (name, exc))
    print("passed=%d failed=%d total=%d" % (passed, failed, passed + failed))
    print("SUMMARY: PASS %d/%d" % (passed, passed + failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
