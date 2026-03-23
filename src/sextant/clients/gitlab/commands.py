import sys
import click
import httpx
import json
from rich.console import Console
from rich.table import Table
from sextant.utils import Lazy
from sextant.clients.gitlab.client import GitLabClient


PIPELINE_STATUS_STYLE = {
    'success': 'green',
    'failed': 'red',
    'running': 'blue',
    'pending': 'yellow',
    'canceled': 'dim',
    'skipped': 'dim',
}


@click.group()
@click.pass_context
def main(ctx):
    """Interact with GitLab."""
    def factory():
        config = ctx.obj['config'].reveal(ctx.info_name)
        return GitLabClient.from_config(config)

    client = Lazy(factory)
    ctx.obj['client'] = client

    def cleanup():
        if client._instance is not None:
            client._instance.http.close()
    ctx.call_on_close(cleanup)


@main.group()
def project():
    """Manage projects."""


@project.command('list')
@click.option('--search', '-s', help='Search project name')
@click.option('--all', 'all_', is_flag=True, help='Include non-member projects')
@click.pass_obj
def list_project(obj, search, all_):
    """List projects."""
    try:
        projects = obj['client'].list_projects(search=search, membership=not all_)

        if sys.stdout.isatty():
            table = Table('id', 'project', 'visibility', 'url')
            for p in projects:
                table.add_row(
                    str(p['id']),
                    p['path_with_namespace'],
                    p['visibility'],
                    p['web_url'],
                )
            Console().print(table)
        else:
            click.echo(json.dumps(projects))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@project.command('get')
@click.argument('project_id')
@click.pass_obj
def get_project(obj, project_id):
    """Get project details."""
    try:
        p = obj['client'].get_project(project_id)

        if sys.stdout.isatty():
            click.echo(click.style(p['name_with_namespace'], bold=True))
            click.echo(p.get('description', ''))
            click.echo(click.style('Info:', bold=True))
            click.echo(f"URL: {p['web_url']}")
            click.echo(f"Default branch: {p['default_branch']}")
            click.echo(f"Visibility: {p['visibility']}")
            click.echo(f"Forks: {p['forks_count']}")
            click.echo(f"Stars: {p['star_count']}")
            click.echo(f"Open issues: {p['open_issues_count']}")
        else:
            click.echo(json.dumps(p))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.group()
def mr():
    """Manage merge requests."""


@mr.command('list')
@click.option('--project', '-p', 'project_id', help='Project ID or URL-encoded path')
@click.option('--state', type=click.Choice(['opened', 'closed', 'merged', 'all']), default='opened')
@click.option('--author', help='Filter by author username')
@click.pass_obj
def list_mr(obj, project_id, state, author):
    """List merge requests."""
    try:
        mrs = obj['client'].list_merge_requests(
            project_id=project_id, state=state, author=author,
        )

        if sys.stdout.isatty():
            table = Table('iid', 'project', 'state', 'author', 'title')
            for m in mrs:
                style = 'green' if m['state'] == 'merged' else 'default'
                table.add_row(
                    str(m['iid']),
                    m['references']['full'],
                    m['state'],
                    m['author']['username'],
                    m['title'],
                    style=style,
                )
            Console().print(table)
        else:
            click.echo(json.dumps(mrs))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@mr.command('get')
@click.argument('project_id')
@click.argument('mr_iid')
@click.pass_obj
def get_mr(obj, project_id, mr_iid):
    """Get merge request details."""
    try:
        m = obj['client'].get_merge_request(project_id, mr_iid)

        if sys.stdout.isatty():
            click.echo(click.style(f"!{m['iid']} {m['title']}", bold=True))
            click.echo(f"State: {m['state']}")
            click.echo(f"Author: {m['author']['username']}")
            click.echo(f"Source: {m['source_branch']} -> {m['target_branch']}")
            click.echo(f"URL: {m['web_url']}")
            if m.get('description'):
                click.echo(click.style('Description:', bold=True))
                click.echo(m['description'])
        else:
            click.echo(json.dumps(m))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.group()
def issue():
    """Manage issues."""


@issue.command('list')
@click.option('--project', '-p', 'project_id', help='Project ID or URL-encoded path')
@click.option('--state', type=click.Choice(['opened', 'closed', 'all']), default='opened')
@click.option('--assignee', help='Filter by assignee username')
@click.pass_obj
def list_issue(obj, project_id, state, assignee):
    """List issues."""
    try:
        issues = obj['client'].list_issues(
            project_id=project_id, state=state, assignee=assignee,
        )

        if sys.stdout.isatty():
            table = Table('iid', 'project', 'state', 'author', 'title')
            for i in issues:
                table.add_row(
                    str(i['iid']),
                    i['references']['full'],
                    i['state'],
                    i['author']['username'],
                    i['title'],
                )
            Console().print(table)
        else:
            click.echo(json.dumps(issues))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@main.group()
def pipeline():
    """Manage pipelines."""


@pipeline.command('list')
@click.argument('project_id')
@click.option('--status', type=click.Choice(['running', 'pending', 'success', 'failed', 'canceled', 'skipped']))
@click.option('--ref', help='Filter by branch or tag')
@click.pass_obj
def list_pipeline(obj, project_id, status, ref):
    """List pipelines for a project."""
    try:
        pipelines = obj['client'].list_pipelines(
            project_id, status=status, ref=ref,
        )

        if sys.stdout.isatty():
            table = Table('id', 'status', 'ref', 'sha', 'url')
            for p in pipelines:
                style = PIPELINE_STATUS_STYLE.get(p['status'], 'default')
                table.add_row(
                    str(p['id']),
                    p['status'],
                    p['ref'],
                    p['sha'][:8],
                    p['web_url'],
                    style=style,
                )
            Console().print(table)
        else:
            click.echo(json.dumps(pipelines))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)


@pipeline.command('get')
@click.argument('project_id')
@click.argument('pipeline_id')
@click.pass_obj
def get_pipeline(obj, project_id, pipeline_id):
    """Get pipeline details and jobs."""
    try:
        p = obj['client'].get_pipeline(project_id, pipeline_id)
        jobs = obj['client'].list_pipeline_jobs(project_id, pipeline_id)

        if sys.stdout.isatty():
            click.echo(click.style(f"Pipeline #{p['id']}", bold=True))
            click.echo(f"Status: {p['status']}")
            click.echo(f"Ref: {p['ref']}")
            click.echo(f"SHA: {p['sha']}")
            click.echo(f"URL: {p['web_url']}")

            if jobs:
                table = Table('id', 'name', 'stage', 'status', 'duration')
                for j in jobs:
                    style = PIPELINE_STATUS_STYLE.get(j['status'], 'default')
                    duration = f"{j['duration']:.0f}s" if j.get('duration') else '-'
                    table.add_row(
                        str(j['id']),
                        j['name'],
                        j['stage'],
                        j['status'],
                        duration,
                        style=style,
                    )
                Console().print(table)
        else:
            click.echo(json.dumps({'pipeline': p, 'jobs': jobs}))

    except httpx.HTTPStatusError as e:
        click.echo(e.response.text, err=True)
