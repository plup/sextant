import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from sextant.utils import humanize, deshumanize


class TestHumanize:

    def test_seconds(self):
        now = datetime.now()
        assert humanize(now - timedelta(seconds=30)) == "30s"

    def test_minutes(self):
        now = datetime.now()
        assert humanize(now - timedelta(minutes=5)) == "5m"

    def test_hours(self):
        now = datetime.now()
        assert humanize(now - timedelta(hours=3)) == "3h"

    def test_days(self):
        now = datetime.now()
        assert humanize(now - timedelta(days=2)) == "2d"

    def test_years(self):
        now = datetime.now()
        assert humanize(now - timedelta(days=400)) == "1y"

    def test_now(self):
        assert humanize(datetime.now()) == "now"

    def test_subsecond(self):
        now = datetime.now()
        assert humanize(now - timedelta(milliseconds=100)) == "now"


class TestDeshumanize:

    def test_seconds(self):
        assert deshumanize("30s") == timedelta(seconds=30)

    def test_minutes(self):
        assert deshumanize("5m") == timedelta(minutes=5)

    def test_hours(self):
        assert deshumanize("2h") == timedelta(hours=2)

    def test_days(self):
        assert deshumanize("7d") == timedelta(days=7)

    def test_years(self):
        assert deshumanize("1y") == timedelta(days=365)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match='Wrong relative time format'):
            deshumanize("abc")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match='Wrong relative time format'):
            deshumanize("")

    def test_pipe_not_matched(self):
        with pytest.raises(ValueError, match='Wrong relative time format'):
            deshumanize("5|")
