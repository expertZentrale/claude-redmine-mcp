import pytest
from mcp.server.mcpserver.exceptions import ToolError

from redmine_mcp.client import ReadOnlyViolation

WRITE_TOOLS = {
    'create_issue',
    'update_issue',
    'log_time',
    'create_issue_relation',
    'save_wiki_page',
    'create_helpdesk_ticket',
    'create_sprint',
    'update_sprint',
    'update_issue_agile_data',
    'add_crm_note',
    'add_checklist_item',
    'update_checklist_item',
}


def test_read_only_registers_no_write_tools(ro):
    names = ro.tool_names()
    assert not names & WRITE_TOOLS
    assert {'search_issues', 'get_issue', 'redmine_get', 'list_helpdesk_tickets', 'list_sprints'} <= names


def test_read_write_registers_write_tools(rw):
    assert WRITE_TOOLS <= rw.tool_names()


def test_annotations(rw):
    import asyncio

    tools = {t.name: t for t in asyncio.run(rw.mcp.list_tools())}
    assert tools['get_issue'].annotations.read_only_hint is True
    assert tools['update_issue'].annotations.read_only_hint is False
    assert tools['save_wiki_page'].annotations.destructive_hint is True


@pytest.mark.parametrize(
    'call',
    [
        lambda r: r.issue.create(project_id='p', subject='x'),
        lambda r: r.issue.update(1, notes='x'),
        lambda r: r.issue.delete(1),
        lambda r: r.expert_agile_data.update(1, story_points=3),
        lambda r: r.project.close('p'),
    ],
)
def test_engine_blocks_writes_before_sending(ro, call):
    with pytest.raises(ReadOnlyViolation):
        call(ro.redmine)

    ro.session.request.assert_not_called()


def test_engine_blocks_writes_in_temporary_sessions(ro):
    # redmine.session() / download() build a new engine from engine.__class__
    with ro.redmine.session(return_raw_response=True), pytest.raises(ReadOnlyViolation):
        ro.redmine.issue.update(1, notes='x')


def test_engine_allows_reads(ro):
    ro.respond({'issue': {'id': 1, 'subject': 'Printer'}})
    assert ro.call('get_issue', issue_id=1)['subject'] == 'Printer'
    assert ro.requests[0][0] == 'get'


def test_generic_tools_are_read_only(rw):
    with pytest.raises(ToolError, match='Unknown resource'):
        rw.call('redmine_get', resource='delete', resource_id='1')
