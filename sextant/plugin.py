import subprocess
from requests import Session
from urllib.parse import urljoin
from getpass import getpass
from .auth.okta import OktaClient, OktaSamlClient


class BasePlugin(Session):
    """The base class to inherit a plugin from."""
    def __init__(self, *args, **kwargs):
        self.base_url = kwargs['endpoint']
        self.headers = {"User-Agent": "sextant"}
        self.auth_params = kwargs.pop('auth')
        super().__init__()

    def request(self, method, url, *args, **kwargs):
        """Adds the endpoint to all requests."""
        complete_url = urljoin(self.base_url, url)
        return super().request(method, complete_url, *args, **kwargs)

    def check(self):
        raise NotImplementedError('Method not implemented')

    def get_auth(self):
        """Get a session authenticator."""
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
