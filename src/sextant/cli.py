import click
from sextant.config import Config
from sextant.endpoints.thehive import thehive
from sextant.endpoints.splunk import splunk

@click.group()
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config()

cli.add_command(thehive)
cli.add_command(splunk)
