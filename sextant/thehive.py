"""Operations with The Hive."""
import logging
import requests
import json
import uuid
from rich import print
from rich.console import Console
from rich.table import Table
from functools import wraps, update_wrapper
from urllib3.exceptions import InsecureRequestWarning
from sextant.plugin import BasePlugin, with_auth

logger = logging.getLogger(__name__)
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class ThehivePlugin(BasePlugin):
    name = 'thehive'

    def with_errors(f):
        """Handle errors and messages returned by Splunk."""
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try:
                return f(self, *args, **kwargs)
            except requests.exceptions.HTTPError as e:
                logger.error(e.response.json()['message'])
            except requests.exceptions.ConnectTimeout:
                logger.error('Connection timed out')
        return wrapper

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
    @with_errors
    def types(self, **kwargs):
        """Command: Get observable types"""
        r = self.post('/api/v1/query', json={"query": [{"_name": "listObservableType"}]})
        r.raise_for_status()
        table = Table('name')
        for item in r.json():
            table.add_row(item['name'])

        console = Console()
        console.print(table)

    @with_auth
    @with_errors
    def alert(self, **kwargs):
        """
        Command: Create a fake alert

        :param optional --from: load alert params from file
        """
        # define a fake alert
        payload = {
              "type": "alert",
              "source": "sextant",
              "sourceRef": str(uuid.uuid1()),
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
        # override fields from file
        try:
            _from = kwargs['from']
            with open(_from, 'r') as file:
                payload.update(json.load(file))
        except (KeyError, TypeError):
            pass

        r = self.post('/api/v1/alert', json=payload)
        r.raise_for_status()
        print(r.json())

    @with_auth
    @with_errors
    def observable(self, **kwargs):
        """
        Command: Add an observable to a case

        :param --case: case id
        :param --type: observable type
        :param --data: observable data
        :param optional --tag: a tag
        """
        obs = {'dataType': kwargs['type'], 'data': kwargs['data']}
        tag = kwargs.get('tag')
        obs['tags'] = [tag] if tag else []

        r = self.post(f"/api/v1/case/{kwargs['case']}/observable", json=obs)
        r.raise_for_status()
        return r.json()

