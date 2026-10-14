"""
Turns redminelib resources and resource sets into plain JSON data for tool results.
"""

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
LIST_TEXT_LIMIT = 300


def clamp_limit(limit):
    return max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))


def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()

    return value


def _shorten(data, fields):
    for field in fields:
        text = data.get(field)

        if isinstance(text, str) and len(text) > LIST_TEXT_LIMIT:
            data[field] = (
                text[:LIST_TEXT_LIMIT] + f'… [{len(text) - LIST_TEXT_LIMIT} more chars, fetch the item for all]'
            )

    return data


def resource(res):
    """
    Raw Redmine data of a single resource, unset includes/relations dropped.
    """
    return _clean(dict(res.raw()))


def resource_set(resources, limit, offset=0, shorten=('description', 'text', 'content', 'notes')):
    """
    One page of a resource set. The set has to be created with limit/offset already, redminelib fetches
    everything when no limit is given.
    """
    items = [_shorten(resource(res), shorten) for res in resources]

    try:
        total = resources.total_count
    except Exception:
        total = len(items)

    result = {'total_count': total, 'offset': offset, 'limit': limit, 'count': len(items), 'items': items}

    if offset + len(items) < total:
        result['next_offset'] = offset + len(items)

    return result
