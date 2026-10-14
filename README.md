# redmine – Claude-Code-Plugin mit Redmine-MCP-Server

MCP-Server für Redmine auf Basis von [python-redmine-expert](https://github.com/expertZentrale/python-redmine)
(`redminelib`). Er arbeitet als **ein dedizierter Redmine-User** über dessen API-Key und läuft
**standardmäßig read-only**.

Abgedeckt: Standard-Redmine (Projekte, Issues, Journals, Zeiterfassung, Versionen, Wiki, Volltextsuche,
Stammdaten), `redmine_expert_helpdesk`, `redmine_expert_agile` und die RedmineUP-Plugins (CRM, Helpdesk,
Agile, Checklists). Für alles ohne eigenes Tool gibt es `redmine_get` / `redmine_list` (nur lesend) über alle
Ressourcen der Library.

## Read-only-Modus

Drei unabhängige Ebenen:

1. **Tools:** Mit `read_only` (Default) werden Schreib-Tools gar nicht registriert, Claude sieht sie nicht.
2. **HTTP:** Der Redmine-Client nutzt dann `ReadOnlyEngine`, die jeden Nicht-GET-Request blockiert, bevor er
   gesendet wird – auch aus Code-Pfaden, die kein Tool sind.
3. **Redmine-Rechte:** Der Bot-User darf nur, was seine Rolle erlaubt (siehe unten).

Auch im Schreibmodus gibt es bewusst keine Lösch-Tools, und das Feld `uploads` wird abgelehnt (redminelib würde
sonst lokale Dateien lesen und hochladen).

## Redmine vorbereiten

1. *Administration → Einstellungen → API*: „REST-Schnittstelle aktivieren“.
2. Neuen User anlegen, z. B. `claude-bot` (kein Administrator; Login per Passwort kann gesperrt bleiben).
3. Eigene Rolle anlegen, z. B. „Claude (lesend)“: Issues/Zeit/Wiki/Helpdesk *ansehen*. Für den Schreibmodus eine
   zweite Rolle mit den nötigen Bearbeiten-Rechten.
4. Den User nur in den Projekten als Mitglied mit dieser Rolle eintragen, auf die Claude zugreifen soll.
5. Als `claude-bot` anmelden (oder als Admin über „Benutzer → API-Schlüssel“) und den API-Schlüssel kopieren.

Hinweis: Änderungen erscheinen in Redmine als Aktionen von `claude-bot`, nicht des jeweiligen Menschen.

## Installation als Plugin

Voraussetzung: [uv](https://docs.astral.sh/uv/) (`uvx` im `PATH`), Python ≥ 3.10.

```
/plugin marketplace add expertZentrale/claude-redmine-mcp
/plugin install redmine@expert-redmine
```

Beim Aktivieren fragt Claude Code die Optionen ab (der API-Key wird als sensibel im Keychain gespeichert):

| Option            | Env-Variable          | Default    |                                                          |
|-------------------|-----------------------|------------|----------------------------------------------------------|
| `redmine_url`     | `REDMINE_URL`         | –          | z. B. `https://redmine.example.com`                      |
| `redmine_api_key` | `REDMINE_API_KEY`     | –          | API-Key des Bot-Users                                     |
| `read_only`       | `REDMINE_READ_ONLY`   | `true`     | `false` schaltet die Schreib-Tools frei                   |
| `toolsets`        | `REDMINE_TOOLSETS`    | `standard` | `standard,expert_helpdesk,expert_agile,redmineup` / `all` |
| `verify_ssl`      | `REDMINE_VERIFY_SSL`  | `true`     |                                                          |
| –                 | `REDMINE_TIMEOUT`     | `30`       | Sekunden pro Request                                      |

Lokal testen ohne Installation: `claude --plugin-dir /pfad/zu/claude-redmine-mcp`, dann `/mcp`.

### Ohne Plugin (nur MCP-Server)

```bash
claude mcp add redmine \
  -e REDMINE_URL=https://redmine.example.com -e REDMINE_API_KEY=... -e REDMINE_TOOLSETS=all \
  -- uvx --from git+https://github.com/expertZentrale/claude-redmine-mcp redmine-mcp
```

## Tools

| Toolset           | Lesen                                                                                                                                                                                    | Schreiben (nur `read_only=false`)                                                     |
|-------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `standard`        | `get_current_user`, `list_projects`, `get_project`, `search_issues`, `get_issue`, `list_time_entries`, `list_versions`, `list_project_members`, `list_wiki_pages`, `get_wiki_page`, `search`, `list_reference_data`, `get_attachment` | `create_issue`, `update_issue`, `log_time`, `create_issue_relation`, `save_wiki_page` |
| `expert_helpdesk` | `list_helpdesk_tickets`, `get_helpdesk_ticket`, `list_helpdesk_contacts`, `get_helpdesk_contact`, `list_helpdesk_mailboxes`, `get_helpdesk_project_settings`                              | `create_helpdesk_ticket`, `update_helpdesk_ticket`                                     |
| `expert_agile`    | `list_sprints`, `get_sprint`, `get_issue_agile_data`                                                                                                                                     | `create_sprint`, `update_sprint`, `update_issue_agile_data`                            |
| `redmineup`       | `list_contacts`, `get_contact`, `list_deals`, `get_deal`, `list_redmineup_tickets`, `get_redmineup_ticket`, `list_redmineup_sprints`, `get_checklist`                                     | `add_crm_note`, `add_checklist_item`, `update_checklist_item`                          |
| immer             | `redmine_get`, `redmine_list`                                                                                                                                                             | –                                                                                     |

Listen sind gepaged (Default 25, max. 100, `next_offset` im Ergebnis); lange Texte werden in Listen gekürzt.

## Entwicklung

```bash
uv venv && uv pip install -e '.[dev]' -e ../python-redmine   # lokaler Library-Checkout statt Git-Tag
uv run pytest
uv run ruff check . && uv run ruff format --check .
npx @modelcontextprotocol/inspector uv run redmine-mcp       # mit REDMINE_* im Environment
```
