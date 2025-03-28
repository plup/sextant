import logging
import requests
import base64
from .webauthn import WebAuthnClient
from fido2.server import Fido2Server
from bs4 import BeautifulSoup as Soup

logger = logging.getLogger(__name__)


class OktaClient(object):
    """Client for Okta authentication supporting WebAuthn only."""
    def __init__(self, username, password, endpoint):
        """Set parameters for Okta only."""
        self.username = username
        self.password = password
        self.base_uri = endpoint
        self.auth_url = f'{self.base_uri}/api/v1/authn'

        self.session = requests.Session()
        self.session_token = ''
        self.session_id = ''

    def auth(self):
        """Return a session token."""
        r = self.session.post(self.auth_url, json={
            "username": self.username,
            "password": self.password,
        })
        r.raise_for_status()
        r = r.json()

        if r['status'] == 'UNAUTHENTICATED':
            raise RuntimeError('Wrong credentials')

        if r['status'] == 'SUCCESS':
            return r['sessionToken']

        if r['status'] == 'MFA_REQUIRED':
            return self.check_mfa(r['stateToken'], r['_embedded']['factors'])

    def check_mfa(self, state_token, factors):
        """Hanlde multifactor authentication."""
        # filter webauthn factor
        try:
            factor = next(item for item in factors if item['factorType'] == 'webauthn')
        except StopIteration:
            raise NotImplementedError('Server doesn\'t support WebAuthN)')

        # get the webauthn challenge
        r = self.session.post(
                factor['_links']['verify']['href'],
                json={'stateToken': state_token}
            )
        r.raise_for_status()
        r = r.json()
        if r['status'] != 'MFA_CHALLENGE':
            raise NotImplementedError("The relying party didn't respond with a challenge")

        # extract useful informations
        try:
            credential_id = r['_embedded']['factor']['profile']['credentialId']
            authenticator_name = r['_embedded']['factor']['profile']['authenticatorName']
            challenge = r['_embedded']['factor']['_embedded']['challenge']['challenge']
            user_verification = r['_embedded']['factor']['_embedded']['challenge']['userVerification']
            validation_url = r['_links']['next']['href']
        except KeyError as e:
            raise RuntimeError(f"Can't extract {e} from WebAuthn challenge")

        # make the webauthn signature
        webauthn = WebAuthnClient(
                url = self.base_uri,
                authenticator = authenticator_name,
                user_verification = user_verification,
            )
        assertion = webauthn.verify(credential_id, challenge)

        # extract data from assertion
        client_data = str(base64.urlsafe_b64encode(assertion.client_data), "utf-8")
        signature_data = base64.b64encode(assertion.signature).decode('utf-8')
        auth_data = base64.b64encode(assertion.authenticator_data).decode('utf-8')

        # send signature to remote
        r = self.session.post(
            validation_url,
            json = {
                'stateToken': state_token,
                'clientData': client_data,
                'signatureData': signature_data,
                'authenticatorData': auth_data
            }
        )
        r.raise_for_status()
        r = r.json()
        if r['status'] != 'SUCCESS':
            raise RuntimeError("Can't get a session token")

        return r['sessionToken']


class OktaSamlClient(OktaClient):

    def __init__(self, app_name, app_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saml_url = f'{self.base_uri}/app/{app_name}/{app_id}/sso/saml'

    def auth(self):
        """Add the SAML part retreiving the assertion."""
        # fetch a session token
        session_token = super().auth()
        # fetch the SAML response
        r = self.session.get(self.saml_url, params={'onetimetoken': session_token})
        r.raise_for_status()
        # return the SAML assertion
        soup = Soup(r.text, 'html.parser')
        return soup.find(attrs={'name': 'SAMLResponse'}).get('value')
