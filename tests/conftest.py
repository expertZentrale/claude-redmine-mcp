import asyncio
import json
from unittest import mock

import pytest

from redmine_mcp.client import create_redmine
from redmine_mcp.config import Settings
from redmine_mcp.server import build_server

ALL_TOOLSETS = ('standard', 'expert_helpdesk', 'expert_agile', 'redmineup')


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self.history = []
        self.content = json.dumps(payload).encode() if payload is not None else b''
        self._payload = payload

    def json(self):
        return self._payload


class Server:
    """
    MCP server with the HTTP session replaced, responses are queued per test.
    """

    def __init__(self, read_only):
        self.settings = Settings(
            url='https://redmine.test', api_key='secret', read_only=read_only, toolsets=ALL_TOOLSETS
        )
        self.redmine = create_redmine(self.settings)
        self.session = mock.Mock()
        self.redmine.engine.session = self.session
        self.mcp, self.registered = build_server(self.settings, self.redmine)

    def respond(self, *payloads, status_code=200):
        self.session.request.side_effect = [FakeResponse(p, status_code) for p in payloads]

    def call(self, name, **arguments):
        result = asyncio.run(self.mcp.call_tool(name, arguments))
        return json.loads(result.content[0].text)

    def tool_names(self):
        return {tool.name for tool in asyncio.run(self.mcp.list_tools())}

    @property
    def requests(self):
        return [(c.args[0], c.args[1], c.kwargs) for c in self.session.request.call_args_list]


@pytest.fixture
def ro():
    return Server(read_only=True)


@pytest.fixture
def rw():
    return Server(read_only=False)
