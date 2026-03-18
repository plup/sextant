import httpx


class SentinelOneClient:
    """SentinelOne REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_config(cls, config):
        """Build a SentinelOneClient from a revealed endpoint config dict."""
        http = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"ApiToken {config['credentials']['secret']}"},
            verify=config.get('verify', True),
        )
        return cls(http)

    def check(self):
        """Verify authentication, return system info string."""
        r = self.http.get('/web/api/v2.1/system/info')
        r.raise_for_status()
        info = r.json()['data']
        return f"{info['version']} (build {info['build']})"

    def list_agents(self, limit=50, cursor=None, query=None, active=None):
        """Return paginated agent list and pagination dict."""
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if query:
            params['computerName__contains'] = query
        if active is not None:
            params['isActive'] = active

        r = self.http.get('/web/api/v2.1/agents', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def get_agent(self, name):
        """Return a single agent dict matching the given hostname."""
        r = self.http.get('/web/api/v2.1/agents', params={'computerName__contains': name, 'limit': 1})
        r.raise_for_status()
        data = r.json()['data']
        if not data:
            raise LookupError(f"agent {name} not found")
        return data[0]

    def list_threats(self, limit=50, cursor=None, incident_statuses=None,
                     created_after=None, created_before=None):
        """Return paginated threat list and pagination dict."""
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if incident_statuses:
            params['incidentStatuses'] = incident_statuses
        if created_after:
            params['createdAt__gte'] = created_after
        if created_before:
            params['createdAt__lte'] = created_before

        r = self.http.get('/web/api/v2.1/threats', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def get_threat(self, threat_id):
        """Return a single threat dict."""
        r = self.http.get('/web/api/v2.1/threats', params={'ids': threat_id})
        r.raise_for_status()
        data = r.json()['data']
        if not data:
            raise LookupError(f"threat {threat_id} not found")
        return data[0]

    def list_scripts(self, limit=50, query=None, script_type=None, os_types=None):
        """Return available remote scripts."""
        params = {'limit': limit}
        if query:
            params['query'] = query
        if script_type:
            params['scriptType'] = script_type
        if os_types:
            params['osTypes'] = os_types

        r = self.http.get('/web/api/v2.1/remote-scripts', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def execute_script(self, script_id, agent_filter, description,
                       output_destination='SentinelCloud', input_params=None,
                       timeout=3600):
        """Execute a remote script on agents matching the filter. Return the task response."""
        payload = {
            'filter': agent_filter,
            'data': {
                'scriptId': script_id,
                'taskDescription': description,
                'outputDestination': output_destination,
                'scriptRuntimeTimeoutSeconds': timeout,
            },
        }
        if input_params:
            payload['data']['inputParams'] = input_params

        r = self.http.post('/web/api/v2.1/remote-scripts/execute', json=payload)
        r.raise_for_status()
        return r.json()['data']

    def get_script_status(self, parent_task_id, limit=50):
        """Return execution status for tasks under a parent task ID."""
        params = {'parentTaskId': parent_task_id, 'limit': limit}
        r = self.http.get('/web/api/v2.1/remote-scripts/status', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def get_script_results(self, task_ids):
        """Fetch download URLs for completed script task results."""
        r = self.http.post(
            '/web/api/v2.1/remote-scripts/fetch-files',
            json={'data': {'taskIds': task_ids}},
        )
        r.raise_for_status()
        data = r.json()['data']
        return data.get('download_links', []), data.get('errors', [])

    def download_file(self, url, dest):
        """Download a file from a pre-signed URL to a local path."""
        with httpx.stream('GET', url) as r:
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def list_activities(self, limit=50, cursor=None, activity_types=None,
                        created_after=None, created_before=None):
        """Return paginated activity list and pagination dict."""
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if activity_types:
            params['activityTypes'] = activity_types
        if created_after:
            params['createdAt__gte'] = created_after
        if created_before:
            params['createdAt__lte'] = created_before

        r = self.http.get('/web/api/v2.1/activities', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']
