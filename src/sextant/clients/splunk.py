import click
import httpx
import json
import sys
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from sextant.utils import deshumanize

@click.group()
@click.pass_context
def main(ctx):
    """Get events from Splunk."""
    # instantiate client from config
    config = ctx.obj['config'].reveal(ctx.info_name)
    ctx.obj['client'] = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
            verify = False
        )

@main.group()
def job():
    """Manage search jobs."""

@job.command('get')
@click.argument('sid')
@click.pass_obj
def get_job(obj, sid):
    """Get the search job results."""
    try:
        r = obj['client'].get(f'/services/search/v2/jobs/{sid}/results',
                              params={'output_mode':'json'})
        r.raise_for_status()
        results = r.json()['results']
        if sys.stdout.isatty():
            # limit output to the search
            print(results)
        else:
            print(json.dumps(results))
    except httpx.HTTPStatusError as e:
        print(e.response.text)


@main.command()
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

@main.group()
def search():
    """Manage savedsearches."""

@search.command('list')
@click.option('--name', help='Search name contains')
@click.option('--user', help='Owner of the search')
@click.pass_obj
def list_search(obj, user, name):
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

@search.command('get')
@click.argument('name')
@click.pass_obj
def get_search(obj, name):
    """Get the savedsearch details."""
    try:
        r = obj['client'].get(f'/services/saved/searches/{name}',
                              params={'output_mode':'json'})
        r.raise_for_status()
        results = r.json()['entry'][0]
        if sys.stdout.isatty():
            # limit output to the search and common parameters
            click.echo(click.style('Description', bold=True))
            click.echo(click.style(results['content']['description'], italic=True))
            click.echo(click.style('Search:', bold=True))
            click.echo(results['content']['search'])
            click.echo(click.style('Schedule:', bold=True))
            click.echo(f"Cron: {results['content']['cron_schedule']}")
            click.echo(f"Latest: {results['content']['dispatch.latest_time']}")
            click.echo(f"Earliest: {results['content']['dispatch.earliest_time']}")
            click.echo(click.style('Alert:', bold=True))
            click.echo(f"Actions: {results['content']['actions']}")
        else:
            click.echo(json.dumps(results))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)

@search.command('run')
@click.option('--to', '-t')
@click.option('--from', '-f', 'from_')
@click.option('--trigger', is_flag=True, help='Trigger actions')
@click.argument('name')
@click.pass_obj
def run_alert(obj, name, trigger, to, from_):
    """Force the search to run and trigger alert actions."""
    try:
        data = {}
        if trigger:
            data['trigger_actions'] = 1

        def convert_time(time):
            """Helper for time convertion."""
            try:
                return f'-{deshumanize(time)}' # test relative time format

            except ValueError:
                # assume format is iso and convert it to epoch in seconds
                data['dispatch.time_format'] = "%s"
                return int(datetime.fromisoformat(time).timestamp())

        try:
            if to:
                data['dispatch.latest_time'] = convert_time(to)
            if from_:
                data['dispatch.earliest_time'] = convert_time(from_)

        except ValueError:
            click.echo('Time format must be relative or ISO8601')
            return

        r = obj['client'].post(f'/services/saved/searches/{name}/dispatch', data=data,
                              params={'output_mode':'json'})
        r.raise_for_status()
        click.echo(r.json())

    except httpx.HTTPStatusError as e:
        print(e.response.text)

@main.command()
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
