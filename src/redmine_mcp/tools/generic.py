"""
Read access to every resource redminelib knows, for whatever the curated tools do not cover.
"""

import re
from typing import Annotated, Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from redminelib import resources

from .. import serialize
from . import page
from .standard import Limit, Offset

Resource = Annotated[
    str, Field(description='Resource name in snake_case, e.g. "news", "file", "issue_category", "deal_status"')
]


def _resource_names():
    return sorted(re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower() for name in resources.registry)


def _manager(redmine, resource):
    if resource not in _resource_names():
        raise ToolError(f'Unknown resource {resource!r}, available: {", ".join(_resource_names())}')

    return getattr(redmine, resource)


def register(tool, redmine):
    @tool()
    def redmine_get(
        resource: Resource,
        resource_id: Annotated[str, Field(description='Id, or e.g. the title for wiki pages')],
        params: Annotated[
            dict[str, Any] | None, Field(description='e.g. {"project_id": "x"} or {"include": "attachments"}')
        ] = None,
    ) -> dict:
        """Any single Redmine resource by id (read-only)."""
        manager = _manager(redmine, resource)
        resource_id = int(resource_id) if resource_id.isdigit() else resource_id
        return serialize.resource(manager.get(resource_id, **(params or {})))

    @tool()
    def redmine_list(
        resource: Resource,
        filters: Annotated[
            dict[str, Any] | None, Field(description='e.g. {"project_id": "x"}, empty lists all')
        ] = None,
        limit: Limit = 25,
        offset: Offset = 0,
    ) -> dict:
        """Any Redmine resource list, filtered or all (read-only). Unknown names return the list of resources."""
        return page(_manager(redmine, resource), filters or {}, limit, offset)
