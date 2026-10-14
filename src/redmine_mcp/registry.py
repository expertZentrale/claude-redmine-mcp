"""
Tool registration: write tools are left out entirely in read-only mode, redminelib errors become tool errors.
"""

import functools

import requests
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from redminelib import exceptions

from .client import ReadOnlyViolation

_MESSAGES = {
    exceptions.AuthError: 'Redmine rejected the API key (401), check REDMINE_API_KEY',
    exceptions.ForbiddenError: 'The Redmine user of this server lacks the permission for this (403)',
    exceptions.ResourceNotFoundError: 'Not found (404), or not visible to the Redmine user of this server',
    exceptions.ResourceRequirementsError: 'The Redmine plugin providing this resource is not installed or enabled',
}


def _translate(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ReadOnlyViolation as e:
            raise ToolError(str(e)) from e
        except requests.exceptions.Timeout as e:
            raise ToolError('Redmine did not answer in time, try again or raise REDMINE_TIMEOUT') from e
        except requests.exceptions.RequestException as e:
            raise ToolError(f'Redmine is not reachable: {e.__class__.__name__}') from e
        except exceptions.BaseRedmineError as e:
            for cls, message in _MESSAGES.items():
                if isinstance(e, cls):
                    raise ToolError(message) from e

            raise ToolError(f'{e.__class__.__name__}: {e}') from e

    return wrapper


class ToolRegistrar:
    def __init__(self, mcp, settings):
        self.mcp = mcp
        self.settings = settings
        self.registered = []

    def __call__(self, write=False, destructive=False, idempotent=False):
        """
        Decorator registering a tool, write tools are skipped in read-only mode.
        """

        def decorator(fn):
            if write and self.settings.read_only:
                return fn

            annotations = ToolAnnotations(
                read_only_hint=not write,
                destructive_hint=destructive if write else False,
                idempotent_hint=idempotent if write else True,
                open_world_hint=True,
            )
            self.mcp.add_tool(_translate(fn), annotations=annotations)
            self.registered.append(fn.__name__)
            return fn

        return decorator
