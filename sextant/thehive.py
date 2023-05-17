"""Operations with The Hive."""
import requests
from thehive4py.api import TheHiveApi
from thehive4py.models import Case, CaseObservable
from thehive4py.query import *
from functools import wraps, update_wrapper
from thehive4py.exceptions import *
from requests.exceptions import *
from urllib3.exceptions import InsecureRequestWarning
from sextant.plugin import Plugin


requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class TheHiveClient(TheHiveApi):
    """Extends The Hive API and adds client methods."""
    def raise_errors(f):
        """
        Wraps the method forcing error status code to raise exceptions.
        Also decodes the response from json and handle the mixed status codes.
        """
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try:
                r = f(self, *args, **kwargs)
                r.raise_for_status()
                results = r.json()

                # handle mixed status code
                if r.status_code == 207:
                    try:
                        error = results.get('failure')[0]
                        message = f"{error['message']} ({error['type']})"
                    except KeyError:
                        message = 'Unexcepted error happened. Check logs.'
                    raise TheHiveException(message)

                return results

            # hanlde default API errors
            except HTTPError as e:
                message = e.response.json().get('message')
                if e.response.status_code == 404:
                    message = f'Resource {message} not found'
                raise TheHiveException(message)

        return wrapper

    @raise_errors
    def create_alert(self, *args, **kwargs):
        return super().create_alert(*args, **kwargs)

    @raise_errors
    def get_alert(self, *args, **kwargs):
        return super().get_alert(*args, **kwargs)

    @raise_errors
    def find_cases(self, *args, **kwargs):
        return super().find_cases(*args, **kwargs)

    @raise_errors
    def find_observables(self, *args, **kwargs):
        return super().find_observables(*args, **kwargs)

    @raise_errors
    def get_case_observable(self, *args, **kwargs):
        return super().get_case_observable(*args, **kwargs)

    @raise_errors
    def create_case_observable(self, *args, **kwargs):
        """Adds an observable to an existing case."""
        return super().create_case_observable(*args, **kwargs)

    @raise_errors
    def get_custom_fields(self):
        """Returns a list of existing custom fields."""
        req = f'{self.url}/api/customField'
        return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)

    @raise_errors
    def get_observable_types(self):
        """Returns a list of existing observable types."""
        req = f'{self.url}/api/observable/type?range=all'
        return requests.get(req, proxies=self.proxies, auth=self.auth, verify=self.cert)


class ThehivePlugin(Plugin):
    name = 'thehive'
    def __init__(self, *args, **kwargs):
        self.client = TheHiveApi(
                kwargs['endpoint'],
                kwargs['auth']['apikey'],
                version = 5,
                cert = False
            )

    def check(self, verbose=False):
        try:
            self.client.health().text
            return True
        except TheHiveException as e:
            return False
