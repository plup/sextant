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

    def format(self, results, filter_fields):
        """Returns a filtered list of objects ready for displaying."""
        # filter fields
        fields = ['id', 'dataType', 'sighted', 'tlp', 'data']
        rows = []
        for result in results:
            rows.append([str(result[k]) for k in fields])
        return (rows, fields)

    def types(self):
        """Get all observables types available."""
        resp = self.client.get_observable_types()
        if resp.status_code != 200:
            raise Exception('error')
        return resp.json()

    def iocs(self):
        """Get all IOCs."""
        query = Eq('ioc', True)
        resp = self.client.find_observables(query=query, sort=[], range='all')
        if resp.status_code != 200:
            # manage bad request
            raise Exception('error')
        return resp.json()
