import re
from datetime import datetime, timedelta

def humanize(time):
    """Return time as a human-readable relative time string."""
    periods = (
        ("y", 60 * 60 * 24 * 365),
        ("d", 60 * 60 * 24),
        ("h", 60 * 60),
        ("m", 60),
        ("s", 1),
    )
    delta = datetime.now() - time

    for period, time_window in periods:
        if delta.total_seconds() >= time_window:
            how_many = int(delta.total_seconds() / time_window)
            return f"{how_many}{period}"

    return "now"  # less than a second ago

def deshumanize(time):
    """Convert a human relative time in timedelta."""
    try:
        parse = re.match(r'(\d+)([s|m|h|d|y])', time)
        value = int(parse.group(1))
        unit = parse.group(2)
        if unit == 's':
            return timedelta(seconds=value)
        if unit == 'm':
            return timedelta(minutes=value)
        if unit == 'h':
            return timedelta(hours=value)
        if unit == 'd':
            return timedelta(days=value)
        if unit == 'y':
            return timedelta(years=value)

    except IndexError:
        raise RuntimeError(f'Wrong relative time format "{time}"')
