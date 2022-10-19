"""Operations with Splunk."""
import requests

class SplunkClient(object):
    """Call Splunk through the REST API."""
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def check_tokens(self):
        r = requests.get(f'{self.endpoint}/services/admin/token-auth/tokens_auth')
        print(r)
