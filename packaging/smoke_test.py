"""
Starts a built server binary and checks the MCP handshake and the tool list over stdio.
"""

import json
import os
import subprocess
import sys

binary = sys.argv[1]
messages = [
    {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2025-06-18',
            'capabilities': {},
            'clientInfo': {'name': 'smoke', 'version': '1'},
        },
    },
    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
]
env = dict(
    os.environ,
    REDMINE_URL='https://redmine.invalid',
    REDMINE_API_KEY='smoke',
    REDMINE_TOOLSETS='all',
    REDMINE_TIMEOUT='1',
)
stdin = ''.join(json.dumps(m) + '\n' for m in messages)
result = subprocess.run([binary], input=stdin, capture_output=True, text=True, env=env, timeout=120)
responses = {r['id']: r for r in map(json.loads, result.stdout.splitlines()) if 'id' in r}

try:
    names = {tool['name'] for tool in responses[2]['result']['tools']}
except KeyError:
    sys.exit(f'No tool list.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')

expected = {'get_issue', 'search_issues', 'get_helpdesk_ticket', 'list_sprints', 'list_contacts', 'redmine_get'}
if not expected <= names or 'update_issue' in names:
    sys.exit(f'Unexpected tool list: {sorted(names)}')

print(f'ok: {responses[1]["result"]["serverInfo"]}, {len(names)} read-only tools')
