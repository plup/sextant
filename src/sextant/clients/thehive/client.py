import uuid
import httpx


class TheHiveClient:
    """TheHive REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_config(cls, config):
        """Build a TheHiveClient from a revealed endpoint config dict."""
        verify = config.get('verify', True)
        if config['credentials'].get('secret'):
            http = httpx.Client(
                base_url=config['remote'],
                headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
                verify=verify,
            )
        else:
            http = httpx.Client(
                base_url=config['remote'],
                auth=httpx.BasicAuth(
                    username=config['credentials']['username'],
                    password=config['credentials']['password'],
                ),
                verify=verify,
            )
        return cls(http)

    def check(self):
        """Verify authentication, return current user info string."""
        r = self.http.get('/api/v1/user/current')
        r.raise_for_status()
        user = r.json()
        return f"{user['login']} ({user.get('profile', 'unknown')})"

    def create_alert(self, alert_data):
        """Create an alert, return the response dict."""
        alert_data['sourceRef'] = str(uuid.uuid4())
        r = self.http.post('/api/v1/alert', json=alert_data)
        r.raise_for_status()
        return r.json()

    def list_alerts(self, since_ms):
        """List alerts since timestamp (milliseconds)."""
        r = self.http.post('/api/v1/query', json={
            "query": [
                {"_name": "listAlert"},
                {"_name": "filter", "_gte": {"_field": "date", "_value": since_ms}},
                {"_name": "sort", "_fields": [{"date": "desc"}]},
            ],
            "excludeFields": ["description", "summary"],
        })
        r.raise_for_status()
        return r.json()

    def get_alert(self, alert_id):
        """Return the alert dict."""
        r = self.http.get(f'/api/v1/alert/{alert_id}')
        r.raise_for_status()
        return r.json()

    def list_cases(self, since_ms):
        """List cases since timestamp (milliseconds)."""
        r = self.http.post('/api/v1/query', json={
            "query": [
                {"_name": "listCase"},
                {"_name": "filter", "_gte": {"_field": "newDate", "_value": since_ms}},
                {"_name": "sort", "_fields": [{"newDate": "desc"}]},
            ],
            "excludeFields": ["description", "summary"],
        })
        r.raise_for_status()
        return r.json()
