import logging
from getpass import getpass
from fido2.hid import CtapHidDevice
from fido2.client import Fido2Client, UserInteraction, ClientError as Fido2ClientError
from fido2.webauthn import PublicKeyCredentialRequestOptions, PublicKeyCredentialType, PublicKeyCredentialDescriptor
from fido2.utils import websafe_decode

logger = logging.getLogger(__name__)


class CliInteraction(UserInteraction):

    def prompt_up(self):
        print("Touch your security key...\n")

    def request_pin(self, permissions, rd_id):
        return getpass("FIDO2 PIN: ")


class WebAuthnClient(object):

    def __init__(self, url, authenticator, user_verification):
        self.name = authenticator
        self.uv = user_verification
        self.rp = {'id': url[8:], 'name': url[8:]}

        # locate FIDO authenticator
        try:
            dev = next(CtapHidDevice.list_devices())
        except StopIteration:
            raise SystemError('No FIDO device found.')

        # init client
        self.client = Fido2Client(dev, url, user_interaction=CliInteraction())

    def verify(self, credential_id, challenge):
        try:
            # build the allowed list
            allow_list = [
                PublicKeyCredentialDescriptor(PublicKeyCredentialType.PUBLIC_KEY, websafe_decode(credential_id))
            ]

            # serialize the request_options as a PublicKeyCredentialRequestOptions
            options = PublicKeyCredentialRequestOptions(
                    challenge = challenge,
                    rp_id = self.rp['id'],
                    user_verification = self.uv,
                    allow_credentials = allow_list,
                )

            assertions = self.client.get_assertion(options)
            return assertions.get_response(0)

        except Fido2ClientError as e:
            if e.code == Fido2ClientError.ERR.DEVICE_INELIGIBLE:
                logger.error('Security key is ineligible')
            raise RuntimeError(f'No credential retreived from Yubikey: {e}')



