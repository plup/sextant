import logging
import httpx

logger = logging.getLogger('sextant')


class GitLabClient:
    """GitLab REST API client."""

    def __init__(self, http: httpx.Client):
        self.http = http

    def paginate(self, path, params=None):
        """Yield all items from a paginated GitLab endpoint."""
        params = dict(params or {})
        params.setdefault('per_page', 100)
        page = 1
        while True:
            params['page'] = page
            r = self.http.get(path, params=params)
            r.raise_for_status()
            items = r.json()
            if not items:
                break
            yield from items
            next_page = r.headers.get('x-next-page', '')
            if not next_page:
                break
            page = int(next_page)

    @classmethod
    def from_config(cls, config):
        """Build a GitLabClient from a revealed endpoint config dict."""
        http = httpx.Client(
            base_url=config['remote'],
            headers={'PRIVATE-TOKEN': config['credentials']['secret']},
            verify=config.get('verify', True),
            timeout=120,
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

    def list_registry_repositories(self, project_id):
        """Return container registry repositories for a project."""
        return list(self.paginate(
            f'/api/v4/projects/{project_id}/registry/repositories',
            params={'tags': True, 'tags_count': True},
        ))

    def list_all_images(self, include_personal=False):
        """Yield (project, repositories) for every project with images."""
        params = {'archived': 'false', 'simple': 'true', 'order_by': 'path', 'sort': 'asc'}
        for project in self.paginate('/api/v4/projects', params):
            if not include_personal and project.get('namespace', {}).get('kind') == 'user':
                continue
            try:
                repos = self.list_registry_repositories(project['id'])
            except httpx.HTTPStatusError as e:
                logger.info(f"{project['path_with_namespace']}: {e.response.status_code}")
                continue
            if repos:
                yield project, repos
