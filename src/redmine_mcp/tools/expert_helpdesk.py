"""
redmine_expert_helpdesk: tickets, contacts, mailboxes and project settings.
"""

from typing import Annotated, Any

from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page
from .standard import Extra, Limit, Offset, Project

Filters = Annotated[dict[str, Any] | None, Field(description='More filters supported by the helpdesk API')]


def register(tool, redmine):
    @tool()
    def list_helpdesk_tickets(project: Project, filters: Filters = None, limit: Limit = 25, offset: Offset = 0) -> dict:
        """Helpdesk tickets of a project."""
        return page(redmine.helpdesk_ticket, merge_extra({'project_id': project}, filters), limit, offset)

    @tool()
    def get_helpdesk_ticket(ticket_id: int, include_messages: bool = True) -> dict:
        """A helpdesk ticket with its contact, mailbox, SLA state and, by default, the mail history."""
        params = {'include': ['messages']} if include_messages else {}
        return serialize.resource(redmine.helpdesk_ticket.get(ticket_id, **params))

    @tool()
    def list_helpdesk_contacts(
        project: Project,
        search: Annotated[str | None, Field(description='Name, email or company contains')] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Helpdesk contacts of a project."""
        return page(redmine.helpdesk_contact, compact(project_id=project, search=search), limit, offset)

    @tool()
    def get_helpdesk_contact(contact_id: int) -> dict:
        """A helpdesk contact."""
        return serialize.resource(redmine.helpdesk_contact.get(contact_id))

    @tool()
    def list_helpdesk_mailboxes(project: Project) -> dict:
        """Mailboxes configured for the helpdesk of a project."""
        return page(redmine.helpdesk_mailbox, {'project_id': project}, serialize.MAX_LIMIT, 0)

    @tool()
    def get_helpdesk_project_settings(project: Project) -> dict:
        """Helpdesk settings (SLA etc.) of a project."""
        return serialize.resource(redmine.helpdesk_project_setting.get(project))

    @tool(write=True)
    def create_helpdesk_ticket(
        project: Project,
        subject: str,
        description: str,
        contact_email: str,
        contact_name: str | None = None,
        tracker_id: int | None = None,
        mailbox_id: int | None = None,
        extra: Extra = None,
    ) -> dict:
        """Creates a helpdesk ticket for a contact."""
        fields = compact(
            project_id=project,
            subject=subject,
            description=description,
            contact_email=contact_email,
            contact_name=contact_name,
            tracker_id=tracker_id,
            mailbox_id=mailbox_id,
        )
        return changed(redmine.helpdesk_ticket.create(**merge_extra(fields, extra)))

    @tool(write=True)
    def update_helpdesk_ticket(
        ticket_id: int,
        notes: Annotated[str | None, Field(description='Internal comment added to the history')] = None,
        status_id: int | None = None,
        assigned_to_id: int | None = None,
        priority_id: int | None = None,
        extra: Extra = None,
    ) -> dict:
        """Changes a helpdesk ticket and/or adds a comment."""
        fields = compact(notes=notes, status_id=status_id, assigned_to_id=assigned_to_id, priority_id=priority_id)
        return changed(redmine.helpdesk_ticket.update(ticket_id, **merge_extra(fields, extra)), ticket_id=ticket_id)
