import click
import httpx
from rich.console import Console
from rich.table import Table

@click.group()
@click.pass_obj
def splunk(obj):
    """Get events from Splunk."""
    # instantiate client from config
    config = obj['config'].get_endpoint('splunk')
    obj['client'] = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
            verify = False
        )

@splunk.command()
@click.pass_obj
def indexes(obj):
    """Return a list of accessible indexes"""
    r = obj['client'].get('/services/data/indexes',
                          params={'output_mode': 'json', 'count':0, 'datatype':'all'})
    r.raise_for_status()
    total = r.json()['paging']['total']
    table = Table('indexes', 'datatype', 'counts')
    for item in r.json()['entry']:
        style = 'red' if item['content']['disabled'] else 'default'
        table.add_row(item['name'], item['content']['datatype'],
                      str(item['content']['totalEventCount']),
                      style=style)

    console = Console()
    console.print(table)
    console.print(f'total: {total}')
