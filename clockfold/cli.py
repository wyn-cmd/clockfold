import argparse
import datetime as dt
import sys

from .core import (
    GAP,
    FOLD,
    POLICIES,
    classify,
    daily_runs,
    format_delta,
    format_offset,
    load_zone,
    occurrences,
    parse_time,
    transitions,
)

KIND_WORD = {
    GAP: "nonexistent (gap)",
    FOLD: "ambiguous (fold)",
}

SHORT_WORD = {
    GAP: "nonexistent",
    FOLD: "ambiguous",
}


def _naive(text):
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return dt.datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise SystemExit("could not read %r as a date and time" % text)


def cmd_classify(args):
    zone = load_zone(args.zone)
    naive = _naive(args.when)
    reading = classify(naive, zone)
    stamp = naive.strftime("%Y-%m-%d %H:%M")

    if reading.kind not in KIND_WORD:
        print("%s in %s is normal" % (stamp, args.zone))
        print("  instant: %s (%s)" % (reading.earlier.isoformat(), format_offset(reading.pre_offset)))
        return 0

    print("%s in %s is %s" % (stamp, args.zone, KIND_WORD[reading.kind]))
    print("  pre transition offset: %s" % format_offset(reading.pre_offset))
    print("  post transition offset: %s" % format_offset(reading.post_offset))
    if reading.kind == GAP:
        print("  gap length: %s" % format_delta(reading.shift))
    else:
        print("  earlier instant: %s (%s)" % (reading.earlier.isoformat(), format_offset(reading.pre_offset)))
        print("  later instant:   %s (%s)" % (reading.later.isoformat(), format_offset(reading.post_offset)))
    return 0


def cmd_resolve(args):
    zone = load_zone(args.zone)
    naive = _naive(args.when)
    reading = classify(naive, zone)
    instants = occurrences(naive, zone, args.policy)
    stamp = naive.strftime("%Y-%m-%d %H:%M")

    print("%s in %s is %s" % (stamp, args.zone, KIND_WORD.get(reading.kind, "normal")))
    print("policy %s gives %d instant%s" % (args.policy, len(instants), "" if len(instants) == 1 else "s"))
    for instant in instants:
        print("  %s" % instant.isoformat())
    return 0


def cmd_schedule(args):
    zone = load_zone(args.zone)
    hour, minute, _ = parse_time(args.at)
    start = dt.date.fromisoformat(args.start)
    runs = daily_runs(args.at, zone, start, days=args.days, policy=args.policy)

    if len(runs) == 1:
        print("policy %s, 1 of %d days produces a run" % (args.policy, args.days))
    else:
        print("policy %s, %d of %d days produce runs" % (args.policy, len(runs), args.days))
    for step in range(args.days):
        day = start + dt.timedelta(days=step)
        naive = dt.datetime(day.year, day.month, day.day, hour, minute)
        reading = classify(naive, zone)
        produced = occurrences(naive, zone, args.policy)
        label = "%s %02d:%02d" % (day.isoformat(), hour, minute)
        if not produced:
            print("  %s -> skipped (%s)" % (label, SHORT_WORD.get(reading.kind, "dropped")))
        for instant in produced:
            print("  %s -> %s" % (label, instant.isoformat()))
    return 0


def cmd_transitions(args):
    zone = load_zone(args.zone)
    found = transitions(args.year, zone)
    if not found:
        print("%s has no offset change in %d" % (args.zone, args.year))
        return 0
    for instant, before, after in found:
        # print the reading the clock would have shown next under the old offset,
        # next to the reading it actually jumps to
        old_wall = (instant - dt.timedelta(minutes=1)).astimezone(zone)
        old_wall = old_wall + dt.timedelta(minutes=1)
        print("%s -> %s local, offset %s -> %s" % (
            old_wall.strftime("%Y-%m-%d %H:%M"),
            instant.astimezone(zone).strftime("%H:%M"),
            format_offset(before),
            format_offset(after),
        ))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="clockfold",
        description="Classify, resolve and expand local clock readings around daylight saving transitions.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("classify", help="describe one wall clock reading")
    p.add_argument("when", help="local date and time, for example '2026-03-08 02:30'")
    p.add_argument("zone", help="IANA zone name, for example America/New_York")
    p.set_defaults(func=cmd_classify)

    p = subs.add_parser("resolve", help="turn one reading into UTC instants under a policy")
    p.add_argument("when")
    p.add_argument("zone")
    p.add_argument("--policy", default="earlier", choices=POLICIES)
    p.set_defaults(func=cmd_resolve)

    p = subs.add_parser("schedule", help="expand a daily local time across a date range")
    p.add_argument("at", help="local time of day, for example 02:30")
    p.add_argument("zone")
    p.add_argument("--start", required=True, help="first date, ISO format")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--policy", default="earlier", choices=POLICIES)
    p.set_defaults(func=cmd_schedule)

    p = subs.add_parser("transitions", help="list the offset changes a zone makes in a year")
    p.add_argument("year", type=int)
    p.add_argument("zone")
    p.set_defaults(func=cmd_transitions)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
