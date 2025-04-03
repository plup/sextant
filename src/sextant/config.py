import yaml
import subprocess
from pathlib import Path

class Config:

    def __init__(self, file=Path('~/.config/sextant/config.yaml')):
        with open(file.expanduser(), 'r') as f:
            self.config = yaml.safe_load(f)

    def reveal(self):
        """Reveal secrets from the configuration."""
        for key in self.config['endpoints']:
            endpoint = self.config['endpoints'][key]
            if endpoint['credential']['provider'] == '1password':
                endpoint['secret'] = self.onepassword(
                        endpoint['credential']['item'],
                        endpoint['credential']['field']
                    )
        return self.config

    def onepassword(self, item, field):
        """Get secrets from 1password."""
        try:
            cmd = f'op item get {item} --fields={field} --reveal'
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True)
            return result.stdout.decode().strip()

        except subprocess.CalledProcessError as e:
            RuntimeError(e.stderr.decode())
