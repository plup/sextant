import sys
import click
import httpx
import json
import uuid
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
def alert():
    """Manage alerts."""

@alert.command()
@click.argument('file', type=click.File())
@click.pass_obj
def new (obj, file):
    """Create an alert from a JSON file."""
    try:
        alert = json.load(file)
        alert['sourceRef'] = str(uuid.uuid4())
        r = obj['client'].post('/api/v1/alert', json=alert)
        r.raise_for_status()
        print(r.json())

    except httpx.HTTPStatusError as e:
        print(e.response.json())

@alert.command('list')
@click.option('--from', '-f', 'from_', default='10m')
@click.pass_obj
def list_alert(obj, from_):
    """Get the last alerts from TheHive."""
    try:
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
            table = Table('id', 'ago', 'severity', 'status', 'obs', 'title', title='Alerts')
            for alert in r.json():
                table.add_row(
                    alert['_id'],
                    humanize(datetime.fromtimestamp(alert['date'] / 1000)),
                    alert['severityLabel'],
                    alert['status'],
                    str(alert['observableCount']),
                    alert['title'],
                )
            console = Console()
            console.print(table)
        else:
            print(r.text)

    except httpx.HTTPStatusError as e:
        print(e.response.text)

@alert.command()
@click.argument('alert_id')
@click.pass_obj
def get(obj, alert_id):
    """Get the alert from TheHive."""
    r = obj['client'].get(f'/api/v1/alert/{alert_id}')
    r.raise_for_status()
    print(r.text)

@main.group()
def case():
    """Manage cases."""

@case.command('list')
@click.option('--from', '-f', 'from_', default='10m')
@click.pass_obj
def list_case(obj, from_):
    """Get the last cases from TheHive."""
    try:
        # convert from filter
        date = int((datetime.now() - deshumanize(from_)).timestamp() * 1000)
        r = obj['client'].post(
                '/api/v1/query',
                 json={
                    "query": [
                        {"_name": "listCase"},
                        {"_name": "filter", "_gte": {"_field": "newDate", "_value": date}},
                        {"_name": "sort", "_fields": [{"newDate": "desc"}]},
                    ],
                    "excludeFields": ["description", "summary"] # save bandwidth
                }
            )
        r.raise_for_status()
        if sys.stdout.isatty():
            # display results
            table = Table('id', 'ago', 'severity', 'status', 'stage', 'title', title='Cases')
            for case in r.json():
                table.add_row(
                    case['_id'],
                    humanize(datetime.fromtimestamp(case['newDate'] / 1000)),
                    case['severityLabel'],
                    case['status'],
                    case['stage'],
                    case['title'],
                )
            console = Console()
            console.print(table)
        else:
            print(r.text)

    except httpx.HTTPStatusError as e:
        print(e.response.text)
