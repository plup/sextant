"""Contains the CLI commands."""

import click
import yaml
import json
from importlib import metadata
from rich.table import Table
from rich.console import Console
from .auth.okta import get_credentials
from .thehive import TheHiveClient


def format(results, fields, title):
    """Turns list of objects in a table."""
    # filter output
    rows = []
    for result in results:
        # force returning name for files
        if result['dataType'] == 'file':
            result['data'] = result['attachment']['name']
        rows.append([str(result[k]) for k in fields])

    # build the table
    table = Table(title=title)
    for field in fields:
        table.add_column(field)
    for row in rows:
        table.add_row(*row)

    return table

# click entrypoint
@click.group()
@click.option('-c', '--config', envvar='SEXTANT_CONFIG', type=click.Path(exists=True),
              default='config.yml')
@click.version_option(metadata.version(__name__.split('.')[0]))
@click.pass_context
def main(ctx, config):
    """Navigate through cosmic events."""
    with open(config) as f:
       conf = yaml.safe_load(f)
       ctx.obj = TheHiveClient(conf['thehive'])

# okta commands
@main.command()
def okta():
    """Test Okta authentication with Yubikey."""
    get_credentials()
    click.echo('ok')

# thehive commands
@main.group()
@click.pass_obj
def obs(thehive):
    """Manage observables."""

@obs.command()
@click.pass_obj
def types(thehive):
    """Display all observable types."""
    fields = ['name', 'isAttachment', 'createdBy']
    results = thehive.types()
    table = format(results, fields, 'Observable types')
    Console().print(table)

@obs.command()
@click.option('--ioc', is_flag=True)
@click.pass_obj
def search(thehive, ioc):
    """Search across observables."""
    fields = ['id', 'dataType', 'ioc', 'sighted', 'tlp', 'data']

    if ioc:
        results = thehive.iocs()
        table = format(results, fields, 'IOCs')
        Console().print(table)
