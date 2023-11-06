"""Contains the CLI commands."""
import click
import confuse
import sys
import uuid
import logging
from argparse import ArgumentParser
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


def load():

    try:
        version = metadata.version(__name__.split('.')[0])
        config = confuse.Configuration('sextant')

        # main parser
        parser = ArgumentParser(description='Find your way through celestial events.', add_help=False)
        parser.add_argument('--version', action='version', version=f'%(prog)s v{version}')
        parser.add_argument('-c', '--context', type=str, help='Active context')
        parser.add_argument('-v', '--verbose', action='count', default=0, help='Logging level')
        parser.add_argument('--status', action='store_true', help='Check submodules connectivity')

        # parse global arguments
        args,_ = parser.parse_known_args()

        # handle verbosity
        try:
            logging.basicConfig()
            if args.verbose == 0:
                logging.getLogger().setLevel(logging.CRITICAL)
            if args.verbose == 1:
                logging.getLogger().setLevel(logging.WARNING)
            if args.verbose == 2:
                logging.getLogger().setLevel(logging.INFO)
            if args.verbose >= 3:
                logging.getLogger().setLevel(logging.DEBUG)
        except:
            logging.getLogger(__name__).critical('Logging not setup properly')

        # select context
        if args.context:
            conf = config['contexts'][args.context].get()
        else:
            conf = next(iter(config['contexts'].values())).get()

        # restore help and set submodules for plugin argument parsing
        parser.add_argument('-h', '--help', action='help')
        subparsers = parser.add_subparsers(dest='modules', help='Modules')

        # register plugins
        plugins = []
        try:
            from .splunk import SplunkPlugin
            # add a subparser for the plugin
            plugin_parser = subparsers.add_parser(SplunkPlugin.name, help='Splunk')
            plugin_subparsers = plugin_parser.add_subparsers(help='Splunk module help')
            plugins.append(SplunkPlugin(plugin_subparsers, **conf['splunk']))

            from .thehive import ThehivePlugin
            plugin_parser = subparsers.add_parser(ThehivePlugin.name, help='TheHive')
            plugin_subparsers = plugin_parser.add_subparsers(title=ThehivePlugin.name)
            plugins.append(ThehivePlugin(plugin_subparsers, **conf['thehive']))

        except KeyError as e:
            raise RuntimeError(f'Error when registering: {e} not found')

        # parsing arguments and running code
        args = parser.parse_args()

        if args.status:
            return status(plugins)

        if args.modules:
            try:
                kwargs = args.__dict__
                func = kwargs.pop('func')
                func(**kwargs)
            except KeyError as e:
                parser.print_help()

    except RuntimeError as e:
        print(e)

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
