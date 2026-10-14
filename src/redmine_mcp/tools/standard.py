"""
Core Redmine: projects, issues, time tracking, versions, wiki, search and reference data.
"""

from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page, require_one

Project = Annotated[str, Field(description='Project identifier (e.g. "support") or numeric id')]
Limit = Annotated[int, Field(ge=1, le=serialize.MAX_LIMIT, description='Page size')]
Offset = Annotated[int, Field(ge=0, description='Items to skip, use next_offset of the previous page')]
Extra = Annotated[
    dict[str, Any] | None,
    Field(description='Additional Redmine API fields, e.g. {"custom_fields": [{"id": 5, "value": "x"}]}'),
]

ISSUE_INCLUDES = ('journals', 'attachments', 'relations', 'children', 'watchers', 'changesets', 'allowed_statuses')
REFERENCE_DATA = {
    'issue_statuses': lambda r: r.issue_status.all(),
    'trackers': lambda r: r.tracker.all(),
    'issue_priorities': lambda r: r.enumeration.filter(resource='issue_priorities'),
    'time_entry_activities': lambda r: r.enumeration.filter(resource='time_entry_activities'),
    'document_categories': lambda r: r.enumeration.filter(resource='document_categories'),
    'custom_fields': lambda r: r.custom_field.all(),
    'queries': lambda r: r.query.all(),
    'roles': lambda r: r.role.all(),
    'groups': lambda r: r.group.all(),
}
MAX_DOWNLOAD_BYTES = 5_000_000


def register(tool, redmine):
    @tool()
    def get_current_user() -> dict:
        """The Redmine user this server acts as, with its memberships."""
        return serialize.resource(redmine.user.get('current', include=['memberships', 'groups']))

    @tool()
    def list_projects(limit: Limit = 25, offset: Offset = 0) -> dict:
        """Projects visible to the server's Redmine user."""
        return page(redmine.project, {}, limit, offset, method='all')

    @tool()
    def get_project(project: Project) -> dict:
        """A project with its trackers, issue categories, enabled modules and time entry activities."""
        return serialize.resource(
            redmine.project.get(
                project, include=['trackers', 'issue_categories', 'enabled_modules', 'time_entry_activities']
            )
        )

    @tool()
    def search_issues(
        project: Project | None = None,
        status: Annotated[str, Field(description='"open", "closed", "*" (all) or a status id')] = 'open',
        assigned_to: Annotated[str | None, Field(description='User id or "me"')] = None,
        tracker_id: int | None = None,
        fixed_version_id: int | None = None,
        parent_id: int | None = None,
        query_id: Annotated[int | None, Field(description='Saved query id, see list_reference_data("queries")')] = None,
        subject: Annotated[str | None, Field(description='Subject contains, e.g. "~printer"')] = None,
        updated_on: Annotated[str | None, Field(description='e.g. ">=2026-01-01" or "><2026-01-01|2026-01-31"')] = None,
        sort: Annotated[str | None, Field(description='e.g. "updated_on:desc,priority"')] = None,
        filters: Annotated[
            dict[str, Any] | None,
            Field(description='More Redmine issue filters, e.g. {"cf_12": "foo", "author_id": "me"}'),
        ] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Issues matching the filters (long descriptions are shortened, use get_issue for the full issue)."""
        params = compact(
            project_id=project,
            status_id=status,
            assigned_to_id=assigned_to,
            tracker_id=tracker_id,
            fixed_version_id=fixed_version_id,
            parent_id=parent_id,
            query_id=query_id,
            sort=sort,
            updated_on=updated_on,
            subject=subject,
        )
        return page(redmine.issue, merge_extra(params, filters), limit, offset)

    @tool()
    def get_issue(
        issue_id: int,
        include: Annotated[
            list[Literal[ISSUE_INCLUDES]] | None,
            Field(description='Defaults to journals, attachments, relations, children'),
        ] = None,
    ) -> dict:
        """A single issue with its history (journals), attachments, relations and subtasks."""
        include = include or ['journals', 'attachments', 'relations', 'children']
        return serialize.resource(redmine.issue.get(issue_id, include=include))

    @tool()
    def list_time_entries(
        project: Project | None = None,
        issue_id: int | None = None,
        user: Annotated[str | None, Field(description='User id or "me"')] = None,
        from_date: Annotated[str | None, Field(description='YYYY-MM-DD')] = None,
        to_date: Annotated[str | None, Field(description='YYYY-MM-DD')] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Spent time entries."""
        params = compact(project_id=project, issue_id=issue_id, user_id=user, from_date=from_date, to_date=to_date)
        return page(redmine.time_entry, params, limit, offset)

    @tool()
    def list_versions(project: Project, limit: Limit = 25, offset: Offset = 0) -> dict:
        """Versions (milestones/releases) of a project, including shared ones."""
        return page(redmine.version, {'project_id': project}, limit, offset)

    @tool()
    def list_project_members(project: Project, limit: Limit = 25, offset: Offset = 0) -> dict:
        """Members of a project with their roles."""
        return page(redmine.project_membership, {'project_id': project}, limit, offset)

    @tool()
    def list_wiki_pages(project: Project, limit: Limit = 100, offset: Offset = 0) -> dict:
        """Index of the wiki pages of a project."""
        return page(redmine.wiki_page, {'project_id': project}, limit, offset)

    @tool()
    def get_wiki_page(project: Project, title: str, version: int | None = None) -> dict:
        """A wiki page with its text, optionally an older version."""
        params = compact(project_id=project, version=version, include='attachments')
        return serialize.resource(redmine.wiki_page.get(title, **params))

    @tool()
    def search(
        query: str,
        project: Annotated[str | None, Field(description='Limit the search to this project')] = None,
        types: Annotated[
            list[Literal['issues', 'news', 'documents', 'changesets', 'wiki_pages', 'messages', 'projects']] | None,
            Field(description='What to search, defaults to everything'),
        ] = None,
        titles_only: bool = False,
        open_issues: bool = False,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Redmine full text search across issues, wiki pages, news, documents, changesets and forum messages."""
        limit = serialize.clamp_limit(limit)
        url = f'{redmine.url}/projects/{project}/search.json' if project else f'{redmine.url}/search.json'
        params = {'q': query, 'limit': limit, 'offset': offset}

        for name in types or ():
            params[name] = 1
        if titles_only:
            params['titles_only'] = 1
        if open_issues:
            params['open_issues'] = 1

        response = redmine.engine.request('get', url, params=params)
        items = response.get('results', [])
        result = {'total_count': response.get('total_count', len(items)), 'offset': offset, 'items': items}

        if offset + len(items) < result['total_count']:
            result['next_offset'] = offset + len(items)

        return result

    @tool()
    def list_reference_data(kind: Literal[tuple(REFERENCE_DATA)]) -> dict:
        """
        Ids and names needed for filters and changes: issue statuses, trackers, priorities, time entry activities,
        document categories, custom fields (admin only), saved queries, roles, groups (admin only).
        """
        items = [serialize.resource(res) for res in REFERENCE_DATA[kind](redmine)]
        return {'kind': kind, 'count': len(items), 'items': items}

    @tool()
    def get_attachment(
        attachment_id: int,
        include_content: Annotated[bool, Field(description='Return the content of text files')] = False,
        max_chars: int = 50_000,
    ) -> dict:
        """Metadata of an attachment and, for text files, optionally its content."""
        attachment = redmine.attachment.get(attachment_id)
        result = serialize.resource(attachment)

        if include_content:
            content_type = result.get('content_type') or ''

            if not content_type.startswith('text/') and content_type not in ('application/json', 'application/xml'):
                result['content_error'] = f'Content of {content_type or "unknown"} files is not returned'
            elif (result.get('filesize') or 0) > MAX_DOWNLOAD_BYTES:
                result['content_error'] = f'File is larger than {MAX_DOWNLOAD_BYTES // 1_000_000} MB'
            else:
                text = attachment.download().content.decode('utf-8', errors='replace')
                result['content'] = text[:max_chars]
                result['content_truncated'] = len(text) > max_chars

        return result

    # Write tools, not registered in read-only mode

    @tool(write=True)
    def create_issue(
        project: Project,
        subject: str,
        description: str | None = None,
        tracker_id: int | None = None,
        status_id: int | None = None,
        priority_id: int | None = None,
        assigned_to_id: int | None = None,
        category_id: int | None = None,
        fixed_version_id: int | None = None,
        parent_issue_id: int | None = None,
        start_date: Annotated[str | None, Field(description='YYYY-MM-DD')] = None,
        due_date: Annotated[str | None, Field(description='YYYY-MM-DD')] = None,
        estimated_hours: float | None = None,
        is_private: bool | None = None,
        extra: Extra = None,
    ) -> dict:
        """Creates an issue."""
        fields = compact(
            project_id=project,
            subject=subject,
            description=description,
            tracker_id=tracker_id,
            status_id=status_id,
            priority_id=priority_id,
            assigned_to_id=assigned_to_id,
            category_id=category_id,
            fixed_version_id=fixed_version_id,
            parent_issue_id=parent_issue_id,
            start_date=start_date,
            due_date=due_date,
            estimated_hours=estimated_hours,
            is_private=is_private,
        )
        return changed(redmine.issue.create(**merge_extra(fields, extra)))

    @tool(write=True)
    def update_issue(
        issue_id: int,
        notes: Annotated[str | None, Field(description='Comment added to the history')] = None,
        private_notes: bool | None = None,
        subject: str | None = None,
        description: str | None = None,
        tracker_id: int | None = None,
        status_id: int | None = None,
        priority_id: int | None = None,
        assigned_to_id: Annotated[int | None, Field(description='0 to unassign')] = None,
        category_id: int | None = None,
        fixed_version_id: int | None = None,
        parent_issue_id: int | None = None,
        start_date: str | None = None,
        due_date: str | None = None,
        estimated_hours: float | None = None,
        done_ratio: int | None = None,
        extra: Extra = None,
    ) -> dict:
        """Changes fields of an issue and/or adds a comment."""
        fields = compact(
            notes=notes,
            private_notes=private_notes,
            subject=subject,
            description=description,
            tracker_id=tracker_id,
            status_id=status_id,
            priority_id=priority_id,
            assigned_to_id=assigned_to_id,
            category_id=category_id,
            fixed_version_id=fixed_version_id,
            parent_issue_id=parent_issue_id,
            start_date=start_date,
            due_date=due_date,
            estimated_hours=estimated_hours,
            done_ratio=done_ratio,
        )
        fields = merge_extra(fields, extra)

        if not fields:
            raise ToolError('Nothing to change')

        return changed(redmine.issue.update(issue_id, **fields), issue_id=issue_id)

    @tool(write=True)
    def log_time(
        hours: float,
        issue_id: int | None = None,
        project: Project | None = None,
        activity_id: Annotated[
            int | None, Field(description='See list_reference_data("time_entry_activities")')
        ] = None,
        spent_on: Annotated[str | None, Field(description='YYYY-MM-DD, defaults to today')] = None,
        comments: str | None = None,
        extra: Extra = None,
    ) -> dict:
        """Logs spent time on an issue or project for the server's Redmine user."""
        require_one(issue_id=issue_id, project=project)
        fields = compact(
            hours=hours,
            issue_id=issue_id,
            project_id=project,
            activity_id=activity_id,
            spent_on=spent_on,
            comments=comments,
        )
        return changed(redmine.time_entry.create(**merge_extra(fields, extra)))

    @tool(write=True)
    def create_issue_relation(
        issue_id: int,
        issue_to_id: int,
        relation_type: Literal[
            'relates',
            'duplicates',
            'duplicated',
            'blocks',
            'blocked',
            'precedes',
            'follows',
            'copied_to',
            'copied_from',
        ] = 'relates',
        delay: Annotated[int | None, Field(description='Days, only for precedes/follows')] = None,
    ) -> dict:
        """Links two issues."""
        fields = compact(issue_id=issue_id, issue_to_id=issue_to_id, relation_type=relation_type, delay=delay)
        return changed(redmine.issue_relation.create(**fields))

    @tool(write=True, destructive=True, idempotent=True)
    def save_wiki_page(
        project: Project,
        title: str,
        text: Annotated[str, Field(description='Complete new page text, replaces the current one')],
        comments: Annotated[str | None, Field(description='Change comment')] = None,
        parent_title: str | None = None,
    ) -> dict:
        """Creates a wiki page or replaces the text of an existing one (the old text stays in the page history)."""
        fields = compact(project_id=project, text=text, comments=comments, parent_title=parent_title)
        return changed(redmine.wiki_page.update(title, **fields), project=project, title=title)
