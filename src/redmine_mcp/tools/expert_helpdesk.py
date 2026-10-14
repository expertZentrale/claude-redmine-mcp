"""
redmine_expert_helpdesk: tickets, contacts, mailboxes and project settings.

The ticket list of the helpdesk API only pages (limit/offset) and silently ignores every filter, so filtered
ticket lists go through /issues.json and the issue query filters the plugin adds (helpdesk_kunde,
helpdesk_awaiting_agent, helpdesk_sla_reaction, helpdesk_sla_solution).
"""

from typing import Annotated, Literal

from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page
from .standard import Extra, Limit, Offset, Project

SlaState = Literal['met', 'running', 'warning', 'breached', 'breached_done']


def register(tool, redmine):
    @tool()
    def search_helpdesk_tickets(
        project: Project | None = None,
        customer: Annotated[
            str | None,
            Field(description='Name or email of the customer (contains, case-insensitive), e.g. "kaden" or "@acme.de"'),
        ] = None,
        awaiting_agent: Annotated[
            bool | None, Field(description='true: the customer wrote last and waits for an answer')
        ] = None,
        sla_reaction: Annotated[SlaState | None, Field(description='State of the reaction time SLA')] = None,
        sla_solution: Annotated[SlaState | None, Field(description='State of the solution time SLA')] = None,
        status: Annotated[str, Field(description='"open", "closed", "*" (all) or a status id')] = 'open',
        assigned_to: Annotated[str | None, Field(description='User id or "me"')] = None,
        sort: Annotated[str | None, Field(description='e.g. "updated_on:desc" or "helpdesk_sla_reaction"')] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """
        Helpdesk tickets filtered by customer, waiting state and SLA. Use this instead of list_helpdesk_tickets
        whenever a filter is needed. Returns issues, long descriptions are shortened.
        """
        params = compact(
            project_id=project,
            status_id=status,
            assigned_to_id=assigned_to,
            sort=sort,
            # Short form of the Redmine query syntax, ~ is "contains"
            helpdesk_kunde=f'~{customer}' if customer else None,
            helpdesk_awaiting_agent=None if awaiting_agent is None else int(awaiting_agent),
            helpdesk_sla_reaction=sla_reaction,
            helpdesk_sla_solution=sla_solution,
        )
        return page(redmine.issue, params, limit, offset)

    @tool()
    def list_helpdesk_tickets(project: Project, limit: Limit = 25, offset: Offset = 0) -> dict:
        """
        All helpdesk tickets of a project, newest first, closed ones included, with contact, mailbox and SLA.
        The API offers no filters here, use search_helpdesk_tickets to filter.
        """
        return page(redmine.helpdesk_ticket, {'project_id': project}, limit, offset)

    @tool()
    def get_helpdesk_ticket(ticket_id: int, include_messages: bool = True) -> dict:
        """
        A helpdesk ticket with contact, mailbox, SLA state and the mail log (direction in = customer mail,
        out = reply sent, init = contact assigned). The log has no mail text: the first mail is the description,
        replies and further mails are journals, see get_issue.
        """
        params = {'include': ['messages']} if include_messages else {}
        return serialize.resource(redmine.helpdesk_ticket.get(ticket_id, **params))

    @tool()
    def list_helpdesk_contacts(
        project: Project,
        search: Annotated[str | None, Field(description='Name, email or company contains')] = None,
        email: Annotated[str | None, Field(description='Exact email address, takes precedence over search')] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Helpdesk contacts (customers) of a project."""
        return page(redmine.helpdesk_contact, compact(project_id=project, search=search, email=email), limit, offset)

    @tool()
    def get_helpdesk_contact(contact_id: int) -> dict:
        """A helpdesk contact. Their tickets: search_helpdesk_tickets(customer=<email>)."""
        return serialize.resource(redmine.helpdesk_contact.get(contact_id))

    @tool()
    def list_helpdesk_mailboxes(project: Project) -> dict:
        """Mailboxes of the helpdesk of a project (needs the manage_helpdesk permission, secrets are never shown)."""
        return page(redmine.helpdesk_mailbox, {'project_id': project}, serialize.MAX_LIMIT, 0)

    @tool()
    def get_helpdesk_project_settings(project: Project) -> dict:
        """Helpdesk settings of a project: SLA times per priority, autoresponder, info requests, AI options."""
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
        """
        Creates a helpdesk ticket for a customer, creating the contact if needed. No mail is sent to the customer.
        Comments and status changes of helpdesk tickets go through update_issue, which also records the SLA
        first response.
        """
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
