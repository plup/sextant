"""Contains the CLI commands."""

import click
import yaml
import json
from importlib import metadata
from rich.table import Table
from rich.console import Console
from .auth.okta import get_credentials
from .thehive import TheHiveClient

# click entrypoint
@click.group()
@click.option('-c', '--config', envvar='SEXTANT_CONFIG', type=click.Path(exists=True),
              default='config.yml')
@click.version_option(metadata.version(__name__.split('.')[0]))
@click.pass_context
def main(ctx, config):
    """Navigate through cosmic events."""
    # store the config as context
    ctx.ensure_object(dict)
    with open(config) as f:
       ctx.obj = yaml.safe_load(f)

@main.command()
def okta():
    """Test Okta authentication with Yubikey."""
    get_credentials()
    click.echo('ok')

@main.command()
@click.option('-t', '--type', is_flag=True)
@click.pass_obj
def obs(config, type):
    """Manage observables."""
    thehive = TheHiveClient(config['thehive'])
    if type:
        table = Table(title='Observable types')
        rows, fields = thehive.types(table=True)
        for field in fields:
            table.add_column(field)
        for row in rows:
            table.add_row(*row)

        console = Console()
        console.print(table)

