import click
import httpx
import json
import sys
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from sextant.utils import Lazy, deshumanize
from sextant.clients.splunk.client import SplunkClient


def get_stdin(ctx, param, value):
    """Callback reading arguments from stdin '-'."""
    if value == '-' and not click.get_text_stream('stdin').isatty():
        return click.get_text_stream('stdin').read().strip()
    return value


def display_results(results, fields=None):
    """Display Splunk results in terminal guessing the fields if not set."""
    if not results:
        click.echo('No result', err=True)
        return

    try:
        fields = fields.split(',')
    except AttributeError:
        fields = [f for f in results[0].keys() if not f.startswith('_')][:5]
        if results[0].get('_time'):
            fields.insert(0, '_time')

    table = Table(*fields)
    for row in results:
        table.add_row(*[str(row.get(f, 'NA')) for f in fields])

    Console().print(table)


@click.group()
@click.pass_context
def main(ctx):
    """Get events from Splunk."""
    def factory():
        config = ctx.obj['config'].reveal(ctx.info_name)
        return SplunkClient.from_config(config)

    client = Lazy(factory)
    ctx.obj['client'] = client

    def cleanup():
        if client._instance is not None:
            client._instance.http.close()
    ctx.call_on_close(cleanup)


@main.group()
def job():
    """Manage search jobs."""


@job.command('list')
@click.option('--name', help='Search string in job name')
@click.option('--user', help='Filter on owner of the job')
@click.pass_obj
def list_job(obj, name, user):
    """List available jobs."""
    entries, total = obj['client'].list_jobs(user=user, name=name)

    if sys.stdout.isatty():
        table = Table('sid', 'status', 'events', 'owner')
        for entry in entries:
            table.add_row(
                entry['name'],
                entry['content']['dispatchState'],
                str(entry['content']['eventCount']),
                entry['acl']['owner'],
            )
        console = Console()
        console.print(table)
        console.print(f'total: {total}')
    else:
        click.echo(json.dumps(entries))


@job.command('get')
@click.argument('sid', callback=get_stdin)
@click.option('--fields', default=None)
@click.option('-w', '--wait', default=0, help='Wait for job to finish')
@click.pass_obj
def get_job(obj, sid, fields, wait):
    """Get the search job results."""
    try:
        results = obj['client'].get_job_results(sid, wait=wait)
        if results is None:
            click.echo(f'Empty response fetching result for {sid}', err=True)
            return

        if sys.stdout.isatty():
            display_results(results, fields)
        else:
            click.echo(json.dumps(results))

    except ValueError as e:
        click.echo(str(e), err=True)
    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.command()
@click.pass_obj
def indexes(obj):
    """Display accessible indexes."""
    entries, total = obj['client'].list_indexes()

    if sys.stdout.isatty():
        table = Table('indexes', 'datatype', 'counts')
        for item in entries:
            style = 'red' if item['content']['disabled'] else 'default'
            table.add_row(item['name'], item['content']['datatype'],
                          str(item['content']['totalEventCount']),
                          style=style)
        console = Console()
        console.print(table)
        console.print(f'total: {total}')
    else:
        click.echo(json.dumps(entries))


@main.group()
def search():
    """Manage savedsearches."""


@search.command('list')
@click.option('--name', help='Search name contains')
@click.option('--user', help='Owner of the search')
@click.pass_obj
def list_search(obj, user, name):
    """Display savedsearches."""
    entries, total = obj['client'].list_searches(user=user, name=name)

    if sys.stdout.isatty():
        table = Table('search', 'user', 'action', title='savedsearches')
        for item in entries:
            table.add_row(item['name'], item['acl']['owner'], item['content']['actions'])
        console = Console()
        console.print(table)
        console.print(f'total: {total}')
    else:
        click.echo(json.dumps(entries))


@search.command('get')
@click.argument('name')
@click.pass_obj
def get_search(obj, name):
    """Get the savedsearch details."""
    try:
        entry = obj['client'].get_search(name)

        if sys.stdout.isatty():
            click.echo(click.style('Description', bold=True))
            click.echo(click.style(entry['content']['description'], italic=True))
            click.echo(click.style('Search:', bold=True))
            click.echo(entry['content']['search'])
            click.echo(click.style('Schedule:', bold=True))
            click.echo(f"Cron: {entry['content']['cron_schedule']}")
            click.echo(f"Next: {entry['content']['next_scheduled_time']}")
            click.echo(f"Latest: {entry['content']['dispatch.latest_time']}")
            click.echo(f"Earliest: {entry['content']['dispatch.earliest_time']}")
            click.echo(click.style('Alert:', bold=True))
            click.echo(f"Actions: {entry['content']['actions']}")
            click.echo(f"Expire: {entry['content']['alert.expires']}")
        else:
            click.echo(json.dumps(entry))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@search.command('run')
@click.option('--to', '-t')
@click.option('--from', '-f', 'from_')
@click.option('--trigger', is_flag=True, help='Trigger actions')
@click.argument('name')
@click.pass_obj
def run_search(obj, name, trigger, to, from_):
    """Force the search to run and trigger alert actions."""
    try:
        data = {}
        if trigger:
            data['trigger_actions'] = 1

        def convert_time(time):
            try:
                return f'-{deshumanize(time)}'
            except ValueError:
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

        sid = obj['client'].dispatch_search(name, data)
        click.echo(sid)

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


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
    with obj['client'].stream_query(query, earliest=f'-{from_}', latest=to) as lines:
        if sys.stdout.isatty():
            try:
                first_result = json.loads(next(lines)).get('result')
                fields = [f for f in first_result.keys() if not f.startswith('_')][:5]
                if first_result.get('_time'):
                    fields.insert(0, '_time')
            except AttributeError:
                click.echo('No result', err=True)
                return

            table = Table(*fields)
            with Live(table, refresh_per_second=1):
                table.add_row(*[first_result[f] for f in fields])
                for row in lines:
                    if not row:
                        break
                    result = json.loads(row).get('result')
                    table.add_row(*[result[f] for f in fields])
        else:
            for line in lines:
                click.echo(line)
