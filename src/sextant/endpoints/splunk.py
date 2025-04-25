import click
import httpx
import json
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live

@click.group()
@click.pass_obj
def splunk(obj):
    """Get events from Splunk."""
    # instantiate client from config
    config = obj['config'].get_endpoint('splunk')
    obj['client'] = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
            verify = False
        )

@splunk.command()
@click.pass_obj
def indexes(obj):
    """Display accessible indexes."""
    r = obj['client'].get('/services/data/indexes',
                          params={'output_mode': 'json', 'count':0, 'datatype':'all'})
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

@splunk.command()
@click.option('--name', help='Search name contains')
@click.option('--user', help='Owner of the search')
@click.pass_obj
def searches(obj, user, name):
    """Display savedsearches."""
    payload = {'output_mode': 'json', 'count': 0, 'search': []}
    # build search filters
    if user:
        payload['search'].append(f'eai:acl.owner={user}')
    if name:
        payload['search'].append(f'name="*{name}*"')

    r = obj['client'].get('/services/saved/searches', params=payload)
    r.raise_for_status()
    total = r.json()['paging']['total']
    table = Table('search', 'user', 'action', title='savedsearches')
    for item in r.json()['entry']:
        table.add_row(item['name'], item['acl']['owner'], item['content']['actions'])
    console = Console()
    console.print(table)
    console.print(f'total: {total}')

@splunk.command()
@click.option('--trigger', is_flag=True, help='Force the search to run')
@click.argument('name')
@click.pass_obj
def search(obj, name, trigger):
    """Get the savedsearch details."""
    if trigger:
        r = obj['client'].post(f'/services/saved/searches/{name}/dispatch',
                               data={'trigger_actions': 1})
        r.raise_for_status()
    else:
        r = obj['client'].get(f'/services/saved/searches/{name}',
                              params={'output_mode':'json'})
        r.raise_for_status()
        results = r.json()['entry'][0]
        if sys.stdout.isatty():
            # limit output to the search
            print(results['content']['search'])
        else:
            print(json.dumps(results))

@splunk.command()
@click.option('--from', '-f', 'from_', default='10m')
@click.option('--to', '-t', default='now')
@click.argument('query')
@click.pass_obj
def query(obj, query, to, from_):
    """
    Run a search query.

    Example of queries:

     "search index=_internal | head 1 | fieldsummary"
     "|metadata index=_internal type=sourcetypes"
    """
    payload = {'search': query,
               'earliest_time': f'-{from_}', 'latest_time': to,
               'output_mode': 'json', 'preview': False, 'summarize': True}
    with obj['client'].stream('POST', '/services/search/jobs/export', data=payload) as r:
        r.raise_for_status()
        if sys.stdout.isatty():
            # generate a live table
            try:
                it = r.iter_lines()
                # guess returned fields from first result
                first_result = json.loads(next(it)).get('result')
                # extract 5 first common fields
                fields = [f for f in first_result.keys() if not f.startswith('_')][:5]
                # also keep _time if it exists
                if first_result.get('_time'):
                    fields.insert(0, '_time')
            except AttributeError:
                print('No result')
                return

            # build the result table
            table = Table(*fields)
            with Live(table, refresh_per_second=1):
                table.add_row(*[first_result[f] for f in fields]) # display first result
                for row in it:
                    if not row:
                        break
                    result = json.loads(row).get('result')
                    table.add_row(*[result[f] for f in fields])
        else:
            # pass lines to a pipe
            for line in r.iter_lines():
                print(line)
