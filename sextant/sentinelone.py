import logging
from requests.exceptions import HTTPError
from rich.console import Console
from rich.table import Table
from sextant.plugin import BasePlugin, with_auth

logger = logging.getLogger(__name__)


class S1Plugin(BasePlugin):
    name = 's1'

    def __init__(self, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        super().__init__(*args, **kwargs)
        self.auth_type = 'ApiToken'

    def check(self):
        try:
            r = self.get('/web/api/v2.1/system/status')
            r.raise_for_status()
            return True
        except HTTPError as e:
            logger.error(e)
            return False

    @with_auth
    def blocklist(self, *args, **kwargs):
        """Command: Check blocklists."""
        try:
            r = self.get('/web/api/v2.1/restrictions')
            r.raise_for_status()
            print(r.json())
        except HTTPError as e:
            logger.error(e)

    @with_auth
    def rules(self, **kwargs):
        """
        Command: List rules.

        :param optional --name: contains in name
        """
        try:
            name = kwargs.get('name')
            payload = {'limit': 100}
            if name:
                payload['name__contains'] = name
            r = self.get('/web/api/v2.1/cloud-detection/rules', params=payload)
            r.raise_for_status()
            total = r.json()['pagination']['totalItems']
            table = Table('name', 'alert count')
            for item in r.json()['data']:
                style = 'red' if item['status'].lower() == 'disabled' else 'default'
                table.add_row(item['name'], str(item['generatedAlerts']), style=style)

            console = Console()
            console.print(table)
            console.print(f'total: {total}')
        except HTTPError as e:
            logger.error(e)
