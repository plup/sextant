"""Operations with The Hive."""
import requests
from thehive4py.api import TheHiveApi
from thehive4py.query import *
from functools import wraps, update_wrapper
from thehive4py.exceptions import *
from requests.exceptions import *
from urllib3.exceptions import InsecureRequestWarning


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class TheHiveClient(TheHiveApi):
    """Extends The Hive API and adds client methods."""
    def raise_for_status(f):
        """
        Wraps the method forcing error status code to raise exceptions.
        Also decodes the response from json.
        """
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try:
                r = f(self, *args, **kwargs)
                r.raise_for_status()
                return r.json()
            except HTTPError as e:
                message = e.response.json().get('message')
                if e.response.status_code == 404:
                    message = f'Resource {message} not found'
                raise ObservableException(message)
        return wrapper

    @raise_for_status
    def get_case_observable(self, *args, **kwargs):
        return super().get_case_observable(*args, **kwargs)

    @raise_for_status
    def find_observables(self, *args, **kwargs):
        return super().find_observables(*args, **kwargs)

    @raise_for_status
    def get_custom_fields(self):
        """Returns a list of existing custom fields."""
        req = f'{self.url}/api/customField'
        return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)

    @raise_for_status
    def get_observable_types(self):
        """Returns a list of existing observable types."""
        req = f'{self.url}/api/observable/type?range=all'
        return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)

    def get_custom_tags(self):
        """Returns a list of existing custom tags."""

        req = f'{self.url}/api/v1/query?name=organisation-custom-tags'
        #params = {
        #    "range": attributes.get("range", "all"),
        #    "sort": attributes.get("sort", [])
        #}
        filters = {
  "_name": "filter",
  "_like": {
    "_field": "text",
    "_value": "field*"
  }
}
        query = Like('text', 'field*')
        print(query)
        return
        return self.__find_rows("/api/alert/_search", **attributes)

        payload = {}
        return request.post(req, proxies=self.proxies, auth=self.auth, verify=self.cert, data=payload)
