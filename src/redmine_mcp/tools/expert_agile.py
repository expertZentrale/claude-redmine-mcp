"""
redmine_expert_agile: sprints and the agile data (story points, sprint) of issues.
"""

from typing import Annotated, Literal

from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page
from .standard import Extra, Limit, Offset, Project

Date = Annotated[str, Field(description='YYYY-MM-DD')]


def register(tool, redmine):
    @tool()
    def list_sprints(project: Project, limit: Limit = 25, offset: Offset = 0) -> dict:
        """Sprints of a project."""
        return page(redmine.expert_agile_sprint, {'project_id': project}, limit, offset)

    @tool()
    def get_sprint(project: Project, sprint_id: int) -> dict:
        """A sprint with issue count and story points."""
        return serialize.resource(redmine.expert_agile_sprint.get(sprint_id, project_id=project))

    @tool()
    def get_issue_agile_data(issue_id: int) -> dict:
        """Story points, sprint and board position of an issue."""
        return serialize.resource(redmine.expert_agile_data.get(issue_id))

    @tool(write=True)
    def create_sprint(
        project: Project, name: str, start_date: Date, end_date: Date, description: str | None = None
    ) -> dict:
        """Creates a sprint."""
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
            Field(description='active makes it the active sprint, closed is refused while it has open issues'),
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
        sprint_id: Annotated[int | None, Field(description='Sprint to move the issue into')] = None,
        extra: Extra = None,
    ) -> dict:
        """Sets story points and/or the sprint of an issue."""
        fields = merge_extra(compact(story_points=story_points, sprint_id=sprint_id), extra)
        return changed(redmine.expert_agile_data.update(issue_id, **fields), issue_id=issue_id)
