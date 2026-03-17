import click
from importlib import import_module
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from sextant import SextantError, SextantConfigurationError
from sextant.config import SextantConfig

def entrypoint():
    """Controller registering commands from config."""
    try:
        config = SextantConfig()

        @click.group()
        @click.pass_context
        def cli(ctx):
            """Sextant."""
            ctx.ensure_object(dict)
            ctx.obj['config'] = config

        @cli.command()
        def check():
            """Test authentication against all endpoints."""
            table = Table('endpoint', 'client', 'status', 'info')

            for endpoint in config.endpoints:
                name = endpoint['name']
                client_type = endpoint['client']
                try:
                    module = import_module(f"sextant.clients.{client_type}")
                    ep_config = config.reveal(name)
                    client = module.Client.from_config(ep_config)
                    try:
                        info = client.check()
                        table.add_row(name, client_type, '[green]ok[/green]', info)
                    finally:
                        client.http.close()
                except ModuleNotFoundError:
                    table.add_row(name, client_type, '[yellow]skip[/yellow]', 'client not found')
                except Exception as e:
                    table.add_row(name, client_type, '[red]error[/red]', str(e))

            Console().print(table)

        for endpoint in config.endpoints:
            try:
                module = import_module(f"sextant.clients.{endpoint['client']}")
                cli.add_command(module.main, endpoint['name'])
            except ModuleNotFoundError:
                rprint(f"[red]No client found for {endpoint['client']}")

        cli()

    except SextantError as e:
        rprint(f"[red]{e}[/red]")
