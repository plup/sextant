import logging
import requests
import base64
from getpass import getpass
from .webauthn import WebAuthnClient
from fido2.server import Fido2Server

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OktaClient(object):

    def __init__(self, username, password, endpoint, app_link):
        """Set parameters for Okta only."""
        self.logger = logger
        self.factor = 'OKTA'
        self.username = username
        self.password = password
        self.app_link = app_link
        self.https_base_uri = endpoint
        self.auth_url = f'{self.https_base_uri}/api/v1/authn'

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

        if r['status'] == 'SUCCESS':
            session_token = r['sessionToken']
        elif r['status'] == 'MFA_REQUIRED':
            session_token = self.check_mfa(r['stateToken'], r['_embedded']['factors'])
        elif r['status'] == 'UNAUTHENTICATED':
            raise RuntimeError('Wrong credentials')

        return session_token

    def check_mfa(self, state_token, factors):
        """
        Hanlde Multi factore authentication.
        Only supports WebAuthn.
        """
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
                url = self.https_base_uri,
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


def get_credentials(login, endpoint, app_link):

    okta = OktaClient(
            login,
            getpass(),
            endpoint = endpoint,
            app_link = app_link
    )
    print(okta.auth())

