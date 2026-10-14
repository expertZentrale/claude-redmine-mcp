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
