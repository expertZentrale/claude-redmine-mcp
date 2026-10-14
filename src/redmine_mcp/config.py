"""
Settings read from the environment, the plugin passes its userConfig values in as REDMINE_* variables.
"""

import os
from dataclasses import dataclass

TOOLSETS = ('standard', 'expert_helpdesk', 'expert_agile', 'redmineup')
_TRUE = ('1', 'true', 'yes', 'on')
_FALSE = ('0', 'false', 'no', 'off')


class ConfigError(Exception):
    pass


def _env(name, default=None):
    value = os.environ.get(name, '').strip()

    # An unset optional plugin userConfig value can arrive as an empty string or as the unexpanded placeholder
    if not value or value.startswith('${'):
        return default

    return value


def _bool(name, default):
    value = _env(name)

    if value is None:
        return default
    if value.lower() in _TRUE:
        return True
    if value.lower() in _FALSE:
        return False

    raise ConfigError(f'{name} must be one of {_TRUE + _FALSE}, got {value!r}')


def _toolsets(value):
    names = [name.strip() for name in value.split(',') if name.strip()]

    if 'all' in names:
        return TOOLSETS

    unknown = sorted(set(names) - set(TOOLSETS))

    if unknown:
        raise ConfigError(f'Unknown toolset(s) {unknown}, available: {", ".join(TOOLSETS)} or all')

    return tuple(name for name in TOOLSETS if name in names)


@dataclass(frozen=True)
class Settings:
    url: str
    api_key: str
    read_only: bool = True
    toolsets: tuple = ('standard',)
    verify_ssl: bool = True
    timeout: float = 30.0

    @classmethod
    def from_env(cls):
        url = _env('REDMINE_URL')
        api_key = _env('REDMINE_API_KEY')

        if url is None:
            raise ConfigError('REDMINE_URL is not set')
        if api_key is None:
            raise ConfigError('REDMINE_API_KEY is not set')

        try:
            timeout = float(_env('REDMINE_TIMEOUT', '30'))
        except ValueError:
            raise ConfigError('REDMINE_TIMEOUT must be a number of seconds') from None

        return cls(
            url=url.rstrip('/'),
            api_key=api_key,
            # Read-only unless writing is explicitly enabled
            read_only=_bool('REDMINE_READ_ONLY', True),
            toolsets=_toolsets(_env('REDMINE_TOOLSETS', 'standard')),
            verify_ssl=_bool('REDMINE_VERIFY_SSL', True),
            timeout=timeout,
        )
