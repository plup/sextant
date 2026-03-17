import sys
import click
import httpx
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from sextant.utils import Lazy, humanize, deshumanize
from sextant.clients.thehive.client import TheHiveClient


@click.group()
@click.pass_context
def main(ctx):
    """Get events from TheHive."""
    def factory():
        config = ctx.obj['config'].reveal(ctx.info_name)
        return TheHiveClient.from_config(config)

    client = Lazy(factory)
    ctx.obj['client'] = client

    def cleanup():
        if client._instance is not None:
            client._instance.http.close()
    ctx.call_on_close(cleanup)


@main.group()
def alert():
    """Manage alerts."""


@alert.command()
@click.argument('file', type=click.File())
@click.pass_obj
def new(obj, file):
    """Create an alert from a JSON file."""
    try:
        alert_data = json.load(file)
        result = obj['client'].create_alert(alert_data)
        click.echo(json.dumps(result))

    except httpx.HTTPStatusError as e:
        click.echo(json.dumps(e.response.json()), err=True)


@alert.command('list')
@click.option('--from', '-f', 'from_', default='10m')
@click.pass_obj
def list_alert(obj, from_):
    """Get the last alerts from TheHive."""
    try:
        since = int((datetime.now() - deshumanize(from_)).timestamp() * 1000)
        alerts = obj['client'].list_alerts(since_ms=since)

        if sys.stdout.isatty():
            table = Table('id', 'ago', 'severity', 'status', 'obs', 'title', title='Alerts')
            for alert in alerts:
                table.add_row(
                    alert['_id'],
                    humanize(datetime.fromtimestamp(alert['date'] / 1000)),
                    alert['severityLabel'],
                    alert['status'],
                    str(alert['observableCount']),
                    alert['title'],
                )
            Console().print(table)
        else:
            click.echo(json.dumps(alerts))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@alert.command()
@click.argument('alert_id')
@click.pass_obj
def get(obj, alert_id):
    """Get the alert from TheHive."""
    result = obj['client'].get_alert(alert_id)
    click.echo(json.dumps(result))


@main.group()
def case():
    """Manage cases."""


@case.command('list')
@click.option('--from', '-f', 'from_', default='10m')
@click.pass_obj
def list_case(obj, from_):
    """Get the last cases from TheHive."""
    try:
        since = int((datetime.now() - deshumanize(from_)).timestamp() * 1000)
        cases = obj['client'].list_cases(since_ms=since)

        if sys.stdout.isatty():
            table = Table('id', 'ago', 'severity', 'status', 'stage', 'title', title='Cases')
            for case in cases:
                table.add_row(
                    case['_id'],
                    humanize(datetime.fromtimestamp(case['newDate'] / 1000)),
                    case['severityLabel'],
                    case['status'],
                    case['stage'],
                    case['title'],
                )
            Console().print(table)
        else:
            click.echo(json.dumps(cases))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)
