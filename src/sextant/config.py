import yaml
import subprocess
from pathlib import Path
from sextant import SextantConfigurationError

def onepassword(vault, item, field):
    """Get secrets from 1password."""
    try:
        cmd = f'op read -n op://{vault}/{item}/{field}'
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
        return result.stdout.decode()

    except subprocess.CalledProcessError as e:
        raise SextantConfigurationError(e.stderr.decode())

class SextantConfig():

    def __init__(self, file=Path('~/.config/sextant/config.yaml')):
        try:
            with open(file.expanduser(), 'r') as f:
                self.file = yaml.safe_load(f)

        except FileNotFoundError as e:
            raise SextantConfigurationError(f"Configuration file not found: {e}")

    @property
    def endpoints(self):
        """Return the list of endpoints."""
        return self.file['endpoints']

    def reveal(self, name):
        """Load the endpoint config and reveal the secrets."""
        try:
            endpoint = next(ep for ep in self.endpoints if ep['name'] == name)

            if endpoint['credentials']['provider'] == '1password':
                vault = endpoint['credentials']['vault']
                item = endpoint['credentials']['item']
                # reveal values from field names
                revealed_fields = {}
                for key, field in endpoint['credentials']['fields'].items():
                    revealed_fields[key] = onepassword(vault, item, field)
                endpoint['credentials'] = revealed_fields

            return endpoint

        except StopIteration:
            raise SextantConfigurationError(f"Configuration for endpoint {name} not found")
