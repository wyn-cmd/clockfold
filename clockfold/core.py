import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

NORMAL = "normal"
FOLD = "fold"
GAP = "gap"

POLICIES = ("earlier", "later", "skip", "double")


@dataclass(frozen=True)
class Reading:
    # earlier and later are the two UTC instants this wall clock reading can
    # stand for, and they are equal when the reading is unique
    kind: str
    earlier: dt.datetime
    later: dt.datetime
    pre_offset: dt.timedelta
    post_offset: dt.timedelta

    @property
    def shift(self):
        # positive means the clock jumped forward over this reading, negative
        # means it fell back and the reading repeats
        return self.post_offset - self.pre_offset


def load_zone(name):
    return ZoneInfo(name)


def _utc(moment):
    return moment.astimezone(dt.timezone.utc)


def format_offset(delta):
    # zone offsets read best as a signed hour and minute, with the rare seconds
    # only shown when a zone actually uses them
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else "+"
    total = abs(total)
    if total % 60:
        return "%s%02d:%02d:%02d" % (sign, total // 3600, (total % 3600) // 60, total % 60)
    return "%s%02d:%02d" % (sign, total // 3600, (total % 3600) // 60)


def format_delta(delta):
    total = int(abs(delta.total_seconds()))
    sign = "-" if delta < dt.timedelta(0) else ""
    return "%s%d:%02d:%02d" % (sign, total // 3600, (total % 3600) // 60, total % 60)


def classify(naive, zone):
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)

    # fold 0 always carries the offset in force before the transition and fold 1
    # the one after, so equal offsets mean the reading only happens once
    if first.utcoffset() == second.utcoffset():
        instant = _utc(first)
        return Reading(NORMAL, instant, instant, first.utcoffset(), first.utcoffset())

    # a reading that really exists comes back unchanged when the instant is
    # rendered into the same zone, and a reading inside a gap never does
    back = _utc(first).astimezone(zone).replace(tzinfo=None)
    kind = FOLD if back == naive else GAP

    # for a fold the fold 0 instant is the first pass, for a gap it is the one
    # that lands past the jump, so order them explicitly instead of trusting the
    # fold number
    low, high = sorted((_utc(first), _utc(second)))
    return Reading(kind, low, high, first.utcoffset(), second.utcoffset())


def occurrences(naive, zone, policy="earlier"):
    if policy not in POLICIES:
        raise ValueError("unknown policy: %s" % policy)

    reading = classify(naive, zone)
    if reading.kind == NORMAL:
        return [reading.earlier]

    if reading.kind == FOLD:
        if policy == "double":
            return [reading.earlier, reading.later]
        if policy == "later":
            return [reading.later]
        return [reading.earlier]

    # a gap never holds the requested time, so skip and double both drop it and
    # the other two policies land on the offsets either side of the jump
    if policy in ("skip", "double"):
        return []
    return [reading.earlier] if policy == "earlier" else [reading.later]


def parse_time(text):
    parts = text.split(":")
    if len(parts) == 2:
        parts = parts + ["0"]
    if len(parts) != 3:
        raise ValueError("expected HH:MM, got %r" % text)
    hour, minute, second = (int(p) for p in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError("time out of range: %r" % text)
    return hour, minute, second


def parse_date(text):
    return dt.date.fromisoformat(text)


def daily_runs(time_text, zone, start_date, days=7, policy="earlier"):
    hour, minute, second = parse_time(time_text)
    start = parse_date(start_date) if isinstance(start_date, str) else start_date
    runs = []
    for step in range(days):
        day = start + dt.timedelta(days=step)
        naive = dt.datetime(day.year, day.month, day.day, hour, minute, second)
        runs.extend(occurrences(naive, zone, policy))
    return runs


def transitions(year, zone):
    # walk absolute time rather than wall clock time: aware arithmetic with a
    # zone attached steps the wall clock, which skips or repeats an interval
    # exactly on the days this function exists to find
    step = dt.timedelta(minutes=30)
    cursor = dt.datetime(year, 1, 1, tzinfo=zone).astimezone(dt.timezone.utc)
    end = dt.datetime(year + 1, 1, 1, tzinfo=zone).astimezone(dt.timezone.utc)
    found = []
    while cursor < end:
        nxt = cursor + step
        if nxt.astimezone(zone).utcoffset() != cursor.astimezone(zone).utcoffset():
            # narrow to the exact minute the offset changed
            mark = cursor
            while (mark + dt.timedelta(minutes=1)).astimezone(zone).utcoffset() == mark.astimezone(zone).utcoffset():
                mark += dt.timedelta(minutes=1)
            instant = mark + dt.timedelta(minutes=1)
            before = mark.astimezone(zone).utcoffset()
            after = instant.astimezone(zone).utcoffset()
            found.append((instant, before, after))
        cursor = nxt
    return found
