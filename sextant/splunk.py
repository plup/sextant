import logging
import requests
import argparse
from functools import wraps
from rich.console import Console
from rich.table import Table
from sextant.plugin import BasePlugin, with_auth


class SplunkPlugin(BasePlugin):
    name = 'splunk'

    def with_errors(f):
        """Handle errors and messages returned by Splunk."""
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try:
                return f(self, *args, **kwargs)
            except requests.exceptions.HTTPError as e:
                logging.error(e.response.json()['messages'][0]['text'])
        return wrapper

    @with_auth
    def check(self):
        try:
            r = self.get('/services/apps/local')
            r.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            return False

    @with_auth
    @with_errors
    def index(self, *args, name=None, **kwargs):
        """
        Command: Get informations about indexes

        :param optional name: name of the index to fetch fields from
        """
        if not name:
            r = self.get('/services/data/indexes', params={'output_mode': 'json', 'count':0, 'datatype':'all'})
            r.raise_for_status()
            total = r.json()['paging']['total']
            table = Table('name', 'datatype')
            for item in r.json()['entry']:
                style = 'red' if item['content']['disabled'] else 'default'
                table.add_row(item['name'], item['content']['datatype'], style=style)

            console = Console()
            console.print(table)
            console.print(f'total: {total}')

        else:
            payload = {'search': f'walklex index={name} type=field | eval field=trim(field) | dedup field | fields field | sort field',
                       'output_mode': 'json_rows'}
            r = self.post('/services/search/jobs/export', data=payload)
            r.raise_for_status()

            table = Table('field')
            for row in r.json()['rows']:
                table.add_row(row[0].strip())
            console = Console()
            console.print(table)

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
            if not r.text:
                print('No data')
                return

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
