import json
import httpx
from contextlib import contextmanager
from time import sleep


class SplunkClient:
    """Splunk REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_config(cls, config):
        """Build a SplunkClient from a revealed endpoint config dict."""
        http = httpx.Client(
            base_url=config['remote'],
            headers={'Authorization': f"Bearer {config['credentials']['secret']}"},
            verify=config.get('verify', True),
        )
        return cls(http)

    def check(self):
        """Verify authentication, return server info string."""
        r = self.http.get('/services/server/info', params={'output_mode': 'json'})
        r.raise_for_status()
        info = r.json()['entry'][0]['content']
        return f"{info['serverName']} ({info['version']})"

    def list_jobs(self, user=None, name=None):
        """Return (entries, total) for search jobs."""
        payload = {'output_mode': 'json', 'count': 0, 'search': []}
        if user:
            payload['search'].append(f'eai:acl.owner={user}')
        if name:
            payload['search'].append(f'label="*{name}*"')

        r = self.http.get('/services/search/jobs', params=payload)
        r.raise_for_status()
        data = r.json()
        return data['entry'], data['paging']['total']

    def get_job_results(self, sid, wait=0):
        """Fetch job results, optionally polling until complete. Returns list or None."""
        elapsed = 0
        while elapsed <= wait:
            r = self.http.get(
                f'/services/search/v2/jobs/{sid}/results',
                params={'output_mode': 'json'},
            )
            r.raise_for_status()
            if not wait or r.text:
                break
            sleep(elapsed := elapsed + 3)

        if not r.text:
            return None
        try:
            return r.json()['results']
        except json.JSONDecodeError:
            raise ValueError(r.text)

    def list_indexes(self):
        """Return (entries, total) for accessible indexes."""
        r = self.http.get(
            '/services/data/indexes',
            params={'output_mode': 'json', 'count': 0, 'datatype': 'all'},
        )
        r.raise_for_status()
        data = r.json()
        return data['entry'], data['paging']['total']

    def list_searches(self, user=None, name=None):
        """Return (entries, total) for saved searches."""
        payload = {'output_mode': 'json', 'count': 0, 'search': []}
        if user:
            payload['search'].append(f'eai:acl.owner={user}')
        if name:
            payload['search'].append(f'name="*{name}*"')

        r = self.http.get('/services/saved/searches', params=payload)
        r.raise_for_status()
        data = r.json()
        return data['entry'], data['paging']['total']

    def get_search(self, name):
        """Return the saved search entry dict."""
        r = self.http.get(
            f'/services/saved/searches/{name}',
            params={'output_mode': 'json'},
        )
        r.raise_for_status()
        return r.json()['entry'][0]

    def dispatch_search(self, name, data):
        """Dispatch a saved search, return the SID."""
        r = self.http.post(
            f'/services/saved/searches/{name}/dispatch',
            data=data,
            params={'output_mode': 'json'},
        )
        r.raise_for_status()
        return r.json()['sid']

    @contextmanager
    def stream_query(self, query, earliest, latest):
        """Context manager yielding raw JSON lines from a Splunk export search."""
        payload = {
            'search': query,
            'earliest_time': earliest,
            'latest_time': latest,
            'output_mode': 'json',
            'preview': False,
            'summarize': True,
        }
        with self.http.stream('POST', '/services/search/jobs/export', data=payload) as r:
            r.raise_for_status()
            yield r.iter_lines()
