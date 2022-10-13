"""Operations with The Hive."""
import requests
from thehive4py.api import TheHiveApi
from thehive4py.query import Eq, And


class TheHiveApiExt(TheHiveApi):
    """Extends The Hive API."""
    def get_fields(self):
        """Returns a list of existing custom fields."""
        req = f'{self.url}/api/customField'
        try:
            return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)
        except requests.exceptions.RequestException as e:
            raise CustomFieldException("Can't retreive custom fields")

    def get_observable_types(self):
        """Returns a list of existing observable types."""
        req = f'{self.url}/api/observable/type?range=all'
        try:
            return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)
        except requests.exceptions.RequestException as e:
            raise CustomFieldException("Can't retreive observable types")


class TheHiveClient(object):
    """Making the request to The Hive backend."""
    def __init__(self, config):
        self.client = TheHiveApiExt(config['endpoint'], config['apikey'], cert=False)

    def types(self, table=False):
        """Get all observables grouped by type."""
        resp = self.client.get_observable_types()
        if resp.status_code != 200:
            raise Exception('error')

        results = resp.json()

        if table:
            # filter fields
            fields = ['name', 'isAttachment', 'createdBy']
            rows = []
            for result in results:
                rows.append([str(result[k]) for k in fields])
            return (rows, fields)

        return results
