"""Contains the CLI commands."""

import click
from importlib import metadata

# click entrypoint
@click.group()
@click.version_option(metadata.version(__name__.split('.')[0]))
@click.pass_context
def main(ctx):
    """Search in events."""
    # init context
    pass


@main.command()
def hello():
    """Say hello to the world."""
    click.echo('ok')
