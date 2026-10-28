---
name: redmine
description: How to work with Redmine through the redmine MCP tools - finding issues, reading their history, helpdesk tickets and customers, SLA, the helpdesk knowledge base, sprints and story points, logging time and changing issues. Use whenever the user mentions Redmine, a ticket or issue number (#1234), helpdesk tickets, customers, SLA, knowledge base entries, sprints, story points or spent time in Redmine.
---

# Working with Redmine

The `redmine` MCP server acts as one dedicated Redmine user. Everything is limited to what that user can see and
do: a 403/404 usually means missing permissions or project membership, not a missing object. `get_current_user`
shows the user and its project memberships, answers only cover those projects - say so when it matters.

## Read-only and write mode

By default the server is read-only: there are no tools that change anything, and any write is blocked on the HTTP
level. If the user asks for a change, say that the server runs read-only and that it can be switched with the
plugin's `read_only` option. Do not try to work around it.

In read-write mode every change is made in the name of the bot user. Confirm the exact change with the user
before calling a write tool. Redmine silently ignores changes the user may not make (e.g. a status the workflow
does not allow), so:

- before a status change fetch `get_issue(id, include=["allowed_statuses"])` and pick a status from that list,
- after the change read the issue again and report what actually changed.

Nothing in this server mails customers. Creating helpdesk tickets does not send mail, `helpdesk_init` is refused.

## Keep results small

- Ask for counts first: any list tool with `limit=1` returns `total_count`.
- Prefer filters over full text search. `search` (Redmine full text) matches signatures, quotes and mentions
  and easily returns hundreds of hits; use it for topics, not for people.
- Lists are paged, follow `next_offset` only when needed. Long texts in lists are shortened, fetch the single
  item for the full text.

## Issues (standard Redmine)

- `#1234` is an issue id → `get_issue(1234)`. `journals` are comments and field changes, the original mail of a
  helpdesk ticket is the `description`.
- Projects take the identifier (`support`) or the numeric id.
- `search_issues` defaults to open issues, `status="*"` for all. `assigned_to="me"` is the bot user, not the
  person you are talking to - use their user id.
- Filters use the Redmine query syntax in `filters`, an operator prefix in the value: `"~text"` contains,
  `">=2026-01-01"`, `"><2026-01-01|2026-01-31"`, `"!5"` not, `"*"` any, `"!*"` none. Custom fields: `cf_<id>`.
  Several ids: `"issue_id": "1,2,3"`.
- Unknown filter names are silently ignored by Redmine and return unfiltered results. If a filtered count looks
  like the unfiltered one, compare with `limit=1` without the filter.
- Ids of statuses, trackers, priorities, activities, saved queries: `list_reference_data`.

## Project members and groups

| Question | Call |
|---|---|
| Members of a project, membership ids | `list_project_members(project)` |
| User ids by name | `list_users(name="schubert")` |
| Users and projects of a group | `get_group(id)`, group ids: `list_reference_data("groups")` |
| Role ids | `list_reference_data("roles")` |

- Write tools: `add_project_member` (user or group id), `update_project_member` (replaces the roles),
  `remove_project_member`, `create_group`, `add_group_users`, `remove_group_users`.
- Members need the "manage members" permission in the project; users, groups and `list_users` need an admin API
  key. A 403 means the key lacks that, say so instead of retrying.
- Prefer adding a group to a project over adding its users one by one. Memberships a user has through a group
  cannot be removed with `remove_project_member`, remove the user from the group or the group from the project.
- Check first whether the users are already members or the group already exists, then confirm the list of
  changes (who, which roles) with the user.

## Helpdesk (redmine_expert_helpdesk, toolset `expert_helpdesk`)

Helpdesk tickets are normal issues plus a customer (contact), a mailbox, a mail log and SLA times.

| Question | Call |
|---|---|
| Tickets of a customer | `search_helpdesk_tickets(customer="kaden", status="*")` (name or email, contains) |
| Customers waiting for an answer | `search_helpdesk_tickets(awaiting_agent=true)` |
| SLA breached / at risk | `search_helpdesk_tickets(sla_reaction="breached")`, values `met running warning breached breached_done`, same for `sla_solution` |
| Contact data | `list_helpdesk_contacts(project, search=...)` or `email=` (exact) |
| SLA state and mail log of one ticket | `get_helpdesk_ticket(id)` |
| Mail texts | `get_issue(id)`: description (first mail) and journals (replies, further mails) |
| SLA times, autoresponder, settings | `get_helpdesk_project_settings(project)` |

- `list_helpdesk_tickets` only pages through all tickets of a project (closed ones included); the helpdesk API
  ignores every filter there. Filter with `search_helpdesk_tickets`.
- The mail log in `get_helpdesk_ticket` has no mail body: `direction` `in` = customer mail, `out` = reply sent,
  `init` = contact assigned.
- Comments and status changes on helpdesk tickets go through `update_issue`, which also records the SLA first
  response. A comment does not mail the customer - replies to customers are made in Redmine itself.
- The same filters work in `search_issues` too: `helpdesk_kunde`, `helpdesk_awaiting_agent` (`1`/`0`),
  `helpdesk_sla_reaction`, `helpdesk_sla_solution`; sort by them with `sort="helpdesk_sla_reaction"`.

### Knowledge base

Problem/solution pairs the AI extracts from closed tickets. Approved entries are embedded and used for AI answers
and solution proposals, only the problem text is matched against new tickets.

| Question | Call |
|---|---|
| Known solution for a problem | `list_helpdesk_kb_entries(project, search="vpn")` (problem or solution contains), full text: `get_helpdesk_kb_entry(id)` |
| Entries waiting for review | `list_helpdesk_kb_entries(project, status="pending")`; `skipped` (no solution found) is hidden unless asked for, `status="all"` |
| Entry of a ticket | `list_helpdesk_kb_entries(project, issue_id=4711, status="all")` |
| Approve / reject after review | `curate_helpdesk_kb_entry(entry_id, decision="approve")` |
| Correct the texts | `update_helpdesk_kb_entry(entry_id, problem=..., solution=...)` |

- Entry ids are not ticket ids. One entry per ticket, `create_helpdesk_kb_entry` fails for a ticket that has one.
- Approving puts an entry into the AI answers at once. Show the user problem and solution and confirm before
  approving; create new entries as `pending` unless the user wants them approved. Write the problem the way a
  customer would describe it.
- Every write returns `vector_sync`: `indexed` and `removed` are fine, anything else means the vector store did not
  take the change - report it.
- Rejected entries are kept, so a new extraction does not bring them back. The server cannot delete entries or
  start a reindex/re-extraction, that is done in Redmine's knowledge base tab.

## Agile (redmine_expert_agile, toolset `expert_agile`)

| Question | Call |
|---|---|
| What is in the current sprint, points done, points per person | `get_sprint_overview(project)` or `sprint="<id>"` |
| Sprints of a project | `list_sprints(project)` (needs the manage_expert_agile_sprints permission) |
| Story points and sprint of one issue | `get_issue_agile_data(id)` |
| Issues by story points | `search_issues(filters={"story_points": ">=5"})`, `"*"` estimated, `"!*"` not estimated |
| Issues of a sprint without totals | `search_issues(filters={"expert_agile_sprint_id": "active"}, status="*")` or `"5|7"` |

- Story points and sprint are not part of the issue data, `get_sprint_overview` fetches them per issue
  (up to 200 issues, `truncated` says when there are more).
- There is no velocity or burndown API, compute it from sprints and their issues when asked. The plugin's own
  "velocity" chart counts created vs. closed issues, not story points.
- Sprint status: `open`, `active` (only one per project, activating another one reopens the previous one),
  `closed` (refused while the sprint has open issues).

## RedmineUP plugins (toolset `redmineup`)

CRM contacts and deals (`list_contacts`, `get_contact`, `list_deals`, `get_deal`), RedmineUP helpdesk tickets
(`list_redmineup_tickets`, `get_redmineup_ticket`), Agile sprints (`list_redmineup_sprints`) and checklists
(`get_checklist`). A "plugin is not installed" error means the Redmine instance lacks that plugin.

## Anything else

`redmine_list` / `redmine_get` read every resource redminelib knows, with the resource name in snake_case:
`redmine_list("news", {"project_id": "support"})`, `redmine_list("issue_category", {"project_id": "x"})`,
`redmine_get("user", "42")`, `redmine_get("wiki_page", "Start", {"project_id": "x"})`.
