import re
from datetime import datetime, timedelta


class Lazy:
    """Proxy that defers object creation until first attribute access.

    Wraps a factory callable and delays invocation until an attribute is
    actually used. This avoids expensive setup (e.g. fetching secrets from
    1Password) when it isn't needed, such as when the user runs --help.
    The real instance is created once on first access and cached for reuse.
    """

    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    def __getattr__(self, name):
        if self._instance is None:
            self._instance = self._factory()
        return getattr(self._instance, name)

def humanize(time: datetime) -> str:
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

def deshumanize(time: str) -> timedelta:
    """Convert a human relative time in timedelta."""
    try:
        parse = re.match(r'(\d+)([smhdy])', time)
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
            return timedelta(days=value * 365)

    except (AttributeError, IndexError):
        raise ValueError(f'Wrong relative time format "{time}"')
