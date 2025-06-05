import click
from importlib import import_module
from rich import print as rprint
from sextant import SextantError, SextantConfigurationError
from sextant.config import SextantConfig

def entrypoint():
    """Controller registering commands from config."""
    try:
        # read configuration
        config = SextantConfig()

        # create a click group
        @click.group()
        @click.pass_context
        def cli(ctx):
            """Sextant."""
            ctx.ensure_object(dict)
            ctx.obj['config'] = config # expose config

        # dynamically register modules
        for endpoint in config.endpoints:
            try:
                # import the client
                module = import_module(f"sextant.clients.{endpoint['client']}")
                cli.add_command(module.main, endpoint['name'])

            except ModuleNotFoundError:
                rprint(f"[red]No client found for {endpoint['client']}")

        # invoke command
        cli()

    except SextantError as e:
        rprint(f"[red]{e}[red]")
