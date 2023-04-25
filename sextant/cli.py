"""Contains the CLI commands."""

import click
import confuse
import sys
import uuid
from functools import update_wrapper
from importlib import metadata
from pathlib import Path
from csv import DictWriter
from rich import print
from rich.table import Table
from rich.console import Console
from thehive4py.query import Eq, And
from thehive4py.models import Alert, Case, CaseObservable
from thehive4py.exceptions import TheHiveException


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

# click entrypoint
@click.group()
@click.option('--config', envvar='SEXTANT_CONFIG', type=click.Path(exists=True))
@click.option('-c', '--context', help='Context to use from the config')
@click.version_option(metadata.version(__name__.split('.')[0]))
@click.pass_context
def main(ctx, config, context):
    """Find your way through cosmic events."""
    # load the configuration object
    config_obj = confuse.Configuration('sextant')
    if config:
        config_obj.set_file(config)

    # extend defaults with selected context
    conf = config_obj['contexts']['default'].get()
    if context:
        conf.update(config_obj['contexts'][context].get())

    # register plugins
    plugins = {}
    try:
        from .thehive import TheHivePlugin
        plugins['thehive'] = TheHivePlugin(**conf['thehive'])
    except KeyError as e:
        print(f'TheHive: error when registering: {e} not found')

    try:
        from .splunk import SplunkPlugin
        plugins['splunk'] = SplunkPlugin(**conf['splunk'])
    except KeyError as e:
        print(f'Error when registering Splunk: {e}')

    ctx.obj = plugins

# config
@main.command()
@click.pass_obj
def config(config):
    """Display current configuration."""
    print(config)

# status
@main.command()
@click.pass_obj
def status(plugins):
    """Check states of all registered components."""
    for name, plugin in plugins.items():
        print(plugin.check())

# alert commands
@main.group()
@click.pass_context
def alert(ctx):
    """Manage cases."""
    conf = ctx.obj['thehive']
    ctx.obj = TheHiveClient(conf['endpoint'].get(), conf['apikey'].get(), version=4, cert=False)

@alert.command
@click.argument('id', type=int)
@click.pass_obj
def get(thehive, id):
    alert = thehive.get_alert(f'~{id}')
    print(alert)

@alert.command
@click.option('--title')
@click.option('--description', default='N/A')
@click.option('--tags', help='List of tags, ex: good,luck')
@click.pass_obj
def create(thehive, title, description, tags):
    alert = Alert(
        type = 'external',
        source = 'sextant',
        sourceRef = str(uuid.uuid4())[0:6],
        title = title,
        description = description,
        tags = tags.split(','),
    )
    alert = thehive.create_alert(alert)
    print(alert)

@alert.command
@click.argument('id', type=int)
@click.option('--field', help='One field to update, ex: title=Alert')
@click.option('--tags', help='List of tags, ex: good,luck')
@click.pass_obj
def update(thehive, id, field, tags):
    # FIXME: pass a dynamic list of options --title "new title" --tags good,luck
    try:
        fields = []
        alert = thehive.get_alert(f'~{id}')
        if field:
            key, value = field.split('=')
            alert[key] = value
        if tags:
            fields.append('tags')
            alert['tags'] = tags.split(',')
        alert = thehive.update_alert(alert=Alert(json=alert), alert_id=f'~{id}', fields=fields)
        print(alert)
    except ValueError:
        print('Wrong format for parameters')

# case commands
@main.group()
@click.pass_context
def case(ctx):
    """Manage cases."""
    conf = ctx.obj['thehive']
    ctx.obj = TheHiveClient(conf['endpoint'].get(), conf['apikey'].get(), version=4, cert=False)

@case.command
@click.option('--csv', is_flag=True)
@click.pass_obj
def list(thehive, csv):
    """Display all summaries."""
    params = []
    results = thehive.find_cases(query=And(*params))
    fields = [
        'flag',
        'startDate',
        'endDate',
        'title',
        'description',
        'createdAt',
        'createdBy',
        'caseId',
        'id',
        'pap',
        'tlp',
        'status',
        'summary',
        'tags',
    ]

    if csv:
        writer = DictWriter(sys.stdout, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)
        return

    print(results)

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
@click.option('--csv', is_flag=True)
@click.pass_obj
def search(thehive, ioc, sighted, type, csv):
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

    if csv:
        print(results)
        return

    table = format(results, fields, 'Observables')
    print(table)
    print(f'objects: {len(results)}')

@obs.command()
@click.argument('id', type=int)
@click.pass_obj
def get(thehive, id):
    """Retrieve details about an observable."""
    observable = thehive.get_case_observable(f'~{id}')
    print(observable)

@obs.command()
@click.argument('id')
@click.argument('content')
@click.option('-t', '--type', help='Type of the observable')
@click.option('--ioc', is_flag=True)
@click.option('--sighted', is_flag=True)
@click.option('-n', '--notes', help='Notes about the observable')
@click.pass_obj
def add(thehive, id, content, type, ioc, sighted, notes):
    """Attach an observable to a case."""
    if type == 'file':
        path = Path(content)
        if not path.is_file():
            raise Exception('File does not exist')
        content = str(path)

    observable = CaseObservable(dataType=type, data=content, ioc=ioc, sighted=sighted, message=notes, tlp=2, ignoreSimiliarity=True)
    results = thehive.create_case_observable(f'~{id}', observable)
    print(results)


