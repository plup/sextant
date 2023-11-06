import subprocess
from requests import Session
from urllib.parse import urljoin
from .auth.okta import OktaClient, OktaSamlClient

class Plugin(Session):
    """The base class to inherit a plugin from."""
    def __init__(self, *args, **kwargs):
        self.base_url = kwargs['endpoint']
        self.headers = {"User-Agent": "sextant"}
        self.auth(kwargs.pop('auth'))
        super().__init__()

    def request(self, method, url, *args, **kwargs):
        """Adds the endpoint to all requests."""
        complete_url = urljoin(self.base_url, url)
        return super().request(method, complete_url, *args, **kwargs)

    def check(self):
        raise NotImplementedError('Method not implemented')

    def auth(self, params):
        """Manage authentication."""
        if params['type'] == 'okta':
            okta = OktaSamlClient(
                    endpoint = params['endpoint'],
                    app_name = params['app_name'],
                    app_id = params['app_id'],
                    username = params['login'],
                    password = getpass(f'Password for {auth_config["login"]}: '),
            )

        elif params['type'] == '1password':
            try:
                cmd = f'op item get {params["item"]} --fields=credential,type'
                result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
                token, _type = result.stdout.decode().split(',')
                self.headers['Authorization'] = f'Bearer {token}'

            except subprocess.CalledProcessError as e:
                raise RuntimeError(e.stderr.decode())
        else:
            raise NotImplementedError('Authentication type not supported')
