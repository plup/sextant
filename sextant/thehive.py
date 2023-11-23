"""Operations with The Hive."""
import requests
import json
from rich import print
from rich.table import Table
from functools import wraps, update_wrapper
from urllib3.exceptions import InsecureRequestWarning
from sextant.plugin import BasePlugin, with_auth


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class ThehivePlugin(BasePlugin):
    name = 'thehive'

    def __init__(self, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        super().__init__(*args, **kwargs)
        self.verify = False

    def check(self):
        try:
            r = self.get('/api/v1/status/public')
            r.raise_for_status()
            return True
        except Exception:
            return False

    @with_auth
    def alert(self, **kwargs):
        """Command: Create a fake alert"""
        payload = {
              "type": "alertType",
              "source": "sextant",
              "sourceRef": "1",
              "title": "Test alert",
              "description": "This is a test alert from the sextant",
              "severity": 1,
              "tlp": 0,
              "pap": 0,
              "flag": True,
              "summary": "Nothing really bad happened",
              "observables": [
                 { "dataType": "url", "data": "http://example.org" },
                 { "dataType": "mail", "data": "foo@example.org" },
                 { "dataType": "hostname", "data": "localhost" },
              ],
            }
        r = self.post('/api/v1/alert', json=payload)
        r.raise_for_status()
        print(r.json())
