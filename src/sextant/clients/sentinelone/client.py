import time
import tempfile
import zipfile

import httpx
from dataclasses import dataclass, field
from pathlib import Path


FETCH_PASSWORD = 'Sextant-Fetch1'


@dataclass
class ScriptResult:
    """Result of a remote script execution on a single agent."""
    task_id: str
    agent_id: str
    agent_name: str
    status: str
    detail: str
    path: Path | None = None
    files: list[tuple[str, int]] = field(default_factory=list)
    stdout: str = ''
    stderr: str = ''
    error: str = ''


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

    def list_agents(self, limit=50, cursor=None, query=None, active=None,
                    group_ids=None, site_ids=None):
        """Return paginated agent list and pagination dict."""
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if query:
            params['computerName__contains'] = query
        if active is not None:
            params['isActive'] = active
        if group_ids:
            params['groupIds'] = ','.join(group_ids) if isinstance(group_ids, list) else group_ids
        if site_ids:
            params['siteIds'] = ','.join(site_ids) if isinstance(site_ids, list) else site_ids

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

    def get_script(self, name):
        """Return a single script dict matching the given name."""
        scripts, _ = self.list_scripts(query=name, limit=10)
        for s in scripts:
            if s.get('scriptName') == name:
                return s
        raise LookupError(f"script '{name}' not found")

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

    TERMINAL_STATUSES = {'completed', 'failed', 'canceled', 'expired', 'partially_completed'}

    def get_script_status(self, parent_task_id, limit=50):
        """Return execution status for tasks under a parent task ID."""
        params = {'parentTaskId': parent_task_id, 'limit': limit}
        r = self.http.get('/web/api/v2.1/remote-scripts/status', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def wait_for_script(self, parent_task_id, interval=5, on_poll=None):
        """Poll until all tasks under a parent task reach a terminal status.

        Calls on_poll(tasks) on each poll if provided. Returns the final task list.
        """
        while True:
            tasks, _ = self.get_script_status(parent_task_id)
            if on_poll:
                on_poll(tasks)
            if tasks and all(t.get('status') in self.TERMINAL_STATUSES for t in tasks):
                return tasks
            time.sleep(interval)

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

    def fetch_script_results(self, parent_task_id, output_dir):
        """Download script results for a parent task and extract output.

        Returns a list of ScriptResult, one per agent task.
        Raises LookupError if no tasks are found.
        """
        tasks, _ = self.get_script_status(parent_task_id)
        if not tasks:
            raise LookupError(f"no tasks found for {parent_task_id}")

        task_dir = Path(output_dir) / parent_task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        tasks_by_id = {t['id']: t for t in tasks}
        links, fetch_errors = self.get_script_results(list(tasks_by_id))

        links_by_task = {link['taskId']: link for link in links}
        error_by_task = {err['taskId']: err.get('errorString', '') for err in fetch_errors}

        results = []
        for task_id, task in tasks_by_id.items():
            result = ScriptResult(
                task_id=task_id,
                agent_id=task.get('agentId', ''),
                agent_name=task.get('agentComputerName', ''),
                status=task.get('status', ''),
                detail=task.get('detailedStatus', ''),
            )

            if task_id in error_by_task:
                result.error = error_by_task[task_id]
            elif task_id in links_by_task:
                link = links_by_task[task_id]
                agent_name = task.get('agentComputerName', task_id)
                dest = task_dir / f"{agent_name}_{task_id}.zip"
                self.download_file(link['downloadUrl'], dest)
                result.path = dest

                with zipfile.ZipFile(dest) as zf:
                    for name in zf.namelist():
                        if name.startswith('stdout'):
                            result.stdout = zf.read(name).decode(errors='replace').rstrip()
                        elif name.startswith('stderr'):
                            result.stderr = zf.read(name).decode(errors='replace').rstrip()
                        else:
                            result.files.append((name, zf.getinfo(name).file_size))

            results.append(result)

        return results

    def list_activities(self, limit=50, cursor=None, activity_types=None,
                        agent_ids=None, created_after=None, created_before=None):
        """Return paginated activity list and pagination dict."""
        params = {'limit': limit}
        if cursor:
            params['cursor'] = cursor
        if activity_types:
            params['activityTypes'] = activity_types
        if agent_ids:
            params['agentIds'] = ','.join(agent_ids) if isinstance(agent_ids, list) else agent_ids
        if created_after:
            params['createdAt__gte'] = created_after
        if created_before:
            params['createdAt__lte'] = created_before

        r = self.http.get('/web/api/v2.1/activities', params=params)
        r.raise_for_status()
        body = r.json()
        return body['data'], body['pagination']

    def fetch_files(self, agent_id, files, password=FETCH_PASSWORD):
        """Request the agent to upload specified files to the management console.

        Returns the API response data dict.
        """
        r = self.http.post(
            f'/web/api/v2.1/agents/{agent_id}/actions/fetch-files',
            json={'data': {'files': files, 'password': password}},
        )
        r.raise_for_status()
        return r.json()['data']

    UPLOAD_ACTIVITY_TYPES = '80'

    def wait_for_upload(self, agent_id, started_after, interval=5, timeout=300, on_poll=None):
        """Poll activities until a file-upload activity appears for the agent.

        Returns the activity dict. Raises TimeoutError if not found within timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if on_poll:
                on_poll()
            activities, _ = self.list_activities(
                limit=10,
                agent_ids=[agent_id],
                activity_types=self.UPLOAD_ACTIVITY_TYPES,
                created_after=started_after,
            )
            if activities:
                return activities[0]
            time.sleep(interval)
        raise TimeoutError(f"upload not completed within {timeout}s")

    def download_upload(self, agent_id, activity_id, dest, password=FETCH_PASSWORD):
        """Download an uploaded file archive from the management console.

        If password is provided, the archive is decrypted and re-written
        without password protection.
        """
        if password is None:
            target = dest
        else:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            target = Path(tmp.name)
            tmp.close()

        with self.http.stream('GET', f'/web/api/v2.1/agents/{agent_id}/uploads/{activity_id}') as r:
            r.raise_for_status()
            with open(target, 'wb') as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

        if password is not None:
            pwd = password.encode()
            with zipfile.ZipFile(target) as src, zipfile.ZipFile(dest, 'w') as out:
                for name in src.namelist():
                    out.writestr(name, src.read(name, pwd=pwd))
            target.unlink()
