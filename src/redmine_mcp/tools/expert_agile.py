"""
redmine_expert_agile: sprints and the agile data (story points, sprint) of issues.

Story points and sprint are not part of the issue JSON, only of /issues/:id/expert_agile_data.json, so
sprint totals are computed here from one agile data request per issue.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from redminelib import exceptions

from .. import serialize
from . import changed, compact, merge_extra, page
from .standard import Extra, Limit, Offset, Project

Date = Annotated[str, Field(description='YYYY-MM-DD')]
MAX_SPRINT_ISSUES = 200


def _agile_data(redmine, issue_id):
    try:
        return redmine.expert_agile_data.get(issue_id).raw()
    except exceptions.ResourceNotFoundError:
        return {}


def register(tool, redmine):
    @tool()
    def list_sprints(project: Project, limit: Limit = 25, offset: Offset = 0) -> dict:
        """
        Sprints of a project (active first, then open, then closed), without sprints shared in from other
        projects. Needs the manage_expert_agile_sprints permission.
        """
        return page(redmine.expert_agile_sprint, {'project_id': project}, limit, offset)

    @tool()
    def get_sprint(project: Project, sprint_id: int) -> dict:
        """A sprint with the number of issues and the sum of story points (both only counting visible issues)."""
        return serialize.resource(redmine.expert_agile_sprint.get(sprint_id, project_id=project))

    @tool()
    def get_sprint_overview(
        project: Project,
        sprint: Annotated[str, Field(description='"active" for the current sprint or a sprint id')] = 'active',
    ) -> dict:
        """
        Issues of a sprint with their story points, and totals per status and assignee (done = closed issues).
        Answers "what is in the current sprint", "how many points are done", "points per person".
        """
        if sprint != 'active' and not sprint.isdigit():
            raise ToolError('sprint must be "active" or a sprint id')

        issues = []
        offset = 0
        more = True

        while more and len(issues) < MAX_SPRINT_ISSUES:
            chunk = page(
                redmine.issue,
                {'project_id': project, 'expert_agile_sprint_id': sprint, 'status_id': '*'},
                serialize.MAX_LIMIT,
                offset,
            )
            issues.extend(chunk['items'])
            more = 'next_offset' in chunk
            offset = chunk.get('next_offset', offset)

        truncated = more or len(issues) > MAX_SPRINT_ISSUES
        issues = issues[:MAX_SPRINT_ISSUES]

        with ThreadPoolExecutor(max_workers=8) as pool:
            agile = list(pool.map(lambda issue: _agile_data(redmine, issue['id']), issues))

        totals = {'issues': 0, 'story_points': 0, 'done_story_points': 0, 'unestimated_issues': 0}
        by_status = defaultdict(lambda: {'issues': 0, 'story_points': 0})
        by_assignee = defaultdict(lambda: {'issues': 0, 'open_issues': 0, 'story_points': 0, 'done_story_points': 0})
        items = []
        # Redmine silently ignores the sprint filter where the agile module is off, the agile data is the truth
        not_in_sprint = 0

        for issue, data in zip(issues, agile, strict=True):
            sprint_id = data.get('sprint_id')

            if sprint_id is None or (sprint.isdigit() and sprint_id != int(sprint)):
                not_in_sprint += 1
                continue

            sp = data.get('story_points')
            totals['issues'] += 1
            closed = issue['status'].get('is_closed', False)
            status = issue['status']['name']
            assignee = issue.get('assigned_to', {}).get('name', '(unassigned)')
            value = sp or 0

            totals['story_points'] += value
            totals['done_story_points'] += value if closed else 0
            totals['unestimated_issues'] += sp is None
            by_status[status]['issues'] += 1
            by_status[status]['story_points'] += value
            by_assignee[assignee]['issues'] += 1
            by_assignee[assignee]['open_issues'] += not closed
            by_assignee[assignee]['story_points'] += value
            by_assignee[assignee]['done_story_points'] += value if closed else 0
            items.append(
                {
                    'id': issue['id'],
                    'subject': issue['subject'],
                    'tracker': issue['tracker']['name'],
                    'status': status,
                    'closed': closed,
                    'assigned_to': assignee,
                    'story_points': sp,
                }
            )

        return {
            'project': project,
            'sprint': sprint,
            'totals': totals,
            'by_status': dict(by_status),
            'by_assignee': dict(by_assignee),
            'issues': items,
            'truncated': truncated,
            'ignored_issues_not_in_sprint': not_in_sprint,
        }

    @tool()
    def get_issue_agile_data(issue_id: int) -> dict:
        """Story points, sprint id and board position of an issue (all null when never set)."""
        return serialize.resource(redmine.expert_agile_data.get(issue_id))

    @tool(write=True)
    def create_sprint(
        project: Project, name: str, start_date: Date, end_date: Date, description: str | None = None
    ) -> dict:
        """Creates a sprint. Names are unique per project, unshared sprints of a project must not overlap."""
        fields = compact(
            project_id=project, name=name, start_date=start_date, end_date=end_date, description=description
        )
        return changed(redmine.expert_agile_sprint.create(**fields))

    @tool(write=True)
    def update_sprint(
        project: Project,
        sprint_id: int,
        status: Annotated[
            Literal['open', 'active', 'closed'] | None,
            Field(
                description='active makes it the active sprint (the previous one goes back to open), '
                'closed is refused while the sprint has open issues'
            ),
        ] = None,
        name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Changes a sprint, also used to activate or close it."""
        sprint = redmine.expert_agile_sprint.get(sprint_id, project_id=project)
        sprint.save(
            **compact(status=status, name=name, start_date=start_date, end_date=end_date, description=description)
        )
        return changed(sprint)

    @tool(write=True)
    def update_issue_agile_data(
        issue_id: int,
        story_points: int | None = None,
        sprint_id: Annotated[
            int | None,
            Field(description='Open or active sprint to move the issue into, needs manage_expert_agile_backlog'),
        ] = None,
        extra: Extra = None,
    ) -> dict:
        """Sets story points and/or the sprint of an issue."""
        fields = merge_extra(compact(story_points=story_points, sprint_id=sprint_id), extra)
        return changed(redmine.expert_agile_data.update(issue_id, **fields), issue_id=issue_id)
