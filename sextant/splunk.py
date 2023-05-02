import requests
from sextant.plugin import PluginCore
from splunklib import client
from getpass import getpass
from .auth.okta import OktaClient, OktaSamlClient


class SplunkPlugin(PluginCore):

    def __init__(self, *args, **kwargs):
        self.endpoint = kwargs.get('endpoint')
        # manage auth
        auth_config = kwargs['auth']
        if auth_config['type'] == 'okta':
            self.okta = OktaSamlClient(
                    username = auth_config['login'],
                    password = getpass(f'Password for {auth_config["login"]}: '),
                    endpoint = auth_config['endpoint'],
                    app_name = auth_config['app_name'],
                    app_id = auth_config['app_id'],
            )

    def check(self):
        saml_assertion = self.okta.auth()
        r = requests.get(f'{self.endpoint}:8089/services/apps/local')
        print(r)
        return True

    def indexes(self):
        return self.service.indexes.get_default()
