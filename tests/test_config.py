import pytest

from redmine_mcp.config import TOOLSETS, ConfigError, Settings


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for name in ('REDMINE_READ_ONLY', 'REDMINE_TOOLSETS', 'REDMINE_VERIFY_SSL', 'REDMINE_TIMEOUT'):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv('REDMINE_URL', 'https://redmine.test/')
    monkeypatch.setenv('REDMINE_API_KEY', 'secret')
    return monkeypatch


def test_defaults_are_read_only():
    settings = Settings.from_env()
    assert settings.read_only is True
    assert settings.toolsets == ('standard',)
    assert settings.url == 'https://redmine.test'


@pytest.mark.parametrize('value', ['', '${user_config.read_only}'])
def test_unset_plugin_values_fall_back_to_defaults(env, value):
    env.setenv('REDMINE_READ_ONLY', value)
    env.setenv('REDMINE_TOOLSETS', value)
    assert Settings.from_env().read_only is True
    assert Settings.from_env().toolsets == ('standard',)


@pytest.mark.parametrize(('value', 'expected'), [('false', False), ('0', False), ('true', True), ('YES', True)])
def test_read_only_values(env, value, expected):
    env.setenv('REDMINE_READ_ONLY', value)
    assert Settings.from_env().read_only is expected


def test_invalid_read_only_value_is_an_error(env):
    env.setenv('REDMINE_READ_ONLY', 'maybe')

    with pytest.raises(ConfigError):
        Settings.from_env()


def test_toolsets(env):
    env.setenv('REDMINE_TOOLSETS', 'expert_agile, standard')
    assert Settings.from_env().toolsets == ('standard', 'expert_agile')

    env.setenv('REDMINE_TOOLSETS', 'all')
    assert Settings.from_env().toolsets == TOOLSETS

    env.setenv('REDMINE_TOOLSETS', 'standard,crm')
    with pytest.raises(ConfigError, match='crm'):
        Settings.from_env()


def test_missing_key(env):
    env.delenv('REDMINE_API_KEY')

    with pytest.raises(ConfigError, match='REDMINE_API_KEY'):
        Settings.from_env()
