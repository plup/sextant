"""Contains the CLI commands."""
import confuse
import sys
import logging
import importlib
from importlib import metadata
from argparse import ArgumentParser

logging.basicConfig()
logger = logging.getLogger('sextant')

def register_plugins(subparsers, config):
    """Import all plugins available in the plugins module."""
    plugins = {}
    for plugin_name in config.keys():
        try:
            # make the import
            module = importlib.import_module(f'sextant.plugins.{plugin_name}')
            instance = getattr(module, 'Plugin')
            # add a subparser for the plugin
            plugin_parser = subparsers.add_parser(plugin_name, help=plugin_name)
            plugin_subparsers = plugin_parser.add_subparsers(help=f'{plugin_name} module help')
            # initiate the plugin
            plugin = instance(plugin_subparsers, **config[plugin_name])
            plugins[plugin_name] = plugin

        except ModuleNotFoundError:
            logger.info(f'Plugin {plugin_name} not found. Configuration ignored.')

        except AttributeError as e:
            logger.info(f'{e}. Configuration ignored.')

    return plugins

def load():

    try:
        version = metadata.version(__name__.split('.')[0])
        config = confuse.Configuration('sextant')

        # main parser
        parser = ArgumentParser(description='Navigate through events.', add_help=False)
        parser.add_argument('-c', '--context', type=str, help='Active context')
        parser.add_argument('-v', '--verbose', action='count', default=0, help='Logging level')
        parser.add_argument('--version', action='version', version=f'%(prog)s v{version}')
        parser.add_argument('--status', action='store_true', help='Check submodules connectivity')

        # parse global arguments
        args,_ = parser.parse_known_args()

        # handle verbosity
        if args.verbose == 0:
            logger.setLevel(logging.ERROR)
        if args.verbose == 1:
            logger.setLevel(logging.WARNING)
        if args.verbose == 2:
            logger.setLevel(logging.INFO)
        if args.verbose >= 3:
            logger.setLevel(logging.DEBUG)

        # select context
        if args.context:
            plugin_conf = config['contexts'][args.context].get()
        else:
            plugin_conf = next(iter(config['contexts'].values())).get()

        # restore help and set submodules for plugin argument parsing
        parser.add_argument('-h', '--help', action='help')
        subparsers = parser.add_subparsers(dest='modules', help='Modules')

        # register plugins passing the subparser and the context config
        plugins = register_plugins(subparsers, plugin_conf)

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
    for name, plugin in plugins.items():
        print(name, plugin.check())
