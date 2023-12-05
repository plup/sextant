import logging
from requests.exceptions import HTTPError
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
    def rules(self, *args, **kwargs):
        """Command: List rules."""
        try:
            r = self.get('/web/api/v2.1/cloud-detection/rules')
            r.raise_for_status()
            print(r.json())
        except HTTPError as e:
            logger.error(e)
