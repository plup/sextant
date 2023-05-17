"""Contains the CLI commands."""
import argparse
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


def load(context=None):

    version = metadata.version(__name__.split('.')[0])
    config = confuse.Configuration('sextant')

    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                    description='Find your way through celestial events.')
    parser.add_argument('--version', action='version', version=f'%(prog)s v{version}')
    parser.add_argument('--status', action='store_true', help='Check submodules connectivity')

    module_parsers = parser.add_subparsers(dest='module', help='Modules')

    # select context
    if context:
        conf = config['contexts'][context].get()
    else:
        conf = next(iter(config['contexts'].values())).get()

    # register plugins
    plugins = []
    try:
        from .splunk import SplunkPlugin
        plugins.append(SplunkPlugin(module_parsers, **conf['splunk']))

        from .thehive import ThehivePlugin
        plugins.append(ThehivePlugin(module_parsers, **conf['thehive']))

    except KeyError as e:
        print(f'Error when registering Splunk: {e} not found')

    # parsing arguments
    args = parser.parse_args()

    if args.module and args.func:
        return args.func(args)

    if args.status:
        return status(plugins)


def status(plugins):
    """Check states of all registered components."""
    for plugin in plugins:
        print(plugin.name, plugin.check())

# alert commands
@click.group()
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
@click.group()
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
@click.group()
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


