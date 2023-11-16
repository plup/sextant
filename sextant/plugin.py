import subprocess
import inspect
import argparse
from requests import Session
from urllib.parse import urljoin
from getpass import getpass
from functools import wraps
from docstring_parser import parse as docparse
from .auth.okta import OktaClient, OktaSamlClient

def with_auth(f):
    """Set the proper header for the authentication."""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.headers.get('Authorization'):
            self.headers['Authorization'] = f'{self.auth_type} {self.get_token()}'
        return f(self, *args, **kwargs)
    return wrapper


class BasePlugin(Session):
    """The base class to inherit a plugin from."""
    def __init__(self, *args, **kwargs):
        self.make_args(args[0])
        self.base_url = kwargs.pop('endpoint')
        self.auth_params = kwargs.pop('auth')
        self.auth_type = 'Bearer'
        super().__init__()
        self.headers["User-Agent"] = "sextant"

    def request(self, method, url, *args, **kwargs):
        """Adds the endpoint to all requests."""
        complete_url = urljoin(self.base_url, url)
        return super().request(method, complete_url, *args, **kwargs)

    def make_args(self, subparsers):
        """Use methods docstring to make CLI arguments."""
        # search for Commands
        for name, obj in inspect.getmembers(self, inspect.ismethod):
            doc = inspect.getdoc(obj)
            if doc and doc.lower().startswith('command:'):
                # build the arg parser from docstring
                docstring = docparse(inspect.getdoc(obj))
                title = docstring.short_description[8:]
                parser = subparsers.add_parser(name, help=title)
                for param in docstring.params:
                    if param.type_name == 'remain':
                        parser.add_argument(param.arg_name, nargs=argparse.REMAINDER, help=param.description)
                    else:
                        parser.add_argument(param.arg_name, help=param.description)
                parser.set_defaults(func=obj)

       # parser = subparsers.add_parser('query', help='Search command')
       # parser.add_argument('query', nargs=argparse.REMAINDER, help='query to run (ex: "search index=notable earliest=-60m")')
       # parser.set_defaults(func=self.query)

    def check(self):
        raise NotImplementedError('Method not implemented')

    def get_token(self):
        """Fetch a token from the provider and set the session auth."""
        params = self.auth_params
        if params['type'] == 'okta':
            okta = OktaSamlClient(
                endpoint = params['endpoint'],
                app_name = params['app_name'],
                app_id = params['app_id'],
                username = params['login'],
                password = getpass(f'Password for {params["login"]}: '),
            )
            return okta

        elif params['type'] == '1password':
            try:
                cmd = f'op item get {params["item"]} --fields=credential'
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
                token = result.stdout.decode().strip()
                return token

            except subprocess.CalledProcessError as e:
                raise RuntimeError(e.stderr.decode())

        else:
            raise NotImplementedError('Authentication type not supported')
