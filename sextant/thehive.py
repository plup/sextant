"""Operations with The Hive."""
import requests
import json
from rich import print
from rich.table import Table
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
                if r.status_code == 204:
                    return None

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
                try:
                    message = e.response.json().get('message')
                    if e.response.status_code == 404:
                        message = f'Resource {message} not found'
                    raise TheHiveException(message)
                except JSONDecodeError:
                    raise TheHiveException(e)

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
    def send_query(self, query):
        """Return the results of the query."""
        return requests.post(f'{self.url}/api/v1/query', auth=self.auth, verify=self.cert, json=query)

    @raise_errors
    def update_case(self, id_, data):
        """Update the case with new data."""
        return requests.patch(f'{self.url}/api/v1/case/{id_}', auth=self.auth, verify=self.cert, json=data)

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

    @raise_errors
    def get_dashboards(self):
        """Returns the list of dashboards."""
        req = f'{self.url}/api/v1/query?name=get-all-dashboards'
        return requests.post(req, auth=self.auth, verify=self.cert, json={'query': [{'_name': 'listDashboard'}]})

    @raise_errors
    def delete_dashboard(self, id_):
        return requests.delete(f'{self.url}/api/v1/dashboard/{id_}', auth=self.auth, verify=self.cert)


class ThehivePlugin(Plugin):
    name = 'thehive'

    def __init__(self, subparsers, *args, **kwargs):
        """Attach a new parser to the subparsers of the main module."""
        # register query commands
        query_parser = subparsers.add_parser('query', help='Query command')
        query_parser.add_argument('query', type=str, help='Query as JSON string')
        query_parser.set_defaults(func=self.query)

        debug_parser = subparsers.add_parser('fix-customfields', help='Specific update code')
        debug_parser.set_defaults(func=self.fix_customfields)

        # register observable commands
        obs_parser = subparsers.add_parser('observables', aliases=['obs'], help='Observables command')
        obs_subparsers = obs_parser.add_subparsers(title='observables', description='Manage observables')

        search_parser = obs_subparsers.add_parser('search', help='Search in observables')
        search_parser.add_argument('--type', nargs='?', help='Return only observables with this type')
        search_parser.add_argument('--ioc', action='store_true', help='Return only IOCs')
        search_parser.add_argument('--sighted', action='store_true', help='Return only sighted IOCs')
        search_parser.set_defaults(func=self.search_observable)

        get_parser = obs_subparsers.add_parser('get', help='Display the observable')
        get_parser.add_argument('id', type=str, help='Observable ~id')
        get_parser.set_defaults(func=self.get_observable)

        add_parser = obs_subparsers.add_parser('add', help='Add an observable to an alert')
        add_parser.add_argument('id', type=str, help='Case ~id')
        add_parser.add_argument('content', type=str, help='Observable content')
        add_parser.add_argument('--type', nargs='?', help='Return only observables with this type')
        add_parser.add_argument('--ioc', action='store_true', help='Return only IOCs')
        add_parser.add_argument('--sighted', action='store_true', help='Return only sighted IOCs')
        add_parser.add_argument('--notes', nargs='?', help='Notes')
        add_parser.set_defaults(func=self.add_observable)

        types_parser = obs_subparsers.add_parser('types', help='List accepted observable types')
        types_parser.set_defaults(func=self.list_observable_types)

        # register dashboard commands
        dash_parser = subparsers.add_parser('dashboards', aliases=['dash'], help='Dashboard command')
        dash_subparsers = dash_parser.add_subparsers(title='observables', description='Manage dashboards')

        get_parser = dash_subparsers.add_parser('get', help='Retreive dashboards')
        get_parser.set_defaults(func=self.list_dashboard)

        del_parser = dash_subparsers.add_parser('rm', help='Delete dashboards')
        del_parser.add_argument('id', type=str, help='Dashboard ~id')
        del_parser.set_defaults(func=self.delete_dashboard)

        # set authentication
        if kwargs['auth']['type'] == 'apikey':
            self.client = TheHiveClient(
                    kwargs['endpoint'],
                    kwargs['auth']['token'],
                    version = 5,
                    cert = False
                )
        else:
            raise NotImplementedError('Unsupported authentication protocol')

    def check(self, verbose=False):
        try:
            self.client.health().text
            return True
        except TheHiveException as e:
            return False

    def query(self, *args, **kwargs):
        """Run queries and display results."""
        query = {'query': json.loads(kwargs['query'])}
        results = self.client.send_query(query)
        self.display(results)

    def list_observable_types(self, *args, **kwargs):
        """Display all observable types."""
        results = self.client.get_observable_types()
        self.display(results, ['name', 'isAttachment', 'createdBy'])

    def search_observable(self, *args, **kwargs):
        """Search across observables."""
        params = []
        if kwargs.get('ioc'):
            params.append(Eq('ioc', True))
        if kwargs.get('sigthed'):
            params.append(Eq('sighted', True))
        type_ = kwargs.get('type')
        if type_:
            params.append(Eq('dataType', type_))

        results = self.client.find_observables(query=And(*params))
        self.display(results, ['id', 'dataType', 'ioc', 'sighted', 'tlp', 'data'])

    def get_observable(self, *args, **kwargs):
        observable = self.client.get_case_observable(kwargs['id'])
        self.display(observable)

    def add_observable(self, *args, **kwargs):
        """Attach an observable to a case."""
        content = kwargs['content']
        if kwargs['type'] == 'file':
            path = Path(content)
            if not path.is_file():
                raise Exception('File does not exist')
            content = str(path)

        observable = CaseObservable(
                dataType = kwargs['type'],
                data = content,
                ioc = kwargs['ioc'],
                sighted = kwargs['sighted'],
                message = kwargs['notes'],
            )
        results = self.client.create_case_observable(kwargs['id'], observable)
        print(results)

    def list_dashboard(self, *args, **kwargs):
        """List exisitng dashboards."""
        dashboards = self.client.get_dashboards()
        self.display(
                dashboards,
                ['_id', 'title', 'owner', 'status', 'version', 'description'],
            )

    def delete_dashboard(self, *args, **kwargs):
        """Delete dashboard."""
        self.client.delete_dashboard(kwargs['id'])

    def display(self, results, fields=[]):
        """Render the results."""
        if not isinstance(results, list) or not fields:
            print(results)
            return

        # filter output
        rows = []
        for result in results:
            # force returning name for files
            if result.get('dataType') == 'file':
                result['data'] = result['attachment']['name']
            rows.append([str(result[k]) for k in fields])

        # build the table
        table = Table()
        for field in fields:
            table.add_column(field)
        for row in rows:
            table.add_row(*row)

        print(table)
        print(f'objects: {len(results)}')

    def fix_customfields(self, *args, **kwargs):
        dry = kwargs.get('dry', False)
        # fecth existing custom fields
        fields = self.client.send_query(query={'query':[{"_name":"listCustomField"},{"_name":"filter","_eq":{"_field":"name","_value":"investigation-category"}}]})
        options = fields[0]['options']
        cases = self.client.send_query(query={'query':[{"_name":"listCase"}]})
        for case in cases:
            for field in case['customFields']:
                if field['name'] == 'investigation-category':
                    if field['value'] == 'Suspicious user activity':
                        field['value'] = 'Suspicious user account activity'
                        self.client.update_case(case['_id'], {'customFields': case['customFields']})
                    if field['value'] not in options:
                        print(case['_id'], field['value'])
                    # detect all cases with multiple values
