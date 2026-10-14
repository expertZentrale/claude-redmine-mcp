"""
RedmineUP plugins: CRM (contacts, deals, notes), Helpdesk tickets, Agile and Checklists.
"""

from typing import Annotated, Any, Literal

from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page
from .standard import Limit, Offset, Project

Filters = Annotated[dict[str, Any] | None, Field(description='More filters supported by the plugin API')]


def register(tool, redmine):
    @tool()
    def list_contacts(
        project: Project | None = None,
        search: Annotated[str | None, Field(description='Name, email, phone or company contains')] = None,
        tags: Annotated[str | None, Field(description='Comma separated tag names')] = None,
        filters: Filters = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """RedmineUP CRM contacts."""
        params = merge_extra(compact(project_id=project, search=search, tags=tags), filters)
        return page(redmine.contact, params, limit, offset)

    @tool()
    def get_contact(contact_id: int) -> dict:
        """A RedmineUP CRM contact with notes, deals and related issues."""
        return serialize.resource(redmine.contact.get(contact_id, include=['notes', 'contacts', 'deals', 'issues']))

    @tool()
    def list_deals(
        project: Project | None = None,
        status_id: Annotated[str | None, Field(description='Deal status id, "*" for all')] = None,
        filters: Filters = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """RedmineUP CRM deals."""
        params = merge_extra(compact(project_id=project, status_id=status_id), filters)
        return page(redmine.deal, params, limit, offset)

    @tool()
    def get_deal(deal_id: int) -> dict:
        """A RedmineUP CRM deal with its notes."""
        return serialize.resource(redmine.deal.get(deal_id, include=['notes']))

    @tool()
    def list_redmineup_tickets(
        project: Project | None = None, filters: Filters = None, limit: Limit = 25, offset: Offset = 0
    ) -> dict:
        """RedmineUP Helpdesk tickets."""
        return page(redmine.ticket, merge_extra(compact(project_id=project), filters), limit, offset)

    @tool()
    def get_redmineup_ticket(issue_id: int) -> dict:
        """A RedmineUP Helpdesk ticket with its customer correspondence."""
        return serialize.resource(redmine.ticket.get(issue_id, include=['journals', 'journal_messages']))

    @tool()
    def list_redmineup_sprints(project: Project) -> dict:
        """RedmineUP Agile sprints of a project."""
        return page(redmine.agile_sprint, {'project_id': project}, serialize.MAX_LIMIT, 0)

    @tool()
    def get_checklist(issue_id: int) -> dict:
        """RedmineUP checklist items of an issue."""
        return page(redmine.checklist, {'issue_id': issue_id}, serialize.MAX_LIMIT, 0)

    @tool(write=True)
    def add_crm_note(
        source_type: Literal['Contact', 'Deal'],
        source_id: int,
        content: str,
        project: Project | None = None,
    ) -> dict:
        """Adds a note to a RedmineUP CRM contact or deal."""
        fields = compact(source_type=source_type, source_id=source_id, content=content, project_id=project)
        return changed(redmine.note.create(**fields))

    @tool(write=True)
    def add_checklist_item(issue_id: int, subject: str, is_done: bool = False) -> dict:
        """Adds an item to the RedmineUP checklist of an issue."""
        return changed(redmine.checklist.create(issue_id=issue_id, subject=subject, is_done=is_done))

    @tool(write=True)
    def update_checklist_item(checklist_id: int, is_done: bool | None = None, subject: str | None = None) -> dict:
        """Ticks/unticks or renames a RedmineUP checklist item."""
        fields = compact(is_done=is_done, subject=subject)
        return changed(redmine.checklist.update(checklist_id, **fields), checklist_id=checklist_id)
