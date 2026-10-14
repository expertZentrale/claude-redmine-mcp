---
name: redmine
description: How to work with Redmine through the redmine MCP tools - finding issues, reading their history, helpdesk tickets, sprints, logging time and changing issues. Use whenever the user mentions Redmine, a ticket or issue number (#1234), helpdesk tickets, sprints or spent time in Redmine.
---

# Working with Redmine

The `redmine` MCP server acts as one dedicated Redmine user. Everything is limited to what that user can see and
do, a 403/404 usually means missing permissions or project membership, not a missing object. `get_current_user`
shows the user and its project memberships.

## Read-only mode

By default the server is read-only: there are no tools that change anything, and any write is blocked on the HTTP
level. If the user asks for a change, say that the server runs read-only and that it can be switched with the
plugin's `read_only` option. Do not try to work around it.

In read-write mode every change is made in the name of the bot user. Confirm the exact change with the user before
calling a write tool, and prefer adding a comment (`update_issue` with `notes`) over overwriting fields.

## Finding things

- `#1234` is an issue id → `get_issue(1234)`, its `journals` are the comments and field changes.
- Projects take the identifier (`support`) or the numeric id.
- `search_issues` defaults to open issues, use `status="*"` for all. `assigned_to="me"` means the bot user.
  Custom fields filter as `filters={"cf_<id>": "value"}`, operators work as in Redmine: `">=2026-01-01"`, `"~text"`.
- Ids for statuses, trackers, priorities and time entry activities come from `list_reference_data`.
- `search` is the Redmine full text search (issues, wiki, news, documents, changesets, forums).
- Lists are paged: keep `limit` small and follow `next_offset` only when needed. Long texts in lists are
  shortened, fetch the single item for the full text.
- Anything without a dedicated tool: `redmine_list` / `redmine_get` with the resource name in snake_case,
  e.g. `redmine_list("news", {"project_id": "support"})`, `redmine_list("issue_category", {"project_id": "x"})`.

## Plugins

Toolsets are enabled per installation (`toolsets` option): `expert_helpdesk` (helpdesk tickets, contacts,
mailboxes, SLA), `expert_agile` (sprints, story points), `redmineup` (RedmineUP CRM contacts/deals, helpdesk
tickets, checklists). A "plugin is not installed" error means the Redmine instance lacks that plugin.
