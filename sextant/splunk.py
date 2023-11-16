import logging
import requests
import argparse
from rich.console import Console
from rich.table import Table
from sextant.plugin import BasePlugin, with_auth
from .auth.okta import OktaClient, OktaSamlClient


class SplunkPlugin(BasePlugin):
    name = 'splunk'

    def __init__(self, subparsers, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        super().__init__(*args, **kwargs)

        # register commands
        parser = subparsers.add_parser('query', help='Search command')
        parser.add_argument('query', nargs=argparse.REMAINDER, help='query to run (ex: "search index=notable earliest=-60m")')
        parser.set_defaults(func=self.query)

        parser = subparsers.add_parser('savedsearches', help='Find savedsearches')
        parser.add_argument('--name', nargs='?', help='Filter on search name')
        parser.add_argument('--user', nargs='?', help='Filter on username')
        parser.add_argument('--action', nargs='?', help='Filter on action')
        parser.add_argument('--count', type=int, default=0, help='Limit the results')
        parser.set_defaults(func=self.savedsearches)

        parser = subparsers.add_parser('savedsearch', help='Get a savedsearch')
        parser.add_argument('--get', nargs='?', help='Get the search')
        parser.set_defaults(func=self.savedsearch)

    @with_auth
    def check(self):
        try:
            r = self.get('/services/apps/local')
            r.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            return False

    @with_auth
    def query(self, query, *args, count=100, **kwargs):
        """
        Command: Run search queries

        :param int --count: limit of items to return
        :param remain query: the query to run
        """
        try:
            payload = {'search': query, 'output_mode': 'json_rows', 'max_count': count}
            r = self.post('/services/search/jobs/export', data=payload)
            r.raise_for_status()
            table = Table(*r.json()['fields'])
            for row in r.json()['rows']:
                table.add_row(*row)

            console = Console()
            console.print(table)

        except requests.exceptions.HTTPError as e:
            print(f"Error: {r.json()['messages'][0]['text']}")

    @with_auth
    def jobs(self, *args, **kwargs):
        """Command: List the running jobs"""
        r = self.get('/services/search/jobs', params={'output_mode': 'json'})
        r.raise_for_status()
        print(r.text)

    @with_auth
    def alerts(self, *args, name=None, user=None, action=None, count=0, **kwargs):
        """
        Command: Find saved searches

        :param --name: string contained in the search name
        :param --user: owner of the search
        :param --action: actions triggered
        """
        try:
            payload = {'output_mode': 'json', 'count': count, 'search': []}
            # build search filters
            if user:
                payload['search'].append(f'eai:acl.owner={user}')
            if name:
                payload['search'].append(f'name="*{name}*"')
            r = self.get('/services/saved/searches', params=payload)
            r.raise_for_status()
            results = r.json()['entry']
            total = r.json()['paging']['total']

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print(f"Error: {r.json()['messages'][0]['text']}")
            else:
                print(e)
            return

        # filter on action
        if action:
            results = [item for item in results
                        if action in item['content']['actions']]

        # display results
        table = Table('search name', 'actions', title='Alerts')
        for item in results:
            table.add_row(item['name'], item['content']['actions'])
        console = Console()
        console.print(table)
        console.print(f'total: {total}')

    @with_auth
    def alert(self, name, *args, **kwargs):
        """
        Command: get details on a saved search.

        :param --name: unique ID for the search
        """
        try:
            print(name)
            payload = {'output_mode': 'json'}
            name = requests.utils.quote(name)
            r = self.get(f'/services/saved/searches/{name}', params=payload)
            r.raise_for_status()
            # directly output the json to be parsed by an external tool
            print(r.text)
        except requests.exceptions.HTTPError as e:
            print(e)
