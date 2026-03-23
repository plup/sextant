import httpx


class GitLabClient:
    """GitLab REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    @classmethod
    def from_config(cls, config):
        """Build a GitLabClient from a revealed endpoint config dict."""
        http = httpx.Client(
            base_url=config['remote'],
            headers={'PRIVATE-TOKEN': config['credentials']['secret']},
            verify=config.get('verify', True),
        )
        return cls(http)

    def check(self):
        """Verify authentication, return current user info string."""
        r = self.http.get('/api/v4/user')
        r.raise_for_status()
        user = r.json()
        return f"{user['username']} ({user['name']})"

    def list_projects(self, search=None, membership=True):
        """Return a list of projects."""
        params = {'per_page': 50, 'order_by': 'updated_at'}
        if membership:
            params['membership'] = True
        if search:
            params['search'] = search
        r = self.http.get('/api/v4/projects', params=params)
        r.raise_for_status()
        return r.json()

    def get_project(self, project_id):
        """Return a single project dict."""
        r = self.http.get(f'/api/v4/projects/{project_id}')
        r.raise_for_status()
        return r.json()

    def list_merge_requests(self, project_id=None, state='opened', author=None):
        """Return merge requests, optionally scoped to a project."""
        params = {'per_page': 50, 'state': state}
        if author:
            params['author_username'] = author
        if project_id:
            path = f'/api/v4/projects/{project_id}/merge_requests'
        else:
            path = '/api/v4/merge_requests'
        r = self.http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def get_merge_request(self, project_id, mr_iid):
        """Return a single merge request dict."""
        r = self.http.get(f'/api/v4/projects/{project_id}/merge_requests/{mr_iid}')
        r.raise_for_status()
        return r.json()

    def list_issues(self, project_id=None, state='opened', assignee=None):
        """Return issues, optionally scoped to a project."""
        params = {'per_page': 50, 'state': state}
        if assignee:
            params['assignee_username'] = assignee
        if project_id:
            path = f'/api/v4/projects/{project_id}/issues'
        else:
            path = '/api/v4/issues'
        r = self.http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def list_pipelines(self, project_id, status=None, ref=None):
        """Return pipelines for a project."""
        params = {'per_page': 50}
        if status:
            params['status'] = status
        if ref:
            params['ref'] = ref
        r = self.http.get(f'/api/v4/projects/{project_id}/pipelines', params=params)
        r.raise_for_status()
        return r.json()

    def get_pipeline(self, project_id, pipeline_id):
        """Return a single pipeline dict."""
        r = self.http.get(f'/api/v4/projects/{project_id}/pipelines/{pipeline_id}')
        r.raise_for_status()
        return r.json()

    def list_pipeline_jobs(self, project_id, pipeline_id):
        """Return jobs for a pipeline."""
        params = {'per_page': 100}
        r = self.http.get(
            f'/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs',
            params=params,
        )
        r.raise_for_status()
        return r.json()
