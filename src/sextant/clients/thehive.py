import sys
import click
import httpx
from rich.console import Console
from rich.table import Table
from datetime import datetime
from sextant.utils import humanize, deshumanize

@click.group()
@click.pass_context
def main(ctx):
    """Get events from TheHive."""
    # retreive client config from context
    config = ctx.obj['config'].reveal(ctx.info_name)

    # expose a client
    if config['credentials'].get('secret'):
        ctx.obj['client'] = httpx.Client(
                base_url=config['remote'],
                headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
                verify = False
            )
    else:
        httpx.BasicAuth(username="username", password="secret")
        ctx.obj['client'] = httpx.Client(
                base_url=config['remote'],
                auth = httpx.BasicAuth(
                    username = config['credentials']['username'],
                    password = config['credentials']['password']
                ),
                verify = False
            )

@main.group()
@click.pass_obj
def alert(obj):
    """Manage alerts."""

@alert.command()
@click.option('--from', '-f', 'from_', default='10m')
@click.pass_obj
def list(obj, from_):
    """Get the last alerts from TheHive."""
    # convert from filter
    date = int((datetime.now() - deshumanize(from_)).timestamp() * 1000)
    r = obj['client'].post(
            '/api/v1/query',
             json={
                "query": [
                    {"_name": "listAlert"},
                    {"_name": "filter", "_gte": {"_field": "date", "_value": date}},
                    {"_name": "sort", "_fields": [{"date": "desc"}]},
                ],
                "excludeFields": ["description", "summary"] # save bandwidth
            }
        )
    r.raise_for_status()
    if sys.stdout.isatty():
        # display results
        table = Table('id', 'ago', 'status', 'severity', 'obs', 'title', title='Alerts')
        for alert in r.json():
            table.add_row(
                alert['_id'],
                humanize(datetime.fromtimestamp(alert['date'] / 1000)),
                alert['status'],
                alert['severityLabel'],
                str(alert['observableCount']),
                alert['title'],
            )
        console = Console()
        console.print(table)
    else:
        print(r.text)

@alert.command()
@click.argument('alert_id')
@click.pass_obj
def get(obj, alert_id):
    """Get the alert from TheHive."""
    r = obj['client'].get(f'/api/v1/alert/{alert_id}')
    r.raise_for_status()
    print(r.text)
