import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError


def test_search_issues_fetches_one_page(ro):
    ro.respond(
        {'issues': [{'id': 1, 'subject': 'A', 'description': 'x' * 1000}], 'total_count': 40, 'limit': 25, 'offset': 0}
    )

    result = ro.call('search_issues', project='support', assigned_to='me', filters={'cf_12': 'foo'})

    method, url, kwargs = ro.requests[0]
    assert (method, url) == ('get', 'https://redmine.test/issues.json')
    assert kwargs['params'] == {
        'project_id': 'support',
        'status_id': 'open',
        'assigned_to_id': 'me',
        'cf_12': 'foo',
        'limit': 25,
        'offset': 0,
    }
    assert kwargs['headers']['X-Redmine-API-Key'] == 'secret'
    assert result['total_count'] == 40
    assert result['next_offset'] == 1
    assert len(result['items'][0]['description']) < 400


def test_limit_is_clamped(ro):
    ro.respond({'projects': [], 'total_count': 0, 'limit': 100, 'offset': 0})

    # The schema refuses > 100, the server clamps anyway
    from redmine_mcp.tools import page

    page(ro.redmine.project, {}, 5000, 0, method='all')
    assert ro.requests[0][2]['params']['limit'] == 100


def test_get_issue_default_includes(ro):
    ro.respond({'issue': {'id': 7, 'journals': [{'id': 1, 'notes': 'hi'}]}})

    result = ro.call('get_issue', issue_id=7)

    assert ro.requests[0][2]['params']['include'] == 'journals,attachments,relations,children'
    assert result['journals'][0]['notes'] == 'hi'
    # Unset relations/includes of redminelib are not part of the result
    assert 'time_entries' not in result


def test_search_scoped_to_project(ro):
    ro.respond({'results': [{'id': 1, 'type': 'issue', 'title': 'X'}], 'total_count': 1})

    result = ro.call('search', query='printer', project='support', types=['issues', 'wiki_pages'])

    method, url, kwargs = ro.requests[0]
    assert url == 'https://redmine.test/projects/support/search.json'
    assert kwargs['params']['issues'] == 1 and kwargs['params']['wiki_pages'] == 1
    assert result['items'][0]['title'] == 'X'


def test_not_found_becomes_tool_error(ro):
    ro.respond(None, status_code=404)

    with pytest.raises(ToolError, match='Not found'):
        ro.call('get_issue', issue_id=99999)


def test_update_issue_sends_put(rw):
    rw.respond(None)

    result = rw.call('update_issue', issue_id=5, notes='Done', status_id=3)

    method, url, kwargs = rw.requests[0]
    assert (method, url) == ('put', 'https://redmine.test/issues/5.json')
    assert json.loads(kwargs['data']) == {'issue': {'notes': 'Done', 'status_id': 3}}
    assert result == {'ok': True, 'issue_id': 5}


def test_create_issue_with_extra_fields(rw):
    rw.respond({'issue': {'id': 11, 'subject': 'New'}})

    result = rw.call(
        'create_issue', project='support', subject='New', extra={'custom_fields': [{'id': 1, 'value': 'a'}]}
    )

    method, url, kwargs = rw.requests[0]
    assert (method, url) == ('post', 'https://redmine.test/projects/support/issues.json')
    assert json.loads(kwargs['data'])['issue']['custom_fields'] == [{'id': 1, 'value': 'a'}]
    assert result['item']['id'] == 11


def test_uploads_are_refused(rw):
    # redminelib would read the named local file and upload it
    with pytest.raises(ToolError, match='uploads'):
        rw.call('create_issue', project='p', subject='x', extra={'uploads': [{'path': '/etc/passwd'}]})

    rw.session.request.assert_not_called()


def test_generic_list(ro):
    ro.respond({'news': [{'id': 1, 'title': 'Hello'}], 'total_count': 1, 'limit': 25, 'offset': 0})

    result = ro.call('redmine_list', resource='news', filters={'project_id': 'p'})

    assert ro.requests[0][1] == 'https://redmine.test/news.json'
    assert ro.requests[0][2]['params']['project_id'] == 'p'
    assert result['items'][0]['title'] == 'Hello'


def test_reference_data(ro):
    ro.respond({'issue_priorities': [{'id': 1, 'name': 'Low'}]})

    result = ro.call('list_reference_data', kind='issue_priorities')

    assert ro.requests[0][1] == 'https://redmine.test/enumerations/issue_priorities.json'
    assert result['items'] == [{'id': 1, 'name': 'Low'}]


def test_helpdesk_ticket_with_messages(ro):
    ro.respond({'helpdesk_ticket': {'id': 3, 'subject': 'Help', 'messages': [{'id': 1}]}})

    result = ro.call('get_helpdesk_ticket', ticket_id=3)

    assert ro.requests[0][1] == 'https://redmine.test/helpdesk/tickets/3.json'
    assert result['messages'] == [{'id': 1}]


def test_connection_errors_become_tool_errors(ro):
    import requests

    ro.session.request.side_effect = requests.exceptions.ConnectionError('boom')

    with pytest.raises(ToolError, match='not reachable'):
        ro.call('get_issue', issue_id=1)


@pytest.mark.parametrize(
    ('tool', 'arguments'), [('get_current_user', {}), ('redmine_get', {'resource': 'user', 'resource_id': 'current'})]
)
def test_api_key_is_never_returned(ro, tool, arguments):
    ro.respond({'user': {'id': 742, 'login': 'bot', 'api_key': 'leaked', 'nested': [{'api_key': 'leaked'}]}})

    result = ro.call(tool, **arguments)

    assert result['login'] == 'bot'
    assert 'leaked' not in json.dumps(result)


def test_helpdesk_init_is_refused(rw):
    # redmine_expert_helpdesk would mail the customer
    with pytest.raises(ToolError, match='helpdesk_init'):
        rw.call('create_issue', project='p', subject='x', extra={'helpdesk_init': {'contact_email': 'a@b.c'}})

    rw.session.request.assert_not_called()


def test_search_helpdesk_tickets_uses_issue_filters(ro):
    ro.respond({'issues': [], 'total_count': 0, 'limit': 25, 'offset': 0})

    ro.call('search_helpdesk_tickets', project='34', customer='kaden', awaiting_agent=True, sla_reaction='breached')

    method, url, kwargs = ro.requests[0]
    assert url == 'https://redmine.test/issues.json'
    assert kwargs['params'] == {
        'project_id': '34',
        'status_id': 'open',
        'helpdesk_kunde': '~kaden',
        'helpdesk_awaiting_agent': 1,
        'helpdesk_sla_reaction': 'breached',
        'limit': 25,
        'offset': 0,
    }


def test_list_helpdesk_tickets_has_no_filters(ro):
    import asyncio

    tool = next(t for t in asyncio.run(ro.mcp.list_tools()) if t.name == 'list_helpdesk_tickets')
    assert set(tool.input_schema['properties']) == {'project', 'limit', 'offset'}


def test_sprint_overview_totals(ro):
    def issue(id_, status, closed, assignee=None):
        data = {
            'id': id_,
            'subject': f'S{id_}',
            'tracker': {'name': 'Story'},
            'status': {'name': status, 'is_closed': closed},
        }
        if assignee:
            data['assigned_to'] = {'id': 1, 'name': assignee}
        return data

    ro.route(
        {
            '/issues.json': {
                'issues': [issue(1, 'Erledigt', True, 'Ann'), issue(2, 'Neu', False, 'Ann'), issue(3, 'Neu', False)],
                'total_count': 3,
                'limit': 100,
                'offset': 0,
            },
            '/issues/1/expert_agile_data.json': {
                'expert_agile_data': {'issue_id': 1, 'story_points': 5, 'sprint_id': 7}
            },
            '/issues/2/expert_agile_data.json': {
                'expert_agile_data': {'issue_id': 2, 'story_points': 3, 'sprint_id': 7}
            },
            '/issues/3/expert_agile_data.json': {
                'expert_agile_data': {'issue_id': 3, 'story_points': None, 'sprint_id': 7}
            },
        }
    )

    result = ro.call('get_sprint_overview', project='scrum')

    issues_request = next(r for r in ro.requests if r[1].endswith('/issues.json'))
    assert issues_request[2]['params']['expert_agile_sprint_id'] == 'active'
    assert result['totals'] == {'issues': 3, 'story_points': 8, 'done_story_points': 5, 'unestimated_issues': 1}
    assert result['by_assignee']['Ann'] == {'issues': 2, 'open_issues': 1, 'story_points': 8, 'done_story_points': 5}
    assert result['by_assignee']['(unassigned)']['issues'] == 1
    assert result['truncated'] is False
    assert result['ignored_issues_not_in_sprint'] == 0


def test_sprint_overview_drops_issues_outside_the_sprint(ro):
    # Where the agile module is off Redmine ignores the sprint filter and returns all issues
    ro.route(
        {
            '/issues.json': {
                'issues': [{'id': 1, 'subject': 'X', 'tracker': {'name': 'Bug'}, 'status': {'name': 'Neu'}}],
                'total_count': 1,
                'limit': 100,
                'offset': 0,
            },
            '/issues/1/expert_agile_data.json': {
                'expert_agile_data': {'issue_id': 1, 'story_points': None, 'sprint_id': None}
            },
        }
    )

    result = ro.call('get_sprint_overview', project='p')

    assert result['issues'] == [] and result['ignored_issues_not_in_sprint'] == 1
    assert result['totals']['issues'] == 0


def test_sprint_overview_rejects_bad_sprint(ro):
    with pytest.raises(ToolError, match='active'):
        ro.call('get_sprint_overview', project='scrum', sprint='current')
