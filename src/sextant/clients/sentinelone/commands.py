import functools
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from sextant.clients.sentinelone.client import SentinelOneClient
from sextant.utils import Lazy, humanize, deshumanize

log = logging.getLogger(__name__)


def handle_errors(f):
    """Catch common exceptions and print them to stderr."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except LookupError as e:
            click.echo(str(e), err=True)
        except TimeoutError as e:
            click.echo(str(e), err=True)
        except httpx.HTTPStatusError as e:
            click.echo(f"{e.response.status_code} {e.response.reason_phrase}", err=True)
    return wrapper


def read_hosts_file(path):
    """Read hostnames from a file, one per line, skipping blanks and comments."""
    hosts = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            hosts.append(line)
    return tuple(hosts)


def target_options(f):
    """Shared click options for agent targeting."""
    f = click.option('--all', 'target_all', is_flag=True, help='Target all active agents')(f)
    f = click.option('--site', '-s', 'site_ids', default=None, help='Target agents by site ID (comma-separated)')(f)
    f = click.option('--group', '-g', 'group_ids', default=None, help='Target agents by group ID (comma-separated)')(f)
    f = click.option('--agent', '-a', 'agent_names', multiple=True, help='Target agent(s) by hostname (repeatable)')(f)
    f = click.option('--file', '-f', 'hosts_file', type=click.Path(exists=True), default=None, help='File containing hostnames (one per line)')(f)
    return f


def resolve_target_names(agent_names, hosts_file):
    """Return agent names from either --agent or --file (mutually exclusive)."""
    if agent_names and hosts_file:
        raise click.UsageError('--agent and --file are mutually exclusive')
    if hosts_file:
        return read_hosts_file(hosts_file)
    return agent_names


def wait_for_online(client, names, interval=30, timeout=3600, on_poll=None):
    """Poll until all named agents report as active. Returns list of agent dicts."""
    deadline = time.monotonic() + timeout
    pending = set(names)
    agents = {}

    while pending:
        for name in list(pending):
            try:
                agent = client.get_agent(name)
                if agent.get('isActive'):
                    agents[name] = agent
                    pending.discard(name)
            except LookupError:
                pass

        if not pending:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"agents not online within {timeout}s: {', '.join(sorted(pending))}")
        if on_poll:
            on_poll(pending)
        time.sleep(interval)

    return [agents[name] for name in names]


def resolve_agents(client, agent_names=None, group_ids=None, site_ids=None, target_all=False):
    """Resolve target agents from CLI targeting options. Returns a list of agent dicts."""
    if agent_names:
        return [client.get_agent(name) for name in agent_names]
    if group_ids:
        agents, _ = client.list_agents(group_ids=[g.strip() for g in group_ids.split(',')], active=True)
        return agents
    if site_ids:
        agents, _ = client.list_agents(site_ids=[s.strip() for s in site_ids.split(',')], active=True)
        return agents
    if target_all:
        agents, _ = client.list_agents(active=True)
        return agents
    raise click.UsageError('Specify a target: --agent, --group, --site, or --all')


def build_agent_filter(client, agent_names=None, group_ids=None, site_ids=None, target_all=False):
    """Build an API-level agent filter dict from CLI targeting options."""
    if agent_names:
        return {'ids': [client.get_agent(name)['id'] for name in agent_names]}
    if group_ids:
        return {'groupIds': [g.strip() for g in group_ids.split(',')]}
    if site_ids:
        return {'siteIds': [s.strip() for s in site_ids.split(',')]}
    if target_all:
        return {'isActive': [True]}
    raise click.UsageError('Specify a target: --agent, --group, --site, or --all')


@click.group()
@click.pass_context
def main(ctx):
    """Manage SentinelOne endpoints."""
    def factory():
        config = ctx.obj['config'].reveal(ctx.info_name)
        return SentinelOneClient.from_config(config)

    client = Lazy(factory)
    ctx.obj['client'] = client

    def cleanup():
        if client._instance is not None:
            client._instance.http.close()
    ctx.call_on_close(cleanup)


@main.group()
def agent():
    """Manage agents."""


@agent.command('list')
@click.option('--query', '-q', help='Filter by hostname (contains)')
@click.option('--active/--inactive', default=None, help='Filter by active status')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
@handle_errors
def list_agents(obj, query, active, limit):
    """List agents.

    \b
    Examples:
      sextant s1 agent list
      sextant s1 agent list -q myhost
      sextant s1 agent list --active -n 10
    """
    agents, pagination = obj['client'].list_agents(
        limit=limit, query=query, active=active,
    )

    if sys.stdout.isatty():
        table = Table('id', 'hostname', 'os', 'version', 'status', 'last active', title='Agents')
        for a in agents:
            status = '[green]active[/green]' if a.get('isActive') else '[red]inactive[/red]'
            last_active = a.get('lastActiveDate', '')
            if last_active:
                try:
                    last_active = humanize(datetime.fromisoformat(last_active.replace('Z', '+00:00')).replace(tzinfo=None))
                except (ValueError, AttributeError):
                    pass
            table.add_row(
                a.get('id', ''),
                a.get('computerName', ''),
                a.get('osName', ''),
                a.get('agentVersion', ''),
                status,
                last_active,
            )
        console = Console()
        console.print(table)
        console.print(f"total: {pagination.get('totalItems', len(agents))}")
    else:
        click.echo(json.dumps(agents))


@agent.command('get')
@click.argument('name')
@click.pass_obj
@handle_errors
def get_agent(obj, name):
    """Get agent details by hostname.

    \b
    Examples:
      sextant s1 agent get myhost
    """
    a = obj['client'].get_agent(name)
    if sys.stdout.isatty():
        click.echo(click.style('Agent Info', bold=True))
        click.echo(f"  Hostname:   {a.get('computerName', '')}")
        click.echo(f"  OS:         {a.get('osName', '')} ({a.get('osType', '')})")
        click.echo(f"  Version:    {a.get('agentVersion', '')}")
        click.echo(f"  Active:     {a.get('isActive', '')}")
        click.echo(f"  Network:    {a.get('networkStatus', '')}")
        click.echo(f"  External IP:{a.get('externalIp', '')}")
        click.echo(f"  Domain:     {a.get('domain', '')}")
        click.echo(f"  Group:      {a.get('groupName', '')}")
        click.echo(f"  Site:       {a.get('siteName', '')}")
        click.echo(f"  Infected:   {a.get('infected', '')}")
        click.echo(f"  Machine:    {a.get('machineType', '')}")
        click.echo(f"  Last seen:  {a.get('lastActiveDate', '')}")
    else:
        click.echo(json.dumps(a))


@agent.command('check')
@target_options
@click.pass_obj
@handle_errors
def check_agents(obj, agent_names, group_ids, site_ids, target_all, hosts_file):
    """Check whether targeted agents are online.

    \b
    Examples:
      sextant s1 agent check -a myhost
      sextant s1 agent check -a host1 -a host2
      sextant s1 agent check -f hosts.txt
      sextant s1 agent check --group 12345
    """
    names = resolve_target_names(agent_names, hosts_file)
    if names:
        agents = []
        for name in names:
            try:
                agents.append(obj['client'].get_agent(name))
            except LookupError:
                agents.append({'computerName': name, 'isActive': False, 'notFound': True})
    elif group_ids or site_ids or target_all:
        agents = resolve_agents(obj['client'], group_ids=group_ids, site_ids=site_ids, target_all=target_all)
    else:
        raise click.UsageError('Specify a target: --agent, --file, --group, --site, or --all')

    if not agents:
        raise LookupError('no agents matched the target filter')

    if sys.stdout.isatty():
        table = Table('hostname', 'status', 'network', 'last active', title='Agent Status')
        for a in agents:
            hostname = a.get('computerName', '')
            if a.get('notFound'):
                status = '[yellow]not found[/yellow]'
                network = ''
                last_active = ''
            else:
                status = '[green]online[/green]' if a.get('isActive') else '[red]offline[/red]'
                net = a.get('networkStatus', '')
                network = '[green]connected[/green]' if net == 'connected' else f"[red]{net}[/red]" if net else ''
                last_active = a.get('lastActiveDate', '')
                if last_active:
                    try:
                        last_active = humanize(datetime.fromisoformat(last_active.replace('Z', '+00:00')).replace(tzinfo=None))
                    except (ValueError, AttributeError):
                        pass
            table.add_row(hostname, status, network, last_active)
        console = Console()
        console.print(table)
        online = sum(1 for a in agents if a.get('isActive'))
        found = sum(1 for a in agents if not a.get('notFound'))
        console.print(f"online: {online}/{found}")
    else:
        click.echo(json.dumps([
            {
                'hostname': a.get('computerName', ''),
                'active': a.get('isActive', False),
                'networkStatus': a.get('networkStatus', ''),
                'lastActiveDate': a.get('lastActiveDate', ''),
                'found': not a.get('notFound', False),
            }
            for a in agents
        ]))


@agent.command('fetch')
@click.argument('files', nargs=-1, required=True)
@target_options
@click.option('--wait', '-w', is_flag=True, help='Wait for upload and download the file')
@click.option('--output', '-o', 'output_dir', default='/tmp', help='Directory to save downloaded file')
@click.option('--timeout', '-t', default=300, help='Max seconds to wait for upload')
@click.pass_obj
@handle_errors
def fetch_files(obj, files, agent_names, group_ids, site_ids, target_all, hosts_file, wait, output_dir, timeout):
    """Fetch files from one or more agents.

    Requests agents to upload the specified files as an archive.
    Use --wait to wait for the upload and download automatically.

    \b
    Examples:
      sextant s1 agent fetch /etc/passwd -a myhost --wait
      sextant s1 agent fetch /var/log/syslog /etc/hosts -a host1 -a host2 -w
      sextant s1 agent fetch /tmp/report.log --group 12345 --wait
      sextant s1 agent fetch /etc/passwd -f hosts.txt --wait
    """
    agent_names = resolve_target_names(agent_names, hosts_file)
    agents = resolve_agents(obj['client'], agent_names, group_ids, site_ids, target_all)
    if not agents:
        raise LookupError('no agents matched the target filter')

    started_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    file_list = list(files)

    for ag in agents:
        agent_id = ag['id']
        hostname = ag.get('computerName', agent_id)
        result = obj['client'].fetch_files(agent_id, file_list)
        if not result.get('success'):
            click.echo(click.style(f"[{hostname}] fetch request not accepted", fg='red'), err=True)
            continue
        click.echo(f"fetch requested for {len(file_list)} file(s) from {hostname}")

    if not wait:
        return

    for ag in agents:
        agent_id = ag['id']
        hostname = ag.get('computerName', agent_id)

        def on_poll():
            click.echo(f"waiting for upload from {hostname}...", err=True)

        try:
            activity = obj['client'].wait_for_upload(
                agent_id, started_at, timeout=timeout, on_poll=on_poll,
            )
            activity_id = activity['id']
            dest = Path(output_dir) / f"{hostname}_{activity_id}.zip"
            obj['client'].download_upload(agent_id, str(activity_id), dest)
            click.echo(f"[{hostname}] downloaded: {dest}")
        except TimeoutError:
            click.echo(click.style(f"[{hostname}] upload timed out", fg='red'), err=True)


@agent.command('download')
@click.argument('name')
@click.argument('activity_id')
@click.option('--output', '-o', 'output_dir', default='/tmp', help='Directory to save downloaded file')
@click.pass_obj
@handle_errors
def download_upload(obj, name, activity_id, output_dir):
    """Download a previously uploaded file archive from an agent.

    \b
    Examples:
      sextant s1 agent download myhost 123456789
      sextant s1 agent download myhost 123456789 -o /tmp/results
    """
    ag = obj['client'].get_agent(name)
    hostname = ag.get('computerName', name)
    dest = Path(output_dir) / f"{hostname}_{activity_id}.zip"
    obj['client'].download_upload(ag['id'], activity_id, dest)
    click.echo(f"downloaded: {dest}")


@main.group()
def threat():
    """Manage threats."""


@threat.command('list')
@click.option('--status', 'incident_status', type=click.Choice(
    ['unresolved', 'in_progress', 'resolved'], case_sensitive=False),
    help='Filter by incident status')
@click.option('--from', '-f', 'from_', default=None, help='Relative time window (e.g. 1h, 7d)')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
@handle_errors
def list_threats(obj, incident_status, from_, limit):
    """List threats.

    \b
    Examples:
      sextant s1 threat list
      sextant s1 threat list --status unresolved
      sextant s1 threat list --status unresolved --from 7d
    """
    created_after = None
    if from_:
        created_after = (datetime.utcnow() - deshumanize(from_)).strftime('%Y-%m-%dT%H:%M:%SZ')

    threats, pagination = obj['client'].list_threats(
        limit=limit,
        incident_statuses=incident_status,
        created_after=created_after,
    )

    if sys.stdout.isatty():
        table = Table('id', 'name', 'classification', 'agent', 'status', 'confidence', title='Threats')
        for t in threats:
            info = t.get('threatInfo', {})
            agent_info = t.get('agentRealtimeInfo', {})
            table.add_row(
                t.get('id', ''),
                info.get('threatName', ''),
                info.get('classification', ''),
                agent_info.get('agentComputerName', ''),
                info.get('incidentStatus', ''),
                info.get('confidenceLevel', ''),
            )
        console = Console()
        console.print(table)
        console.print(f"total: {pagination.get('totalItems', len(threats))}")
    else:
        click.echo(json.dumps(threats))


@threat.command('get')
@click.argument('threat_id')
@click.pass_obj
@handle_errors
def get_threat(obj, threat_id):
    """Get threat details.

    \b
    Examples:
      sextant s1 threat get 123456789
    """
    t = obj['client'].get_threat(threat_id)
    if sys.stdout.isatty():
        info = t.get('threatInfo', {})
        agent_info = t.get('agentRealtimeInfo', {})
        click.echo(click.style('Threat Info', bold=True))
        click.echo(f"  Name:           {info.get('threatName', '')}")
        click.echo(f"  Classification: {info.get('classification', '')}")
        click.echo(f"  Confidence:     {info.get('confidenceLevel', '')}")
        click.echo(f"  Status:         {info.get('incidentStatus', '')}")
        click.echo(f"  Mitigation:     {info.get('mitigationStatus', '')}")
        click.echo(f"  Verdict:        {info.get('analystVerdict', '')}")
        click.echo(f"  Agent:          {agent_info.get('agentComputerName', '')}")
        click.echo(f"  File:           {info.get('filePath', '')}")
        click.echo(f"  SHA256:         {info.get('sha256', '')}")
        click.echo(f"  Engines:        {', '.join(info.get('detectionEngines', []))}")
        click.echo(f"  Created:        {info.get('createdAt', '')}")
    else:
        click.echo(json.dumps(t))


@main.group()
def script():
    """Run and monitor remote scripts."""


@script.command('list')
@click.option('--query', '-q', help='Search scripts by name')
@click.option('--os', 'os_types', help='Filter by OS type (linux, windows, macos)')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
@handle_errors
def list_scripts(obj, query, os_types, limit):
    """List available remote scripts.

    \b
    Examples:
      sextant s1 script list
      sextant s1 script list -q "collect"
      sextant s1 script list --os linux
    """
    scripts, pagination = obj['client'].list_scripts(
        limit=limit, query=query, os_types=os_types,
    )

    if sys.stdout.isatty():
        table = Table('name', 'os', 'description', title='Scripts')
        for s in scripts:
            table.add_row(
                s.get('scriptName', ''),
                ', '.join(s.get('osTypes', [])),
                (s.get('scriptDescription', '') or '')[:80],
            )
        console = Console()
        console.print(table)
        console.print(f"total: {pagination.get('totalItems', len(scripts))}")
    else:
        click.echo(json.dumps(scripts))


@script.command('get')
@click.argument('script_name')
@click.pass_obj
@handle_errors
def get_script(obj, script_name):
    """Show script details and input instructions.

    \b
    Examples:
      sextant s1 script get "My Script"
    """
    s = obj['client'].get_script(script_name)
    if sys.stdout.isatty():
        click.echo(click.style('Script Info', bold=True))
        click.echo(f"  Name:         {s.get('scriptName', '')}")
        click.echo(f"  ID:           {s.get('id', '')}")
        click.echo(f"  OS:           {', '.join(s.get('osTypes', []))}")
        click.echo(f"  Type:         {s.get('scriptType', '')}")
        click.echo(f"  Description:  {s.get('scriptDescription', '')}")
        click.echo(f"  Created by:   {s.get('createdByUser', '')}")

        instructions = s.get('inputInstructions') or s.get('inputRequired')
        if instructions:
            click.echo()
            click.echo(click.style('Input Instructions', bold=True))
            click.echo(f"  {instructions}")

        example = s.get('inputExample')
        if example:
            click.echo()
            click.echo(click.style('Input Example', bold=True))
            click.echo(f"  {example}")
    else:
        click.echo(json.dumps(s))


def display_script_results(results):
    """Display script results to the terminal or as JSON when piped."""
    if not sys.stdout.isatty():
        click.echo(json.dumps([
            {
                'agent': r.agent_name,
                'status': r.status,
                'stdout': r.stdout,
                'stderr': r.stderr,
                'error': r.error,
            }
            for r in results
        ]))
        return

    for result in results:
        header = click.style(f"[{result.agent_name}]", bold=True) + f" ({result.status})"
        if result.path:
            header += f" {result.path}"
        click.echo(header)

        if result.error:
            click.echo(click.style(result.error, fg='red'), err=True)
            continue
        if not result.path:
            click.echo(f"  {result.detail}")
            continue

        for name, size in result.files:
            log.info(f"  {name} ({size}B)")
        if result.stdout:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(click.style(result.stderr, fg='red'), err=True)


@script.command('run')
@click.argument('script_name')
@target_options
@click.option('--bg', is_flag=True, help='Submit and return immediately without waiting for results')
@click.option('--poll', is_flag=True, help='Poll until agents come online before executing (requires --agent or --file)')
@click.option('--online-timeout', default=3600, help='Max seconds to wait for agents to come online')
@click.option('--params', '-p', 'input_params', default=None, help='Input parameters for the script')
@click.option('--description', '-d', 'description', default='sextant remote script execution', help='Task description')
@click.option('--timeout', '-t', default=3600, help='Script runtime timeout in seconds')
@click.option('--output', '-o', 'output_dir', default='/tmp', help='Directory to save result files')
@click.pass_obj
@handle_errors
def run_script(obj, script_name, agent_names, group_ids, site_ids, target_all, hosts_file,
               bg, poll, online_timeout, input_params, description, timeout, output_dir):
    """Execute a remote script on one or more agents.

    By default, waits for completion and displays results. Use --bg to submit
    and return immediately. Use --poll to wait for offline agents to come
    online before executing (requires --agent or --file targeting).

    \b
    Examples:
      sextant s1 script run "My Script" -a myhost
      sextant s1 script run "My Script" -a host1 -a host2
      sextant s1 script run "My Script" --all --bg
      sextant s1 script run "My Script" -a myhost -p "arg1 arg2"
      sextant s1 script run "My Script" -f hosts.txt
      sextant s1 script run "My Script" -f hosts.txt --poll
    """
    agent_names = resolve_target_names(agent_names, hosts_file)

    if poll:
        if not agent_names:
            raise click.UsageError('--poll requires --agent or --file targeting')

        def on_poll(pending):
            click.echo(f"waiting for {len(pending)} agent(s) to come online: {', '.join(sorted(pending))}", err=True)

        agents = wait_for_online(obj['client'], agent_names, timeout=online_timeout, on_poll=on_poll)
        agent_filter = {'ids': [a['id'] for a in agents]}
    else:
        agent_filter = build_agent_filter(
            obj['client'], agent_names, group_ids, site_ids, target_all,
        )

    script = obj['client'].get_script(script_name)

    result = obj['client'].execute_script(
        script_id=script['id'],
        agent_filter=agent_filter,
        description=description,
        input_params=input_params,
        timeout=timeout,
    )

    if result.get('pending'):
        click.echo(f"pending approval (id: {result.get('pendingExecutionId', '')})")
        return

    task_id = result.get('parentTaskId', '')
    click.echo(f"task started (id: {task_id}), affected: {result.get('affected', 0)}")

    if not bg and task_id:
        def on_poll(tasks):
            counts = {}
            for t in tasks:
                s = t.get('status', 'unknown')
                counts[s] = counts.get(s, 0) + 1
            summary = ', '.join(f"{s}: {n}" for s, n in sorted(counts.items()))
            click.echo(f"polling... {summary}", err=True)

        obj['client'].wait_for_script(task_id, on_poll=on_poll)

        results = obj['client'].fetch_script_results(task_id, output_dir)
        display_script_results(results)


@script.command('status')
@click.argument('task_id')
@click.pass_obj
@handle_errors
def script_status(obj, task_id):
    """Check execution status of a remote script task.

    \b
    Examples:
      sextant s1 script status 123456789
    """
    tasks, pagination = obj['client'].get_script_status(task_id)

    if sys.stdout.isatty():
        table = Table('agent', 'status', 'details', title='Script Status')
        for t in tasks:
            table.add_row(
                t.get('agentComputerName', ''),
                t.get('status', ''),
                t.get('detailedStatus', ''),
            )
        Console().print(table)
    else:
        click.echo(json.dumps(tasks))


@script.command('results')
@click.argument('task_id')
@click.option('--output', '-o', 'output_dir', default='/tmp', help='Directory to save result files')
@click.pass_obj
@handle_errors
def script_results(obj, task_id, output_dir):
    """Download script result files by parent task ID.

    \b
    Examples:
      sextant s1 script results 123456789
      sextant s1 script results 123456789 -o /tmp/results
    """
    results = obj['client'].fetch_script_results(task_id, output_dir)
    display_script_results(results)


@main.group()
def activity():
    """Browse activity log."""


@activity.command('list')
@click.option('--from', '-f', 'from_', default='1h', help='Relative time window')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
@handle_errors
def list_activities(obj, from_, limit):
    """List recent activities.

    \b
    Examples:
      sextant s1 activity list
      sextant s1 activity list --from 24h
      sextant s1 activity list --from 7d -n 100
    """
    since = (datetime.utcnow() - deshumanize(from_)).strftime('%Y-%m-%dT%H:%M:%SZ')
    activities, pagination = obj['client'].list_activities(
        limit=limit, created_after=since,
    )

    if sys.stdout.isatty():
        table = Table('id', 'ago', 'type', 'description', title='Activities')
        for a in activities:
            created = a.get('createdAt', '')
            if created:
                try:
                    ago = humanize(datetime.fromisoformat(created.replace('Z', '+00:00')).replace(tzinfo=None))
                except (ValueError, AttributeError):
                    ago = created
            else:
                ago = ''
            desc = a.get('primaryDescription', '') or a.get('description', '')
            table.add_row(
                str(a.get('id', '')),
                ago,
                str(a.get('activityType', '')),
                desc[:80],
            )
        console = Console()
        console.print(table)
        console.print(f"total: {pagination.get('totalItems', len(activities))}")
    else:
        click.echo(json.dumps(activities))
