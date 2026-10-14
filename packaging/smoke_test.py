"""
Starts a built server binary and checks the MCP handshake and the tool list over stdio.
"""

import json
import os
import queue
import subprocess
import sys
import threading

TIMEOUT = 120

binary = sys.argv[1]
env = dict(
    os.environ,
    REDMINE_URL='https://redmine.invalid',
    REDMINE_API_KEY='smoke',
    REDMINE_TOOLSETS='all',
    REDMINE_TIMEOUT='1',
)
process = subprocess.Popen(
    [binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
)
lines = queue.Queue()
threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True).start()


def send(message):
    process.stdin.write(json.dumps(message) + '\n')
    process.stdin.flush()


def receive(request_id):
    # Like a real client, stdin stays open until the answer is there
    while True:
        try:
            response = json.loads(lines.get(timeout=TIMEOUT))
        except queue.Empty:
            process.kill()
            sys.exit(f'No answer to request {request_id} within {TIMEOUT}s.\nstderr:\n{process.stderr.read()}')

        if response.get('id') == request_id:
            return response


try:
    send(
        {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2025-06-18',
                'capabilities': {},
                'clientInfo': {'name': 'smoke', 'version': '1'},
            },
        }
    )
    server_info = receive(1)['result']['serverInfo']
    send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    names = {tool['name'] for tool in receive(2)['result']['tools']}
finally:
    process.stdin.close()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()

expected = {'get_issue', 'search_issues', 'get_helpdesk_ticket', 'list_sprints', 'list_contacts', 'redmine_get'}

if not expected <= names or 'update_issue' in names:
    sys.exit(f'Unexpected tool list: {sorted(names)}')

print(f'ok: {server_info}, {len(names)} read-only tools')
