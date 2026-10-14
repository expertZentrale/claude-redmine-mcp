"""
Entry point of the Redmine MCP server (stdio).
"""

import logging
import sys

from mcp.server.mcpserver import MCPServer

from . import __version__
from .client import create_redmine
from .config import ConfigError, Settings
from .registry import ToolRegistrar
from .tools import expert_agile, expert_helpdesk, generic, redmineup, standard

log = logging.getLogger('redmine_mcp')

TOOLSET_MODULES = {
    'standard': standard,
    'expert_helpdesk': expert_helpdesk,
    'expert_agile': expert_agile,
    'redmineup': redmineup,
}

INSTRUCTIONS = """\
Access to Redmine as a dedicated Redmine user, everything is limited to what that user may see and do.
Mode: {mode}. Toolsets: {toolsets}.
Lists are paged (limit/offset, next_offset in the result). Ids of statuses, trackers, priorities and activities
come from list_reference_data. redmine_get/redmine_list read any resource the curated tools do not cover.
{write_hint}"""


def build_server(settings, redmine=None):
    redmine = redmine if redmine is not None else create_redmine(settings)
    write_hint = (
        'This server is read-only, there are no tools to change Redmine and any write attempt is blocked.'
        if settings.read_only
        else 'Changes are made in the name of the Redmine user of this server, confirm them with the user first.'
    )
    mcp = MCPServer(
        name='redmine',
        version=__version__,
        instructions=INSTRUCTIONS.format(
            mode='read-only' if settings.read_only else 'read-write',
            toolsets=', '.join(settings.toolsets),
            write_hint=write_hint,
        ),
    )
    tool = ToolRegistrar(mcp, settings)

    for name in settings.toolsets:
        TOOLSET_MODULES[name].register(tool, redmine)

    generic.register(tool, redmine)
    return mcp, tool.registered


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='redmine-mcp: %(message)s')

    try:
        settings = Settings.from_env()
    except ConfigError as e:
        log.error('%s', e)
        sys.exit(2)

    redmine = create_redmine(settings)

    try:
        user = redmine.user.get('current')
        log.info('connected to %s as %s', settings.url, user.login)
    except Exception as e:  # The tools report the error again, the server still starts
        log.warning('could not verify the connection to %s: %s', settings.url, e)

    mcp, registered = build_server(settings, redmine)
    log.info(
        '%s mode, toolsets %s, %d tools',
        'read-only' if settings.read_only else 'READ-WRITE',
        ','.join(settings.toolsets),
        len(registered),
    )
    mcp.run('stdio')
