from sextant.plugin import PluginCore
from splunklib import client
from .auth.okta import get_credentials

class SplunkPlugin(PluginCore):

    def __init__(self, *args, **kwargs):
        auth_config = kwargs['auth']
        if auth_config['type'] == 'okta':
            get_credentials(
                endpoint = auth_config['endpoint'],
                app_link = auth_config['app_link'],
                login = auth_config['login'],
            )
        #self.service = client.connect()

    def check(self):
        return True

    def indexes(self):
        return self.service.indexes.get_default()
