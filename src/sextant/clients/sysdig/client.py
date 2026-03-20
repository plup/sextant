import httpx


class SysdigClient:
    """Sysdig Secure REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_config(cls, config):
        """Build a SysdigClient from a revealed endpoint config dict."""
        http = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
            verify=config.get('verify', True),
        )
        return cls(http)

    def check(self):
        """Verify authentication, return current user info string."""
        r = self.http.get('/api/user/me')
        r.raise_for_status()
        user = r.json()['user']
        return f"{user['username']} ({user.get('systemRole', 'unknown')})"

    def list_events(self, limit=50, from_ns=None, to_ns=None, filter=None, cursor=None):
        """Return paginated security events and page metadata."""
        params = {'limit': limit}
        if from_ns is not None:
            params['from'] = int(from_ns)
        if to_ns is not None:
            params['to'] = int(to_ns)
        if filter:
            params['filter'] = filter
        if cursor:
            params['cursor'] = cursor

        r = self.http.get('/api/v1/secureEvents', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body.get('page', {})

    def get_event(self, event_id):
        """Return a single security event dict."""
        r = self.http.get(f'/api/v1/secureEvents/{event_id}')
        r.raise_for_status()
        return r.json()

    def list_policies(self):
        """Return all runtime policies."""
        r = self.http.get('/api/v2/policies')
        r.raise_for_status()
        return r.json()

    def get_policy(self, policy_id):
        """Return a single policy dict."""
        r = self.http.get(f'/api/v2/policies/{policy_id}')
        r.raise_for_status()
        return r.json()

    def list_alerts(self):
        """Return all configured alerts."""
        r = self.http.get('/api/alerts')
        r.raise_for_status()
        return r.json().get('alerts', [])

    def get_alert(self, alert_id):
        """Return a single alert dict."""
        r = self.http.get(f'/api/alerts/{alert_id}')
        r.raise_for_status()
        return r.json().get('alert', r.json())

    def list_connected_agents(self):
        """Return connected agents and total count."""
        r = self.http.get('/api/agents/connected')
        r.raise_for_status()
        body = r.json()
        return body.get('agents', []), body.get('total', 0)
