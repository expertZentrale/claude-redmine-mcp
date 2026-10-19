"""
redmine_expert_helpdesk: tickets, contacts, mailboxes, project settings and the knowledge base.

The ticket list of the helpdesk API only pages (limit/offset) and silently ignores every filter, so filtered
ticket lists go through /issues.json and the issue query filters the plugin adds (helpdesk_kunde,
helpdesk_awaiting_agent, helpdesk_sla_reaction, helpdesk_sla_solution).

Knowledge base entries are problem/solution pairs extracted from closed tickets, approved ones are embedded
into a vector store for the AI answers. Deleting entries and the reindex/reextract jobs are left out: the
server deletes nothing, and a re-extraction costs one AI call per entry and overwrites uncurated entries.
"""

from typing import Annotated, Literal

from pydantic import Field

from .. import serialize
from . import changed, compact, merge_extra, page, require_one
from .standard import Extra, Limit, Offset, Project

SlaState = Literal['met', 'running', 'warning', 'breached', 'breached_done']
KbEntryId = Annotated[int, Field(description='Id of the knowledge base entry, not of the ticket')]
KB_PROBLEM = 'Problem as a customer would describe it, only this text is embedded and matched against new tickets'
KbStatus = Annotated[
    Literal['approved', 'pending'] | None,
    Field(description='approved: embedded and used for AI answers, pending: waits for review'),
]


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

    @tool()
    def list_helpdesk_kb_entries(
        project: Project,
        status: Annotated[
            str | None,
            Field(
                description='pending, approved, skipped (no solution found), rejected, several comma-separated, '
                'or all. Default: everything but skipped'
            ),
        ] = None,
        search: Annotated[str | None, Field(description='Text in problem or solution, case-insensitive')] = None,
        issue_id: Annotated[int | None, Field(description='Only the entry of this ticket')] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """
        Knowledge base of the helpdesk: problem/solution pairs extracted from closed tickets, most recently changed
        first. Use it to find known solutions or entries waiting for review (status="pending"). Long texts are
        shortened, get_helpdesk_kb_entry has them in full.
        """
        filters = compact(project_id=project, status=status, q=search, issue_id=issue_id)
        return page(redmine.helpdesk_kb_entry, filters, limit, offset)

    @tool()
    def get_helpdesk_kb_entry(entry_id: KbEntryId) -> dict:
        """
        A knowledge base entry with its ticket, status, whether it is in the vector store (indexed) and whether a
        person curated it (curated entries are never overwritten by a new extraction).
        """
        return serialize.resource(redmine.helpdesk_kb_entry.get(entry_id))

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

    @tool(write=True)
    def create_helpdesk_kb_entry(
        project: Project,
        issue_id: Annotated[int, Field(description='Ticket of the project the entry is about, one entry per ticket')],
        problem: Annotated[str, Field(description=KB_PROBLEM)],
        solution: str | None = None,
        status: KbStatus = 'pending',
    ) -> dict:
        """
        Adds a knowledge base entry for a ticket that has none. It counts as curated, closing the ticket again does
        not replace it. Approved entries are used for AI answers at once, keep new entries pending unless the user
        wants them approved. vector_sync in the result: indexed (searchable), removed (pending, not searchable) or
        a failure (not_configured, problem_blank, index_failed).
        """
        fields = compact(project_id=project, issue_id=issue_id, problem=problem, solution=solution, status=status)
        return changed(redmine.helpdesk_kb_entry.create(**fields))

    @tool(write=True, destructive=True, idempotent=True)
    def update_helpdesk_kb_entry(
        entry_id: KbEntryId,
        problem: Annotated[str | None, Field(description=KB_PROBLEM)] = None,
        solution: str | None = None,
        status: KbStatus = None,
    ) -> dict:
        """
        Corrects the texts of a knowledge base entry (replaced, not appended) or sets it approved/pending, only the
        given fields change. Rejecting: curate_helpdesk_kb_entry. vector_sync in the result tells whether AI
        answers use the new text: indexed, removed, or a failure (not_configured, problem_blank, index_failed,
        unindex_failed).
        """
        require_one(problem=problem, solution=solution, status=status)
        fields = compact(problem=problem, solution=solution, status=status)
        return changed(redmine.helpdesk_kb_entry.update(entry_id, **fields))

    @tool(write=True, idempotent=True)
    def curate_helpdesk_kb_entry(
        entry_id: KbEntryId,
        decision: Annotated[
            Literal['approve', 'reject'],
            Field(
                description='approve: embed it and use it for AI answers, reject: remove it from AI answers, '
                'the entry is kept so a new extraction does not bring it back'
            ),
        ],
    ) -> dict:
        """
        Approves or rejects a knowledge base entry after review. vector_sync in the result: indexed (approved and
        searchable), removed (rejected), or a failure (not_configured, problem_blank, index_failed, unindex_failed).
        """
        manager = redmine.helpdesk_kb_entry
        return changed(manager.approve(entry_id) if decision == 'approve' else manager.reject(entry_id))
