"""Contains the CLI commands."""

import click
import confuse
from functools import update_wrapper
from importlib import metadata
from rich import print
from rich.table import Table
from rich.console import Console
from thehive4py.query import Eq, And
from thehive4py.exceptions import TheHiveException
from splunklib import client
from .auth.okta import get_credentials
from .thehive import TheHiveClient


def format(results, fields, title):
    """Turns list of objects in a table."""
    # filter output
    rows = []
    for result in results:
        # force returning name for files
        if result.get('dataType') == 'file':
            result['data'] = result['attachment']['name']
        rows.append([str(result[k]) for k in fields])

    # build the table
    table = Table(title=title)
    for field in fields:
        table.add_column(field)
    for row in rows:
        table.add_row(*row)

    return table

def handle_errors(f):
    @click.pass_context
    def run(ctx, *args, **kwargs):
        try:
            return ctx.invoke(f, *args, **kwargs)
        except TheHiveException as e:
            print(f'[bold red]{e}[/bold red]')
    return update_wrapper(run, f)


# click entrypoint
@click.group()
@click.option('-c', '--config', envvar='SEXTANT_CONFIG', type=click.Path(exists=True),
              default='config.yml')
@click.version_option(metadata.version(__name__.split('.')[0]))
@click.pass_context
def main(ctx, config):
    """Navigate through cosmic events."""
    # load the configuration object
    ctx.obj = confuse.Configuration('sextant')
    if config:
        ctx.obj.set_file(config)


# okta commands
@main.command()
@click.pass_obj
def okta(conf):
    """Test Okta authentication with Yubikey."""
    get_credentials(
        endpoint = conf['okta']['endpoint'].get(),
        app_link = conf['okta']['app_link'].get(),
        login = conf['okta']['login'].get()
    )
    click.echo('ok')


# alert commands
@main.group()
def search():
    """Manage alerts."""

@search.command
@click.pass_obj
def list(conf):
    s = client.connect(username=conf['splunk']['login'].get(),
                       password=conf['splunk']['password'].get())
    print(s.indexes.get_default())


# observable commands
@main.group()
@click.pass_context
def obs(ctx):
    """Manage observables."""
    # pass the hive client as context object for subcommands
    conf = ctx.obj['thehive']
    ctx.obj = TheHiveClient(conf['endpoint'].get(), conf['apikey'].get(), version=4, cert=False)

@obs.command()
@click.pass_obj
@handle_errors
def types(thehive):
    """Display all observable types."""
    fields = ['name', 'isAttachment', 'createdBy']
    results = thehive.get_observable_types()
    table = format(results, fields, 'Observable types')
    print(table)
    print(f'objects: {len(results)}')

@obs.command()
@click.option('--ioc', is_flag=True)
@click.option('--sighted', is_flag=True)
@click.option('-t', '--type')
@click.pass_obj
@handle_errors
def search(thehive, ioc, sighted, type):
    """Search across observables."""
    fields = ['id', 'dataType', 'ioc', 'sighted', 'tlp', 'data']
    params = []

    if ioc:
        params.append(Eq('ioc', True))

    if sighted:
        params.append(Eq('sighted', True))

    if type:
        params.append(Eq('dataType', type))

    results = thehive.find_observables(query=And(*params))
    table = format(results, fields, 'Observables')
    print(table)
    print(f'objects: {len(results)}')

@obs.command()
@click.argument('id', type=int)
@click.pass_obj
@handle_errors
def get(thehive, id):
    observable = thehive.get_case_observable(f'~{id}')
    print(observable)

