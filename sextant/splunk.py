import logging
import requests
import argparse
import json
from functools import wraps
from rich.console import Console
from rich.table import Table
from rich.live import Live
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
    def indexes(self, **kwargs):
        """Command: List indexes"""
        r = self.get('/services/data/indexes', params={'output_mode': 'json', 'count':0, 'datatype':'all'})
        r.raise_for_status()
        total = r.json()['paging']['total']
        table = Table('indexes', 'datatype', 'counts')
        for item in r.json()['entry']:
            style = 'red' if item['content']['disabled'] else 'default'
            table.add_row(item['name'], item['content']['datatype'],
                          str(item['content']['totalEventCount']),
                          style=style)

        console = Console()
        console.print(table)
        console.print(f'total: {total}')

    @with_auth
    @with_errors
    def index(self, **kwargs):
        """
        Command: Get informations about an index

        :param name: name of the index
        :param optional --from: first event (default: 1h)
        :param optional --to: last event (default: now)
        :param optional --stype: filter on source type
        :param flag --stypes: display the source types seen in documents
        """
        name = kwargs['name']
        _from = kwargs['from'] or '1h'
        to = kwargs['to'] or 'now'
        sourcetype = kwargs['stype'] or '*'
        sourcetypes = kwargs['stypes']

        if sourcetypes:
            query = f'metadata index={name} type=sourcetypes'
            fields = ['sourcetype', 'totalCount']

        else:
            query = f'search index={name} sourcetype={sourcetype} | fieldsummary | fields field',
            fields = ['field']

        payload = {'search': query,
                   'earliest_time': f'-{_from}', 'latest_time': to,
                   'output_mode': 'json', 'preview': False}
        r = self.post('/services/search/jobs/export', data=payload, stream=True)
        r.raise_for_status()

        table = Table(*fields)
        with Live(table, refresh_per_second=1):
            for row in r.iter_lines():
                row = row.decode().strip()
                if row:
                    try:
                        result = json.loads(row).get('result')
                        table.add_row(*[result[f] for f in fields])
                    except TypeError:
                        print('No result')

    @with_auth
    @with_errors
    def query(self, **kwargs):
        """
        Command: Run search queries

        :param optional --from: first event (default: 1h)
        :param optional --to: last event (default: now)
        :param query: the query to run
        """
        # fetch params
        _from = kwargs['from'] or '1h'
        to = kwargs['to'] or 'now'
        query = kwargs['query']

        # ru nthe query
        # count and max_time seems to be ignored when streaming
        payload = {'search': query,
                   'earliest_time': f'-{_from}', 'latest_time': to,
                   'output_mode': 'json', 'preview': False, 'summarize': True}
        r = self.post('/services/search/jobs/export', data=payload, stream=True)
        r.raise_for_status()

        # guess returned fields from first result by returning the first 5 not internal
        try:
            it = r.iter_lines()
            row = json.loads(next(it).decode().strip()).get('result')
            fields = [f for f in row.keys() if not f.startswith('_')][:5]
        except AttributeError:
            print('No result')
            return

        # build the result table
        table = Table(*fields)
        with Live(table, refresh_per_second=1):
            for row in r.iter_lines():  # iterator starts from first element
                row = row.decode().strip()
                if not row:
                    break
                result = json.loads(row).get('result')
                table.add_row(*[result[f] for f in fields])

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
