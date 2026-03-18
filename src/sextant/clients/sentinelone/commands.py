import sys
import click
import httpx
import json
import zipfile
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from sextant.utils import Lazy, humanize, deshumanize
from sextant.clients.sentinelone.client import SentinelOneClient


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
def list_agents(obj, query, active, limit):
    """List agents."""
    try:
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

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@agent.command('get')
@click.argument('name')
@click.pass_obj
def get_agent(obj, name):
    """Get agent details by hostname."""
    try:
        a = obj['client'].get_agent(name)
        if sys.stdout.isatty():
            click.echo(click.style('Agent Info', bold=True))
            click.echo(f"  Hostname:   {a.get('computerName', '')}")
            click.echo(f"  OS:         {a.get('osName', '')} ({a.get('osType', '')})")
            click.echo(f"  Version:    {a.get('agentVersion', '')}")
            click.echo(f"  Active:     {a.get('isActive', '')}")
            click.echo(f"  External IP:{a.get('externalIp', '')}")
            click.echo(f"  Domain:     {a.get('domain', '')}")
            click.echo(f"  Group:      {a.get('groupName', '')}")
            click.echo(f"  Site:       {a.get('siteName', '')}")
            click.echo(f"  Infected:   {a.get('infected', '')}")
            click.echo(f"  Machine:    {a.get('machineType', '')}")
            click.echo(f"  Last seen:  {a.get('lastActiveDate', '')}")
        else:
            click.echo(json.dumps(a))

    except LookupError as e:
        click.echo(str(e), err=True)
    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


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
def list_threats(obj, incident_status, from_, limit):
    """List threats."""
    try:
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

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@threat.command('get')
@click.argument('threat_id')
@click.pass_obj
def get_threat(obj, threat_id):
    """Get threat details."""
    try:
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

    except LookupError as e:
        click.echo(str(e), err=True)
    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.group()
def script():
    """Run and monitor remote scripts."""


@script.command('list')
@click.option('--query', '-q', help='Search scripts by name')
@click.option('--os', 'os_types', help='Filter by OS type (linux, windows, macos)')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
def list_scripts(obj, query, os_types, limit):
    """List available remote scripts."""
    try:
        scripts, pagination = obj['client'].list_scripts(
            limit=limit, query=query, os_types=os_types,
        )

        if sys.stdout.isatty():
            table = Table('id', 'name', 'os', 'type', 'description', title='Scripts')
            for s in scripts:
                table.add_row(
                    s.get('id', ''),
                    s.get('scriptName', ''),
                    ', '.join(s.get('osTypes', [])),
                    s.get('scriptType', ''),
                    (s.get('scriptDescription', '') or '')[:60],
                )
            console = Console()
            console.print(table)
            console.print(f"total: {pagination.get('totalItems', len(scripts))}")
        else:
            click.echo(json.dumps(scripts))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@script.command('run')
@click.argument('script_id')
@click.option('--agent', '-a', 'agent_name', default=None, help='Target agent by hostname')
@click.option('--group', '-g', 'group_ids', default=None, help='Target agents by group ID (comma-separated)')
@click.option('--site', '-s', 'site_ids', default=None, help='Target agents by site ID (comma-separated)')
@click.option('--all', 'target_all', is_flag=True, help='Target all agents')
@click.option('--params', '-p', 'input_params', default=None, help='Input parameters for the script')
@click.option('--description', '-d', 'description', default='sextant remote script execution', help='Task description')
@click.option('--timeout', '-t', default=3600, help='Script runtime timeout in seconds')
@click.option('--output', 'output_dest', default='SentinelCloud',
              type=click.Choice(['SentinelCloud', 'Local', 'None'], case_sensitive=True),
              help='Output destination')
@click.pass_obj
def run_script(obj, script_id, agent_name, group_ids, site_ids, target_all,
               input_params, description, timeout, output_dest):
    """Execute a remote script on one or more agents.

    Target agents with --agent (single hostname), --group, --site, or --all.
    """
    try:
        agent_filter = {}
        if agent_name:
            agent = obj['client'].get_agent(agent_name)
            agent_filter['ids'] = [agent['id']]
        elif group_ids:
            agent_filter['groupIds'] = [g.strip() for g in group_ids.split(',')]
        elif site_ids:
            agent_filter['siteIds'] = [s.strip() for s in site_ids.split(',')]
        elif target_all:
            agent_filter['isActive'] = [True]
        else:
            raise click.UsageError('Specify a target: --agent, --group, --site, or --all')

        result = obj['client'].execute_script(
            script_id=script_id,
            agent_filter=agent_filter,
            description=description,
            output_destination=output_dest,
            input_params=input_params,
            timeout=timeout,
        )

        if result.get('pending'):
            click.echo(f"pending approval (id: {result.get('pendingExecutionId', '')})")
        else:
            click.echo(f"task started (id: {result.get('parentTaskId', '')}), affected: {result.get('affected', 0)}")

    except LookupError as e:
        click.echo(str(e), err=True)
    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@script.command('status')
@click.argument('task_id')
@click.pass_obj
def script_status(obj, task_id):
    """Check execution status of a remote script task."""
    try:
        tasks, pagination = obj['client'].get_script_status(task_id)

        if sys.stdout.isatty():
            table = Table('id', 'agent', 'status', 'details', title='Script Status')
            for t in tasks:
                table.add_row(
                    t.get('id', ''),
                    t.get('agentComputerName', ''),
                    t.get('status', ''),
                    t.get('detailedStatus', ''),
                )
            Console().print(table)
        else:
            click.echo(json.dumps(tasks))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@script.command('results')
@click.argument('task_id')
@click.option('--output', '-o', 'output_dir', default='.', help='Directory to save result files')
@click.pass_obj
def script_results(obj, task_id, output_dir):
    """Download script result files by parent task ID."""
    try:
        tasks, _ = obj['client'].get_script_status(task_id)
        task_ids = [t['id'] for t in tasks]
        if not task_ids:
            click.echo('no tasks found for this task id', err=True)
            return

        links, errors = obj['client'].get_script_results(task_ids)

        for link in links:
            raw_name = link.get('fileName', f"{link.get('taskId', 'unknown')}.zip")
            filename = raw_name.removesuffix('.zip') if raw_name.endswith('.zip.zip') else raw_name
            dest = Path(output_dir) / filename
            click.echo(f"downloading {filename}...")
            obj['client'].download_file(link['downloadUrl'], dest)
            click.echo(f"saved {dest}")

            with zipfile.ZipFile(dest) as zf:
                entries = zf.namelist()
                click.echo(click.style(f"[files]", bold=True))
                for name in entries:
                    size = zf.getinfo(name).file_size
                    click.echo(f"  {name} ({size}B)")
                for name in entries:
                    if name.startswith(('stdout', 'stderr')):
                        label = 'stderr' if name.startswith('stderr') else 'stdout'
                        content = zf.read(name).decode(errors='replace').rstrip()
                        if content:
                            click.echo(click.style(f"[{label}]", bold=True))
                            click.echo(content)

        for err in errors:
            click.echo(f"error for task {err.get('taskId', '')}: {err.get('errorString', '')}", err=True)

        if not links and not errors:
            click.echo('no results available yet')

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.group()
def activity():
    """Browse activity log."""


@activity.command('list')
@click.option('--from', '-f', 'from_', default='1h', help='Relative time window')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
def list_activities(obj, from_, limit):
    """List recent activities."""
    try:
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

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)
