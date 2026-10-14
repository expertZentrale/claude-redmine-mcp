"""
Toolsets, each module exposes register(tool, redmine).
"""

from mcp.server.mcpserver.exceptions import ToolError

from .. import serialize

# uploads: redminelib reads and uploads the local files named there.
# helpdesk_init: redmine_expert_helpdesk mails the customer with send_mail, nothing may do that through extra.
_FORBIDDEN_FIELDS = ('uploads', 'helpdesk_init')


def compact(**fields):
    """
    Keyword arguments without the ones the caller left unset.
    """
    return {k: v for k, v in fields.items() if v is not None}


def merge_extra(fields, extra):
    """
    Adds the free-form extra fields, explicit arguments win.
    """
    if extra:
        blocked = sorted(set(extra) & set(_FORBIDDEN_FIELDS))

        if blocked:
            raise ToolError(f'Field(s) {blocked} are not supported by this server')

        fields = dict(extra, **fields)

    return fields


def page(manager, filters, limit, offset, method='filter'):
    """
    Fetches exactly one page, redminelib would fetch everything without a limit.
    """
    limit = serialize.clamp_limit(limit)
    offset = max(0, int(offset or 0))
    params = dict(filters, limit=limit, offset=offset)

    if method == 'filter' and not filters:
        method = 'all'

    return serialize.resource_set(getattr(manager, method)(**params), limit, offset)


def require_one(**values):
    if not any(v is not None for v in values.values()):
        raise ToolError(f'One of {", ".join(values)} is required')


def changed(result, **ids):
    """
    Uniform result of write tools.
    """
    if hasattr(result, 'raw'):
        return {'ok': True, 'item': serialize.resource(result)}

    return dict({'ok': bool(result)}, **ids)
