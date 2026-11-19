# clockfold

Small standard-library tool for the two clock readings that break scheduled jobs: the wall time that happens twice when a zone leaves daylight saving, and the wall time that never happens when it enters. Both are silent failures. A daily 02:30 job either fires twice, fires once at the wrong instant, or does not fire at all, and nothing in the cron line hints that the day is different.

clockfold classifies a local reading, resolves it under a policy, and expands a daily schedule into concrete UTC instants across a transition so you can see what would actually happen.

Python 3.9 or newer. No dependencies and no install step; the package imports straight from the repository and the zone database comes from the system tzdata through `zoneinfo`.

## Classifying a wall clock reading

```
python3 -m clockfold classify "2026-03-08 02:30" America/New_York
```

```
2026-03-08 02:30 in America/New_York is nonexistent (gap)
  pre transition offset: -05:00
  post transition offset: -04:00
  gap length: 1:00:00
```

The same reading on the other side of the year is ambiguous rather than missing:

```
python3 -m clockfold classify "2026-11-01 01:30" America/New_York
```

```
2026-11-01 01:30 in America/New_York is ambiguous (fold)
  earlier instant: 2026-11-01T05:30:00+00:00 (-04:00)
  later instant:   2026-11-01T06:30:00+00:00 (-05:00)
```

Anything outside a transition prints `normal` and one instant.

## Resolving under a policy

Four policies cover the conventions schedulers actually use:

- `earlier` resolves an ambiguous reading to the first pass and moves a nonexistent reading back to the instant just before the gap.
- `later` resolves an ambiguous reading to the second pass and moves a nonexistent reading forward past the gap.
- `skip` drops a nonexistent reading entirely and keeps only the first pass of an ambiguous one, for jobs that must not run twice.
- `double` keeps both passes of an ambiguous reading and drops a nonexistent one, for jobs that must not be silently skipped.

```
python3 -m clockfold resolve "2026-11-01 01:30" America/New_York --policy later
```

```
2026-11-01 01:30 in America/New_York is ambiguous (fold)
policy later gives 1 instant
  2026-11-01T06:30:00+00:00
```

## Expanding a daily schedule

The useful case is a recurring local time. `schedule` walks day by day and reports every transition day it crosses.

```
python3 -m clockfold schedule 02:30 America/New_York --start 2026-03-07 --days 3 --policy skip
```

```
policy skip, 2 of 3 days produce runs
  2026-03-07 02:30 -> 2026-03-07T07:30:00+00:00
  2026-03-08 02:30 -> skipped (nonexistent)
  2026-03-09 02:30 -> 2026-03-09T06:30:00+00:00
```

Switch to `--policy double` on the November date and the middle day produces two runs twelve months later, which is the mistake that duplicates side effects.

## Listing a zone's transition days

```
python3 -m clockfold transitions 2026 Australia/Lord_Howe
```

```
2026-04-05 02:00 -> 01:30 local, offset +11:00 -> +10:30
2026-10-04 02:00 -> 02:30 local, offset +10:30 -> +11:00
```

Lord Howe shifts by thirty minutes rather than an hour, so the gap length is read from the offsets instead of assumed to be one hour.

## Using it as a library

```python
# expanding a job into concrete instants is the whole point
from clockfold import load_zone, daily_runs

zone = load_zone("Europe/London")
for run in daily_runs("01:30", zone, "2026-10-24", days=3, policy="double"):
    print(run)
```

`daily_runs` returns aware UTC datetimes in order, `occurrences` handles a single reading, and `classify` returns the kind plus both candidate instants when the offsets differ.

## Running the tests

```
python3 -m unittest discover -s tests -v
```

The suite runs against the system tz database, so a zone whose rules change can legitimately move a test date. The dates used here, New York and Lord Howe in 2026, are stable.

## License

MIT. See LICENSE.
