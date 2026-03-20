import functools
import json
import sys
from datetime import datetime

import click
import httpx
from rich.console import Console
from rich.table import Table

from sextant.clients.sysdig.client import SysdigClient
from sextant.utils import Lazy, humanize, deshumanize

SEVERITY_LABELS = {0: 'none', 1: 'info', 2: 'low', 3: 'low', 4: 'medium', 5: 'medium', 6: 'high', 7: 'high'}

SEVERITY_COLORS = {
    'info': 'blue', 'low': 'cyan', 'medium': 'yellow', 'high': 'red', 'none': 'dim',
}


def handle_errors(f):
    """Catch common exceptions and print them to stderr."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except LookupError as e:
            click.echo(str(e), err=True)
        except httpx.HTTPStatusError as e:
            click.echo(f"{e.response.status_code} {e.response.reason_phrase}", err=True)
    return wrapper


def severity_label(value):
    """Convert numeric severity (0-7) to a display label."""
    try:
        return SEVERITY_LABELS.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def severity_styled(value):
    """Return a Rich-styled severity string."""
    label = severity_label(value)
    color = SEVERITY_COLORS.get(label, 'default')
    return f'[{color}]{label}[/{color}]'


@click.group()
@click.pass_context
def main(ctx):
    """Manage Sysdig Secure."""
    def factory():
        config = ctx.obj['config'].reveal(ctx.info_name)
        return SysdigClient.from_config(config)

    client = Lazy(factory)
    ctx.obj['client'] = client

    def cleanup():
        if client._instance is not None:
            client._instance.http.close()
    ctx.call_on_close(cleanup)


@main.group()
def event():
    """Browse security events."""


@event.command('list')
@click.option('--from', '-f', 'from_', default='1h', help='Relative time window (e.g. 1h, 7d)')
@click.option('--severity', '-s', default=None, help='Min severity filter (e.g. 4)')
@click.option('--limit', '-n', default=50, help='Max results to return')
@click.pass_obj
@handle_errors
def list_events(obj, from_, severity, limit):
    """List recent security events.

    \b
    Examples:
      sextant sysdig event list
      sextant sysdig event list --from 24h
      sextant sysdig event list --from 7d -s 4
    """
    now = datetime.utcnow()
    from_dt = now - deshumanize(from_)
    from_ns = int(from_dt.timestamp()) * 1_000_000_000
    to_ns = int(now.timestamp()) * 1_000_000_000

    sev_filter = f'severity >= "{severity}"' if severity else None
    events, page = obj['client'].list_events(
        limit=limit, from_ns=from_ns, to_ns=to_ns, filter=sev_filter,
    )

    if sys.stdout.isatty():
        table = Table('id', 'ago', 'severity', 'rule', 'source', title='Events')
        for e in events:
            ts = e.get('timestamp', 0)
            try:
                ago = humanize(datetime.utcfromtimestamp(ts / 1_000_000_000))
            except (ValueError, OSError):
                ago = ''
            table.add_row(
                str(e.get('id', '')),
                ago,
                severity_styled(e.get('severity', '')),
                e.get('ruleName', ''),
                e.get('source', ''),
            )
        console = Console()
        console.print(table)
    else:
        click.echo(json.dumps(events))


@event.command('get')
@click.argument('event_id')
@click.pass_obj
@handle_errors
def get_event(obj, event_id):
    """Get event details.

    \b
    Examples:
      sextant sysdig event get 123456
    """
    e = obj['client'].get_event(event_id)
    if sys.stdout.isatty():
        click.echo(click.style('Event Info', bold=True))
        click.echo(f"  ID:        {e.get('id', '')}")
        click.echo(f"  Severity:  {severity_label(e.get('severity', ''))}")
        click.echo(f"  Rule:      {e.get('ruleName', '')}")
        click.echo(f"  Source:    {e.get('source', '')}")
        click.echo(f"  Policy:    {e.get('policyId', '')}")
        click.echo(click.style('Output:', bold=True))
        click.echo(f"  {e.get('output', '')}")
        content = e.get('content', {})
        if content:
            click.echo(click.style('Content:', bold=True))
            for k, v in content.items():
                click.echo(f"  {k}: {v}")
    else:
        click.echo(json.dumps(e))


@main.group()
def policy():
    """Manage runtime policies."""


@policy.command('list')
@click.pass_obj
@handle_errors
def list_policies(obj):
    """List runtime policies.

    \b
    Examples:
      sextant sysdig policy list
    """
    policies = obj['client'].list_policies()

    if sys.stdout.isatty():
        table = Table('id', 'name', 'severity', 'type', 'enabled', title='Policies')
        for p in policies:
            enabled = '[green]yes[/green]' if p.get('enabled') else '[red]no[/red]'
            table.add_row(
                str(p.get('id', '')),
                p.get('name', ''),
                severity_styled(p.get('severity', '')),
                p.get('type', ''),
                enabled,
            )
        Console().print(table)
    else:
        click.echo(json.dumps(policies))


@policy.command('get')
@click.argument('policy_id')
@click.pass_obj
@handle_errors
def get_policy(obj, policy_id):
    """Get policy details.

    \b
    Examples:
      sextant sysdig policy get 12345
    """
    p = obj['client'].get_policy(policy_id)
    if sys.stdout.isatty():
        click.echo(click.style('Policy Info', bold=True))
        click.echo(f"  ID:          {p.get('id', '')}")
        click.echo(f"  Name:        {p.get('name', '')}")
        click.echo(f"  Description: {p.get('description', '')}")
        click.echo(f"  Severity:    {severity_label(p.get('severity', ''))}")
        click.echo(f"  Type:        {p.get('type', '')}")
        click.echo(f"  Enabled:     {p.get('enabled', '')}")
        click.echo(f"  Scope:       {p.get('scope', 'all')}")
        rules = p.get('ruleNames', [])
        if rules:
            click.echo(click.style('Rules:', bold=True))
            for r in rules:
                click.echo(f"  - {r}")
        actions = p.get('actions', [])
        if actions:
            click.echo(click.style('Actions:', bold=True))
            for a in actions:
                click.echo(f"  - {a.get('type', '')}")
    else:
        click.echo(json.dumps(p))


@main.group()
def alert():
    """Manage alerts."""


@alert.command('list')
@click.pass_obj
@handle_errors
def list_alerts(obj):
    """List configured alerts.

    \b
    Examples:
      sextant sysdig alert list
    """
    alerts = obj['client'].list_alerts()

    if sys.stdout.isatty():
        table = Table('id', 'name', 'severity', 'enabled', 'type', title='Alerts')
        for a in alerts:
            enabled = '[green]yes[/green]' if a.get('enabled') else '[red]no[/red]'
            table.add_row(
                str(a.get('id', '')),
                a.get('name', ''),
                severity_styled(a.get('severity', '')),
                enabled,
                a.get('type', ''),
            )
        Console().print(table)
    else:
        click.echo(json.dumps(alerts))


@alert.command('get')
@click.argument('alert_id')
@click.pass_obj
@handle_errors
def get_alert(obj, alert_id):
    """Get alert details.

    \b
    Examples:
      sextant sysdig alert get 12345
    """
    a = obj['client'].get_alert(alert_id)
    if sys.stdout.isatty():
        click.echo(click.style('Alert Info', bold=True))
        click.echo(f"  ID:          {a.get('id', '')}")
        click.echo(f"  Name:        {a.get('name', '')}")
        click.echo(f"  Description: {a.get('description', '')}")
        click.echo(f"  Severity:    {severity_label(a.get('severity', ''))}")
        click.echo(f"  Type:        {a.get('type', '')}")
        click.echo(f"  Enabled:     {a.get('enabled', '')}")
        click.echo(f"  Condition:   {a.get('condition', '')}")
    else:
        click.echo(json.dumps(a))


@main.group()
def agent():
    """View connected agents."""


@agent.command('list')
@click.pass_obj
@handle_errors
def list_agents(obj):
    """List connected agents.

    \b
    Examples:
      sextant sysdig agent list
    """
    agents, total = obj['client'].list_connected_agents()

    if sys.stdout.isatty():
        table = Table('id', 'hostname', 'os', 'version', 'status', title='Connected Agents')
        for a in agents:
            status = '[green]connected[/green]' if a.get('status', '').lower() in ('connected', 'online') else a.get('status', '')
            table.add_row(
                str(a.get('id', '')),
                a.get('hostName', ''),
                a.get('os', ''),
                a.get('agentVersion', ''),
                status,
            )
        console = Console()
        console.print(table)
        console.print(f"total: {total}")
    else:
        click.echo(json.dumps(agents))
