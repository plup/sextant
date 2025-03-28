import click
from sextant.config import Config
from sextant.endpoints.thehive import thehive

@click.group()
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config().reveal()

cli.add_command(thehive)
