import logging
import requests
import getpass
from fido2.hid import CtapHidDevice
from fido2.client import Fido2Client, UserInteraction
from fido2.server import Fido2Server

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CliInteraction(UserInteraction):

    def prompt_up(self):
        print("\nTouch your authentication device...\n")



class OktaAuth(object):

    def __init__(self, username, password, endpoint, app_link):
        """Set parameters for Okta only."""
        self.logger = logger
        self.factor = 'OKTA'
        self.username = username
        self.password = password
        self.totp_token = None
        self.app_link = app_link
        self.https_base_uri = endpoint
        self.auth_url = f'{self.https_base_uri}/api/v1/authn'

        self.session = requests.Session()
        self.session_token = ''
        self.session_id = ''

    def primary_auth(self):
        r = self.session.post(self.auth_url, json={
            "username": self.username,
            "password": self.password,
        }).json()
        if r['status'] == 'MFA_REQUIRED':
            self.check_mfa(r['stateToken'], r['_embedded']['factors'])


    def check_mfa(self, state_token, factors):
        """Implement WebAuthn."""
        #  filter webauthn support
        proposed_factor_types = [f['factorType'] for f in factors]
        if 'webauthn' not in proposed_factor_types:
            raise NotImplementedError(f'Server proposed unsupported authentication mechanism {proposed_factor_types.join(", ")}')

        # get the webauthn credential request details for the selected factor
        r = self.session.post(factors[0]['_links']['verify']['href'], json={'stateToken': state_token}).json()
        if r['status'] != 'MFA_CHALLENGE':
            raise NotImplementedError("The relying party didn't respond with a challenge")

        credential_id = r['_embedded']['factor']['profile']['credentialId']
        authenticator_name = r['_embedded']['factor']['profile']['authenticatorName']
        challenge = r['_embedded']['factor']['_embedded']['challenge']
        username = r['_embedded']['user']['profile']['login']

        # locate FIDO authenticator
        dev = next(CtapHidDevice.list_devices(), None)
        if not dev:
            raise SystemError('No FIDO device found.')

        client = Fido2Client(dev, self.https_base_uri, user_interaction=CliInteraction())

        # serialize the request_options as a PublicKeyCredentialRequestOptions()

        ### test the format using server method generation
        uv = 'discouraged'
        user = {'id': b'sr53971'}
        server = Fido2Server({'id': 'id.payward.com', 'name': 'sample'}, attestation='direct')
        create_options, state = server.register_begin(user, user_verification=uv, authenticator_attachment='cross-platform')

        result = client.make_credential(create_options['publicKey'])

        auth_data = server.register_complete(
            state, result.client_data, result.attestation_object
        )
        credentials = [auth_data.credential_data]

        request_options, state = server.authenticate_begin(credentials, user_verification=uv)
        print(request_options)

        ### result to mimic
        result = client.get_assertion(request_options['publicKey'])
        result = result.get_response(0)
        print(result)


        return

    def get_assertion(self):

        return self.primary_auth()

def get_credentials(login, endpoint, app_link):

    auth = OktaAuth(
            login,
            getpass.getpass(),
            endpoint = endpoint,
            app_link = app_link
    )
    assertion = auth.get_assertion()
    print(assertion)

