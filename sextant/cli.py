"""Contains the CLI commands."""
import confuse
import sys
import logging
from argparse import ArgumentParser
from importlib import metadata

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
                logging.getLogger().setLevel(logging.ERROR)
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
            from sextant.splunk import SplunkPlugin
            # add a subparser for the plugin
            plugin_parser = subparsers.add_parser(SplunkPlugin.name, help='Splunk')
            plugin_subparsers = plugin_parser.add_subparsers(help='Splunk module help')
            plugins.append(SplunkPlugin(plugin_subparsers, **conf['splunk']))
        except KeyError as e:
            print(f'No config for {e}')
        except Exception as e:
            print(f'Error when registering: {e}')

        try:
            from sextant.thehive import ThehivePlugin
            plugin_parser = subparsers.add_parser(ThehivePlugin.name, help='TheHive')
            plugin_subparsers = plugin_parser.add_subparsers(title=ThehivePlugin.name)
            plugins.append(ThehivePlugin(plugin_subparsers, **conf['thehive']))
        except KeyError as e:
            print(f'No config for {e}')
        except Exception as e:
            print(f'Error when registering: {e}')

        try:
            from sextant.sentinelone import Plugin
            plugin_parser = subparsers.add_parser(Plugin.name, help='SentinelOne')
            plugin_subparsers = plugin_parser.add_subparsers(title=Plugin.name)
            plugins.append(Plugin(plugin_subparsers, **conf['sentinelone']))
        except KeyError as e:
            print(f'No config for {e}')
        except Exception as e:
            print(f'Error when registering: {e}')

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
