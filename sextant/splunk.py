import requests
from sextant.plugin import Plugin
from getpass import getpass
from .auth.okta import OktaClient, OktaSamlClient


class SplunkPlugin(Plugin):
    name = 'splunk'

    def __init__(self, parsers, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        # register commands
        parser = parsers.add_parser('splunk', help='Splunk')
        parser.set_defaults(func=self.routes)
        parser.add_argument('--search', nargs='?', help='Run a search')
        parser.add_argument('--savedsearch', nargs='?', help='Find saved searches')

        # get splunk params
        self.endpoint = kwargs.get('endpoint')
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

    def routes(self, ns):
        if ns.search:
            return self.search(ns.search)
        if ns.savedsearch:
            return self.savedsearch(ns.savedsearch)

    def check(self):
        r = self.session.get(f'{self.endpoint}:8089/services/apps/local')
        r.raise_for_status()
        return True

    def search(self, query, max_count=100):
        """Run search queries."""
        try:
            payload = {'search': query, 'output_mode': 'json', 'max_count': max_count}
            r = self.session.post(f'{self.endpoint}:8089/services/search/jobs/export', data=payload)
            r.raise_for_status()
            print(r.text)

        except requests.exceptions.HTTPError as e:
            print(f"Error: {r.json()['messages'][0]['text']}")

    def savedsearch(self, username=None):
        """
        Find saved searches.
        Support filtering on username.
        """
        try:
            payload = {'output_mode': 'json'}
            # build filters
            if username:
                payload['search'] = f'eai:acl.owner={username}'
            r = self.session.get(f'{self.endpoint}:8089/services/saved/searches', params=payload)
            r.raise_for_status()
            print(r.text)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print(f"Error: {r.json()['messages'][0]['text']}")
            else:
                print(e)
