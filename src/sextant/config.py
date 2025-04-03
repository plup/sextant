import yaml
import subprocess
from pathlib import Path

def onepassword(vault, item, field):
    """Get secrets from 1password."""
    try:
        cmd = f'op read -n op://{vault}/{item}/{field}'
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
        return result.stdout.decode()

    except subprocess.CalledProcessError as e:
        RuntimeError(e.stderr.decode())

class Config():

    def __init__(self, file=Path('~/.config/sextant/config.yaml')):
        with open(file.expanduser(), 'r') as f:
            self.file = yaml.safe_load(f)

    def get_endpoint(self, name):
        """Load the endpoint config and reveal the secrets."""
        endpoint = self.file['endpoints'][name]

        if endpoint['credentials']['provider'] == '1password':
            vault = endpoint['credentials']['vault']
            item = endpoint['credentials']['item']
            # reveal values from field names
            revealed_fields = {}
            for key, field in endpoint['credentials']['fields'].items():
                revealed_fields[key] = onepassword(vault, item, field)
            endpoint['credentials'] = revealed_fields

        return endpoint
