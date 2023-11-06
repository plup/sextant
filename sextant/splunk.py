import logging
import requests
from rich.console import Console
from rich.table import Table
from sextant.plugin import BasePlugin
from .auth.okta import OktaClient, OktaSamlClient


class SplunkPlugin(BasePlugin):
    name = 'splunk'

    def __init__(self, subparsers, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        super().__init__(*args, **kwargs)

        # register commands
        parser = subparsers.add_parser('search', help='Search command')
        parser.add_argument('--query', nargs='?', help='Run a search query')
        parser.set_defaults(func=self.search)

        parser = subparsers.add_parser('savedsearches', help='Find savedsearches')
        parser.add_argument('--name', nargs='?', help='Filter on search name')
        parser.add_argument('--user', nargs='?', help='Filter on username')
        parser.add_argument('--action', nargs='?', help='Filter on action')
        parser.add_argument('--count', type=int, default=0, help='Limit the results')
        parser.set_defaults(func=self.savedsearches)

        parser = subparsers.add_parser('savedsearch', help='Get a savedsearch')
        parser.add_argument('--get', nargs='?', help='Get the search')
        parser.set_defaults(func=self.savedsearch)

        # authenticate
        self.auth()

    def check(self):
        try:
            r = self.get('/services/apps/local')
            r.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            return False

    def search(self, query, *args, max_count=100, **kwargs):
        """Run search queries."""
        try:
            payload = {'search': query, 'output_mode': 'json', 'max_count': max_count}
            r = self.post('/services/search/jobs/export', data=payload)
            r.raise_for_status()
            print(r.text)

        except requests.exceptions.HTTPError as e:
            print(f"Error: {r.json()['messages'][0]['text']}")

    def savedsearches(self, *args, name=None, user=None, action=None, count=0, **kwargs):
        """
        Find saved searches.
        Support filtering on username.
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

    def savedsearch(self, get, *args, **kwargs):
        """Configuration or actions on a savedsearch."""
        try:
            payload = {'output_mode': 'json'}
            name = requests.utils.quote(get)
            r = self.get(f'/services/saved/searches/{name}', params=payload)
            r.raise_for_status()
            # directly output the json to be parsed by an external tool
            print(r.text)
        except requests.exceptions.HTTPError as e:
            print(e)
