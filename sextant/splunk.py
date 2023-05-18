import requests
from rich.console import Console
from rich.table import Table
from sextant.plugin import Plugin
from getpass import getpass
from .auth.okta import OktaClient, OktaSamlClient


class SplunkPlugin(Plugin):
    name = 'splunk'

    def __init__(self, subparsers, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        # register commands
        parser = subparsers.add_parser('search', help='Search command')
        parser.add_argument('--query', nargs='?', help='Run a search query')
        parser.set_defaults(func=self.search)

        parser = subparsers.add_parser('savedsearch', help='Find savedsearches')
        parser.add_argument('--name', nargs='?', help='Filter on search name')
        parser.add_argument('--user', nargs='?', help='Filter on username')
        parser.add_argument('--action', nargs='?', help='Filter on action')
        parser.add_argument('--count', type=int, default=0, help='Limit the results')
        parser.add_argument('--migrate', action='store_true', help='Update the alert configuration.')
        parser.set_defaults(func=self.savedsearch)

        # get splunk params
        self.endpoint = kwargs.get('endpoint')

        # set authentication
        self.auth(kwargs['auth'])

    def auth(self, auth_config):
        """Manage authentication."""
        if auth_config['type'] == 'okta':
            self.okta = OktaSamlClient(
                    username = auth_config['login'],
                    password = getpass(f'Password for {auth_config["login"]}: '),
                    endpoint = auth_config['endpoint'],
                    app_name = auth_config['app_name'],
                    app_id = auth_config['app_id'],
            )
        if auth_config['type'] == 'apikey':
            self.session = requests.Session()
            self.session.headers = {"Authorization": f"Bearer {auth_config['token']}"}

    def check(self):
        r = self.session.get(f'{self.endpoint}:8089/services/apps/local')
        r.raise_for_status()
        return True

    def search(self, query, *args, max_count=100, **kwargs):
        """Run search queries."""
        try:
            payload = {'search': query, 'output_mode': 'json', 'max_count': max_count}
            r = self.session.post(f'{self.endpoint}:8089/services/search/jobs/export', data=payload)
            r.raise_for_status()
            print(r.text)

        except requests.exceptions.HTTPError as e:
            print(f"Error: {r.json()['messages'][0]['text']}")

    def savedsearch(self, *args, name=None, user=None, action=None, count=0, migrate=False, **kwargs):
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
            r = self.session.get(f'{self.endpoint}:8089/services/saved/searches', params=payload)
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

        if migrate:
            return self.migrate(results)

        # display results
        table = Table('search name', 'actions', title='Alerts')
        for item in results:
            table.add_row(item['name'], item['content']['actions'])
        console = Console()
        console.print(table)
        console.print(f'total: {total}')

    def migrate(self, alerts):
        """Migrate alerts to new app."""
        for alert in alerts:
            try:
                id = alert['id']
                config = alert['content']
                # map params
                print(config['actions'])

            except: raise
