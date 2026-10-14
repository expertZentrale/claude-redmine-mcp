"""
Redmine client factory and the engine that enforces the read-only mode on the HTTP level.
"""

from redminelib import Redmine
from redminelib.engines import SyncEngine


class ReadOnlyViolation(Exception):
    def __init__(self, method, url):
        super().__init__(
            f'Blocked {method.upper()} {url}: the Redmine MCP server runs in read-only mode '
            f'(set REDMINE_READ_ONLY=false / the read_only plugin option to allow changes)'
        )


class ReadOnlyEngine(SyncEngine):
    """
    Refuses every request that is not a GET before it is sent, independent of which tools are registered.
    """

    def request(self, method, url, headers=None, params=None, data=None):
        if method.lower() != 'get':
            raise ReadOnlyViolation(method, url)

        return super().request(method, url, headers=headers, params=params, data=data)


def create_redmine(settings):
    return Redmine(
        settings.url,
        key=settings.api_key,
        engine=ReadOnlyEngine if settings.read_only else SyncEngine,
        requests={'timeout': settings.timeout, 'verify': settings.verify_ssl},
    )
